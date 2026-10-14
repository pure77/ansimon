"""새 기상 CSV에서 노인 온열질환 발생 위험도를 예측한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from preprocessing.preprocess import normalize_station_column, read_csv


PROJECT_ROOT = Path(__file__).resolve().parent
MODEL_PATH = PROJECT_ROOT / "models" / "xgboost_pipeline.joblib"
THRESHOLD_PATH = PROJECT_ROOT / "models" / "threshold.json"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "predictions.csv"

DATE_COLUMN = "일시"
REGION_COLUMN = "지점"
TARGET_COLUMN = "온열질환자(노인)발생여부"
RISK_COLUMN = "risk_score"
PREDICTION_COLUMN = "prediction"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="기상 CSV를 입력받아 0~1 사이의 온열질환 발생 위험도를 예측합니다."
    )
    parser.add_argument("input", type=Path, help="예측할 기상 CSV 경로")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help=f"결과 CSV 경로(기본값: {DEFAULT_OUTPUT_PATH})",
    )
    return parser.parse_args()


def prepare_features(dataframe: pd.DataFrame, expected_columns: list[str]) -> pd.DataFrame:
    """학습 때와 같은 형태로 날짜, 지점명, 범주형 값을 정리한다."""
    if dataframe.empty:
        raise ValueError("입력 CSV에 예측할 데이터가 없습니다.")
    if DATE_COLUMN not in dataframe.columns:
        raise KeyError(f"필요한 컬럼이 없습니다: ['{DATE_COLUMN}']")

    prepared = dataframe.copy()
    prepared[DATE_COLUMN] = pd.to_datetime(
        prepared[DATE_COLUMN].astype("string").str.strip(),
        format="mixed",
        errors="raise",
    )

    if REGION_COLUMN in prepared.columns:
        stations = prepared[REGION_COLUMN].astype("string").str.strip()
        raw_station_mask = stations.notna() & stations.str.match(r"^.*\(\d+\)$")
        if raw_station_mask.any():
            normalized = normalize_station_column(prepared.loc[raw_station_mask])
            prepared.loc[raw_station_mask, REGION_COLUMN] = normalized[REGION_COLUMN]
        prepared[REGION_COLUMN] = prepared[REGION_COLUMN].astype("string").str.strip()

    if TARGET_COLUMN in prepared.columns:
        prepared = prepared.drop(columns=TARGET_COLUMN)

    categorical_columns = prepared.select_dtypes(
        include=["object", "string", "category"]
    ).columns
    for column in categorical_columns:
        prepared[column] = (
            prepared[column].astype("string").str.strip().replace("", pd.NA)
        )

    if "폭염영향예보(단계)" in prepared.columns:
        prepared["폭염영향예보(단계)"] = prepared["폭염영향예보(단계)"].fillna("없음")

    prepared["월"] = prepared[DATE_COLUMN].dt.month
    prepared["연중일"] = prepared[DATE_COLUMN].dt.dayofyear
    prepared = prepared.drop(columns=DATE_COLUMN)

    missing_columns = [name for name in expected_columns if name not in prepared.columns]
    if missing_columns:
        raise KeyError(f"모델 예측에 필요한 컬럼이 없습니다: {missing_columns}")
    return prepared.loc[:, expected_columns]


def predict_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
    """입력 데이터에 risk_score와 O/X 예측 결과를 붙여 반환한다."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"학습된 모델이 없습니다: {MODEL_PATH}")
    if not THRESHOLD_PATH.exists():
        raise FileNotFoundError(f"예측 임계값 파일이 없습니다: {THRESHOLD_PATH}")

    pipeline = joblib.load(MODEL_PATH)
    expected_columns = list(pipeline.feature_names_in_)
    features = prepare_features(dataframe, expected_columns)

    with THRESHOLD_PATH.open(encoding="utf-8") as threshold_file:
        threshold = float(json.load(threshold_file)["threshold"])

    scores = np.clip(pipeline.predict_proba(features)[:, 1], 0.0, 1.0)
    result = dataframe.copy()
    result[RISK_COLUMN] = scores
    result[PREDICTION_COLUMN] = np.where(scores >= threshold, "O", "X")
    return result


def predict_csv(input_path: Path, output_path: Path = DEFAULT_OUTPUT_PATH) -> pd.DataFrame:
    """CSV를 읽어 예측하고 결과를 UTF-8 CSV로 저장한다."""
    if not input_path.exists():
        raise FileNotFoundError(f"입력 CSV가 없습니다: {input_path}")

    result = predict_dataframe(read_csv(input_path))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, encoding="utf-8-sig", float_format="%.6f")
    print(f"입력 행 수: {len(result):,}")
    print(f"위험도 범위: {result[RISK_COLUMN].min():.6f} ~ {result[RISK_COLUMN].max():.6f}")
    print(f"예측 결과 저장: {output_path}")
    return result


if __name__ == "__main__":
    arguments = parse_args()
    predict_csv(arguments.input, arguments.output)
