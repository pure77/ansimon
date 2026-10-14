# -*- coding: utf-8 -*-
"""통화 질문(intervention_plan.questions_json) 생성.

**문장은 LLM 이 짓고, 무엇을 물을지는 코드가 정한다.**

이유가 있다. 통화 결과는 call_observation 의 네 컬럼(shelter_intent /
can_move_alone / help_needed / symptom_mentioned)으로만 저장된다. 질문 목록이
이 슬롯과 어긋나면 요약 LLM 이 답을 어느 칸에 넣을지 몰라 전부 UNKNOWN 이 되고,
그러면 통화를 하고도 사회복지사에게 아무것도 남지 않는다.

그래서 슬롯 구성(쉼터가 없으면 쉼터 질문을 빼고, CRITICAL 이면 증상 질문을 넣는다)은
코드가 결정하고, 그 슬롯의 한국어 문장만 Alan 에게 맡긴다. Alan 이 죽거나 이상한 걸
돌려주면 슬롯 단위로 템플릿을 되돌린다 — 전부 버리지 않는다.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

import aiohttp

# .env 의 ALAN_API_MODE 가 alan_query(앨런 공개 API, GET ?content=&client_id=) 로 고정돼 있다.
# 다른 규격이면 anshimon-rag/alan_client.py 의 어댑터 표를 보고 _ask() 만 갈아끼운다.
ALAN_URL = os.getenv("ALAN_API_URL") or "https://kdt-api-function.azurewebsites.net/api/v1/question"
ALAN_TIMEOUT = int(os.getenv("QUESTION_TIMEOUT_SEC", "30"))

# 슬롯 -> (기본 문장, 무엇을 판정하려는 질문인가)
SLOTS = {
    "shelter_intent": ("쉼터에 가실 의향이 있으신가요?", "무더위쉼터에 갈 의향"),
    "can_move_alone": ("혼자서 걸어서 가실 수 있으신가요?", "쉼터까지 혼자 이동 가능 여부"),
    "help_needed": ("이동이나 다른 도움이 필요하신가요?", "이동·생활 도움 필요 여부"),
    "symptom_mentioned": ("지금 어지럽거나 머리가 아프신 데는 없으신가요?", "온열질환 의심 증상"),
}

SYSTEM = """너는 고령자에게 전화로 물을 질문을 다듬는 편집자다.

주어진 각 항목에 대해 어르신께 여쭐 한국어 질문을 한 문장씩 만들어 JSON 하나만 출력한다.

규칙
- 짧고 쉬운 말. 존댓말. 한 문장에 하나만 묻는다.
- 숫자, 주소, 시간, 거리를 쓰지 않는다. 그 값들은 앞에서 이미 안내했다.
- 의료 진단을 하지 않는다. 증상은 '있으신지'만 여쭙는다.
- 항목의 뜻을 바꾸지 않는다. 예/아니오로 답할 수 있게 만든다.
- 설명이나 코드블록 없이 JSON 객체만 출력한다."""

_DIGIT = re.compile(r"[0-9]")
_JSON = re.compile(r"\{.*\}", re.S)


def choose_slots(shelter: Optional[dict], risk_level: str) -> list[str]:
    """무엇을 물을지 결정. 여기가 계약의 중심이다."""
    slots = ["shelter_intent", "can_move_alone"] if shelter and shelter.get("name") else []
    slots.append("help_needed")
    if risk_level == "CRITICAL":
        # 가장 위험한 등급에서만 증상을 직접 여쭙는다. 평소에는 어르신이 먼저 말씀하신
        # 경우에만 report.py 가 잡아낸다 — 매번 물으면 불안을 만든다.
        slots.append("symptom_mentioned")
    return slots


def _valid(text: object) -> bool:
    """LLM 문장을 받아들일지. 숫자가 섞이면 버린다 — 안내하지 않은 값을 말하게 된다."""
    return (isinstance(text, str) and 4 <= len(text.strip()) <= 120
            and not _DIGIT.search(text) and "?" in text)


async def _ask(prompt: str, key: str) -> str:
    async with aiohttp.ClientSession() as s:
        # 앨런은 client_id 별로 대화 맥락을 기억한다. 대상자가 섞이지 않게 먼저 비운다.
        try:
            await s.get(ALAN_URL.replace("/question", "/reset-state"),
                        params={"client_id": key}, timeout=aiohttp.ClientTimeout(total=10))
        except Exception:
            pass
        async with s.get(ALAN_URL, params={"content": prompt, "client_id": key},
                         timeout=aiohttp.ClientTimeout(total=ALAN_TIMEOUT)) as r:
            data = await r.json(content_type=None)
    if isinstance(data, str):
        return data
    return data.get("content") or data.get("answer") or data.get("result") or ""


async def generate(slots: list[str], risk_level: str,
                   shelter_name: Optional[str] = None) -> tuple[list[dict], list[str]]:
    """(questions, warnings). questions 는 [{"slot","text"}] — 순서가 통화 순서다."""
    out = {s: SLOTS[s][0] for s in slots}
    warnings: list[str] = []
    key = (os.getenv("ALAN_API_KEY") or "").strip()
    if not key:
        warnings.append("ALAN_API_KEY 가 없어 질문을 기본 템플릿으로 생성했습니다.")
        return [{"slot": s, "text": out[s]} for s in slots], warnings

    asked = "\n".join(f"- {s}: {SLOTS[s][1]}" for s in slots)
    where = f"\n안내한 쉼터 이름은 '{shelter_name}' 이다." if shelter_name else \
            "\n오늘은 안내할 쉼터가 없다. 쉼터를 언급하지 않는다."
    shape = ", ".join('"%s":"..."' % s for s in slots)
    prompt = (f"{SYSTEM}\n\n항목 ({risk_level} 위험 상황):\n{asked}{where}\n\n"
              f"출력 형식: {{{shape}}}")

    try:
        raw = await _ask(prompt, key)
        m = _JSON.search(raw or "")
        data = json.loads(m.group(0)) if m else {}
    except Exception as e:
        warnings.append(f"질문 생성 LLM 실패({type(e).__name__}) — 기본 템플릿을 사용합니다.")
        return [{"slot": s, "text": out[s]} for s in slots], warnings

    for s in slots:
        if _valid(data.get(s)):
            out[s] = data[s].strip()
        else:
            warnings.append(f"질문 '{s}' 가 규칙을 어겨(숫자 포함/길이/형식) 템플릿으로 되돌렸습니다.")
    return [{"slot": s, "text": out[s]} for s in slots], warnings
