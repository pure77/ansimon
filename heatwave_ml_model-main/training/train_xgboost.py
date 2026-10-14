import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "heat_data.csv"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODEL_DIR / "xgboost_pipeline.joblib"
BEST_CONFIG_PATH = MODEL_DIR / "best_config.json"

DATE_COLUMN = "일시"
REGION_COLUMN = "지점"
TARGET_COLUMN = "온열질환자(노인)발생여부"
TUNING_TRAIN_YEARS = tuple(range(2019, 2024))
FINAL_TRAIN_YEARS = tuple(range(2019, 2025))
VALIDATION_YEAR = 2024
TEST_YEAR = 2025
RANDOM_STATE = 42


def load_data() -> pd.DataFrame:
    dataframe = pd.read_csv(DATA_PATH, encoding="utf-8-sig")
    dataframe[DATE_COLUMN] = pd.to_datetime(dataframe[DATE_COLUMN], errors="raise")

    target = dataframe[TARGET_COLUMN].astype("string").str.strip()
    invalid_target = target.notna() & ~target.isin(["O", "X"])
    if invalid_target.any():
        invalid_values = target.loc[invalid_target].drop_duplicates().tolist()
        raise ValueError(f"타깃 컬럼에 O/X 이외의 값이 있습니다: {invalid_values}")
    dataframe[TARGET_COLUMN] = target.map({"X": 0, "O": 1}).astype("int8")

    categorical_columns = dataframe.select_dtypes(include=["object", "string"]).columns
    for column in categorical_columns:
        dataframe[column] = (
            dataframe[column].astype("string").str.strip().replace("", pd.NA)
        )

    dataframe["폭염영향예보(단계)"] = dataframe["폭염영향예보(단계)"].fillna(
        "없음"
    )
    return dataframe.sort_values(DATE_COLUMN, kind="stable").reset_index(drop=True)


def make_features(dataframe: pd.DataFrame) -> pd.DataFrame:
    features = dataframe.drop(columns=TARGET_COLUMN).copy()
    features["월"] = features[DATE_COLUMN].dt.month
    features["연중일"] = features[DATE_COLUMN].dt.dayofyear
    return features.drop(columns=DATE_COLUMN)


def select_year(dataframe: pd.DataFrame, years: tuple[int, ...]) -> pd.DataFrame:
    return dataframe.loc[dataframe[DATE_COLUMN].dt.year.isin(years)].copy()


def build_preprocessor(x_train: pd.DataFrame) -> ColumnTransformer:
    categorical_columns = x_train.select_dtypes(
        include=["object", "string", "category"]
    ).columns.tolist()
    numeric_columns = x_train.columns.difference(categorical_columns).tolist()
    return ColumnTransformer(
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


def build_pipeline(x_train: pd.DataFrame, model_params: dict) -> Pipeline:
    model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        random_state=RANDOM_STATE,
        n_jobs=-1,
        **model_params,
    )
    return Pipeline(
        steps=[("preprocessor", build_preprocessor(x_train)), ("model", model)]
    )


def train() -> Pipeline:
    if not BEST_CONFIG_PATH.exists():
        raise FileNotFoundError(
            "최적 설정이 없습니다. 먼저 training/tune_threshold.py를 실행하세요."
        )

    with BEST_CONFIG_PATH.open(encoding="utf-8") as config_file:
        config = json.load(config_file)

    dataframe = load_data()
    train_data = select_year(dataframe, FINAL_TRAIN_YEARS)
    x_train = make_features(train_data)
    y_train = train_data[TARGET_COLUMN]

    pipeline = build_pipeline(x_train, config["model_params"])
    pipeline.fit(x_train, y_train)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    print(f"Final train years: {FINAL_TRAIN_YEARS[0]}-{FINAL_TRAIN_YEARS[-1]}")
    print(f"Final train rows: {len(train_data):,}")
    print(f"Validation best F1: {config['validation_metrics']['f1']:.4f}")
    print(f"Fixed threshold: {config['threshold']:.6f}")
    print(f"Saved final model: {MODEL_PATH}")
    return pipeline


if __name__ == "__main__":
    train()
