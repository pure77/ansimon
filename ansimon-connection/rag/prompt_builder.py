# -*- coding: utf-8 -*-
"""3) 프롬프트 — 앨런 GET 쿼리스트링(4KB)에 들어가도록 압축한 버전.

한글은 URL 인코딩에서 글자당 9바이트가 된다(`가` -> `%EA%B0%80`). 그래서 프롬프트의
"글자 수"가 아니라 **URL 바이트**가 예산이다. 압축 전 11,018B -> 압축 후 3KB 안쪽.

무엇을 줄였고 왜 품질이 유지되는가:

  1. JSON indent=2 -> 한 줄 `키: 값`.  들여쓰기·따옴표·중괄호·개행(%0A=3B)이 전부 사라진다.
     모델이 읽는 정보량은 그대로다.
  2. 쉼터의 route/lat/lon/distanceM 삭제.  `llm_client.normalize_shelter` 가
     recommendedShelter 를 TMAP 원본으로 **덮어쓰기** 때문에 모델이 이 값을 볼 이유가 없다.
     보여주면 오히려 모델이 길안내를 지어낼 여지만 생긴다 (AC-007).
  3. 출력 스키마에서 recommendedShelter 삭제.  같은 이유로 어차피 버려지는 필드다.
  4. 응급 고정문구(규칙3)는 CRITICAL 일 때만, 직선거리 고지문(규칙4)은 폴백일 때만 넣는다.
     두 문구는 합쳐 1.3KB 인데 평소에는 쓰이지 않는다. 그리고 직선거리 고지문은
     `llm_client.ensure_straight_line_notice()` 가 **결정론적으로 삽입/제거**하므로
     프롬프트는 보조일 뿐이다 — 빠져도 결과가 달라지지 않는다.
  5. 근거 청크의 heading_path 삭제, 본문만.  chunk_id 인용 의무는 그대로다.

줄이지 않은 것: 근거 밖 사실 생성 금지, evidenceChunkIds 의무, 응급 고정문구 원문,
JSON 단일 출력. 이 넷이 evidence_verifier 가 검사하는 항목이고, 여기가 흔들리면
근거 검증에서 전부 막힌다.
"""
from __future__ import annotations

import os
from dataclasses import asdict, is_dataclass
from typing import Any, Optional
from urllib.parse import quote

from schemas import EMERGENCY_GUIDANCE_TEMPLATE, ROUTE_SOURCE_STRAIGHT_LINE, STRAIGHT_LINE_NOTICE

DEFAULT_MODEL = "alan"
DEFAULT_MAX_TOKENS = 1500

# 청크 본문 상한(글자). 넘으면 잘라서 붙인다 — 근거는 문장 하나면 충분하고,
# 긴 청크 하나가 예산을 다 먹으면 다른 근거를 못 보여준다.
CHUNK_CHARS = 160

# recommendedShelter 는 넣지 않는다. llm_client 가 TMAP 원본으로 덮어쓴다.
OUTPUT_SHAPE = ('{"guidanceSentences":[{"text":"","evidenceChunkIds":[""]}],'
                '"emergencyFlag":false,"emergencyMessage":null}')

BASE_RULES = """'안심온' 폭염 안내 생성기. 어르신께 전화로 읽어 드릴 문장을 만든다.

규칙
1. [근거] 에 있는 내용만 사실로 쓴다. 없는 수치·시설명·의학조언을 지어내지 않는다.
2. 문장마다 근거가 된 chunk_id 를 evidenceChunkIds 에 채운다. 비우지 않는다.
3. 짧고 쉬운 존댓말. 한 문장에 한 가지만. 3~4문장.
4. JSON 하나만 출력. 앞뒤 설명·인사·코드블록 금지."""


def _to_plain(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    return obj


def build_system(risk_level: str = "") -> str:
    """상황에 필요한 규칙만 담은 시스템 프롬프트.

    직선거리 고지문(구 규칙4, 797B)은 넣지 않는다. `llm_client.ensure_straight_line_notice()`
    가 폴백이면 넣고 TMAP 이면 빼는 일을 **결정론적으로** 이미 한다. 프롬프트에 또 적는 건
    모델이 지켜줄지 모르는 사본을 예산만큼 들고 다니는 것이다. 검증
    (STRAIGHT_LINE_NOTICE_MISSING)도 그 코드가 넣은 결과를 본다.
    """
    parts = [BASE_RULES]
    if str(risk_level).upper() == "CRITICAL":
        # emergencyMessage 는 코드가 채워주지 않는다. 모델이 써야 하고,
        # evidence_verifier 가 글자 단위로 대조한다. 반드시 원문 그대로 보여준다.
        parts.append(f'5. 응급 안내가 필요하면 emergencyFlag=true, emergencyMessage 는 다음을 '
                     f'그대로: "{EMERGENCY_GUIDANCE_TEMPLATE}"')
    parts.append(f"출력 {OUTPUT_SHAPE}")
    return "\n\n".join(parts)


def _kv(d: dict, keys: tuple) -> str:
    """빈 값은 줄째로 뺀다 — 'null' 을 읽히는 것보다 안 보이는 게 낫다."""
    out = []
    for k in keys:
        v = d.get(k)
        if v in (None, "", [], {}):
            continue
        out.append(f"{k}={','.join(map(str, v)) if isinstance(v, list) else v}")
    return " ".join(out)


def _shelter_line(s: Optional[dict]) -> str:
    """이름과 도보시간만. 좌표·경로·거리는 모델이 볼 이유가 없다(덮어쓰기 때문)."""
    if not s:
        return "(없음)"
    s = {k.replace("_", "").lower(): v for k, v in s.items()}   # snake/camel 둘 다 받는다
    line = str(s.get("name") or "")
    if s.get("openstatus") not in (None, "", "UNKNOWN"):
        line += f" ({s['openstatus']})"
    if s.get("routesource") == ROUTE_SOURCE_STRAIGHT_LINE:
        if s.get("estimatedwalkminutes"):
            line += f" 추정도보 {s['estimatedwalkminutes']}분"
    elif s.get("walkminutes"):
        line += f" 도보 {s['walkminutes']}분"
    return line


def _format_evidence_block(evidence_chunks: list[Any], chars: int = CHUNK_CHARS) -> str:
    lines = []
    for c in evidence_chunks:
        c = _to_plain(c)
        text = " ".join(str(c["text"]).split())          # 개행·중복공백 제거(%0A 는 3B다)
        if len(text) > chars:
            text = text[:chars] + "…"
        lines.append(f"{c['chunk_id']}: {text}")
    return "\n".join(lines) if lines else "(없음)"


def build_user_content(
    elderly_profile: dict,
    risk_snapshot: dict,
    shelter: Optional[dict],
    weather: dict,
    evidence_chunks: list[Any],
    chars: int = CHUNK_CHARS,
) -> str:
    p, r, w = elderly_profile or {}, risk_snapshot or {}, weather or {}
    return "\n".join([
        "[대상] " + _kv(p, ("targetAudience", "target_audience", "age", "livesAlone")),
        "[위험] " + _kv(r, ("riskLevel", "risk_level", "riskScore", "risk_score",
                            "riskFactors", "risk_factors")),
        "[기상] " + _kv(w, ("temperatureC", "heatWarning", "humidity")),
        "[쉼터] " + _shelter_line(shelter),
        "[근거]",
        _format_evidence_block(evidence_chunks, chars),
        "위 내용만 써서 안내 계획을 JSON 으로.",
    ])


def _url_bytes(text: str) -> int:
    return len(quote(text))


def _fit(system: str, build_user, chunks: list) -> str:
    """예산에 들어갈 때까지 근거 청크를 하나씩 뺀다.

    CRITICAL + 직선거리 폴백이 겹치면 고정문구 두 개가 1.3KB 를 더 먹는다. 그때만
    근거를 줄여서 맞춘다 — 규칙을 빼면 근거검증에서 통째로 막히지만, 근거는 하나 적어도
    남은 것으로 문장을 만들 수 있다. 응급 문구 청크는 절대 빼지 않는다
    (pipeline._ensure_emergency_chunk 가 넣은 것이고, 빠지면 CRITICAL 이 항상 보류된다).
    """
    budget = int(os.getenv("ALAN_QUERY_MAX_BYTES", "3900")) - _url_bytes(system) - 40
    # 시스템 규칙에 이미 원문이 실린 청크(= CRITICAL 일 때의 응급 고정문구)는 빼고 보여준다.
    # 같은 문장을 두 번 보여줄 이유가 없고, 그 자리에 진짜 근거를 하나 더 넣는 편이 낫다.
    # retrieved_chunk_ids 는 pipeline 이 원본 목록으로 계산하므로 인용 검증에는 영향이 없다.
    keep = [c for c in chunks if _to_plain(c)["text"] not in system] or list(chunks)
    # 먼저 청크를 짧게 자른다. 근거 5개를 짧게 보는 편이 2개를 길게 보는 것보다 낫다 —
    # 안내 문장은 어차피 한 줄이고, 다양한 근거가 있어야 문장이 겹치지 않는다.
    for chars in (CHUNK_CHARS, 120, 90, 70):
        if _url_bytes(build_user(keep, chars)) <= budget:
            return build_user(keep, chars)
    while len(keep) > 2:
        drop = next((i for i in range(len(keep) - 1, -1, -1)
                     if _to_plain(keep[i])["text"] != EMERGENCY_GUIDANCE_TEMPLATE), None)
        if drop is None:
            break
        keep.pop(drop)
        if _url_bytes(build_user(keep, 70)) <= budget:
            break
    return build_user(keep, 70)


def build_messages(
    elderly_profile: dict,
    risk_snapshot: dict,
    shelter: Optional[dict],
    weather: dict,
    evidence_chunks: list[Any],
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """llm_client._call_real_api() 가 그대로 쓰는 system/messages 페이로드."""
    s = shelter or {}
    system = build_system(risk_snapshot.get("riskLevel") or risk_snapshot.get("risk_level") or "")
    content = _fit(system, lambda ch, n=CHUNK_CHARS: build_user_content(
        elderly_profile, risk_snapshot, shelter, weather, ch, n), evidence_chunks)
    return {"model": model, "max_tokens": max_tokens, "system": system,
            "messages": [{"role": "user", "content": content}]}


if __name__ == "__main__":
    import urllib.parse

    from retrieval import search

    b = lambda t: len(urllib.parse.quote(t))
    chunks = search("노인 폭염 대비 수칙", target_audience=["ELDERLY"], top_k=5)
    sh = {"name": "종로노인종합복지관 경로당", "walk_minutes": 8, "route_source": "TMAP",
          "open_status": "OPEN", "route": ["직진 200m"] * 7, "lat": 37.57, "lon": 126.98}
    mp = build_messages({"targetAudience": ["ELDERLY"], "age": 82},
                        {"riskLevel": "HIGH", "riskScore": 0.83, "riskFactors": ["독거"]},
                        sh, {"temperatureC": 36.2, "heatWarning": "폭염경보"}, chunks)
    flat = mp["system"] + "\n\n" + mp["messages"][0]["content"]
    print(flat)
    print(f"\n--- URL 인코딩 {b(flat)} B (앨런 GET 예산 3900B) ---")
    assert b(flat) < 3900, f"예산 초과: {b(flat)}B"
    # 응급/직선거리 규칙은 필요할 때만 붙는다
    assert EMERGENCY_GUIDANCE_TEMPLATE not in mp["system"]
    assert EMERGENCY_GUIDANCE_TEMPLATE in build_system("CRITICAL")
    # 직선거리 고지문은 프롬프트가 아니라 llm_client.ensure_straight_line_notice() 담당이다
    assert STRAIGHT_LINE_NOTICE not in build_system("CRITICAL")
    print("OK")
