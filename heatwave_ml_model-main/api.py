"""날짜/지역 예측 결과를 HTTP로 내주는 얇은 래퍼. main.py 의 forecast() 로직은 그대로 재사용한다."""
from __future__ import annotations

import os

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from main import DATE_COLUMN, forecast, load_seoul_data

MODEL_VERSION = "heatwave-xgb-v1+illness-xgb-v1"
PORT = int(os.getenv("ML_API_PORT", "8100"))

app = FastAPI(title="안심온 위험도예측 ML API")


class ForecastResponse(BaseModel):
    date: str
    region: str
    heatwaveRiskScore: float
    heatwavePrediction: str
    elderlyHeatIllnessRiskScore: float
    illnessWeatherEstimation: str
    historicalAnalogRows: int
    modelVersion: str


def resolve_forecast_date(date: str | None) -> str:
    """date 가 없으면 서울 기준 오늘을 고른다. 보유 데이터가 오늘보다 뒤까지 있으면 마지막 날 다음 날."""
    if date:
        return date
    today = pd.Timestamp.now(tz="Asia/Seoul").tz_localize(None).normalize()
    dataframe = load_seoul_data()
    next_day = dataframe[DATE_COLUMN].max() + pd.Timedelta(days=1)
    return max(today, next_day).strftime("%Y-%m-%d")


@app.get("/health")
def health() -> dict:
    return {"status": "UP"}


@app.get("/v1/forecast", response_model=ForecastResponse)
def get_forecast(region: str = Query("서울"), date: str | None = Query(None)) -> ForecastResponse:
    forecast_date = resolve_forecast_date(date)
    try:
        result = forecast(forecast_date, region)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return ForecastResponse(
        date=result["date"],
        region=result["region"],
        heatwaveRiskScore=result["heatwave_risk_score"],
        heatwavePrediction=result["heatwave_prediction"],
        elderlyHeatIllnessRiskScore=result["elderly_heat_illness_risk_score"],
        illnessWeatherEstimation=result["illness_weather_estimation"],
        historicalAnalogRows=result["historical_analog_rows"],
        modelVersion=MODEL_VERSION,
    )


if __name__ == "__main__":
    import uvicorn

    print(f"위험도예측 ML API :{PORT}", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT)
