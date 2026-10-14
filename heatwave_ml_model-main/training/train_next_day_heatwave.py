"""서울의 직전 7일 기상 데이터로 다음 날 폭염 여부를 예측한다."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "heat_data_seoul.csv"
MODEL_PATH = PROJECT_ROOT / "models" / "seoul_next_day_heatwave.joblib"
CONFIG_PATH = PROJECT_ROOT / "models" / "seoul_next_day_heatwave_config.json"
TEST_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "seoul_heatwave_test_predictions.csv"
FORECAST_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "seoul_heatwave_latest_forecast.csv"

DATE_COLUMN = "일시"
REGION_COLUMN = "지점"
TARGET_COLUMN = "폭염여부(O/X)"
UNRELATED_TARGET_COLUMN = "온열질환자(노인)발생여부"
WINDOW_DAYS = 7
TUNING_TRAIN_END_YEAR = 2023
VALIDATION_YEAR = 2024
TEST_YEAR = 2025
RANDOM_STATE = 42


def load_data() -> pd.DataFrame:
    dataframe = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    required = {DATE_COLUMN, REGION_COLUMN, TARGET_COLUMN}
    missing = sorted(required - set(dataframe.columns))
    if missing:
        raise KeyError(f"필요한 컬럼이 없습니다: {missing}")

    dataframe[DATE_COLUMN] = pd.to_datetime(dataframe[DATE_COLUMN], errors="raise")
    dataframe = dataframe.sort_values(DATE_COLUMN, kind="stable").reset_index(drop=True)
    if dataframe[DATE_COLUMN].duplicated().any():
        raise ValueError("같은 날짜가 중복되어 있습니다.")
    if set(dataframe[REGION_COLUMN].dropna().unique()) != {"서울"}:
        raise ValueError("서울 이외 지역의 데이터가 포함되어 있습니다.")

    target = dataframe[TARGET_COLUMN].astype("string").str.strip()
    invalid = target.notna() & ~target.isin(["O", "X"])
    if invalid.any():
        raise ValueError(f"폭염여부에 O/X 이외 값이 있습니다: {target[invalid].unique().tolist()}")
    dataframe[TARGET_COLUMN] = target
    return dataframe


def make_supervised(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """각 예측일 직전 7일을 lag 특성으로 펼친다."""
    excluded = {DATE_COLUMN, REGION_COLUMN, UNRELATED_TARGET_COLUMN}
    history_columns = [column for column in dataframe.columns if column not in excluded]
    feature_parts: list[pd.DataFrame] = []

    for lag in range(1, WINDOW_DAYS + 1):
        lagged = dataframe[history_columns].shift(lag)
        lagged.columns = [f"{column}_lag{lag}" for column in history_columns]
        feature_parts.append(lagged)

    features = pd.concat(feature_parts, axis=1)
    features["예측월"] = dataframe[DATE_COLUMN].dt.month
    features["예측연중일"] = dataframe[DATE_COLUMN].dt.dayofyear

    # 연도 사이의 긴 공백을 7일 연속 관측으로 잘못 연결하지 않는다.
    consecutive_window = (
        dataframe[DATE_COLUMN] - dataframe[DATE_COLUMN].shift(WINDOW_DAYS)
    ).dt.days.eq(WINDOW_DAYS)
    features = features.loc[consecutive_window].reset_index(drop=True)
    target = (
        dataframe.loc[consecutive_window, TARGET_COLUMN]
        .map({"X": 0, "O": 1})
        .astype("int8")
        .reset_index(drop=True)
    )
    dates = dataframe.loc[consecutive_window, DATE_COLUMN].reset_index(drop=True)
    return features, target, dates


def build_pipeline(features: pd.DataFrame, target: pd.Series) -> Pipeline:
    categorical_columns = features.select_dtypes(
        include=["object", "string", "category"]
    ).columns.tolist()
    numeric_columns = features.columns.difference(categorical_columns).tolist()
    preprocessor = ColumnTransformer(
        transformers=[
            ("numeric", SimpleImputer(strategy="median"), numeric_columns),
            (
                "categorical",
                Pipeline(
                    steps=[
                        (
                            "imputer",
                            SimpleImputer(strategy="constant", fill_value="정보없음"),
                        ),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            ),
        ]
    )
    positive_count = int(target.sum())
    scale_pos_weight = (len(target) - positive_count) / positive_count
    model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        n_estimators=300,
        learning_rate=0.03,
        max_depth=3,
        min_child_weight=3,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=2.0,
        scale_pos_weight=scale_pos_weight,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    return Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])


def select_f1_threshold(actual: pd.Series, scores: np.ndarray) -> float:
    precision, recall, thresholds = precision_recall_curve(actual, scores)
    if len(thresholds) == 0:
        return 0.5
    denominator = precision[:-1] + recall[:-1]
    f1_values = np.divide(
        2 * precision[:-1] * recall[:-1],
        denominator,
        out=np.zeros_like(denominator),
        where=denominator != 0,
    )
    return float(thresholds[int(np.argmax(f1_values))])


def calculate_metrics(
    actual: pd.Series, scores: np.ndarray, threshold: float
) -> dict[str, float | int | list[list[int]]]:
    prediction = (scores >= threshold).astype("int8")
    matrix = confusion_matrix(actual, prediction, labels=[0, 1])
    return {
        "rows": len(actual),
        "positive_rows": int(actual.sum()),
        "threshold": threshold,
        "accuracy": float(accuracy_score(actual, prediction)),
        "precision": float(precision_score(actual, prediction, zero_division=0)),
        "recall": float(recall_score(actual, prediction, zero_division=0)),
        "f1": float(f1_score(actual, prediction, zero_division=0)),
        "roc_auc": float(roc_auc_score(actual, scores)),
        "pr_auc": float(average_precision_score(actual, scores)),
        "confusion_matrix": matrix.tolist(),
    }


def train_and_evaluate() -> dict:
    dataframe = load_data()
    features, target, dates = make_supervised(dataframe)
    years = dates.dt.year

    tuning_train_mask = years.le(TUNING_TRAIN_END_YEAR)
    validation_mask = years.eq(VALIDATION_YEAR)
    final_train_mask = years.le(VALIDATION_YEAR)
    test_mask = years.eq(TEST_YEAR)

    threshold_model = build_pipeline(
        features.loc[tuning_train_mask], target.loc[tuning_train_mask]
    )
    threshold_model.fit(
        features.loc[tuning_train_mask], target.loc[tuning_train_mask]
    )
    validation_scores = threshold_model.predict_proba(features.loc[validation_mask])[:, 1]
    threshold = select_f1_threshold(target.loc[validation_mask], validation_scores)
    validation_metrics = calculate_metrics(
        target.loc[validation_mask], validation_scores, threshold
    )

    evaluation_model = build_pipeline(
        features.loc[final_train_mask], target.loc[final_train_mask]
    )
    evaluation_model.fit(features.loc[final_train_mask], target.loc[final_train_mask])
    test_scores = evaluation_model.predict_proba(features.loc[test_mask])[:, 1]
    test_metrics = calculate_metrics(target.loc[test_mask], test_scores, threshold)

    test_predictions = pd.DataFrame(
        {
            DATE_COLUMN: dates.loc[test_mask].to_numpy(),
            "actual": target.loc[test_mask].to_numpy(),
            "risk_score": test_scores,
            "prediction": (test_scores >= threshold).astype("int8"),
        }
    )
    TEST_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    test_predictions.to_csv(
        TEST_OUTPUT_PATH, index=False, encoding="utf-8-sig", float_format="%.6f"
    )

    # 성능평가가 끝난 뒤 실제 사용 모델은 현재 보유한 전체 관측값으로 다시 학습한다.
    production_model = build_pipeline(features, target)
    production_model.fit(features, target)
    next_date = dataframe[DATE_COLUMN].max() + pd.Timedelta(days=1)
    placeholder = {column: pd.NA for column in dataframe.columns}
    placeholder[DATE_COLUMN] = next_date
    placeholder[REGION_COLUMN] = "서울"
    placeholder[TARGET_COLUMN] = "X"  # 현재 행 값은 lag 입력에 사용되지 않는다.
    forecast_source = pd.concat(
        [dataframe, pd.DataFrame([placeholder])], ignore_index=True
    )
    forecast_features, _, forecast_dates = make_supervised(forecast_source)
    latest_features = forecast_features.loc[forecast_dates.eq(next_date)]
    if len(latest_features) != 1:
        raise ValueError("최신 7일이 연속되지 않아 다음 날 예측을 만들 수 없습니다.")
    latest_score = float(production_model.predict_proba(latest_features)[0, 1])
    latest_prediction = "O" if latest_score >= threshold else "X"

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": production_model,
            "window_days": WINDOW_DAYS,
            "threshold": threshold,
            "trained_through": dataframe[DATE_COLUMN].max().strftime("%Y-%m-%d"),
            "feature_columns": features.columns.tolist(),
        },
        MODEL_PATH,
    )
    pd.DataFrame(
        [
            {
                "forecast_date": next_date.strftime("%Y-%m-%d"),
                "risk_score": latest_score,
                "prediction": latest_prediction,
            }
        ]
    ).to_csv(
        FORECAST_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
        float_format="%.6f",
    )

    config = {
        "window_days": WINDOW_DAYS,
        "target": TARGET_COLUMN,
        "tuning_train_years": [2019, TUNING_TRAIN_END_YEAR],
        "validation_year": VALIDATION_YEAR,
        "test_year": TEST_YEAR,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "production_model_trained_through": dataframe[DATE_COLUMN]
        .max()
        .strftime("%Y-%m-%d"),
        "latest_forecast": {
            "date": next_date.strftime("%Y-%m-%d"),
            "risk_score": latest_score,
            "prediction": latest_prediction,
        },
    }
    with CONFIG_PATH.open("w", encoding="utf-8") as config_file:
        json.dump(config, config_file, ensure_ascii=False, indent=2)

    print(f"Validation metrics ({VALIDATION_YEAR}): {validation_metrics}")
    print(f"Test metrics ({TEST_YEAR}): {test_metrics}")
    print(
        f"Latest forecast ({next_date.date()}): "
        f"risk_score={latest_score:.6f}, prediction={latest_prediction}"
    )
    print(f"Saved model: {MODEL_PATH}")
    return config


if __name__ == "__main__":
    train_and_evaluate()
