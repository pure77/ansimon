# -*- coding: utf-8 -*-
"""백엔드 연동용 FastAPI 서버

실행:
    uvicorn server:app --host 0.0.0.0 --port 8000 --reload
    브라우저에서 http://localhost:8000/docs  (Swagger UI 로 바로 테스트 가능)

엔드포인트
    GET  /health                    살아있는지
    GET  /v1/diagnostics            Alan / TMAP / 쉼터 / RAG 키·상태 한 번에 확인
    POST /v1/shelter/recommend      위경도 -> TMAP 최적 쉼터 (LLM 없이 쉼터만)
    POST /v1/intervention-plans     위경도(또는 쉼터) -> 쉼터+안내문+근거검증 전체

핵심: /v1/intervention-plans 에 shelter 를 안 주고 latitude/longitude 만 주면
서버가 쉼터 추천(TMAP)을 스스로 돌린 뒤 그 결과를 LLM 컨텍스트로 넣는다.
백엔드(Spring/FastAPI 어느 쪽이든)는 이 한 번의 호출로 끝난다.

응답 코드
    200  기획안 6.2 "최종 안내 계획" 스키마(camelCase). warnings 배열도 함께 온다.
    422  근거 검증 ERROR = 자동전화 보류. issues 를 로그/알림으로 노출할 것.
    502  쉼터/외부 API 실패
    503  RAG 저장소 미준비 (ingest.py 미실행)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
    # 저장소 루트에 .env 하나만 두고 세 서비스가 공유한다. rag/.env 가 따로 있으면 그걸 우선.
    for _d in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent):
        load_dotenv(_d / ".env")
except ImportError:
    pass

import shelter_client
from pipeline import GuidanceGenerationError, generate_intervention_plan
from schemas import ContractModel

app = FastAPI(
    title="안심온 LLM/RAG + 쉼터추천 서버",
    description="검색·프롬프트·생성·근거검증에 TMAP 쉼터 추천까지 묶은 안내 계획 생성 API",
    version="2.0.0",
)

# 프론트엔드(단일 HTML 대시보드)가 file:// 이나 다른 포트에서 바로 붙을 수 있게 열어둔다.
# 운영에서는 allow_origins 를 실제 도메인으로 좁힐 것.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"],
)


class ShelterRequest(ContractModel):
    latitude: float
    longitude: float
    file: Optional[str] = None      # 포털 CSV/JSON 으로 대체하고 싶을 때 (시연 안전빵)
    candidates: int = shelter_client.CANDIDATES


class InterventionPlanRequest(ContractModel):
    elderly_id: int
    risk_snapshot_id: int
    elderly_profile: dict
    risk_snapshot: dict
    shelter: Optional[dict] = None          # 주면 쉼터 조회를 건너뛴다
    weather: Optional[dict] = None
    latitude: Optional[float] = None        # 안 주면 elderly_profile.latitude 를 본다
    longitude: Optional[float] = None
    auto_shelter: bool = True


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/v1/diagnostics")
def diagnostics() -> dict:
    """키가 다 꽂혀 있는지, Alan 이 어떤 규격으로 붙는지 한 화면에서 본다.

    프론트/백엔드 붙이기 전에 여기부터 열어보면 "왜 mock 만 나오지?" 를 바로 안다.
    """
    import alan_client

    def has(name: str) -> bool:
        return bool((os.getenv(name) or "").strip())

    report = {
        "rag": {"chunksReady": (Path(__file__).resolve().parent / "out" / "chunks.jsonl").exists()},
        "keys": {k: has(k) for k in
                 ("ALAN_API_KEY", "TMAP_APP_KEY", "SHELTER_API_BASE_URL", "KMA_API_KEY")},
        "alan": {"mode": alan_client.resolve_mode(), "url": os.getenv("ALAN_API_URL") or None},
        "shelterFile": os.getenv("SHELTER_FILE") or None,
    }
    report["willUseMock"] = not report["keys"]["ALAN_API_KEY"]
    return report


@app.post("/v1/shelter/recommend")
def recommend_shelter(payload: ShelterRequest) -> dict:
    """LLM 없이 쉼터만. 프론트 지도 표시나 쉼터 로직 단독 테스트용."""
    try:
        return shelter_client.recommend_shelter(
            payload.latitude, payload.longitude, payload.file, payload.candidates)
    except shelter_client.ShelterLookupError as e:
        raise HTTPException(status_code=502, detail={"error": "SHELTER_LOOKUP_FAILED",
                                                     "message": str(e)})


@app.post("/v1/intervention-plans")
def create_intervention_plan(payload: InterventionPlanRequest) -> dict:
    try:
        return generate_intervention_plan(
            elderly_id=payload.elderly_id,
            risk_snapshot_id=payload.risk_snapshot_id,
            elderly_profile=payload.elderly_profile,
            risk_snapshot=payload.risk_snapshot,
            shelter=payload.shelter,
            weather=payload.weather,
            latitude=payload.latitude,
            longitude=payload.longitude,
            auto_shelter=payload.auto_shelter,
        )
    except GuidanceGenerationError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "GUIDANCE_GENERATION_BLOCKED",
                "message": str(e),
                "issues": [
                    {"level": i.level, "code": i.code, "message": i.message, "sentence": i.sentence}
                    for i in e.issues
                ],
            },
        )
    except FileNotFoundError as e:
        # 예: ingest.py를 아직 안 돌려서 out/chunks.jsonl이 없는 경우
        raise HTTPException(status_code=503, detail={"error": "RAG_STORE_NOT_READY", "message": str(e)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
