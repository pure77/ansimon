import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    roc_auc_score,
)

from train_xgboost import (
    DATE_COLUMN,
    REGION_COLUMN,
    TARGET_COLUMN,
    TEST_YEAR,
    load_data,
    make_features,
    select_year,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "xgboost_pipeline.joblib"
THRESHOLD_PATH = PROJECT_ROOT / "models" / "threshold.json"
ILLNESS_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "heat_illness.csv"
TEST_OUTPUT = PROJECT_ROOT / "outputs" / "test_predictions.csv"


def evaluate() -> None:
    pipeline = joblib.load(MODEL_PATH)
    with THRESHOLD_PATH.open(encoding="utf-8") as threshold_file:
        threshold = float(json.load(threshold_file)["threshold"])

    illness_data = pd.read_csv(ILLNESS_DATA_PATH, encoding="utf-8-sig")
    label_end_date = pd.to_datetime(illness_data["발생일자"], errors="raise").max()

    dataframe = load_data()
    test_data = select_year(dataframe, (TEST_YEAR,))
    test_data = test_data.loc[test_data[DATE_COLUMN] <= label_end_date].copy()
    if test_data.empty:
        raise ValueError(f"테스트 연도 {TEST_YEAR} 데이터가 없습니다.")

    actual = test_data[TARGET_COLUMN]
    if actual.nunique() < 2:
        raise ValueError("테스트 타깃에 O와 X가 모두 존재하지 않아 평가할 수 없습니다.")

    scores = pipeline.predict_proba(make_features(test_data))[:, 1]
    predictions = (scores >= threshold).astype("int8")

    result = test_data[[DATE_COLUMN, REGION_COLUMN]].copy()
    result["actual"] = actual.to_numpy()
    result["risk_score"] = scores
    result["prediction"] = predictions
    TEST_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(TEST_OUTPUT, index=False, encoding="utf-8-sig")

    print(f"Test year: {TEST_YEAR}")
    print(f"Label end date: {label_end_date.date()}")
    print(f"Threshold: {threshold:.4f}")
    print(f"ROC-AUC: {roc_auc_score(actual, scores):.4f}")
    print(f"PR-AUC: {average_precision_score(actual, scores):.4f}")
    print("Confusion matrix:")
    print(confusion_matrix(actual, predictions))
    print(
        classification_report(
            actual, predictions, target_names=["X", "O"], zero_division=0
        )
    )
    print(f"Saved test predictions: {TEST_OUTPUT}")


if __name__ == "__main__":
    evaluate()
