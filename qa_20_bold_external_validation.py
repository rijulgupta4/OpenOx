from pathlib import Path
import hashlib
import json

import numpy as np
import pandas as pd

from bold_external_validation import (
    OUTPUT_DIR, SPEC_PATH, calibration_intercept, calibration_slope,
    metric_bundle, weighted_average_precision, weighted_roc_auc,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


predictions = pd.read_csv(OUTPUT_DIR / "bold_external_predictions.csv.gz")
summary = json.loads((OUTPUT_DIR / "bold_external_summary.json").read_text(encoding="utf-8"))
support = pd.read_csv(OUTPUT_DIR / "bold_external_support.csv")
spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
manifest = pd.read_csv(OUTPUT_DIR / "bold_external_artifact_manifest.csv")

y = predictions["outcome"].to_numpy(dtype=int)
p = predictions["predicted_risk"].to_numpy(dtype=float)
recomputed = metric_bundle(y, p)

toy_y = np.array([1, 0, 1])
toy_p = np.array([0.9, 0.8, 0.7])
toy_auc_pairwise = np.mean([
    (positive > negative) + 0.5 * (positive == negative)
    for positive in toy_p[toy_y == 1]
    for negative in toy_p[toy_y == 0]
])

alpha = calibration_intercept(y, p)
lp = np.log(np.clip(p, 1e-8, 1 - 1e-8) / (1 - np.clip(p, 1e-8, 1 - 1e-8)))
alpha_residual = np.sum(y - 1 / (1 + np.exp(-(lp + alpha))))
slope = calibration_slope(y, p)
design = np.column_stack([np.ones(len(y)), lp])
# Refit the calibration intercept conditional on the independently recovered slope.
conditional_intercept = calibration_intercept(y, 1 / (1 + np.exp(-(slope * lp))))
calibration_score = design.T @ (
    y - 1 / (1 + np.exp(-(conditional_intercept + slope * lp)))
)

manifest_hashes_match = all(
    sha256(Path(row.path)) == row.sha256 for row in manifest.itertuples(index=False)
)

checks = {
    "eligible row count independently recovered": len(predictions) == 11880,
    "participant count independently recovered": predictions["patient_id"].nunique() == 11441,
    "event count independently recovered": int(y.sum()) == 671,
    "event-positive participant count independently recovered": (
        predictions.loc[predictions["outcome"].eq(1), "patient_id"].nunique() == 667
    ),
    "summary observed rate reproduces": np.isclose(summary["observed_rate"], y.mean(), atol=1e-14),
    "summary mean prediction reproduces": np.isclose(summary["mean_predicted"], p.mean(), atol=1e-14),
    "summary Brier score reproduces": np.isclose(summary["brier"], recomputed["brier"], atol=1e-14),
    "summary log loss reproduces": np.isclose(summary["log_loss"], recomputed["log_loss"], atol=1e-14),
    "summary PR-AUC reproduces": np.isclose(summary["pr_auc"], recomputed["pr_auc"], atol=1e-14),
    "summary ROC-AUC reproduces": np.isclose(summary["roc_auc"], recomputed["roc_auc"], atol=1e-14),
    "ROC-AUC agrees with direct pairwise toy calculation": np.isclose(
        weighted_roc_auc(toy_y, toy_p), toy_auc_pairwise, atol=1e-14
    ),
    "average precision agrees with hand-worked toy result": np.isclose(
        weighted_average_precision(toy_y, toy_p), (1 + 2 / 3) / 2, atol=1e-14
    ),
    "calibration intercept score equation closes": abs(alpha_residual) < 1e-8,
    "calibration slope score equations close": np.max(np.abs(calibration_score)) < 1e-6,
    "all saved artifact hashes match manifest": manifest_hashes_match,
    "MIMIC-III correctly fails threshold support": not bool(
        support.loc[(support.dimension == "source_db") & (support.group == "mimic_iii"), "threshold_support"].iloc[0]
    ),
    "MIMIC-IV correctly fails discrimination support": not bool(
        support.loc[(support.dimension == "source_db") & (support.group == "mimic_iv"), "calibration_discrimination_support"].iloc[0]
    ),
    "race and ethnicity are absent from predictors": "race_ethnicity" not in spec["raw_feature_order"],
    "all predictions are finite and bounded": np.isfinite(p).all() and ((p >= 0) & (p <= 1)).all(),
}
if not all(checks.values()):
    raise AssertionError({key: value for key, value in checks.items() if not value})

qa_path = OUTPUT_DIR / "bold_external_independent_qa.csv"
pd.DataFrame({"check": checks.keys(), "pass": checks.values()}).to_csv(qa_path, index=False)

artifact_paths = sorted(OUTPUT_DIR.glob("bold_*"))
manifest_rows = []
for path in artifact_paths:
    if path.name == "bold_external_artifact_manifest.csv":
        continue
    manifest_rows.append({
        "artifact": path.name, "path": str(path),
        "sha256": sha256(path), "bytes": path.stat().st_size,
    })
pd.DataFrame(manifest_rows).to_csv(
    OUTPUT_DIR / "bold_external_artifact_manifest.csv", index=False
)
print(pd.DataFrame({"check": checks.keys(), "pass": checks.values()}).to_string(index=False))
