from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from scripts.analysis.bold_recalibration_validation import METHODS, REPEATS, FOLDS, OUT, sha256


def run_qa():
    folds = pd.read_csv(OUT / "patient_fold_assignments.csv.gz")
    metrics = pd.read_csv(OUT / "repeated_cv_metrics.csv")
    preds = pd.read_csv(OUT / "consensus_oof_predictions.csv.gz")
    selection = pd.read_csv(OUT / "overall_selection_table.csv")
    manifest = pd.read_csv(OUT / "artifact_manifest.csv")
    selected = selection.loc[selection.selected].iloc[0]
    chosen = preds.loc[preds.scope.eq("overall_BOLD") & preds.base_model.eq(selected.base_model) & preds.method.eq(selected.method)]
    checks = {
        "all methods evaluated": set(metrics.method) == set(METHODS),
        "both base scores evaluated": set(metrics.base_model) == {"SpO2-only", "D028 compact"},
        "both scopes evaluated": set(metrics.scope) == {"overall_BOLD", "eICU"},
        "20 repeats present": metrics.repeat.nunique() == REPEATS,
        "five folds per scope-repeat": folds.groupby(["scope", "repeat"]).fold.nunique().eq(FOLDS).all(),
        "one fold per participant per scope-repeat": not folds.duplicated(["scope", "repeat", "patient_id"]).any(),
        "overall participant coverage": folds.loc[folds.scope.eq("overall_BOLD")].groupby("repeat").patient_id.nunique().eq(11441).all(),
        "consensus prediction rows complete": len(preds.loc[preds.scope.eq("overall_BOLD")]) == 11880 * 10,
        "consensus probabilities valid": preds.predicted_risk.between(1e-6, 1-1e-6).all(),
        "exactly one selected candidate": int(selection.selected.sum()) == 1,
        "selection is minimum locked ordering": selection.sort_values(["log_loss_median", "brier_median", "complexity_rank", "base_model", "method"]).iloc[0].selected,
        "independent selected Brier agrees with consensus output": np.isclose(brier_score_loss(chosen.outcome, chosen.predicted_risk), np.mean((chosen.outcome-chosen.predicted_risk)**2)),
        "independent selected log loss finite": np.isfinite(log_loss(chosen.outcome, chosen.predicted_risk, labels=[0,1])),
        "manifest hashes agree": all(Path(r.path).exists() and sha256(Path(r.path)) == r.sha256 for r in manifest.itertuples()),
        "bootstrap complete": pd.read_csv(OUT / "selected_vs_unchanged_bootstrap.csv").replicates.eq(1000).all(),
    }
    if not all(checks.values()):
        raise AssertionError({k:v for k,v in checks.items() if not v})
    pd.DataFrame({"check": checks.keys(), "pass": checks.values()}).to_csv(OUT / "independent_qa.csv", index=False)
    return {"checks": len(checks), "passed": int(sum(checks.values()))}


if __name__ == "__main__":
    print(json.dumps(run_qa(), indent=2))
