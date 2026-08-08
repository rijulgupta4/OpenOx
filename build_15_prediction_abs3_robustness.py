from pathlib import Path
import subprocess
import sys

import nbformat


HERE = Path(__file__).resolve().parent
SOURCE_BUILDER = HERE / "build_13_prediction_baseline_compact_ridge.py"
SOURCE_NOTEBOOK = HERE / "13_prediction_baseline_compact_ridge.ipynb"
OUT = HERE / "15_prediction_abs3_robustness.ipynb"

# Regenerate the source notebook from its canonical builder, then apply a
# deliberately small set of audited transformations. This keeps the feature
# tiers, preprocessing, tuning grid, and frozen participant splits identical.
subprocess.run([sys.executable, str(SOURCE_BUILDER)], check=True)
nb = nbformat.read(SOURCE_NOTEBOOK, as_version=4)

replacements = {
    "# OpenOx prediction: baseline and compact ridge internal validation":
        "# OpenOx prediction robustness: absolute error ≥3 percentage points",
    "This notebook fits the first two authorized prediction models":
        "This notebook fits the same two authorized prediction models for the richer absolute-error robustness target",
    "- The outcome is SaO2 below 88%.":
        "- The outcome is `abs(SpO2 - SaO2) >= 3` percentage points.",
    "data[\"outcome\"] = (data[\"so2\"] < 88).astype(int)":
        "data[\"outcome\"] = ((data[\"saturation\"] - data[\"so2\"]).abs() >= 3).astype(int)",
    "prediction_internal_baseline_compact.png":
        "prediction_abs3_baseline_compact.png",
    "prediction_internal_oof_predictions.csv.gz":
        "prediction_abs3_oof_predictions.csv.gz",
    "prediction_internal_repeat_metrics.csv":
        "prediction_abs3_repeat_metrics.csv",
    "prediction_internal_threshold_metrics.csv":
        "prediction_abs3_threshold_metrics.csv",
    "prediction_internal_tuning.csv":
        "prediction_abs3_tuning.csv",
    "prediction_internal_fold_coefficients.csv.gz":
        "prediction_abs3_fold_coefficients.csv.gz",
    "prediction_internal_model_comparison.csv":
        "prediction_abs3_model_comparison.csv",
    "prediction_internal_calibration_bins.csv":
        "prediction_abs3_calibration_bins.csv",
    "prediction_internal_qa.csv":
        "prediction_abs3_qa.csv",
    "prediction_internal_metric_summary.csv":
        "prediction_abs3_metric_summary.csv",
    "prediction_internal_artifact_manifest.csv":
        "prediction_abs3_artifact_manifest.csv",
}

counts = {old: 0 for old in replacements}
for cell in nb.cells:
    source = cell.get("source", "")
    for old, new in replacements.items():
        if old in source:
            counts[old] += source.count(old)
            source = source.replace(old, new)
    cell["source"] = source

missing = [old for old, count in counts.items() if count == 0]
if missing:
    raise RuntimeError(f"Expected source text not found: {missing}")

nb.metadata["openox_analysis"] = {
    "target": "abs(SpO2 - SaO2) >= 3 percentage points",
    "role": "secondary richer-event robustness analysis",
    "resampling": "same frozen participant-grouped outer and inner assignments as primary model",
}
nbformat.write(nb, OUT)
print(OUT)
