# -*- coding: utf-8 -*-
"""Alan(앨런) API 어댑터 — 호출 규격이 확정 안 된 상태를 코드로 흡수한다.

기존 llm_client._call_real_api() 는 "일반적인 REST LLM 관례"를 하나 찍어서 하드코딩해
놓은 상태였다(파일 상단 TODO 참고). 문제는 앨런 API 가 흔히 두 가지 형태로 배포된다는
점이다.

  A) 앨런 공개/교육용 API — GET 쿼리스트링. `?content=<질문>&client_id=<UUID>`
     응답: {"ended": true, "content": "...", "action": {...}}
     대화 상태를 client_id 단위로 서버가 기억하므로 매 호출 전 reset-state 를 권장.
  B) OpenAI 호환 게이트웨이 — POST /v1/chat/completions, Authorization: Bearer

어느 쪽인지 문서 없이 단정하지 않고, 어댑터를 여러 개 두고 실제로 찔러본 뒤
성공한 것을 쓴다. `alan_check.py` 가 이 어댑터 목록을 그대로 돌려 진단표를 출력하고,
`llm_client.py` 가 같은 목록으로 실제 호출한다. 규격이 확정되면 ADAPTERS 에서
해당 항목 하나만 남기거나 .env 의 ALAN_API_MODE 로 고정하면 된다.

.env 설정
    ALAN_API_KEY=...              # 앨런 client_id 또는 Bearer 토큰
    ALAN_API_URL=...              # (선택) 엔드포인트를 알고 있으면 고정
    ALAN_API_MODE=alan_query|openai|json_post|auto   # 기본 auto
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

import requests
from urllib.parse import quote

TIMEOUT = 60

# 앨런 공개 API 는 질문을 GET 쿼리스트링으로 받는다. 한글은 URL 인코딩에서 글자당 9바이트로
# 불어나(가 -> %EA%B0%80) RAG 프롬프트 2,600자가 11KB 가 된다. Azure Functions 기본 URL
# 상한은 4KB 라 요청이 서버에 닿기도 전에 잘린다. 막지 않으면 404/타임아웃으로만 보여서
# "왜 계속 mock 이지?" 가 된다. alan_check.py 가 통과하는 건 시험 프롬프트가 짧기 때문이다.
ALAN_QUERY_MAX = int(os.getenv("ALAN_QUERY_MAX_BYTES", "3900"))
DEFAULT_MODEL = "alan"

# 앨런 공개 API 기본 호스트 (교육/해커톤 배포본에서 쓰이는 형태).
# 주최측 문서에 다른 호스트가 적혀 있으면 .env 의 ALAN_API_URL 로 덮어쓴다.
ALAN_QUERY_URL = "https://kdt-api-function.azurewebsites.net/api/v1/question"
ALAN_RESET_URL = "https://kdt-api-function.azurewebsites.net/api/v1/reset-state"

_FENCE_RE = re.compile(r"```(?:json)?|```")


@dataclass
class Adapter:
    name: str
    describe: str
    build: Callable[..., dict]          # -> requests.request(**kwargs)
    parse: Callable[[Any], str]         # 응답 -> 본문 텍스트
    reset: Optional[Callable[[str, str], None]] = None


def _flatten(system: str, messages: list[dict]) -> str:
    """system + messages 를 한 덩어리 텍스트로. 쿼리스트링형 API 용."""
    parts = [system.strip()]
    parts += [m["content"].strip() for m in messages if m.get("content")]
    return "\n\n".join(p for p in parts if p)


def _alan_reset(url: str, key: str) -> None:
    """앨런은 client_id 별로 대화 맥락을 기억한다. 대상자마다 섞이면 안 되니 초기화."""
    try:
        requests.get(url.replace("/question", "/reset-state"),
                     params={"client_id": key}, timeout=10)
    except Exception:
        pass   # 초기화 실패가 본 호출을 막을 이유는 없다


def _b_alan_query(url: str, key: str, system: str, messages: list[dict], **_) -> dict:
    content = _flatten(system, messages)
    size = len(quote(content))
    if size > ALAN_QUERY_MAX:
        raise ValueError(
            f"프롬프트가 GET 쿼리스트링 한계를 넘습니다({size}B > {ALAN_QUERY_MAX}B). "
            f"앨런 공개 API(alan_query)로는 RAG 프롬프트를 보낼 수 없습니다. "
            f"주최측 POST 엔드포인트를 받아 ALAN_API_MODE=openai + ALAN_API_URL 로 쓰거나, "
            f"OPENAI_API_KEY 로 전환하세요.")
    return {
        "method": "GET",
        "url": url or ALAN_QUERY_URL,
        "params": {"content": content, "client_id": key},
        "timeout": TIMEOUT,
    }


def _b_openai(url: str, key: str, system: str, messages: list[dict],
              model: str = DEFAULT_MODEL, max_tokens: int = 1500, **_) -> dict:
    base = (url or os.getenv("LLM_BASE_URL") or "").rstrip("/")
    if not base.endswith("/chat/completions"):
        base = f"{base}/chat/completions"
    return {
        "method": "POST",
        "url": base,
        "headers": {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        "json": {
            "model": os.getenv("LLM_MODEL") or model,
            "messages": [{"role": "system", "content": system}, *messages],
            "max_tokens": max_tokens,
            "temperature": 0,
        },
        "timeout": TIMEOUT,
    }


def _b_json_post(url: str, key: str, system: str, messages: list[dict],
                 model: str = DEFAULT_MODEL, max_tokens: int = 1500, **_) -> dict:
    """기존 llm_client 가 쓰던 추정 규격. 호환을 위해 남겨둔다."""
    return {
        "method": "POST",
        "url": url,
        "headers": {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        "json": {"model": model, "system": system, "messages": messages, "max_tokens": max_tokens},
        "timeout": TIMEOUT,
    }


def _p_alan(data: Any) -> str:
    if isinstance(data, str):
        return data
    return data.get("content") or data.get("answer") or data.get("result") or ""


def _p_openai(data: Any) -> str:
    return data["choices"][0]["message"]["content"]


ADAPTERS: dict[str, Adapter] = {
    "alan_query": Adapter(
        "alan_query", "GET ?content=&client_id=  (앨런 공개 API)",
        _b_alan_query, _p_alan, reset=_alan_reset),
    "openai": Adapter(
        "openai", "POST /chat/completions  (OpenAI 호환 게이트웨이)",
        _b_openai, _p_openai),
    "json_post": Adapter(
        "json_post", "POST {system, messages}  (기존 llm_client 추정 규격)",
        _b_json_post, _p_alan),
}

# auto 탐색 순서. URL 을 모르면 alan_query 가 자체 기본 호스트를 갖고 있어 먼저 온다.
AUTO_ORDER = ("alan_query", "openai", "json_post")


def call_raw(adapter_name: str, system: str, messages: list[dict],
             key: Optional[str] = None, url: Optional[str] = None,
             model: str = DEFAULT_MODEL, max_tokens: int = 1500) -> str:
    """지정한 어댑터로 한 번 호출하고 응답 본문 텍스트를 돌려준다."""
    adapter = ADAPTERS[adapter_name]
    key = key or os.getenv("ALAN_API_KEY", "").strip()
    url = (url if url is not None else os.getenv("ALAN_API_URL", "")).strip()
    if not key:
        raise RuntimeError("ALAN_API_KEY 가 없습니다.")

    if adapter.reset and url:
        adapter.reset(url, key)
    elif adapter.reset:
        adapter.reset(ALAN_RESET_URL, key)

    req = adapter.build(url=url, key=key, system=system, messages=messages,
                        model=model, max_tokens=max_tokens)
    resp = requests.request(**req)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError:
        data = resp.text
    text = adapter.parse(data)
    if not text:
        raise RuntimeError(f"응답에서 텍스트를 찾지 못했습니다: {str(data)[:300]}")
    return text


def resolve_mode() -> str:
    """.env 의 ALAN_API_MODE. 미지정이면 'auto'."""
    return (os.getenv("ALAN_API_MODE") or "auto").strip().lower()


def extract_json(text: str) -> dict:
    """LLM 응답에서 JSON 객체 하나를 뽑아낸다.

    앨런은 검색형 모델이라 JSON 앞뒤로 설명을 붙이는 경우가 잦다. 코드펜스를 벗기고,
    그래도 안 되면 중괄호 균형을 세어 가장 바깥 객체만 잘라낸다.
    """
    cleaned = _FENCE_RE.sub("", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    if start < 0:
        raise ValueError(f"응답에 JSON 객체가 없습니다: {text[:300]}")

    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(cleaned[start:], start):
        if esc:
            esc = False
            continue
        if ch == "\\" and in_str:
            esc = True
        elif ch == '"':
            in_str = not in_str
        elif not in_str:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(cleaned[start:i + 1])
    raise ValueError(f"JSON 객체가 닫히지 않았습니다: {text[:300]}")
