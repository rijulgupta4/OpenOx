from __future__ import annotations

import json
import os
from pathlib import Path

os.environ["MKL_THREADING_LAYER"] = "SEQUENTIAL"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score

from bold_external_validation import calibration_intercept, calibration_slope, sha256


ROOT = Path(r".")
OUT = ROOT / "bold_spo2_baseline_validation"


def run_qa() -> dict:
    predictions = pd.read_csv(OUT / "bold_baseline_predictions.csv.gz")
    performance = pd.read_csv(OUT / "bold_baseline_performance.csv")
    comparison = pd.read_csv(OUT / "bold_baseline_vs_compact.csv")
    intervals = pd.read_csv(OUT / "bold_baseline_bootstrap_intervals.csv")
    differences = pd.read_csv(OUT / "bold_baseline_vs_compact_bootstrap_differences.csv")
    selection = pd.read_csv(OUT / "baseline_penalty_selection.csv")
    spec = json.loads((OUT / "openox_spo2_only_occult_ridge_v1_scoring_spec.json").read_text())
    lock = json.loads((OUT / "baseline_model_lock.json").read_text())
    audit = json.loads((OUT / "baseline_run_audit.json").read_text())
    manifest = pd.read_csv(OUT / "bold_baseline_artifact_manifest.csv")

    y = predictions["outcome"].to_numpy(dtype=int)
    baseline = predictions["baseline_predicted_risk"].to_numpy(dtype=float)
    compact = predictions["compact_predicted_risk"].to_numpy(dtype=float)
    pair = performance.loc[performance["weighting"].eq("pair")].set_index("model")

    independent = {
        "brier": brier_score_loss(y, baseline),
        "log_loss": log_loss(y, baseline, labels=[0, 1]),
        "pr_auc": average_precision_score(y, baseline),
        "roc_auc": roc_auc_score(y, baseline),
        "calibration_intercept": calibration_intercept(y, baseline),
        "calibration_slope": calibration_slope(y, baseline),
    }
    checks = {
        "prediction grain is unique by BOLD pair": predictions["pair_id"].is_unique,
        "expected BOLD denominator": len(predictions) == 11880,
        "expected BOLD participants": predictions["patient_id"].nunique() == 11441,
        "expected BOLD events": int(y.sum()) == 671,
        "baseline model has only saturation": spec["raw_feature_order"] == ["saturation"],
        "OpenOx-only penalty selection chose C=1": float(
            selection.loc[selection["selected_for_full_fit"], "C"].iloc[0]
        ) == 1.0,
        "lock precedes BOLD outcome load within run": audit[
            "model_lock_preceded_outcome_load_in_this_run"
        ] is True,
        "lock and scoring specification hashes agree": lock["scoring_spec_sha256"] == sha256(
            OUT / "openox_spo2_only_occult_ridge_v1_scoring_spec.json"
        ),
        "independent Brier agrees": np.isclose(
            independent["brier"], pair.loc["SpO2-only baseline", "brier"], atol=1e-12
        ),
        "independent log loss agrees": np.isclose(
            independent["log_loss"], pair.loc["SpO2-only baseline", "log_loss"], atol=1e-12
        ),
        "independent PR-AUC agrees": np.isclose(
            independent["pr_auc"], pair.loc["SpO2-only baseline", "pr_auc"], atol=1e-12
        ),
        "independent ROC-AUC agrees": np.isclose(
            independent["roc_auc"], pair.loc["SpO2-only baseline", "roc_auc"], atol=1e-12
        ),
        "independent calibration intercept agrees": np.isclose(
            independent["calibration_intercept"],
            pair.loc["SpO2-only baseline", "calibration_intercept"], atol=1e-10
        ),
        "independent calibration slope agrees": np.isclose(
            independent["calibration_slope"],
            pair.loc["SpO2-only baseline", "calibration_slope"], atol=1e-10
        ),
        "comparison contains all headline metrics": {
            "brier", "log_loss", "pr_auc", "roc_auc", "calibration_intercept",
            "calibration_slope", "mean_predicted"
        }.issubset(set(comparison["metric"])),
        "baseline bootstrap completed": intervals.loc[
            intervals["metric"].isin(["brier", "log_loss", "pr_auc", "roc_auc"]),
            "valid_bootstrap_replicates",
        ].eq(1000).all(),
        "paired difference bootstrap completed": differences.loc[
            differences["metric"].isin(["brier", "log_loss", "pr_auc", "roc_auc"]),
            "valid_bootstrap_replicates",
        ].eq(1000).all(),
    }

    manifest_checks = []
    for row in manifest.itertuples(index=False):
        path = Path(row.path)
        manifest_checks.append(path.exists() and sha256(path) == row.sha256)
    checks["all manifest artifacts exist and hash-match"] = all(manifest_checks)
    if not all(checks.values()):
        raise AssertionError({k: v for k, v in checks.items() if not v})

    output = pd.DataFrame({"check": checks.keys(), "pass": checks.values()})
    output.to_csv(OUT / "bold_baseline_independent_qa.csv", index=False)
    return {"checks": len(checks), "passed": int(sum(checks.values()))}


if __name__ == "__main__":
    print(json.dumps(run_qa(), indent=2))
