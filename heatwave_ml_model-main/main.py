"""날짜와 지역을 입력받아 다음 날 폭염 및 노인 온열질환 위험도를 예측한다."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import joblib
import pandas as pd

from predict import predict_dataframe
from training.train_next_day_heatwave import (
    DATE_COLUMN,
    REGION_COLUMN,
    TARGET_COLUMN,
    make_supervised,
)


PROJECT_ROOT = Path(__file__).resolve().parent
SEOUL_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "heat_data_seoul.csv"
HEATWAVE_MODEL_PATH = PROJECT_ROOT / "models" / "seoul_next_day_heatwave.joblib"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
SUPPORTED_REGION = "서울"
ANALOG_DAY_RANGE = 15


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="날짜와 지역으로 다음 날 폭염 및 노인 온열질환 위험도를 예측합니다."
    )
    parser.add_argument("date", help="예측 날짜. 예: 8/18 또는 2026-08-18")
    parser.add_argument("region", help="지역. 현재 모델은 서울만 지원")
    parser.add_argument("-o", "--output", type=Path, help="결과 CSV 저장 경로")
    return parser.parse_args()


def parse_forecast_date(value: str, latest_date: pd.Timestamp) -> pd.Timestamp:
    value = value.strip()
    month_day = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})", value)
    if month_day:
        return pd.Timestamp(
            year=latest_date.year,
            month=int(month_day.group(1)),
            day=int(month_day.group(2)),
        )
    try:
        return pd.to_datetime(value, format="mixed", errors="raise").normalize()
    except (TypeError, ValueError) as error:
        raise ValueError(f"날짜 형식을 확인하세요: {value}") from error


def load_seoul_data() -> pd.DataFrame:
    dataframe = pd.read_csv(SEOUL_DATA_PATH, encoding="utf-8-sig")
    dataframe[DATE_COLUMN] = pd.to_datetime(dataframe[DATE_COLUMN], errors="raise")
    return dataframe.sort_values(DATE_COLUMN, kind="stable").reset_index(drop=True)


def predict_heatwave(
    dataframe: pd.DataFrame, forecast_date: pd.Timestamp
) -> tuple[float, str]:
    artifact = joblib.load(HEATWAVE_MODEL_PATH)
    latest_date = dataframe[DATE_COLUMN].max()
    if forecast_date != latest_date + pd.Timedelta(days=1):
        raise ValueError(
            f"현재 데이터는 {latest_date.date()}까지이므로 "
            f"{(latest_date + pd.Timedelta(days=1)).date()}만 다음 날 예측할 수 있습니다."
        )

    placeholder = {column: pd.NA for column in dataframe.columns}
    placeholder[DATE_COLUMN] = forecast_date
    placeholder[REGION_COLUMN] = SUPPORTED_REGION
    placeholder[TARGET_COLUMN] = "X"  # 당일 값은 lag 입력에 포함되지 않는다.
    source = pd.concat([dataframe, pd.DataFrame([placeholder])], ignore_index=True)
    features, _, dates = make_supervised(source)
    forecast_features = features.loc[dates.eq(forecast_date)]
    forecast_features = forecast_features.loc[:, artifact["feature_columns"]]
    if len(forecast_features) != 1:
        raise ValueError("예측일 직전 7일 데이터가 연속으로 존재하지 않습니다.")

    score = float(artifact["pipeline"].predict_proba(forecast_features)[0, 1])
    prediction = "O" if score >= float(artifact["threshold"]) else "X"
    return score, prediction


def make_illness_model_input(
    dataframe: pd.DataFrame,
    forecast_date: pd.Timestamp,
    heatwave_prediction: str,
) -> tuple[pd.DataFrame, int]:
    """같은 계절·폭염 상태인 과거 날짜의 대표 기상값을 만든다."""
    history = dataframe.loc[dataframe[DATE_COLUMN] < forecast_date].copy()
    day_distance = (history[DATE_COLUMN].dt.dayofyear - forecast_date.dayofyear).abs()
    analogs = history.loc[
        day_distance.le(ANALOG_DAY_RANGE)
        & history[TARGET_COLUMN].astype("string").str.strip().eq(heatwave_prediction)
    ].copy()
    if analogs.empty:
        raise ValueError("노인 온열질환 위험도 계산에 사용할 과거 유사일이 없습니다.")

    row: dict[str, object] = {}
    for column in dataframe.columns:
        if column == DATE_COLUMN:
            row[column] = forecast_date
        elif column == REGION_COLUMN:
            row[column] = SUPPORTED_REGION
        elif column == TARGET_COLUMN:
            row[column] = heatwave_prediction
        elif pd.api.types.is_numeric_dtype(dataframe[column]):
            row[column] = analogs[column].median()
        else:
            modes = analogs[column].dropna().mode()
            row[column] = modes.iloc[0] if not modes.empty else pd.NA
    return pd.DataFrame([row]), len(analogs)


def forecast(date_value: str, region: str, output_path: Path | None = None) -> dict:
    region = region.strip()
    if region != SUPPORTED_REGION:
        raise ValueError(
            f"현재 폭염 모델은 {SUPPORTED_REGION} 전용입니다. 입력 지역: {region}"
        )
    if not HEATWAVE_MODEL_PATH.exists():
        raise FileNotFoundError(f"폭염 예측 모델이 없습니다: {HEATWAVE_MODEL_PATH}")

    dataframe = load_seoul_data()
    forecast_date = parse_forecast_date(date_value, dataframe[DATE_COLUMN].max())
    # 데이터가 예측일 전날까지 없으면(수집 지연), 최근 관측을 예측일 직전으로 당겨서
    # 다음 날 예측 조건을 맞춘다. 데모/운영 공백 대비 폴백.
    gap_days = (forecast_date - (dataframe[DATE_COLUMN].max() + pd.Timedelta(days=1))).days
    if gap_days > 0:
        dataframe[DATE_COLUMN] = dataframe[DATE_COLUMN] + pd.Timedelta(days=gap_days)
    heatwave_score, heatwave_prediction = predict_heatwave(dataframe, forecast_date)
    illness_input, analog_count = make_illness_model_input(
        dataframe, forecast_date, heatwave_prediction
    )
    illness_result = predict_dataframe(illness_input)
    illness_score = float(illness_result["risk_score"].iloc[0])

    result = {
        "date": forecast_date.strftime("%Y-%m-%d"),
        "region": region,
        "heatwave_risk_score": heatwave_score,
        "heatwave_prediction": heatwave_prediction,
        "elderly_heat_illness_risk_score": illness_score,
        "illness_weather_estimation": "historical_analog",
        "historical_analog_rows": analog_count,
    }
    destination = output_path or (
        OUTPUT_DIR / f"forecast_{forecast_date.strftime('%Y-%m-%d')}_{region}.csv"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([result]).to_csv(
        destination, index=False, encoding="utf-8-sig", float_format="%.6f"
    )

    print(f"예측일/지역: {result['date']} / {region}")
    print(
        f"폭염 확률: {heatwave_score:.6f}, "
        f"폭염 예측: {heatwave_prediction}"
    )
    print(f"노인 온열질환 위험도: {illness_score:.6f}")
    print(f"결과 저장: {destination}")
    return result


if __name__ == "__main__":
    arguments = parse_args()
    forecast(arguments.date, arguments.region, arguments.output)
