# -*- coding: utf-8 -*-
"""엔드투엔드 진입점 - 백엔드가 호출할 함수

문서 수집·청킹(ingest) -> 검색(retrieval) -> 프롬프트(prompt_builder) ->
생성(llm_client) -> 근거 검증(evidence_verifier) -> 출력 스키마(schemas)

이번 통합에서 추가된 것: **쉼터 자동 조회**.
호출자가 위경도만 주면 shelter_client(서울열린데이터광장 + TMAP 보행경로)가 쉼터를
직접 골라 그 결과가 그대로 프롬프트 컨텍스트로 들어간다. 즉 백엔드는

    generate_intervention_plan(elderly_id, risk_snapshot_id, profile, risk)

한 번만 부르면 "쉼터 선정 -> 도보경로 -> 안내문 생성 -> 근거검증"까지 끝난다.
(이미 다른 곳에서 쉼터를 골랐다면 shelter= 로 넘기면 조회를 건너뛴다)

근거 검증에서 ERROR 가 하나라도 나오면 GuidanceGenerationError 를 던져 자동전화
발신을 보류시킨다.
"""
from __future__ import annotations

import os
import sys
from functools import lru_cache
from typing import Any, Optional

import evidence_verifier
import llm_client
import prompt_builder
from retrieval import RetrievedChunk, load_active_chunks
from retrieval import search as retrieve_chunks
from schemas import (AlternativeShelter, GuidanceSentence, InterventionPlan, RiskLevel,
                     ROUTE_SOURCE_STRAIGHT_LINE, ROUTE_SOURCE_TMAP, ShelterRecommendation)
from shelter_reference import ShelterReferenceIndex, load_default_index


class GuidanceGenerationError(Exception):
    """근거 검증 ERROR로 인해 안내 계획 생성을 보류할 때 발생시킨다.

    백엔드의 guidance/contact 모듈은 이 예외를 받으면 자동전화를 걸지 않고 issues 를
    로그/알림으로 노출해야 한다.
    """

    def __init__(self, elderly_id: int, risk_snapshot_id: int,
                 issues: list[evidence_verifier.VerificationIssue]):
        self.elderly_id = elderly_id
        self.risk_snapshot_id = risk_snapshot_id
        self.issues = issues
        summary = "; ".join(str(i) for i in issues if i.level == "ERROR")
        super().__init__(
            f"elderly_id={elderly_id} risk_snapshot_id={risk_snapshot_id} 근거 검증 실패로 "
            f"자동전화 발신을 보류합니다: {summary}"
        )


@lru_cache(maxsize=1)
def _shelter_index() -> ShelterReferenceIndex:
    return load_default_index()


def _build_search_query(elderly_profile: dict, risk_snapshot: dict) -> str:
    audience = elderly_profile.get("targetAudience") or elderly_profile.get("target_audience") or []
    risk_level = risk_snapshot.get("riskLevel") or risk_snapshot.get("risk_level") or ""
    risk_factors = risk_snapshot.get("riskFactors") or risk_snapshot.get("risk_factors") or []
    parts = [" ".join(audience), f"위험도 {risk_level}", " ".join(risk_factors), "폭염 온열질환 예방 수칙"]
    return " ".join(p for p in parts if p).strip()


def _ensure_emergency_chunk(chunks: list) -> list:
    """CRITICAL 일 때 승인된 응급문구 청크가 검색 결과에 반드시 들어가게 한다.

    이게 없으면 생성 단계가 응급문구를 붙이면서 "검색에 없던 chunk_id" 를 인용하게 되고,
    근거검증이 FABRICATED_CHUNK_ID(ERROR)로 잡아 **CRITICAL 케이스가 항상 보류**된다.
    가장 위험한 등급의 전화가 매번 막히는 셈이라, 검색 단계에서 미리 채워 넣는다.
    """
    from schemas import EMERGENCY_GUIDANCE_TEMPLATE

    if any(c.text == EMERGENCY_GUIDANCE_TEMPLATE for c in chunks):
        return chunks
    for c in load_active_chunks():
        if c["text"] == EMERGENCY_GUIDANCE_TEMPLATE:
            return [*chunks, RetrievedChunk(
                chunk_id=c["chunk_id"], document_id=c["document_id"], text=c["text"],
                heading_path=c["heading_path"], target_audience=c["target_audience"],
                page_number=c.get("page_number"), score=1.0)]
    return chunks


def _coords(elderly_profile: dict, latitude: Optional[float],
            longitude: Optional[float]) -> Optional[tuple[float, float]]:
    lat = latitude if latitude is not None else (
        elderly_profile.get("latitude") or elderly_profile.get("lat"))
    lon = longitude if longitude is not None else (
        elderly_profile.get("longitude") or elderly_profile.get("lon"))
    if lat is None or lon is None:
        return None
    return float(lat), float(lon)


def _lookup_shelter(lat: float, lon: float, warnings: list[str]) -> Optional[dict]:
    """TMAP 쉼터 추천. 실패해도 안내 계획 자체는 계속 만든다.

    쉼터가 없어도 "물 마시기·외출 자제" 같은 안내는 여전히 유효하다. 여기서 예외를
    올려버리면 쉼터 API 장애 하나로 전체 전화가 멈춘다 — 그건 과잉 차단이다.
    반대로 쉼터를 '추측'해서 채우는 일은 절대 하지 않는다.
    """
    try:
        import shelter_client
        shelter = shelter_client.recommend_shelter(lat, lon)
    except Exception as e:   # ShelterLookupError 포함
        warnings.append(f"쉼터 조회 실패({type(e).__name__}: {str(e)[:120]}) — 쉼터 안내 없이 진행합니다.")
        print(f"[pipeline] 쉼터 조회 실패: {e}", file=sys.stderr)
        return None

    if shelter.get("route_source") == ROUTE_SOURCE_STRAIGHT_LINE:
        warnings.append(
            f"TMAP 경로 계산 실패 — 직선거리로 '{shelter.get('name')}'을(를) 추천했습니다 "
            f"(추정 도보 {shelter.get('estimated_walk_minutes')}분). 실제 경로 확인이 필요합니다.")
    if shelter.get("needs_review"):
        warnings.append(f"추천 쉼터 needs_review=true ({shelter.get('reason', '도보시간 초과')})")
    return shelter


def generate_intervention_plan(
    elderly_id: int,
    risk_snapshot_id: int,
    elderly_profile: dict,
    risk_snapshot: dict,
    shelter: Optional[dict] = None,
    weather: Optional[dict] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    auto_shelter: bool = True,
) -> dict:
    """백엔드가 호출하는 엔드투엔드 진입점.

    shelter 를 안 주고 위경도(인자 또는 profile.latitude/longitude)를 주면
    shelter_client 가 서울시 쉼터 목록 + TMAP 보행경로로 직접 고른다.

    성공 시 기획안 6.2 "최종 안내 계획" 스키마와 동일한 dict 를 반환한다.
    근거 검증 ERROR 가 있으면 GuidanceGenerationError 를 던진다 (자동전화 보류).
    """
    weather = weather or {}
    warnings: list[str] = []

    # --- 0. 쉼터 확보 (TMAP 연동 지점) ---
    if shelter is None and auto_shelter:
        coords = _coords(elderly_profile, latitude, longitude)
        if coords:
            shelter = _lookup_shelter(coords[0], coords[1], warnings)
        else:
            warnings.append("위경도가 없어 쉼터를 조회하지 않았습니다.")

    audience = elderly_profile.get("targetAudience") or elderly_profile.get("target_audience") or []
    risk_level_raw = risk_snapshot.get("riskLevel") or risk_snapshot.get("risk_level")
    if risk_level_raw == "CRITICAL" and "EMERGENCY" not in audience:
        audience = [*audience, "EMERGENCY"]

    # --- 1. 검색 ---
    query = _build_search_query(elderly_profile, risk_snapshot)
    evidence_chunks = retrieve_chunks(query, target_audience=audience, top_k=5)
    if risk_level_raw == "CRITICAL":
        evidence_chunks = _ensure_emergency_chunk(evidence_chunks)
    retrieved_chunk_ids = {c.chunk_id for c in evidence_chunks}

    # --- 2~3. 프롬프트 + 생성 ---
    messages_payload = prompt_builder.build_messages(
        elderly_profile, risk_snapshot, shelter, weather, evidence_chunks
    )
    raw_output = llm_client.generate_guidance(
        evidence_chunks, risk_snapshot, shelter, messages_payload=messages_payload
    )
    if raw_output.get("_fallbackReason"):
        # 왜 LLM 이 아니라 mock 이 답했는지. 이게 안 보이면 "안내문이 이상한데 왜?" 로 끝난다.
        warnings.append(f"LLM 미사용 — mock 안내문입니다: {raw_output['_fallbackReason']}")

    # --- 4. 근거 검증 ---
    structured_context: dict[str, Any] = {
        "profile": elderly_profile,
        "risk": risk_snapshot,
        "weather": weather,
        "shelter": shelter,
    }
    issues = evidence_verifier.verify_guidance_output(
        raw_output, retrieved_chunk_ids, structured_context, shelter_ref=_shelter_index()
    )

    if evidence_verifier.has_errors(issues):
        raise GuidanceGenerationError(elderly_id, risk_snapshot_id, issues)

    warnings += [str(i) for i in issues if i.level == "WARNING"]

    # --- 5. 출력 스키마 ---
    recommended_shelter = None
    if raw_output.get("recommendedShelter"):
        s = raw_output["recommendedShelter"]
        recommended_shelter = ShelterRecommendation(
            name=s.get("name", ""),
            address=s.get("address") or "",
            distance_m=s.get("distanceM"),
            source=(shelter or {}).get("source", "pipeline"),
            lat=s.get("lat"),
            lon=s.get("lon"),
            walk_minutes=s.get("walkMinutes"),
            walk_meters=s.get("walkMeters"),
            crossings=s.get("crossings"),
            open_status=s.get("openStatus"),
            open_hours_raw=s.get("openHoursRaw"),
            route_source=s.get("routeSource", ROUTE_SOURCE_TMAP),
            estimated_walk_minutes=s.get("estimatedWalkMinutes"),
            needs_review=s.get("needsReview", False),
            route=s.get("route", []),
            alternatives=[AlternativeShelter.model_validate(a) for a in s.get("alternatives", [])],
        )

    plan = InterventionPlan(
        elderly_id=elderly_id,
        risk_snapshot_id=risk_snapshot_id,
        risk_level=RiskLevel(risk_level_raw),
        guidance_sentences=[
            GuidanceSentence(text=s["text"], evidence_chunk_ids=s.get("evidenceChunkIds", []))
            for s in raw_output.get("guidanceSentences", [])
        ],
        recommended_shelter=recommended_shelter,
        emergency_flag=raw_output.get("emergencyFlag", False),
        emergency_message=raw_output.get("emergencyMessage"),
        model_used=raw_output.get("_modelUsed", "unknown"),
        warnings=warnings,
    )
    return plan.to_contract_json()


if __name__ == "__main__":
    import json

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    demo_profile = {"targetAudience": ["ELDERLY"], "age": 82, "livesAlone": True}
    demo_weather = {"temperatureC": 36.2, "heatWarning": "폭염경보"}
    demo_risk = {"riskLevel": "HIGH", "riskScore": 0.83, "riskFactors": ["독거", "고령"]}

    print("=== 케이스 1: 쉼터를 직접 넘기는 기존 방식 ===")
    plan_json = generate_intervention_plan(
        elderly_id=101, risk_snapshot_id=812,
        elderly_profile=demo_profile, risk_snapshot=demo_risk,
        shelter={"name": "종로노인종합복지관 경로당", "address": "서울특별시 종로구 삼봉로 71"},
        weather=demo_weather,
    )
    print(json.dumps(plan_json, ensure_ascii=False, indent=2)[:900])

    print("\n=== 케이스 2: 위경도만 주고 TMAP 자동 조회 (실 API 필요) ===")
    if os.getenv("SHELTER_API_BASE_URL") and os.getenv("TMAP_APP_KEY"):
        plan_json = generate_intervention_plan(
            elderly_id=105, risk_snapshot_id=816,
            elderly_profile={**demo_profile, "latitude": 37.5665, "longitude": 126.9780},
            risk_snapshot=demo_risk, weather=demo_weather,
        )
        print(json.dumps(plan_json.get("recommendedShelter"), ensure_ascii=False, indent=2))
        print("warnings:", plan_json.get("warnings"))
    else:
        print("  (SHELTER_API_BASE_URL / TMAP_APP_KEY 미설정 — 건너뜀)")

    print("\n=== 케이스 3: 쉼터 실존 검증 실패 -> 자동전화 보류 ===")
    try:
        generate_intervention_plan(
            elderly_id=102, risk_snapshot_id=813,
            elderly_profile=demo_profile, risk_snapshot=demo_risk,
            shelter={"name": "가상의쉼터12345 (실존하지않음)", "address": "서울특별시 어딘가 999"},
            weather=demo_weather,
        )
    except GuidanceGenerationError as e:
        print(f"자동전화 보류됨: {e}")
