# -*- coding: utf-8 -*-
"""출력 스키마 (기획안 6.1~6.3 계약)

- 6.1 ML 응답: RiskSnapshot (risk 모듈이 이미 계산해 넘겨주는 입력 계약)
- 6.2 최종 안내 계획: InterventionPlan (이 계층의 출력 계약, guidance/contact 모듈이 소비)
- 6.3 통화 결과: CallOutcome (contact 모듈이 채워 넣는 입력 계약, 현재는 스키마만 정의)

pydantic이 enum/타입을 코드 레벨에서 강제하므로, Spring이 최종 검증을 하기 전
LLM/RAG 계층에서 잘못된 값이 새어나가는 것을 1차로 막는다.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

# 응급 증상 문구는 팀이 승인한 고정 템플릿 그대로 사용해야 한다.
# prompt_builder.py(시스템 규칙 3)와 evidence_verifier.py(근거 검증 표 3번째 항목)가
# 이 상수 하나를 공유해서 "다른 문구로 슬쩍 바뀌는" 환각을 원천 차단한다.
EMERGENCY_GUIDANCE_TEMPLATE = (
    "의식이 없거나 반응이 없으면 즉시 119에 신고하고, 몸을 서늘한 곳으로 옮긴 뒤 "
    "옷을 느슨하게 하고 시원한 물로 체온을 낮추세요."
)

# TMAP 길안내를 못 받아 직선거리로 쉼터를 고른 경우에 반드시 함께 나가는 고지문.
# 응급 문구와 같은 급의 고정 템플릿이다 — LLM 이 이 문장을 바꾸거나 빠뜨리면
# evidence_verifier 가 ERROR 로 잡는다. 어르신이 "3분이면 가겠네" 하고 나섰다가
# 실제로는 15분 걸리는 상황을 만들지 않기 위한 안전장치다.
STRAIGHT_LINE_NOTICE = (
    "지금은 길안내를 받을 수 없어서 직선거리로 가장 가까운 쉼터를 알려드렸습니다. "
    "실제로 걷는 길과 걸리는 시간은 이보다 길 수 있으니, 나가시기 전에 보호자나 "
    "담당 복지사에게 한 번 확인해 주세요."
)

# 쉼터 경로의 출처. TMAP = 실제 보행경로 확인됨 / STRAIGHT_LINE_FALLBACK = 직선거리 추정
ROUTE_SOURCE_TMAP = "TMAP"
ROUTE_SOURCE_STRAIGHT_LINE = "STRAIGHT_LINE_FALLBACK"


def _camel(field_name: str) -> str:
    head, *rest = field_name.split("_")
    return head + "".join(word.capitalize() for word in rest)


class ContractModel(BaseModel):
    """Spring(camelCase) 계약과 맞물리는 모델의 공통 베이스."""

    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class TriState(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


class ContactStatus(str, Enum):
    ANSWERED = "ANSWERED"
    NO_ANSWER = "NO_ANSWER"
    REJECTED = "REJECTED"
    INVALID_NUMBER = "INVALID_NUMBER"
    ESCALATED_TO_GUARDIAN = "ESCALATED_TO_GUARDIAN"


class TargetAudience(str, Enum):
    ELDERLY = "ELDERLY"
    PREGNANT = "PREGNANT"
    DISABLED = "DISABLED"
    CARDIOVASCULAR = "CARDIOVASCULAR"
    RENAL = "RENAL"
    BLOOD_PRESSURE = "BLOOD_PRESSURE"
    DIABETES = "DIABETES"
    OUTDOOR_WORKER = "OUTDOOR_WORKER"
    CHILD = "CHILD"
    EMERGENCY = "EMERGENCY"
    GENERAL = "GENERAL"


# --- 6.1 ML 응답 (risk 모듈 -> 이 계층 입력) --------------------------------


class RiskSnapshot(ContractModel):
    risk_snapshot_id: int
    elderly_id: int
    risk_level: RiskLevel
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_factors: list[str] = Field(default_factory=list)
    generated_at: datetime


# --- 6.2 최종 안내 계획 (이 계층 출력) ---------------------------------------


class GuidanceSentence(ContractModel):
    text: str
    evidence_chunk_ids: list[str] = Field(default_factory=list)


class AlternativeShelter(ContractModel):
    name: str
    walk_minutes: Optional[int] = None
    crossings: Optional[int] = None
    # 직선거리 폴백일 때는 TMAP 도보시간이 없으므로 추정치가 들어간다
    estimated_walk_minutes: Optional[int] = None


class ShelterRecommendation(ContractModel):
    name: str
    address: str = ""
    distance_m: Optional[float] = None
    source: str
    # t-map_location_connection_ansimon(recommend.py)의 TMAP 보행자 경로 결과.
    # shelter 모듈이 이미 도보 기준으로 최적화해 넘겨주므로 여기서는 그대로 보존만 한다.
    lat: Optional[float] = None
    lon: Optional[float] = None
    walk_minutes: Optional[int] = None
    walk_meters: Optional[int] = None
    crossings: Optional[int] = None
    open_status: Optional[str] = None
    open_hours_raw: Optional[str] = None
    # "TMAP" 이면 walk_minutes/walk_meters/crossings/route 가 실제 보행경로 값이고,
    # "STRAIGHT_LINE_FALLBACK" 이면 그것들은 비어 있고 estimated_walk_minutes 만 채워진다.
    # 이 둘을 섞어 쓰면 안 된다 — 추정치를 확정 도보시간처럼 안내하는 순간
    # 어르신이 폭염에 예상보다 오래 걷게 된다.
    route_source: str = ROUTE_SOURCE_TMAP
    estimated_walk_minutes: Optional[int] = None
    needs_review: bool = False
    route: list[str] = Field(default_factory=list)
    alternatives: list[AlternativeShelter] = Field(default_factory=list)


class InterventionPlan(ContractModel):
    elderly_id: int
    risk_snapshot_id: int
    risk_level: RiskLevel
    guidance_sentences: list[GuidanceSentence]
    recommended_shelter: Optional[ShelterRecommendation] = None
    emergency_flag: bool = False
    emergency_message: Optional[str] = None
    model_used: str
    # 자동전화를 막을 정도는 아니지만 사회복지사가 알아야 하는 것들
    # (쉼터 조회 실패, needs_review, 숫자 불일치 WARNING 등). 추가 필드라 기존 계약은 그대로.
    warnings: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_contract_json(self) -> dict:
        """기획안 6.2 예시와 동일한 필드명(camelCase)의 dict로 직렬화."""
        return self.model_dump(mode="json", by_alias=True)


# --- 6.3 통화 결과 (contact 모듈 -> 이 계층으로 되돌아오는 입력, 스키마만 정의) --


class CallOutcome(ContractModel):
    elderly_id: int
    risk_snapshot_id: int
    contact_status: ContactStatus
    call_started_at: Optional[datetime] = None
    call_ended_at: Optional[datetime] = None
    elderly_confirmed_safe: TriState = TriState.UNKNOWN
    follow_up_required: bool = False
    notes: Optional[str] = None
