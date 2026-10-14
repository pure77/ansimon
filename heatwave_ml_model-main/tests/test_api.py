"""api.py 의 핵심 분기(날짜 자동계산, 지역 검증)만 확인한다."""
from __future__ import annotations

from fastapi.testclient import TestClient

from api import MODEL_VERSION, app

client = TestClient(app)


def test_forecast_resolves_the_next_day_and_returns_the_full_schema():
    response = client.get("/v1/forecast", params={"region": "서울"})
    assert response.status_code == 200
    body = response.json()
    assert body["date"] == "2026-08-18"
    assert body["heatwavePrediction"] in ("O", "X")
    assert 0.0 <= body["elderlyHeatIllnessRiskScore"] <= 1.0
    assert body["modelVersion"] == MODEL_VERSION


def test_forecast_rejects_an_unsupported_region():
    response = client.get("/v1/forecast", params={"region": "부산"})
    assert response.status_code == 400
