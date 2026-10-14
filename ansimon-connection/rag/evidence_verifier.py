# -*- coding: utf-8 -*-
"""5) 근거 검증

LLM(또는 mock) 출력이 저장되기 전 아래를 검사한다.

| 항목 | 실패 시 |
|---|---|
| 안내 문장에 evidenceChunkIds가 비어있음 | ERROR |
| 이번 검색에 없던 chunk_id를 인용(조작/환각) | ERROR |
| 응급 증상 문구가 고정 템플릿과 다름 | ERROR |
| 문장 속 숫자가 구조화 컨텍스트와 직접 매칭 안 됨 | WARNING (Spring 재대조 권고) |
| (5-1) 안내 계획의 쉼터가 원천 데이터에 없는 시설 | ERROR |
| 직선거리 폴백인데 고지 문구가 없음 (또는 TMAP 경로인데 붙어 있음) | ERROR |

ERROR가 하나라도 있으면 pipeline.py가 GuidanceGenerationError를 던져
자동전화 발신을 보류시킨다.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Optional

from schemas import (EMERGENCY_GUIDANCE_TEMPLATE, ROUTE_SOURCE_STRAIGHT_LINE,
                     STRAIGHT_LINE_NOTICE)
from shelter_reference import ShelterReferenceIndex

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")


@dataclass
class VerificationIssue:
    level: str  # "ERROR" | "WARNING"
    code: str
    message: str
    sentence: Optional[str] = None

    def __str__(self) -> str:
        prefix = f"[{self.level}:{self.code}]"
        return f"{prefix} {self.message}" + (f" (문장: \"{self.sentence}\")" if self.sentence else "")


def _collect_numbers(value: Any, out: set[str]) -> None:
    if isinstance(value, dict):
        for v in value.values():
            _collect_numbers(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _collect_numbers(v, out)
    elif isinstance(value, (int, float)):
        out.add(str(value))
        # 정수로 떨어지는 float도 매칭되도록 보조 표기 추가 (예: 36.0 -> "36")
        if isinstance(value, float) and value == int(value):
            out.add(str(int(value)))
    elif isinstance(value, str):
        out.update(NUMBER_RE.findall(value))


def _check_evidence_ids(
    guidance_sentences: list[dict], retrieved_chunk_ids: set[str]
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    for sentence in guidance_sentences:
        text = sentence.get("text", "")
        evidence_ids = sentence.get("evidenceChunkIds") or sentence.get("evidence_chunk_ids") or []

        # 직선거리 고지문만 예외. 매뉴얼에서 나온 사실이 아니라 "지금 길안내를 못 받았다"는
        # 시스템 상태 고지라 인용할 청크가 존재할 수 없다. 문구가 고정 템플릿과 정확히
        # 일치할 때만 면제되므로, 이걸 빌미로 근거 없는 문장을 끼워 넣을 수는 없다.
        if text == STRAIGHT_LINE_NOTICE:
            continue

        if not evidence_ids:
            issues.append(
                VerificationIssue(
                    level="ERROR",
                    code="MISSING_EVIDENCE",
                    message="안내 문장에 evidenceChunkIds가 비어 있습니다.",
                    sentence=text,
                )
            )
            continue

        fabricated = [cid for cid in evidence_ids if cid not in retrieved_chunk_ids]
        if fabricated:
            issues.append(
                VerificationIssue(
                    level="ERROR",
                    code="FABRICATED_CHUNK_ID",
                    message=f"이번 검색 결과에 없는 chunk_id를 인용했습니다: {fabricated}",
                    sentence=text,
                )
            )
    return issues


def _check_emergency_template(raw_output: dict) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    if raw_output.get("emergencyFlag"):
        message = raw_output.get("emergencyMessage")
        if message != EMERGENCY_GUIDANCE_TEMPLATE:
            issues.append(
                VerificationIssue(
                    level="ERROR",
                    code="EMERGENCY_TEMPLATE_MISMATCH",
                    message=(
                        "emergencyFlag=true인데 emergencyMessage가 승인된 고정 템플릿과 "
                        f"다릅니다. 실제 값: {message!r}"
                    ),
                )
            )
    return issues


def _check_numeric_consistency(
    guidance_sentences: list[dict], structured_context: dict
) -> list[VerificationIssue]:
    allowed_numbers: set[str] = set()
    _collect_numbers(structured_context, allowed_numbers)

    issues: list[VerificationIssue] = []
    for sentence in guidance_sentences:
        text = sentence.get("text", "")
        numbers_in_sentence = set(NUMBER_RE.findall(text))
        unmatched = numbers_in_sentence - allowed_numbers
        if unmatched:
            issues.append(
                VerificationIssue(
                    level="WARNING",
                    code="NUMERIC_MISMATCH",
                    message=(
                        f"문장 속 숫자 {sorted(unmatched)}가 구조화 컨텍스트와 직접 매칭되지 "
                        "않습니다. Spring 쪽 재대조를 권고합니다."
                    ),
                    sentence=text,
                )
            )
    return issues


def _check_shelter_exists(
    raw_output: dict, shelter_ref: Optional[ShelterReferenceIndex]
) -> list[VerificationIssue]:
    if shelter_ref is None:
        return []
    shelter = raw_output.get("recommendedShelter")
    if not shelter:
        return []

    # 쉼터를 서울시 원천 데이터(OpenAPI/포털 CSV)에서 직접 골라온 경우에는 다시 대조하지
    # 않는다. 이 검사의 목적은 "LLM 이 없는 시설을 지어냈는가"인데, 그 경우 출처가 이미
    # 원천이므로 대조 대상과 대조 기준이 같다. 오히려 참조 인덱스가 샘플 픽스처로
    # 폴백돼 있으면 멀쩡한 실제 쉼터가 전부 ERROR 로 막힌다.
    if str(shelter.get("source", "")).startswith("SEOUL"):
        return []

    name = shelter.get("name", "")
    address = shelter.get("address")
    if not shelter_ref.exists(name, address):
        return [
            VerificationIssue(
                level="ERROR",
                code="SHELTER_NOT_FOUND",
                message=(
                    f"안내 계획에 포함된 쉼터 '{name}'({address})가 서울시 원천 데이터에서 "
                    "확인되지 않습니다."
                ),
            )
        ]
    return []


def _check_shelter_needs_review(raw_output: dict) -> list[VerificationIssue]:
    """t-map_location_connection_ansimon(recommend.py)의 needs_review를 이어받는다.

    그쪽 모듈의 실패 처리 원칙(ANSIMON_WORKFLOW §11)이 "TMAP 실패/도보 20분 초과는
    직선거리로 대체하지 않고 사람에게 넘긴다"이므로, 그 신호를 그대로 존중해
    여기서도 ERROR로 자동전화를 보류시킨다. name/needsReview 어느 케이싱으로 와도
    받아들인다 (recommend.py는 snake_case, Spring 계약은 camelCase).
    """
    shelter = raw_output.get("recommendedShelter")
    if not shelter:
        return []

    needs_review = shelter.get("needsReview", shelter.get("needs_review", False))
    if not needs_review:
        return []

    # 정책 스위치: 쉼터 경로를 못 믿을 때 "전화 자체를 막을 것인가".
    #   1(기본) = 막는다. 기존 동작 유지.
    #   0        = 전화는 걸되 쉼터에 needsReview 를 달아 보낸다. 백엔드/전화 모듈이
    #              쉼터 안내만 빼고 "물 드세요·외출 마세요" 는 그대로 전달하면 된다.
    # 0 을 권하는 이유: 폭염 피크에 TMAP 이 쿼터/장애로 흔들리면 1 일 때는 그날 모든
    # 대상자의 전화가 조용히 사라진다. 쉼터 조회 '실패'는 이미 전화를 막지 않는데
    # 경로 '검증 미완료'만 막는 것도 앞뒤가 안 맞는다.
    blocks = (os.getenv("SHELTER_REVIEW_BLOCKS_CALL") or "1").strip().lower() \
        not in ("0", "false", "no")

    walk_minutes = shelter.get("walkMinutes", shelter.get("walk_minutes"))
    reason = (
        f"도보 {walk_minutes}분으로 20분을 초과" if isinstance(walk_minutes, (int, float)) and walk_minutes > 20
        else "TMAP 경로 계산 실패 또는 검증 미완료"
    )
    return [
        VerificationIssue(
            level="ERROR" if blocks else "WARNING",
            code="SHELTER_ROUTE_NEEDS_REVIEW",
            message=(
                f"추천 쉼터 '{shelter.get('name', '')}'의 TMAP 도보 경로가 "
                f"needs_review 상태입니다 ({reason}). 사람이 먼저 확인해야 합니다."
                + ("" if blocks else " (SHELTER_REVIEW_BLOCKS_CALL=0 — 전화는 진행합니다)")
            ),
        )
    ]


def _check_straight_line_notice(raw_output: dict) -> list[VerificationIssue]:
    """직선거리 폴백에는 고지문이 반드시 있어야 하고, TMAP 경로에는 절대 없어야 한다.

    양방향을 다 본다. 빠지면 어르신이 추정치를 확정 도보시간으로 듣고, 반대로 멀쩡한
    TMAP 경로에 붙으면 신뢰할 수 있는 안내를 못 믿게 만든다. 둘 다 틀린 안내다.
    """
    shelter = raw_output.get("recommendedShelter")
    if not shelter:
        return []

    sentences = raw_output.get("guidanceSentences") or raw_output.get("guidance_sentences") or []
    has_notice = any(s.get("text") == STRAIGHT_LINE_NOTICE for s in sentences)
    is_fallback = shelter.get("routeSource", shelter.get("route_source")) == ROUTE_SOURCE_STRAIGHT_LINE

    if is_fallback and not has_notice:
        return [VerificationIssue(
            level="ERROR", code="STRAIGHT_LINE_NOTICE_MISSING",
            message=("직선거리로 고른 쉼터인데 '길안내를 받을 수 없었다'는 고지 문구가 "
                     "안내에 없습니다. 추정 시간이 확정 도보시간으로 전달될 위험이 있습니다."))]

    if not is_fallback and has_notice:
        return [VerificationIssue(
            level="ERROR", code="STRAIGHT_LINE_NOTICE_UNEXPECTED",
            message="TMAP 보행경로가 확인된 쉼터인데 직선거리 고지 문구가 붙어 있습니다.")]

    return []


def verify_guidance_output(
    raw_output: dict,
    retrieved_chunk_ids: set[str],
    structured_context: dict,
    shelter_ref: Optional[ShelterReferenceIndex] = None,
) -> list[VerificationIssue]:
    guidance_sentences = raw_output.get("guidanceSentences") or raw_output.get("guidance_sentences") or []

    issues: list[VerificationIssue] = []
    issues += _check_evidence_ids(guidance_sentences, retrieved_chunk_ids)
    issues += _check_emergency_template(raw_output)
    issues += _check_numeric_consistency(guidance_sentences, structured_context)
    issues += _check_shelter_exists(raw_output, shelter_ref)
    issues += _check_shelter_needs_review(raw_output)
    issues += _check_straight_line_notice(raw_output)
    return issues


def has_errors(issues: list[VerificationIssue]) -> bool:
    return any(i.level == "ERROR" for i in issues)


if __name__ == "__main__":
    retrieved_ids = {"heat_illness_manual_v1__0013", "heat_illness_manual_v1__0014"}
    context = {"riskLevel": "HIGH", "temperatureC": 36.2, "age": 82}

    print("=== 케이스 1: 정상 ===")
    good_output = {
        "guidanceSentences": [
            {
                "text": "갈증을 느끼지 않아도 규칙적으로 물을 마시세요.",
                "evidenceChunkIds": ["heat_illness_manual_v1__0014"],
            }
        ],
        "emergencyFlag": False,
        "emergencyMessage": None,
        "recommendedShelter": None,
    }
    for issue in verify_guidance_output(good_output, retrieved_ids, context):
        print(" ", issue)

    print("\n=== 케이스 2: 근거 조작 + 응급문구 변형 + 숫자 불일치 ===")
    bad_output = {
        "guidanceSentences": [
            {"text": "물을 하루 3리터 이상 마시세요.", "evidenceChunkIds": []},
            {
                "text": "40도가 넘으면 위험합니다.",
                "evidenceChunkIds": ["heat_illness_manual_v1__9999"],
            },
        ],
        "emergencyFlag": True,
        "emergencyMessage": "위험하면 병원에 가세요.",
        "recommendedShelter": None,
    }
    for issue in verify_guidance_output(bad_output, retrieved_ids, context):
        print(" ", issue)
