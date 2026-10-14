# -*- coding: utf-8 -*-
"""anshimon-rag(:8000) HTTP 클라이언트.

왜 HTTP 인가: 두 저장소 모두 `server.py` 라는 이름의 모듈을 갖고 있어서 in-process
import 로 합치면 sys.path 순서에 따라 엉뚱한 쪽이 잡힌다. 그리고 여기서 clawops·
scikit-learn 을 설치할 이유가 없다. 경계는 이미 HTTP 로 나 있다 — 그대로 쓴다.

anshimon-rag 실행:  uvicorn server:app --port 8000
"""
from __future__ import annotations

import os
from typing import Any, Optional

import aiohttp

BASE = (os.getenv("RAG_BASE_URL") or "http://localhost:8000").rstrip("/")
TIMEOUT = int(os.getenv("RAG_TIMEOUT_SEC", "120"))   # 쉼터 조회 + LLM 이라 넉넉히


class RagError(RuntimeError):
    """RAG 계층이 안내문을 만들지 못했다."""


class GuidanceBlocked(RagError):
    """근거 검증 ERROR(HTTP 422) — 자동 전화 보류.

    쉼터를 지어냈거나 응급 문구가 변형됐다는 뜻이다. 이건 재시도로 풀릴 문제가 아니라
    **사람이 봐야 하는 문제**다. 그래서 전화를 걸지 않고 issues 를 그대로 올린다.
    """

    def __init__(self, message: str, issues: list):
        super().__init__(message)
        self.issues = issues


async def _post(session: aiohttp.ClientSession, path: str, body: dict) -> Any:
    async with session.post(f"{BASE}{path}", json=body,
                            timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as r:
        data = await r.json(content_type=None)
        if r.status == 200:
            return data
        detail = (data or {}).get("detail") or {}
        if r.status == 422:
            raise GuidanceBlocked(detail.get("message") or "근거 검증 실패",
                                  detail.get("issues") or [])
        raise RagError(f"RAG {path} {r.status}: {detail or data}")


async def create_intervention_plan(
    elderly_id: int, risk_snapshot_id: int, elderly_profile: dict, risk_snapshot: dict,
    latitude: Optional[float] = None, longitude: Optional[float] = None,
    weather: Optional[dict] = None, shelter: Optional[dict] = None,
    auto_shelter: bool = True,
) -> dict:
    """위경도만 주면 쉼터 선정(TMAP) -> 안내문 생성 -> 근거검증까지 저쪽이 다 한다.

    반환은 기획안 6.2 InterventionPlan(camelCase): guidanceSentences,
    recommendedShelter, emergencyFlag, modelUsed, warnings.
    """
    body = {
        "elderlyId": elderly_id,
        "riskSnapshotId": risk_snapshot_id,
        "elderlyProfile": elderly_profile,
        "riskSnapshot": risk_snapshot,
        "weather": weather or {},
        "latitude": latitude,
        "longitude": longitude,
        # 공공 쉼터 데이터가 없는 지역이면 False. 조회하면 서울 시설이 수백 km 밖에서 나온다.
        "autoShelter": auto_shelter and shelter is None,
    }
    if shelter:
        body["shelter"] = shelter
    async with aiohttp.ClientSession() as s:
        return await _post(s, "/v1/intervention-plans", body)


async def diagnostics() -> dict:
    """Alan/TMAP/쉼터 키가 꽂혀 있는지. 시연 전에 이걸 먼저 본다."""
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{BASE}/v1/diagnostics",
                         timeout=aiohttp.ClientTimeout(total=15)) as r:
            return await r.json(content_type=None)
