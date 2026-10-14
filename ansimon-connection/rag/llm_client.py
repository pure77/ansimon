# -*- coding: utf-8 -*-
"""생성 단계: Alan API 호출 + 오프라인 mock 폴백

ALAN_API_KEY 가 있으면 실제 Alan LLM 을 호출하고, 없으면 검색된 근거 청크에서 문장을
그대로 채택하는 결정론적 mock 생성기로 자동 폴백한다. 두 경로 모두 prompt_builder 의
OUTPUT_JSON_SHAPE 와 같은 형태의 dict 를 반환하므로 pipeline.py 는 어느 쪽을 탔는지
신경 쓸 필요가 없다. 반환 dict 의 "_modelUsed" 로 사후 구분만 가능하다.

이전 버전과 달라진 점
  - 호출 규격을 하드코딩하지 않는다. alan_client.ADAPTERS 로 분리해 규격이 바뀌어도
    이 파일은 그대로다. 규격 확정 전이면 auto 로 한 번 탐색하고 결과를 캐시한다.
  - 응답이 JSON 앞뒤에 설명을 달고 와도 alan_client.extract_json 이 걷어낸다.
    (앨런은 검색형 모델이라 순수 JSON 만 뱉지 않는 경우가 잦다)
  - 실제 호출이 실패하면 LLM_FALLBACK_TO_MOCK=1(기본)일 때 mock 으로 내려앉는다.
    시연 도중 API 가 죽어도 파이프라인 전체가 멈추지는 않게 하기 위함이다.
    폴백이 일어나면 _modelUsed 가 "mock-deterministic-v1" 이라 사후 식별된다.
  - recommendedShelter 는 LLM 응답이 아니라 TMAP 원본(normalize_shelter)을 쓴다.
    LLM 이 거리·시간·시설명을 생성하면 안 된다는 원칙(AC-007)을 코드로 강제한 것.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, is_dataclass
from typing import Any, Optional

import alan_client
from schemas import (EMERGENCY_GUIDANCE_TEMPLATE, ROUTE_SOURCE_STRAIGHT_LINE,
                     ROUTE_SOURCE_TMAP, STRAIGHT_LINE_NOTICE)

DEFAULT_MODEL = "alan"
DEFAULT_MAX_TOKENS = 1500
MOCK_MODEL_NAME = "mock-deterministic-v1"

_resolved_mode: Optional[str] = None   # auto 탐색 결과 캐시 (프로세스당 1회)


def _to_plain(chunk: Any) -> dict:
    if is_dataclass(chunk) and not isinstance(chunk, type):
        return asdict(chunk)
    return chunk


def _truthy(name: str, default: str = "1") -> bool:
    return (os.getenv(name) or default).strip().lower() not in ("0", "false", "no", "")


# --- 실제 API 경로 ----------------------------------------------------------


def _pick_mode(key: str, url: str) -> str:
    """ALAN_API_MODE 가 지정돼 있으면 그것을, auto 면 한 번만 탐색해 캐시한다."""
    global _resolved_mode

    mode = alan_client.resolve_mode()
    if mode != "auto":
        return mode
    if _resolved_mode:
        return _resolved_mode

    errors = []
    for candidate in alan_client.AUTO_ORDER:
        if candidate in ("openai", "json_post") and not (url or os.getenv("LLM_BASE_URL")):
            continue
        try:
            alan_client.call_raw(candidate, "너는 계산기다.",
                                 [{"role": "user", "content": "1+1은? 숫자만."}], key=key, url=url)
            _resolved_mode = candidate
            print(f"[llm_client] Alan 호출 규격 자동 확정: {candidate}", file=sys.stderr)
            return candidate
        except Exception as e:
            errors.append(f"{candidate}: {type(e).__name__} {str(e)[:80]}")

    raise RuntimeError(
        "Alan API 호출 규격을 찾지 못했습니다. `python alan_check.py` 로 진단하세요. " + " | ".join(errors)
    )


def _api_key(mode: str) -> str:
    """모드에 맞는 키를 고른다.

    openai 규격은 Bearer 인증이라 앨런 client_id(UUID)를 그대로 보내면 401 이다.
    두 키를 각자 자리에 두면 .env 에서 ALAN_API_MODE 한 줄만 바꿔 왕복할 수 있다.
    """
    if mode == "openai":
        return (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "").strip()
    return (os.getenv("ALAN_API_KEY") or "").strip()


def _call_real_api(messages_payload: dict, api_key: str) -> dict:
    url = (os.getenv("ALAN_API_URL") or "").strip()
    mode = _pick_mode(api_key, url)
    text = alan_client.call_raw(
        mode, messages_payload["system"], messages_payload["messages"], key=api_key, url=url,
        model=messages_payload.get("model", DEFAULT_MODEL),
        max_tokens=messages_payload.get("max_tokens", DEFAULT_MAX_TOKENS),
    )
    return alan_client.extract_json(text)


# --- 쉼터 정규화 ------------------------------------------------------------


def normalize_shelter(shelter: Optional[dict]) -> Optional[dict]:
    """shelter_client(snake_case) / 백엔드 계약(camelCase) 어느 쪽으로 와도 받아 camelCase 로.

    TMAP 이 계산한 값은 여기서 전부 통과시킨다. LLM 은 이 숫자를 만들지 않고 설명만 한다.
    """
    if not shelter:
        return None

    def g(*names, default=None):
        for n in names:
            if shelter.get(n) is not None:
                return shelter[n]
        return default

    return {
        # 원천 출처 표시. evidence_verifier 가 "실존 대조를 또 할 필요가 있는가"를 이걸로 판단한다.
        "source": g("source", default="UNKNOWN"),
        "name": g("name", default=""),
        "address": g("address"),
        "distanceM": g("distanceM", "distance_m"),
        "lat": g("lat", "latitude"),
        "lon": g("lon", "longitude"),
        "walkMinutes": g("walkMinutes", "walk_minutes"),
        "walkMeters": g("walkMeters", "walk_meters"),
        "crossings": g("crossings"),
        "routeSource": g("routeSource", "route_source", default=ROUTE_SOURCE_TMAP),
        "estimatedWalkMinutes": g("estimatedWalkMinutes", "estimated_walk_minutes"),
        "openStatus": g("openStatus", "open_status", default="UNKNOWN"),
        "openHoursRaw": g("openHoursRaw", "open_hours_raw"),
        "needsReview": bool(g("needsReview", "needs_review", default=False)),
        "route": g("route", default=[]) or [],
        "alternatives": [
            {
                "name": a.get("name"),
                "walkMinutes": a.get("walkMinutes", a.get("walk_minutes")),
                "crossings": a.get("crossings"),
                "estimatedWalkMinutes": a.get("estimatedWalkMinutes",
                                              a.get("estimated_walk_minutes")),
            }
            for a in (g("alternatives", default=[]) or [])
        ],
    }


def ensure_straight_line_notice(output: dict, shelter_norm: Optional[dict]) -> dict:
    """직선거리 폴백이면 고정 고지문을 안내에 반드시 포함시킨다 (반대도 마찬가지).

    프롬프트로 LLM 에게 부탁만 하면 지키는 날도 있고 아닌 날도 있다. 이 고지문이 빠지면
    어르신이 추정치를 확정 도보시간으로 듣고 폭염에 나서게 되므로, 여기서 결정론적으로
    보장한다. LLM 이 알아서 넣었으면 중복으로 넣지 않는다.

    반대 방향도 정리한다 — TMAP 경로가 멀쩡한데 "길안내를 받을 수 없어서" 라고 말하면
    그것도 틀린 안내다.

    이 문장만 evidenceChunkIds 가 비어 있다. 매뉴얼에서 나온 사실이 아니라 시스템 상태
    고지이기 때문이고, evidence_verifier 가 이 문장에 한해 MISSING_EVIDENCE 를 면제한다.
    """
    sentences = list(output.get("guidanceSentences") or [])
    is_fallback = (shelter_norm or {}).get("routeSource") == ROUTE_SOURCE_STRAIGHT_LINE
    has_notice = any(s.get("text") == STRAIGHT_LINE_NOTICE for s in sentences)

    if is_fallback and not has_notice:
        # 쉼터 안내 바로 앞에 오도록 맨 뒤에 붙인다 (전화 대본이 이 순서로 읽는다)
        sentences.append({"text": STRAIGHT_LINE_NOTICE, "evidenceChunkIds": []})
    elif not is_fallback and has_notice:
        sentences = [s for s in sentences if s.get("text") != STRAIGHT_LINE_NOTICE]

    output["guidanceSentences"] = sentences
    return output


# --- mock 경로 --------------------------------------------------------------


def _find_emergency_template_chunk(evidence_chunks: list[Any]) -> Optional[dict]:
    for c in evidence_chunks:
        c = _to_plain(c)
        if c["text"] == EMERGENCY_GUIDANCE_TEMPLATE:
            return c

    from retrieval import load_active_chunks

    for c in load_active_chunks():
        if c["text"] == EMERGENCY_GUIDANCE_TEMPLATE:
            return c
    return None


def _mock_generate(
    evidence_chunks: list[Any],
    risk_snapshot: dict,
    shelter: Optional[dict],
    max_sentences: int = 4,
    reason: str = "",
) -> dict:
    """검색된 근거 청크의 문장을 그대로 채택하는 결정론적 mock 생성기."""
    # reason 은 왜 mock 으로 내려앉았는지. stderr 로만 흘리면 서버 터미널을 뒤져야 해서
    # 아무도 안 본다. 응답에 실어 보내면 warnings 로 올라와 화면에서 바로 보인다.
    plain_chunks = [_to_plain(c) for c in evidence_chunks]

    guidance_sentences = [
        {"text": c["text"], "evidenceChunkIds": [c["chunk_id"]]}
        for c in plain_chunks[:max_sentences]
        if c["text"] != EMERGENCY_GUIDANCE_TEMPLATE
    ]

    risk_level = (risk_snapshot or {}).get("riskLevel") or (risk_snapshot or {}).get("risk_level")
    emergency_flag = risk_level == "CRITICAL"
    emergency_message = None
    if emergency_flag:
        template_chunk = _find_emergency_template_chunk(plain_chunks)
        if template_chunk:
            emergency_message = EMERGENCY_GUIDANCE_TEMPLATE
            guidance_sentences.append(
                {"text": EMERGENCY_GUIDANCE_TEMPLATE, "evidenceChunkIds": [template_chunk["chunk_id"]]}
            )

    shelter_norm = normalize_shelter(shelter)
    return ensure_straight_line_notice({
        "guidanceSentences": guidance_sentences,
        "emergencyFlag": emergency_flag,
        "emergencyMessage": emergency_message,
        "recommendedShelter": shelter_norm,
        "_modelUsed": MOCK_MODEL_NAME,
        "_fallbackReason": reason,
    }, shelter_norm)


# --- 공개 진입점 ------------------------------------------------------------


def generate_guidance(
    evidence_chunks: list[Any],
    risk_snapshot: dict,
    shelter: Optional[dict] = None,
    messages_payload: Optional[dict] = None,
) -> dict:
    """근거 청크 + 구조화 컨텍스트로 안내 계획 초안(JSON dict)을 생성한다."""
    mode = alan_client.resolve_mode()
    api_key = _api_key(mode)
    if not api_key:
        return _mock_generate(evidence_chunks, risk_snapshot, shelter,
                              reason=f"{mode} 모드에 쓸 API 키가 .env 에 없습니다")

    if messages_payload is None:
        raise ValueError("실제 API 호출에는 prompt_builder.build_messages() 결과가 필요합니다.")

    try:
        result = _call_real_api(messages_payload, api_key)
    except Exception as e:
        if not _truthy("LLM_FALLBACK_TO_MOCK"):
            raise
        print(f"[llm_client] Alan 호출 실패({type(e).__name__}: {str(e)[:120]}) -> mock 폴백",
              file=sys.stderr)
        return _mock_generate(evidence_chunks, risk_snapshot, shelter,
                              reason=f"{type(e).__name__}: {str(e)[:180]}")

    # 쉼터는 LLM 이 만든 값이 아니라 TMAP 원본을 쓴다 (AC-007).
    shelter_norm = normalize_shelter(shelter)
    result["recommendedShelter"] = shelter_norm
    result["_modelUsed"] = messages_payload.get("model", DEFAULT_MODEL)
    return ensure_straight_line_notice(result, shelter_norm)


if __name__ == "__main__":
    from retrieval import search

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    print(f"ALAN_API_KEY 설정됨: {bool(os.environ.get('ALAN_API_KEY'))}"
          f" / MODE={alan_client.resolve_mode()}")

    print("\n=== 일반 위험도(HIGH) ===")
    chunks = search("노인 폭염 대비 수칙", target_audience=["ELDERLY"], top_k=3)
    result = generate_guidance(chunks, {"riskLevel": "HIGH"}, shelter={
        "source": "SEOUL_OPENAPI",
        "name": "종로노인종합복지관 경로당", "address": "서울특별시 종로구 삼봉로 71",
        "walk_minutes": 3, "walk_meters": 162, "crossings": 1,
        "route": ["삼봉로를 따라 80m 이동", "횡단보도 건너기", "도착"], "needs_review": False})
    print(json.dumps(result, ensure_ascii=False, indent=2))

    print("\n=== CRITICAL 위험도(응급 문구 포함) ===")
    chunks = search("의식 잃음 응급조치", target_audience=["EMERGENCY", "ELDERLY"], top_k=3)
    result = generate_guidance(chunks, {"riskLevel": "CRITICAL"}, shelter=None)
    print(json.dumps(result, ensure_ascii=False, indent=2))
