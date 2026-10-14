import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import precision_recall_curve
from xgboost import XGBClassifier

from train_xgboost import (
    DATE_COLUMN,
    REGION_COLUMN,
    RANDOM_STATE,
    TARGET_COLUMN,
    TUNING_TRAIN_YEARS,
    VALIDATION_YEAR,
    build_preprocessor,
    load_data,
    make_features,
    select_year,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = PROJECT_ROOT / "models"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
BEST_CONFIG_PATH = MODEL_DIR / "best_config.json"
THRESHOLD_PATH = MODEL_DIR / "threshold.json"
TUNING_OUTPUT = OUTPUT_DIR / "tuning_results.csv"
REFINEMENT_OUTPUT = OUTPUT_DIR / "tuning_results_refined.csv"
VALIDATION_OUTPUT = OUTPUT_DIR / "validation_predictions.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="최소 Recall을 유지하는 XGBoost와 임계값 F1 최적화"
    )
    parser.add_argument("--trials", type=int, default=24)
    parser.add_argument("--refine", action="store_true")
    parser.add_argument("--min-recall", type=float, default=0.8)
    return parser.parse_args()


def log_uniform(rng: np.random.Generator, low: float, high: float) -> float:
    return float(np.exp(rng.uniform(np.log(low), np.log(high))))


def make_candidates(
    trials: int, positive_ratio: float, rng: np.random.Generator
) -> list[dict]:
    if trials < 2:
        raise ValueError("trials는 2 이상이어야 합니다.")

    imbalance_ratio = (1 - positive_ratio) / positive_ratio
    candidates = [
        {
            "n_estimators": 300,
            "learning_rate": 0.1,
            "max_depth": 6,
            "min_child_weight": 1.0,
            "subsample": 1.0,
            "colsample_bytree": 1.0,
            "gamma": 0.0,
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
            "scale_pos_weight": 1.0,
            "max_delta_step": 0,
            "max_bin": 256,
        },
        {
            "n_estimators": 300,
            "learning_rate": 0.05,
            "max_depth": 5,
            "min_child_weight": 3.0,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "gamma": 0.0,
            "reg_alpha": 0.0,
            "reg_lambda": 1.0,
            "scale_pos_weight": imbalance_ratio,
            "max_delta_step": 0,
            "max_bin": 256,
        },
    ]

    for _ in range(trials - len(candidates)):
        candidates.append(
            {
                "n_estimators": 300,
                "learning_rate": log_uniform(rng, 0.03, 0.2),
                "max_depth": int(rng.integers(3, 9)),
                "min_child_weight": log_uniform(rng, 0.5, 25.0),
                "subsample": float(rng.uniform(0.65, 1.0)),
                "colsample_bytree": float(rng.uniform(0.65, 1.0)),
                "gamma": float(rng.uniform(0.0, 5.0)),
                "reg_alpha": (
                    0.0 if rng.random() < 0.2 else log_uniform(rng, 0.001, 5.0)
                ),
                "reg_lambda": log_uniform(rng, 0.2, 20.0),
                "scale_pos_weight": log_uniform(rng, 1.0, imbalance_ratio),
                "max_delta_step": int(rng.choice([0, 1, 3, 5])),
                "max_bin": int(rng.choice([64, 128, 256])),
            }
        )
    return candidates


def make_refinement_candidates(
    trials: int, incumbent: dict, rng: np.random.Generator
) -> list[dict]:
    if trials < 1:
        raise ValueError("trials는 1 이상이어야 합니다.")

    center = incumbent.copy()
    center["n_estimators"] = 600
    candidates = [center]
    for _ in range(trials - 1):
        candidates.append(
            {
                "n_estimators": 600,
                "learning_rate": float(
                    np.clip(center["learning_rate"] * rng.uniform(0.6, 1.4), 0.03, 0.12)
                ),
                "max_depth": int(rng.integers(2, 6)),
                "min_child_weight": float(
                    np.clip(center["min_child_weight"] * rng.uniform(0.5, 2.0), 0.5, 25)
                ),
                "subsample": float(
                    np.clip(center["subsample"] + rng.uniform(-0.15, 0.15), 0.65, 1.0)
                ),
                "colsample_bytree": float(
                    np.clip(
                        center["colsample_bytree"] + rng.uniform(-0.1, 0.1),
                        0.65,
                        1.0,
                    )
                ),
                "gamma": float(
                    np.clip(center["gamma"] + rng.uniform(-2.0, 2.0), 0.0, 6.0)
                ),
                "reg_alpha": float(
                    np.clip(center["reg_alpha"] * log_uniform(rng, 0.25, 4.0), 0, 5)
                ),
                "reg_lambda": float(
                    np.clip(center["reg_lambda"] * rng.uniform(0.5, 2.0), 0.2, 20)
                ),
                "scale_pos_weight": float(
                    np.clip(
                        center["scale_pos_weight"] * rng.uniform(0.5, 2.0),
                        1.0,
                        20.0,
                    )
                ),
                "max_delta_step": int(rng.choice([0, 1, 3, 5])),
                "max_bin": int(rng.choice([128, 256])),
            }
        )
    return candidates


def best_f1(actual: pd.Series, scores: np.ndarray, min_recall: float) -> dict:
    precision, recall, thresholds = precision_recall_curve(actual, scores)
    denominator = precision[:-1] + recall[:-1]
    f1 = np.divide(
        2 * precision[:-1] * recall[:-1],
        denominator,
        out=np.zeros_like(denominator),
        where=denominator != 0,
    )
    eligible = recall[:-1] >= min_recall
    if not eligible.any():
        raise ValueError(f"Recall {min_recall:.2f} 이상인 임계값이 없습니다.")
    constrained_f1 = np.where(eligible, f1, -1.0)
    best_index = int(np.argmax(constrained_f1))
    return {
        "threshold": float(thresholds[best_index]),
        "precision": float(precision[best_index]),
        "recall": float(recall[best_index]),
        "f1": float(f1[best_index]),
    }


def tune(trials: int, min_recall: float, refine: bool = False) -> dict:
    if not 0 < min_recall <= 1:
        raise ValueError("min_recall은 0보다 크고 1 이하여야 합니다.")

    dataframe = load_data()
    train_data = select_year(dataframe, TUNING_TRAIN_YEARS)
    validation_data = select_year(dataframe, (VALIDATION_YEAR,))
    x_train = make_features(train_data)
    y_train = train_data[TARGET_COLUMN]
    x_validation = make_features(validation_data)
    y_validation = validation_data[TARGET_COLUMN]

    preprocessor = build_preprocessor(x_train)
    encoded_train = preprocessor.fit_transform(x_train)
    encoded_validation = preprocessor.transform(x_validation)
    rng = np.random.default_rng(RANDOM_STATE)
    if refine:
        if not BEST_CONFIG_PATH.exists():
            raise FileNotFoundError("1차 튜닝 결과가 없습니다.")
        with BEST_CONFIG_PATH.open(encoding="utf-8") as config_file:
            incumbent = json.load(config_file)["model_params"]
        candidates = make_refinement_candidates(trials, incumbent, rng)
    else:
        candidates = make_candidates(trials, float(y_train.mean()), rng)

    results = []
    best_result = None
    best_scores = None
    for trial, params in enumerate(candidates, start=1):
        model = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            early_stopping_rounds=30,
            random_state=RANDOM_STATE,
            n_jobs=-1,
            **params,
        )
        model.fit(
            encoded_train,
            y_train,
            eval_set=[(encoded_validation, y_validation)],
            verbose=False,
        )
        scores = model.predict_proba(encoded_validation)[:, 1]
        metrics = best_f1(y_validation, scores, min_recall)
        best_iteration = int(model.best_iteration) + 1
        result = {
            "trial": trial,
            **metrics,
            "best_iteration": best_iteration,
            **params,
        }
        results.append(result)

        if best_result is None or result["f1"] > best_result["f1"]:
            best_result = result
            best_scores = scores.copy()
        print(
            f"Trial {trial:03d}/{trials}: F1={metrics['f1']:.4f}, "
            f"P={metrics['precision']:.4f}, R={metrics['recall']:.4f}, "
            f"threshold={metrics['threshold']:.6f}, trees={best_iteration}"
        )

    results_frame = pd.DataFrame(results).sort_values("f1", ascending=False)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tuning_output = REFINEMENT_OUTPUT if refine else TUNING_OUTPUT
    results_frame.to_csv(tuning_output, index=False, encoding="utf-8-sig")

    model_param_names = candidates[0].keys()
    final_model_params = {
        name: best_result[name] for name in model_param_names if name != "n_estimators"
    }
    final_model_params["n_estimators"] = best_result["best_iteration"]
    config = {
        "tuning_train_years": list(TUNING_TRAIN_YEARS),
        "validation_year": VALIDATION_YEAR,
        "trials": trials,
        "search_stage": "refinement" if refine else "initial",
        "min_recall": min_recall,
        "threshold": best_result["threshold"],
        "validation_metrics": {
            "precision": best_result["precision"],
            "recall": best_result["recall"],
            "f1": best_result["f1"],
        },
        "model_params": final_model_params,
    }
    with BEST_CONFIG_PATH.open("w", encoding="utf-8") as config_file:
        json.dump(config, config_file, ensure_ascii=False, indent=2)
    with THRESHOLD_PATH.open("w", encoding="utf-8") as threshold_file:
        json.dump(
            {
                "threshold": best_result["threshold"],
                "validation_year": VALIDATION_YEAR,
                "selection_metric": "f1_with_min_recall",
                "min_recall": min_recall,
            },
            threshold_file,
            ensure_ascii=False,
            indent=2,
        )

    validation_result = validation_data[[DATE_COLUMN, REGION_COLUMN]].copy()
    validation_result["actual"] = y_validation.to_numpy()
    validation_result["risk_score"] = best_scores
    validation_result.to_csv(VALIDATION_OUTPUT, index=False, encoding="utf-8-sig")

    print("Best validation result:")
    print(f"Minimum recall constraint: {min_recall:.4f}")
    print(f"F1: {best_result['f1']:.4f}")
    print(f"Precision: {best_result['precision']:.4f}")
    print(f"Recall: {best_result['recall']:.4f}")
    print(f"Threshold: {best_result['threshold']:.6f}")
    print(f"Saved config: {BEST_CONFIG_PATH}")
    print(f"Saved all trials: {tuning_output}")
    return config


if __name__ == "__main__":
    arguments = parse_args()
    tune(arguments.trials, arguments.min_recall, arguments.refine)
