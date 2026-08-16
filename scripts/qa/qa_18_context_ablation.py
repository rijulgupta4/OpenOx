"""Recompute selected context-ablation checks through a separate scripted path."""

from pathlib import Path
import hashlib
import json

import nbformat
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from src.paths import PROJECT_ROOT

PROJECT = PROJECT_ROOT
TABLES = PROJECT / "outputs" / "tables"
NOTEBOOK = PROJECT / "notebooks" / "18_prediction_context_ablation_utility.ipynb"
PREDICTIONS = TABLES / "prediction_context_ablation_oof_predictions.csv.gz"
POINT_CURVES = TABLES / "prediction_context_decision_curves.csv"
MANIFEST = TABLES / "prediction_context_ablation_artifact_manifest.csv"
DECISION = TABLES / "prediction_context_freeze_decision.csv"

COMPACT = "Compact transportable ridge"
FULL = "Full context"
THRESHOLDS = np.arange(0.02, 0.101, 0.01)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


predictions = pd.read_csv(PREDICTIONS)
assert predictions["model"].nunique() == 6
assert predictions.groupby(["model", "repeat"]).size().eq(6062).all()
assert predictions.groupby(
    ["model", "repeat", "pulse_row_id"]
).size().eq(1).all()

consensus = (
    predictions.groupby(
        ["model", "patient_id", "pulse_row_id", "outcome"], as_index=False
    )["predicted_risk"].mean()
)

independent_metrics = []
for model in [COMPACT, FULL]:
    current = consensus.loc[consensus["model"].eq(model)].copy()
    counts = current.groupby("patient_id")["pulse_row_id"].transform("size")
    weights = 1.0 / counts.to_numpy(float)
    y = current["outcome"].to_numpy()
    p = current["predicted_risk"].to_numpy()
    independent_metrics.append({
        "model": model,
        "participant_brier": brier_score_loss(y, p, sample_weight=weights),
        "participant_log_loss": log_loss(
            y, p, sample_weight=weights, labels=[0, 1]
        ),
    })
independent_metrics = pd.DataFrame(independent_metrics).set_index("model")

saved_curves = pd.read_csv(POINT_CURVES)
saved_participant = saved_curves.loc[
    saved_curves["weighting"].eq("participant")
].set_index(["model", "threshold"])["net_benefit"]

curve_checks = []
for model in [COMPACT, FULL]:
    current = consensus.loc[consensus["model"].eq(model)].copy()
    counts = current.groupby("patient_id")["pulse_row_id"].transform("size")
    weights = 1.0 / counts.to_numpy(float)
    y = current["outcome"].to_numpy()
    p = current["predicted_risk"].to_numpy()
    for threshold in THRESHOLDS:
        flagged = p >= threshold
        total = weights.sum()
        expected = (
            weights[(y == 1) & flagged].sum() / total
            - weights[(y == 0) & flagged].sum() / total
            * threshold / (1 - threshold)
        )
        saved_model = saved_participant.loc[model]
        saved = saved_model.iloc[
            np.argmin(np.abs(saved_model.index.to_numpy() - threshold))
        ]
        curve_checks.append(np.isclose(expected, saved, atol=1e-12))
assert all(curve_checks)

manifest = pd.read_csv(MANIFEST)
hash_checks = []
for row in manifest.itertuples(index=False):
    path = Path(row.path)
    hash_checks.append(path.exists() and sha256(path) == row.sha256)
assert all(hash_checks)

notebook = nbformat.read(NOTEBOOK, as_version=4)
errors = [
    output
    for cell in notebook.cells
    if cell.cell_type == "code"
    for output in cell.get("outputs", [])
    if output.get("output_type") == "error"
]
assert not errors
assert all(
    cell.get("execution_count") is not None
    for cell in notebook.cells
    if cell.cell_type == "code"
)

decision = pd.read_csv(DECISION).iloc[0]
assert bool(decision["probability_loss_gate"]) is False
assert bool(decision["decision_curve_gate"]) is True
assert bool(decision["prior_high_risk_subgroup_gate"]) is True
assert bool(decision["freeze_pass"]) is False

report = {
    "prediction_grain_verified": True,
    "participant_metrics": independent_metrics.reset_index().to_dict("records"),
    "all_point_decision_curves_recomputed": True,
    "manifest_hashes_verified": len(hash_checks),
    "notebook_error_outputs": len(errors),
    "saved_decision_reproduced": True,
}
print(json.dumps(report, indent=2))
