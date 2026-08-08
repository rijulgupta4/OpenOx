from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

os.environ["MKL_THREADING_LAYER"] = "SEQUENTIAL"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from bold_external_validation import metric_bundle, sha256


WORKSPACE = Path(r".")
OPENOX_ROOT = Path(r".")
BOLD_ROOT = Path(r"data\external\bold")
OUTPUT_DIR = WORKSPACE / "bold_spo2_baseline_validation"
COHORT_PATH = OPENOX_ROOT / "data" / "processed" / "analytic_cohort_180s.csv.gz"
TUNING_PATH = OPENOX_ROOT / "outputs" / "tables" / "prediction_internal_tuning.csv"
BOLD_CSV = BOLD_ROOT / "bold_dataset.csv"
COMPACT_PREDICTIONS_PATH = (
    WORKSPACE / "bold_external_validation" / "bold_external_predictions.csv.gz"
)

EXPECTED_BOLD_SHA256 = "342891ad85e118e7e57bb2ddeadeafce57e99e01d48175c08576bb3855bede44"
C_GRID = [0.01, 0.1, 1.0, 10.0]
RANDOM_STATE = 20260726
BOOTSTRAP_REPLICATES = 1000
BOOTSTRAP_SEED = 20260804


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def make_baseline_pipeline(C: float) -> Pipeline:
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scaler", StandardScaler()),
    ])
    preprocessing = ColumnTransformer(
        [("numeric", numeric, ["saturation"])], remainder="drop"
    )
    model = LogisticRegression(
        penalty="l2", C=C, solver="liblinear", max_iter=2000,
        random_state=RANDOM_STATE,
    )
    return Pipeline([("preprocess", preprocessing), ("model", model)])


def select_penalty(tuning: pd.DataFrame) -> pd.DataFrame:
    baseline = tuning.loc[tuning["model"].eq("SpO2-only baseline")].copy()
    if len(baseline) != 1000:
        raise AssertionError("Expected four penalties across 250 frozen baseline contexts")
    selection = (
        baseline.groupby("C")
        .agg(
            frozen_contexts=("inner_log_loss", "size"),
            mean_inner_log_loss=("inner_log_loss", "mean"),
            median_inner_log_loss=("inner_log_loss", "median"),
            mean_inner_brier=("inner_brier", "mean"),
            median_inner_brier=("inner_brier", "median"),
            fold_wins=("selected", "sum"),
        )
        .reset_index()
        .sort_values(
            ["mean_inner_log_loss", "mean_inner_brier", "C"],
            kind="mergesort",
        )
    )
    selection["selected_for_full_fit"] = False
    selection.loc[selection.index[0], "selected_for_full_fit"] = True
    return selection.sort_values("C").reset_index(drop=True)


def score_from_spec(frame: pd.DataFrame, spec: dict) -> np.ndarray:
    values = frame[["saturation"]].to_numpy(dtype=float)
    median = np.asarray(spec["preprocessing"]["numeric_imputer"]["statistics"])
    imputed = np.where(np.isnan(values), median, values)
    mean = np.asarray(spec["preprocessing"]["numeric_scaler"]["mean"])
    scale = np.asarray(spec["preprocessing"]["numeric_scaler"]["scale"])
    design = (imputed - mean) / scale
    linear = float(spec["intercept"]) + design @ np.asarray(spec["coefficients"])
    return 1.0 / (1.0 + np.exp(-np.clip(linear, -40, 40)))


def participant_weights(frame: pd.DataFrame) -> np.ndarray:
    counts = frame.groupby("patient_id")["patient_id"].transform("size")
    return 1.0 / counts.to_numpy(dtype=float)


def paired_bootstrap(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    subject_codes, subjects = pd.factorize(frame["patient_id"], sort=True)
    y = frame["outcome"].to_numpy(dtype=int)
    baseline = frame["baseline_predicted_risk"].to_numpy(dtype=float)
    compact = frame["compact_predicted_risk"].to_numpy(dtype=float)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    metric_names = [
        "observed_rate", "mean_predicted", "calibration_gap",
        "calibration_intercept", "calibration_slope", "brier", "log_loss",
        "pr_auc", "roc_auc", "sensitivity_5pct", "specificity_5pct",
        "ppv_5pct", "npv_5pct", "flagged_rate_5pct", "net_benefit_5pct",
        "net_benefit_minus_all_5pct",
    ]
    baseline_values = {name: [] for name in metric_names}
    difference_values = {name: [] for name in metric_names if name != "observed_rate"}

    for _ in range(BOOTSTRAP_REPLICATES):
        sampled = rng.multinomial(
            len(subjects), np.repeat(1 / len(subjects), len(subjects))
        )
        weights = sampled[subject_codes].astype(float)
        baseline_metrics = metric_bundle(y, baseline, weights, True)
        compact_metrics = metric_bundle(y, compact, weights, True)
        for name in metric_names:
            baseline_values[name].append(baseline_metrics[name])
        for name in difference_values:
            difference_values[name].append(
                baseline_metrics[name] - compact_metrics[name]
            )

    interval_rows = []
    for name, values in baseline_values.items():
        finite = np.asarray(values, dtype=float)
        finite = finite[np.isfinite(finite)]
        interval_rows.append({
            "metric": name,
            "lower_95": np.quantile(finite, 0.025) if len(finite) else np.nan,
            "upper_95": np.quantile(finite, 0.975) if len(finite) else np.nan,
            "valid_bootstrap_replicates": len(finite),
            "requested_bootstrap_replicates": BOOTSTRAP_REPLICATES,
        })

    difference_rows = []
    for name, values in difference_values.items():
        finite = np.asarray(values, dtype=float)
        finite = finite[np.isfinite(finite)]
        difference_rows.append({
            "metric": name,
            "difference": "SpO2-only baseline minus D028 compact",
            "lower_95": np.quantile(finite, 0.025) if len(finite) else np.nan,
            "upper_95": np.quantile(finite, 0.975) if len(finite) else np.nan,
            "valid_bootstrap_replicates": len(finite),
            "requested_bootstrap_replicates": BOOTSTRAP_REPLICATES,
        })
    return pd.DataFrame(interval_rows), pd.DataFrame(difference_rows)


def run_validation() -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # The model is derived entirely from previously frozen OpenOx artifacts.
    cohort = pd.read_csv(COHORT_PATH)
    development = cohort.loc[
        cohort["saturation"].between(92, 96, inclusive="both"),
        ["pulse_row_id", "patient_id", "saturation", "so2"],
    ].copy()
    development["outcome"] = (development["so2"] < 88).astype(int)
    tuning = pd.read_csv(TUNING_PATH)
    penalty_selection = select_penalty(tuning)
    selected_C = float(
        penalty_selection.loc[
            penalty_selection["selected_for_full_fit"], "C"
        ].iloc[0]
    )

    development_checks = {
        "6062 eligible OpenOx rows": len(development) == 6062,
        "261 OpenOx events": int(development["outcome"].sum()) == 261,
        "123 OpenOx participants": development["patient_id"].nunique() == 123,
        "38 event-positive OpenOx participants": development.loc[
            development["outcome"].eq(1), "patient_id"
        ].nunique() == 38,
        "selected C is 1.0": selected_C == 1.0,
        "all selection contexts are frozen OpenOx contexts": penalty_selection[
            "frozen_contexts"
        ].eq(250).all(),
    }
    if not all(development_checks.values()):
        raise AssertionError({k: v for k, v in development_checks.items() if not v})

    pipeline = make_baseline_pipeline(selected_C)
    pipeline.fit(development[["saturation"]], development["outcome"])
    apparent_risk = pipeline.predict_proba(development[["saturation"]])[:, 1]

    preprocess = pipeline.named_steps["preprocess"]
    numeric_pipe = preprocess.named_transformers_["numeric"]
    imputer = numeric_pipe.named_steps["imputer"]
    scaler = numeric_pipe.named_steps["scaler"]
    model = pipeline.named_steps["model"]
    feature_names = preprocess.get_feature_names_out().astype(str).tolist()

    model_path = OUTPUT_DIR / "openox_spo2_only_occult_ridge_v1.joblib"
    spec_path = OUTPUT_DIR / "openox_spo2_only_occult_ridge_v1_scoring_spec.json"
    joblib.dump(pipeline, model_path, compress=3)
    scoring_spec = {
        "name": "OpenOx SpO2-only occult ridge v1",
        "decision_id": "D034-diagnostic",
        "role": "post-validation diagnostic comparator; not a rescue model",
        "eligibility": {"saturation_min": 92, "saturation_max": 96, "inclusive": True},
        "outcome_definition_for_validation": "SaO2 < 88%",
        "raw_feature_order": ["saturation"],
        "selected_C": selected_C,
        "penalty_selection": (
            "minimum mean inner pooled log loss across 250 pre-existing frozen "
            "OpenOx baseline tuning contexts; mean Brier then smaller C tie-break"
        ),
        "estimator": {
            "class": "sklearn.linear_model.LogisticRegression",
            "penalty": "l2", "solver": "liblinear", "max_iter": 2000,
            "random_state": RANDOM_STATE,
        },
        "preprocessing": {
            "numeric_imputer": {
                "strategy": "median", "add_indicator": True,
                "statistics": imputer.statistics_.astype(float).tolist(),
                "indicator_feature_indices": (
                    imputer.indicator_.features_.astype(int).tolist()
                    if hasattr(imputer, "indicator_") else []
                ),
            },
            "numeric_scaler": {
                "mean": scaler.mean_.astype(float).tolist(),
                "scale": scaler.scale_.astype(float).tolist(),
            },
        },
        "transformed_feature_order": feature_names,
        "intercept": float(model.intercept_[0]),
        "coefficients": model.coef_[0].astype(float).tolist(),
        "claim_boundaries": {
            "chronology": (
                "Specified after the D028 BOLD result was known, using only the "
                "pre-existing OpenOx baseline model and frozen tuning artifacts."
            ),
            "interpretation": (
                "Diagnoses whether added compact predictors contributed to poor "
                "BOLD transport; it is not a second confirmatory validation."
            ),
            "ENCoDE": "Not scored because the eligible occult denominator has zero events.",
        },
    }
    write_json(spec_path, scoring_spec)

    lock_time = datetime.now(timezone.utc)
    model_lock = {
        "decision_id": "D034-diagnostic",
        "status": "locked for post-validation diagnostic scoring",
        "locked_at_utc": lock_time.isoformat(),
        "model": scoring_spec["name"],
        "development_rows": len(development),
        "development_events": int(development["outcome"].sum()),
        "development_participants": development["patient_id"].nunique(),
        "selected_C": selected_C,
        "model_sha256": sha256(model_path),
        "scoring_spec_sha256": sha256(spec_path),
        "outcome_access_rule": (
            "This run writes the model and lock before loading BOLD SaO2 or the "
            "prior D028 BOLD prediction artifact."
        ),
        "chronology_caveat": scoring_spec["claim_boundaries"]["chronology"],
    }
    lock_path = OUTPUT_DIR / "baseline_model_lock.json"
    write_json(lock_path, model_lock)
    penalty_selection.to_csv(OUTPUT_DIR / "baseline_penalty_selection.csv", index=False)
    pd.DataFrame({
        "transformed_feature": ["__intercept__"] + feature_names,
        "coefficient": [float(model.intercept_[0])] + model.coef_[0].astype(float).tolist(),
    }).to_csv(OUTPUT_DIR / "baseline_coefficients.csv", index=False)

    # External outcomes enter only after the diagnostic model lock above is durable.
    outcome_load_time = datetime.now(timezone.utc)
    if sha256(BOLD_CSV) != EXPECTED_BOLD_SHA256:
        raise AssertionError("BOLD source hash changed")
    bold = pd.read_csv(BOLD_CSV, usecols=[
        "unique_subject_id", "unique_hospital_admission_id", "source_db",
        "race_ethnicity", "SpO2", "SaO2",
    ])
    frame = bold.loc[bold["SpO2"].between(92, 96, inclusive="both")].copy()
    frame = frame.rename(columns={
        "unique_subject_id": "patient_id",
        "unique_hospital_admission_id": "pair_id",
        "SpO2": "saturation",
    })
    frame["outcome"] = (frame["SaO2"] < 88).astype(int)
    frame["baseline_predicted_risk"] = pipeline.predict_proba(
        frame[["saturation"]]
    )[:, 1]
    manual_risk = score_from_spec(frame, scoring_spec)

    compact = pd.read_csv(
        COMPACT_PREDICTIONS_PATH,
        usecols=["pair_id", "patient_id", "outcome", "predicted_risk"],
    ).rename(columns={"predicted_risk": "compact_predicted_risk"})
    frame = frame.merge(
        compact, on=["pair_id", "patient_id", "outcome"], how="left",
        validate="one_to_one",
    )

    external_checks = {
        "11880 eligible BOLD rows": len(frame) == 11880,
        "11441 BOLD participants": frame["patient_id"].nunique() == 11441,
        "671 BOLD events": int(frame["outcome"].sum()) == 671,
        "all D028 compact predictions joined": frame["compact_predicted_risk"].notna().all(),
        "serialized and manual baseline scores exactly agree": np.array_equal(
            frame["baseline_predicted_risk"].to_numpy(), manual_risk
        ),
        "baseline risks finite and bounded": np.isfinite(
            frame["baseline_predicted_risk"]
        ).all() and frame["baseline_predicted_risk"].between(0, 1).all(),
        "model lock precedes outcome load in this run": lock_time < outcome_load_time,
    }
    if not all(external_checks.values()):
        raise AssertionError({k: v for k, v in external_checks.items() if not v})

    performance_rows = []
    for weighting in ["pair", "participant_balanced"]:
        weights = None if weighting == "pair" else participant_weights(frame)
        for model_name, column in [
            ("SpO2-only baseline", "baseline_predicted_risk"),
            ("D028 compact", "compact_predicted_risk"),
        ]:
            result = metric_bundle(
                frame["outcome"].to_numpy(), frame[column].to_numpy(), weights, True
            )
            performance_rows.append({
                "model": model_name, "weighting": weighting, **result,
            })
    performance = pd.DataFrame(performance_rows)
    performance.to_csv(OUTPUT_DIR / "bold_baseline_performance.csv", index=False)

    pair_metrics = performance.loc[performance["weighting"].eq("pair")].set_index("model")
    comparison_rows = []
    preferred = {
        "mean_predicted": "closer to observed rate",
        "calibration_gap": "closer to zero",
        "calibration_intercept": "closer to zero",
        "calibration_slope": "closer to one",
        "brier": "lower",
        "log_loss": "lower",
        "pr_auc": "higher",
        "roc_auc": "higher",
        "sensitivity_5pct": "context-dependent",
        "specificity_5pct": "context-dependent",
        "ppv_5pct": "higher",
        "npv_5pct": "higher",
        "flagged_rate_5pct": "context-dependent",
        "net_benefit_5pct": "higher",
        "net_benefit_minus_all_5pct": "higher",
    }
    for metric, direction in preferred.items():
        baseline_value = float(pair_metrics.loc["SpO2-only baseline", metric])
        compact_value = float(pair_metrics.loc["D028 compact", metric])
        comparison_rows.append({
            "metric": metric,
            "SpO2_only_baseline": baseline_value,
            "D028_compact": compact_value,
            "baseline_minus_compact": baseline_value - compact_value,
            "preferred_direction": direction,
        })
    comparison = pd.DataFrame(comparison_rows)
    comparison.to_csv(OUTPUT_DIR / "bold_baseline_vs_compact.csv", index=False)

    baseline_intervals, difference_intervals = paired_bootstrap(frame)
    baseline_intervals.to_csv(
        OUTPUT_DIR / "bold_baseline_bootstrap_intervals.csv", index=False
    )
    difference_intervals.to_csv(
        OUTPUT_DIR / "bold_baseline_vs_compact_bootstrap_differences.csv", index=False
    )

    calibration_rows = []
    for model_name, column in [
        ("SpO2-only baseline", "baseline_predicted_risk"),
        ("D028 compact", "compact_predicted_risk"),
    ]:
        grouped = (
            frame.groupby("saturation")
            .agg(
                rows=("outcome", "size"),
                events=("outcome", "sum"),
                observed_rate=("outcome", "mean"),
                mean_predicted=(column, "mean"),
            )
            .reset_index()
        )
        grouped.insert(0, "model", model_name)
        calibration_rows.append(grouped)
    pd.concat(calibration_rows, ignore_index=True).to_csv(
        OUTPUT_DIR / "bold_baseline_calibration_by_spo2.csv", index=False
    )

    frame[[
        "pair_id", "patient_id", "source_db", "race_ethnicity", "saturation",
        "outcome", "baseline_predicted_risk", "compact_predicted_risk",
    ]].to_csv(
        OUTPUT_DIR / "bold_baseline_predictions.csv.gz",
        index=False, compression="gzip",
    )

    baseline_pair = pair_metrics.loc["SpO2-only baseline"]
    compact_pair = pair_metrics.loc["D028 compact"]
    summary = {
        "analysis_role": "post-validation diagnostic comparator",
        "eligible_rows": len(frame),
        "participants": frame["patient_id"].nunique(),
        "events": int(frame["outcome"].sum()),
        "observed_rate": float(baseline_pair["observed_rate"]),
        "selected_C": selected_C,
        "baseline_mean_predicted": float(baseline_pair["mean_predicted"]),
        "compact_mean_predicted": float(compact_pair["mean_predicted"]),
        "baseline_calibration_intercept": float(baseline_pair["calibration_intercept"]),
        "compact_calibration_intercept": float(compact_pair["calibration_intercept"]),
        "baseline_calibration_slope": float(baseline_pair["calibration_slope"]),
        "compact_calibration_slope": float(compact_pair["calibration_slope"]),
        "baseline_brier": float(baseline_pair["brier"]),
        "compact_brier": float(compact_pair["brier"]),
        "baseline_log_loss": float(baseline_pair["log_loss"]),
        "compact_log_loss": float(compact_pair["log_loss"]),
        "baseline_pr_auc": float(baseline_pair["pr_auc"]),
        "compact_pr_auc": float(compact_pair["pr_auc"]),
        "baseline_roc_auc": float(baseline_pair["roc_auc"]),
        "compact_roc_auc": float(compact_pair["roc_auc"]),
        "claim_boundary": scoring_spec["claim_boundaries"]["interpretation"],
    }
    write_json(OUTPUT_DIR / "bold_baseline_summary.json", summary)
    write_json(OUTPUT_DIR / "baseline_run_audit.json", {
        "model_locked_at_utc": lock_time.isoformat(),
        "bold_outcome_loaded_at_utc": outcome_load_time.isoformat(),
        "model_lock_preceded_outcome_load_in_this_run": lock_time < outcome_load_time,
        "chronology_caveat": scoring_spec["claim_boundaries"]["chronology"],
    })

    qa_checks = {**development_checks, **external_checks,
        "1000 participant bootstrap replicates requested": BOOTSTRAP_REPLICATES == 1000,
        "baseline-only feature contract": scoring_spec["raw_feature_order"] == ["saturation"],
        "BOLD SaO2 is not a predictor": "SaO2" not in scoring_spec["raw_feature_order"],
        "ENCoDE is explicitly not scored": "zero events" in scoring_spec[
            "claim_boundaries"
        ]["ENCoDE"],
    }
    pd.DataFrame({"check": qa_checks.keys(), "pass": qa_checks.values()}).to_csv(
        OUTPUT_DIR / "bold_baseline_qa.csv", index=False
    )

    manifest_rows = []
    for path in sorted(OUTPUT_DIR.iterdir()):
        if path.is_file() and path.name != "bold_baseline_artifact_manifest.csv":
            manifest_rows.append({
                "artifact": path.name, "path": str(path),
                "sha256": sha256(path), "bytes": path.stat().st_size,
            })
    pd.DataFrame(manifest_rows).to_csv(
        OUTPUT_DIR / "bold_baseline_artifact_manifest.csv", index=False
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(run_validation(), indent=2))
