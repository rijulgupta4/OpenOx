from pathlib import Path
import nbformat as nbf


OUT = Path(__file__).with_name("16_prediction_subgroup_audit.ipynb")
nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell(
"""# OpenOx prediction: device and measured-pigmentation subgroup audit

## tl;dr

This notebook performs the next prespecified internal-validation gate for the compact occult-hypoxemia model. It audits calibration, discrimination, sensitivity, and false-negative behavior across supported device/probe and measured-pigmentation groups. It does not tune a threshold, refit the prediction model, or treat sparse subgroup estimates as stable conclusions.
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Context & Methods

### Key assumptions

- Population and outcome remain restricted to SpO2 92-96% with SaO2 below 88%.
- The compact and SpO2-only predictions are the saved D022 out-of-fold predictions.
- The flag threshold is the prespecified 5% risk threshold.
- Forehead MST groups remain `1-4`, `5-7`, and `8-10`; emitter-site ITA remains continuous.
- Device identity is the locked normalized `device_probe_key`.
- Threshold reporting requires at least 100 readings, 10 events, 10 participants, and 5 event-positive participants.
- Calibration-slope and discrimination reporting additionally require at least 30 events and 10 event-positive participants.
- Repeat-level distributions are descriptive because repeats overlap. Participant-cluster bootstrap intervals use the repeated-OOF consensus risk and are labeled as such.
- Subgroup performance is an audit of the model, not evidence that pigmentation should be added as a predictor.
"""))

cells.append(nbf.v4.new_code_cell(
"""import os
os.environ["MKL_THREADING_LAYER"] = "SEQUENTIAL"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

from pathlib import Path
import hashlib
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from scipy.optimize import brentq
from scipy.special import expit, logit
from sklearn.metrics import average_precision_score, roc_auc_score
import statsmodels.api as sm

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
sns.set_theme(style="whitegrid")

PROJECT = Path(r".")
TABLES = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
PROCESSED = PROJECT / "data" / "processed"

COHORT_PATH = PROCESSED / "analytic_cohort_180s.csv.gz"
PIGMENT_PATH = PROCESSED / "pigmentation_covariates_by_pair.csv.gz"
PREDICTION_PATH = TABLES / "prediction_internal_oof_predictions.csv.gz"

MODELS = ["SpO2-only baseline", "Compact transportable ridge"]
MST_LEVELS = ["1-4", "5-7", "8-10"]
THRESHOLD = 0.05
THRESHOLD_SUPPORT = {
    "readings": 100, "events": 10, "participants": 10,
    "event_positive_participants": 5,
}
CALIBRATION_SUPPORT = {
    "events": 30, "event_positive_participants": 10, "nonevents": 100,
}
BOOTSTRAP_REPLICATES = 1000
BOOTSTRAP_SEED = 20260727
"""))

cells.append(nbf.v4.new_markdown_cell("## Data\n\n### 1. Load and reconcile the frozen prediction population"))
cells.append(nbf.v4.new_code_cell(
"""cohort = pd.read_csv(
    COHORT_PATH,
    usecols=["pulse_row_id", "patient_id", "device_probe_key", "saturation", "so2"],
)
pigment = pd.read_csv(
    PIGMENT_PATH,
    usecols=["pulse_row_id", "patient_id", "mst_group", "emitter_site_ita"],
)
predictions = pd.read_csv(PREDICTION_PATH)

assert cohort["pulse_row_id"].is_unique
assert pigment["pulse_row_id"].is_unique
assert set(predictions["model"].unique()) == set(MODELS)

eligible = cohort.loc[cohort["saturation"].between(92, 96)].copy()
eligible["outcome_rebuilt"] = eligible["so2"].lt(88).astype(int)
eligible = eligible.merge(
    pigment.drop(columns="patient_id"),
    on="pulse_row_id",
    how="left",
    validate="one_to_one",
)

analysis = predictions.merge(
    eligible[[
        "pulse_row_id", "patient_id", "device_probe_key", "mst_group",
        "emitter_site_ita", "outcome_rebuilt",
    ]],
    on=["pulse_row_id", "patient_id"],
    how="left",
    validate="many_to_one",
)

assert analysis["outcome_rebuilt"].notna().all()
assert analysis["outcome"].eq(analysis["outcome_rebuilt"]).all()
assert len(eligible) == 6062
assert eligible["outcome_rebuilt"].sum() == 261
assert eligible.loc[eligible["outcome_rebuilt"].eq(1), "patient_id"].nunique() == 38
assert len(analysis) == 6062 * 50 * 2

pd.DataFrame({
    "item": ["eligible readings", "events", "participants", "event-positive participants"],
    "value": [
        len(eligible), eligible["outcome_rebuilt"].sum(),
        eligible["patient_id"].nunique(),
        eligible.loc[eligible["outcome_rebuilt"].eq(1), "patient_id"].nunique(),
    ],
})
"""))

cells.append(nbf.v4.new_markdown_cell("### 2. Apply the prespecified support gates"))
cells.append(nbf.v4.new_code_cell(
"""def support_table(frame, dimension, group_col):
    rows = []
    for group, current in frame.groupby(group_col, dropna=False):
        group_label = "Missing" if pd.isna(group) else str(group)
        events = int(current["outcome_rebuilt"].sum())
        participants = int(current["patient_id"].nunique())
        positive_participants = int(
            current.loc[current["outcome_rebuilt"].eq(1), "patient_id"].nunique()
        )
        row = {
            "dimension": dimension,
            "group": group_label,
            "readings": len(current),
            "events": events,
            "nonevents": len(current) - events,
            "participants": participants,
            "event_positive_participants": positive_participants,
        }
        row["threshold_support"] = (
            row["readings"] >= THRESHOLD_SUPPORT["readings"]
            and row["events"] >= THRESHOLD_SUPPORT["events"]
            and row["participants"] >= THRESHOLD_SUPPORT["participants"]
            and row["event_positive_participants"]
                >= THRESHOLD_SUPPORT["event_positive_participants"]
        )
        row["calibration_support"] = (
            row["threshold_support"]
            and row["events"] >= CALIBRATION_SUPPORT["events"]
            and row["event_positive_participants"]
                >= CALIBRATION_SUPPORT["event_positive_participants"]
            and row["nonevents"] >= CALIBRATION_SUPPORT["nonevents"]
        )
        rows.append(row)
    return pd.DataFrame(rows)


device_support = support_table(eligible, "Device/probe", "device_probe_key")
mst_support = support_table(eligible, "Forehead MST", "mst_group")
support = pd.concat([device_support, mst_support], ignore_index=True)

eligible_devices = set(
    device_support.loc[device_support["threshold_support"], "group"]
)
eligible_mst = set(
    mst_support.loc[
        mst_support["threshold_support"] & mst_support["group"].isin(MST_LEVELS),
        "group",
    ]
)

support.sort_values(["dimension", "threshold_support", "events"], ascending=[True, False, False])
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Results

### 3. Compute repeat-level subgroup performance

Calibration-in-the-large is estimated as an intercept update with the predictions used as an offset. Calibration slope and ranking measures are withheld when the stricter event-support gate fails.
"""))

cells.append(nbf.v4.new_code_cell(
"""def weighted_mean(values, weights=None):
    values = np.asarray(values, dtype=float)
    if weights is None:
        return float(values.mean())
    return float(np.average(values, weights=np.asarray(weights, dtype=float)))


def calibration_intercept(y, p, weights=None):
    y = np.asarray(y, dtype=float)
    lp = logit(np.clip(np.asarray(p, dtype=float), 1e-8, 1 - 1e-8))
    w = np.ones(len(y)) if weights is None else np.asarray(weights, dtype=float)
    target = np.sum(w * y)
    return float(brentq(
        lambda alpha: np.sum(w * expit(alpha + lp)) - target, -30, 30
    ))


def calibration_slope(y, p, weights=None):
    y = np.asarray(y, dtype=float)
    lp = logit(np.clip(np.asarray(p, dtype=float), 1e-8, 1 - 1e-8))
    design = sm.add_constant(lp)
    fit = sm.GLM(
        y, design, family=sm.families.Binomial(), freq_weights=weights
    ).fit(maxiter=200, disp=0)
    return float(fit.params[1])


def metric_row(frame, threshold_support, calibration_support, weighting):
    y = frame["outcome"].to_numpy()
    p = frame["predicted_risk"].to_numpy()
    flagged = p >= THRESHOLD
    if weighting == "participant_balanced":
        counts = frame.groupby("patient_id")["pulse_row_id"].transform("size")
        weights = 1 / counts.to_numpy()
    else:
        weights = None
    observed = weighted_mean(y, weights)
    predicted = weighted_mean(p, weights)
    brier = weighted_mean((y - p) ** 2, weights)

    positive = y == 1
    negative = ~positive
    sensitivity = (
        weighted_mean(flagged[positive], None if weights is None else weights[positive])
        if positive.any() else np.nan
    )
    specificity = (
        weighted_mean(~flagged[negative], None if weights is None else weights[negative])
        if negative.any() else np.nan
    )
    flagged_weight = flagged.astype(float) if weights is None else weights * flagged
    unflagged_weight = (~flagged).astype(float) if weights is None else weights * (~flagged)
    ppv = (
        np.sum((y if weights is None else weights * y) * flagged) / np.sum(flagged_weight)
        if np.sum(flagged_weight) > 0 else np.nan
    )
    npv = (
        np.sum(((1 - y) if weights is None else weights * (1 - y)) * (~flagged))
        / np.sum(unflagged_weight)
        if np.sum(unflagged_weight) > 0 else np.nan
    )

    row = {
        "weighting": weighting,
        "observed_rate": observed,
        "mean_predicted": predicted,
        "calibration_gap": predicted - observed,
        "brier": brier,
        "sensitivity_5pct": sensitivity if threshold_support else np.nan,
        "false_negative_rate_5pct": 1 - sensitivity if threshold_support else np.nan,
        "specificity_5pct": specificity if threshold_support else np.nan,
        "ppv_5pct": ppv if threshold_support else np.nan,
        "npv_5pct": npv if threshold_support else np.nan,
        "calibration_intercept": (
            calibration_intercept(y, p, weights) if threshold_support else np.nan
        ),
        "calibration_slope": (
            calibration_slope(y, p, weights) if calibration_support else np.nan
        ),
        "pr_auc": (
            average_precision_score(y, p, sample_weight=weights)
            if calibration_support else np.nan
        ),
        "roc_auc": (
            roc_auc_score(y, p, sample_weight=weights)
            if calibration_support else np.nan
        ),
    }
    return row


support_lookup = support.set_index(["dimension", "group"]).to_dict("index")
repeat_rows = []
for model in MODELS:
    for repeat in sorted(analysis["repeat"].unique()):
        repeat_frame = analysis.loc[
            analysis["model"].eq(model) & analysis["repeat"].eq(repeat)
        ]
        for dimension, group_col, allowed in [
            ("Device/probe", "device_probe_key", eligible_devices),
            ("Forehead MST", "mst_group", eligible_mst),
        ]:
            for group in sorted(allowed):
                current = repeat_frame.loc[repeat_frame[group_col].astype(str).eq(group)]
                gate = support_lookup[(dimension, group)]
                for weighting in ["pair", "participant_balanced"]:
                    row = metric_row(
                        current, gate["threshold_support"],
                        gate["calibration_support"], weighting,
                    )
                    row.update({
                        "model": model, "repeat": repeat,
                        "dimension": dimension, "group": group,
                    })
                    repeat_rows.append(row)

repeat_metrics = pd.DataFrame(repeat_rows)
assert repeat_metrics.groupby(
    ["model", "dimension", "group", "weighting"]
).size().eq(50).all()

metric_columns = [
    "observed_rate", "mean_predicted", "calibration_gap", "brier",
    "sensitivity_5pct", "false_negative_rate_5pct", "specificity_5pct",
    "ppv_5pct", "npv_5pct", "calibration_intercept",
    "calibration_slope", "pr_auc", "roc_auc",
]
summary = (
    repeat_metrics.groupby(["model", "dimension", "group", "weighting"])[metric_columns]
    .agg(["median", lambda x: x.quantile(0.025), lambda x: x.quantile(0.975)])
)
summary.columns = [
    f"{metric}_{stat}" if stat == "median" else
    f"{metric}_{'p025' if stat == '<lambda_0>' else 'p975'}"
    for metric, stat in summary.columns
]
summary = summary.reset_index()
summary
"""))

cells.append(nbf.v4.new_markdown_cell(
"""### 4. Participant-cluster bootstrap the repeated-OOF consensus risks

The consensus risk is each reading's mean out-of-fold prediction across the 50 repeats. It is used only to obtain participant-cluster uncertainty for this audit; it is not a frozen deployable model.
"""))

cells.append(nbf.v4.new_code_cell(
"""consensus = (
    analysis.groupby(
        ["model", "patient_id", "pulse_row_id", "outcome", "device_probe_key", "mst_group"],
        as_index=False,
        dropna=False,
    )
    .agg(predicted_risk=("predicted_risk", "mean"))
)
assert consensus.groupby("model").size().eq(len(eligible)).all()

rng = np.random.default_rng(BOOTSTRAP_SEED)
patients = np.array(sorted(consensus["patient_id"].unique()))
bootstrap_rows = []

for replicate in range(BOOTSTRAP_REPLICATES):
    sampled = rng.choice(patients, size=len(patients), replace=True)
    sampled_parts = []
    for draw_id, patient in enumerate(sampled):
        part = consensus.loc[consensus["patient_id"].eq(patient)].copy()
        part["bootstrap_patient"] = draw_id
        sampled_parts.append(part)
    boot = pd.concat(sampled_parts, ignore_index=True)

    for model in MODELS:
        model_frame = boot.loc[boot["model"].eq(model)]
        for dimension, group_col, allowed in [
            ("Device/probe", "device_probe_key", eligible_devices),
            ("Forehead MST", "mst_group", eligible_mst),
        ]:
            for group in sorted(allowed):
                current = model_frame.loc[model_frame[group_col].astype(str).eq(group)]
                gate = support_lookup[(dimension, group)]
                has_both_outcomes = current["outcome"].nunique() == 2
                row = metric_row(
                    current,
                    has_both_outcomes,
                    has_both_outcomes and gate["calibration_support"],
                    "pair",
                )
                bootstrap_rows.append({
                    "replicate": replicate, "model": model,
                    "dimension": dimension, "group": group,
                    **{key: row[key] for key in metric_columns},
                })

bootstrap = pd.DataFrame(bootstrap_rows)
bootstrap_summary = (
    bootstrap.groupby(["model", "dimension", "group"])[metric_columns]
    .agg(["median", lambda x: x.quantile(0.025), lambda x: x.quantile(0.975)])
)
bootstrap_summary.columns = [
    f"{metric}_{stat}" if stat == "median" else
    f"{metric}_{'p025' if stat == '<lambda_0>' else 'p975'}"
    for metric, stat in bootstrap_summary.columns
]
bootstrap_summary = bootstrap_summary.reset_index()
bootstrap_summary
"""))

cells.append(nbf.v4.new_markdown_cell(
"""### 5. Test continuous emitter-site ITA for residual calibration

For each repeat and model, a participant-clustered logistic GEE estimates whether ITA remains associated with the outcome after using the model logit as an offset. The ITA coefficient is reported per 10-degree increase. This is a residual-calibration audit, not a feature-selection test.
"""))

cells.append(nbf.v4.new_code_cell(
"""ita_rows = []
for model in MODELS:
    for repeat in sorted(analysis["repeat"].unique()):
        current = analysis.loc[
            analysis["model"].eq(model)
            & analysis["repeat"].eq(repeat)
            & analysis["emitter_site_ita"].notna()
        ].copy()
        current["ita_10_centered"] = (
            current["emitter_site_ita"] - current["emitter_site_ita"].median()
        ) / 10
        offset = logit(np.clip(current["predicted_risk"], 1e-8, 1 - 1e-8))
        design = sm.add_constant(current[["ita_10_centered"]])
        try:
            fit = sm.GEE(
                current["outcome"], design, groups=current["patient_id"],
                family=sm.families.Binomial(), offset=offset,
            ).fit(maxiter=200)
            coefficient = float(fit.params["ita_10_centered"])
            standard_error = float(fit.bse["ita_10_centered"])
            converged = bool(getattr(fit, "converged", True))
        except Exception:
            coefficient, standard_error, converged = np.nan, np.nan, False
        ita_rows.append({
            "model": model, "repeat": repeat,
            "readings": len(current),
            "participants": current["patient_id"].nunique(),
            "events": int(current["outcome"].sum()),
            "event_positive_participants": current.loc[
                current["outcome"].eq(1), "patient_id"
            ].nunique(),
            "ita_span": current["emitter_site_ita"].max() - current["emitter_site_ita"].min(),
            "log_odds_per_10_ita": coefficient,
            "robust_se": standard_error,
            "odds_ratio_per_10_ita": np.exp(coefficient),
            "converged": converged,
        })

ita_residual = pd.DataFrame(ita_rows)
assert ita_residual["converged"].all()
ita_summary = (
    ita_residual.groupby("model")
    .agg(
        repeats=("repeat", "size"),
        readings=("readings", "median"),
        participants=("participants", "median"),
        events=("events", "median"),
        positive_participants=("event_positive_participants", "median"),
        ita_span=("ita_span", "median"),
        log_odds_median=("log_odds_per_10_ita", "median"),
        log_odds_p025=("log_odds_per_10_ita", lambda x: x.quantile(0.025)),
        log_odds_p975=("log_odds_per_10_ita", lambda x: x.quantile(0.975)),
        odds_ratio_median=("odds_ratio_per_10_ita", "median"),
    )
    .reset_index()
)
ita_summary
"""))

cells.append(nbf.v4.new_markdown_cell("### 6. Compare compact and baseline subgroup behavior"))
cells.append(nbf.v4.new_code_cell(
"""pair_summary = summary.loc[summary["weighting"].eq("pair")].copy()
comparison = pair_summary.pivot(
    index=["dimension", "group"], columns="model"
)
comparison.columns = [f"{metric}__{model}" for metric, model in comparison.columns]
comparison = comparison.reset_index()

for metric in [
    "brier_median", "calibration_gap_median", "sensitivity_5pct_median",
    "false_negative_rate_5pct_median", "pr_auc_median", "roc_auc_median",
]:
    compact_col = f"{metric}__Compact transportable ridge"
    baseline_col = f"{metric}__SpO2-only baseline"
    if compact_col in comparison and baseline_col in comparison:
        comparison[f"delta_{metric}_compact_minus_baseline"] = (
            comparison[compact_col] - comparison[baseline_col]
        )

comparison
"""))

cells.append(nbf.v4.new_markdown_cell("### 7. Visualize calibration and false-negative behavior"))
cells.append(nbf.v4.new_code_cell(
"""compact_boot = bootstrap_summary.loc[
    bootstrap_summary["model"].eq("Compact transportable ridge")
].copy()
model_boot = bootstrap_summary.copy()

fig, axes = plt.subplots(2, 2, figsize=(13, 10))

def interval_panel(ax, data, dimension, metric, title, x_label, reference=None):
    current = data.loc[data["dimension"].eq(dimension)].copy()
    order = current.sort_values(f"{metric}_median")["group"].tolist()
    current["group"] = pd.Categorical(current["group"], categories=order, ordered=True)
    current = current.sort_values("group")
    y = np.arange(len(current))
    ax.errorbar(
        current[f"{metric}_median"], y,
        xerr=[
            current[f"{metric}_median"] - current[f"{metric}_p025"],
            current[f"{metric}_p975"] - current[f"{metric}_median"],
        ],
        fmt="o", color="#1f5a85", ecolor="#8fb6d8", capsize=3,
    )
    if reference is not None:
        ax.axvline(reference, color="#555555", linestyle="--", linewidth=1)
    ax.set_yticks(y, current["group"])
    ax.set_title(title)
    ax.set_xlabel(x_label)


interval_panel(
    axes[0, 0], compact_boot, "Forehead MST", "calibration_gap",
    "Compact model calibration gap by forehead MST",
    "Mean predicted risk minus observed rate", reference=0,
)
interval_panel(
    axes[0, 1], compact_boot, "Device/probe", "calibration_gap",
    "Compact model calibration gap by supported device/probe",
    "Mean predicted risk minus observed rate", reference=0,
)

threshold_plot = model_boot.copy()
threshold_plot["label"] = threshold_plot["model"].map({
    "SpO2-only baseline": "SpO2-only",
    "Compact transportable ridge": "Compact",
})
for ax, dimension, title in [
    (axes[1, 0], "Forehead MST", "Sensitivity at the fixed 5% threshold by MST"),
    (axes[1, 1], "Device/probe", "Sensitivity at the fixed 5% threshold by device/probe"),
]:
    current = threshold_plot.loc[threshold_plot["dimension"].eq(dimension)].copy()
    groups = sorted(current["group"].unique())
    positions = np.arange(len(groups))
    for offset, (model, color) in zip(
        [-0.12, 0.12],
        [("SpO2-only baseline", "#d4864a"), ("Compact transportable ridge", "#2f7f72")],
    ):
        part = current.loc[current["model"].eq(model)].set_index("group").loc[groups]
        ax.errorbar(
            part["sensitivity_5pct_median"], positions + offset,
            xerr=[
                part["sensitivity_5pct_median"] - part["sensitivity_5pct_p025"],
                part["sensitivity_5pct_p975"] - part["sensitivity_5pct_median"],
            ],
            fmt="o", color=color, ecolor=color, alpha=0.9, capsize=3,
            label="Compact" if "Compact" in model else "SpO2-only",
        )
    ax.set_yticks(positions, groups)
    # Preserve the full marker and interval when sensitivity is exactly 0 or 1.
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel("Sensitivity (1 - false-negative rate)")
    ax.set_title(title)
    ax.legend(frameon=False)

fig.suptitle(
    "OpenOx occult-hypoxemia prediction subgroup audit\\n"
    "Repeated-OOF consensus risks; participant-cluster bootstrap 95% intervals",
    fontsize=14, fontweight="bold",
)
fig.tight_layout(rect=[0, 0, 1, 0.95])
figure_path = FIGURES / "prediction_subgroup_audit.png"
fig.savefig(figure_path, dpi=180, bbox_inches="tight")
plt.show()
"""))

cells.append(nbf.v4.new_markdown_cell("### 8. Save audited outputs and artifact hashes"))
cells.append(nbf.v4.new_code_cell(
"""qa = {
    "eligible population is 6,062 readings": len(eligible) == 6062,
    "outcome has 261 events": eligible["outcome_rebuilt"].sum() == 261,
    "outcome has 38 positive participants": (
        eligible.loc[eligible["outcome_rebuilt"].eq(1), "patient_id"].nunique() == 38
    ),
    "prediction join is complete": len(analysis) == 6062 * 50 * 2,
    "outcomes reconstruct exactly": analysis["outcome"].eq(analysis["outcome_rebuilt"]).all(),
    "MST categories are prespecified": eligible_mst.issubset(set(MST_LEVELS)),
    "repeat metrics complete": repeat_metrics.groupby(
        ["model", "dimension", "group", "weighting"]
    ).size().eq(50).all(),
    "every bootstrap subgroup has 1,000 replicates": bootstrap.groupby(
        ["model", "dimension", "group"]
    )["replicate"].nunique().eq(1000).all(),
    "ITA GEE fits all converged": ita_residual["converged"].all(),
    "reported risks are bounded": analysis["predicted_risk"].between(0, 1).all(),
}
assert all(qa.values())

paths = {
    "support": TABLES / "prediction_subgroup_support.csv",
    "repeat_metrics": TABLES / "prediction_subgroup_repeat_metrics.csv.gz",
    "summary": TABLES / "prediction_subgroup_summary.csv",
    "cluster_bootstrap": TABLES / "prediction_subgroup_cluster_bootstrap.csv.gz",
    "bootstrap_summary": TABLES / "prediction_subgroup_bootstrap_summary.csv",
    "ita_residual": TABLES / "prediction_subgroup_ita_residual_calibration.csv",
    "ita_summary": TABLES / "prediction_subgroup_ita_summary.csv",
    "comparison": TABLES / "prediction_subgroup_model_comparison.csv",
    "qa": TABLES / "prediction_subgroup_qa.csv",
}

support.to_csv(paths["support"], index=False)
repeat_metrics.to_csv(paths["repeat_metrics"], index=False, compression="gzip")
summary.to_csv(paths["summary"], index=False)
bootstrap.to_csv(paths["cluster_bootstrap"], index=False, compression="gzip")
bootstrap_summary.to_csv(paths["bootstrap_summary"], index=False)
ita_residual.to_csv(paths["ita_residual"], index=False)
ita_summary.to_csv(paths["ita_summary"], index=False)
comparison.to_csv(paths["comparison"], index=False)
pd.DataFrame({"check": qa.keys(), "pass": qa.values()}).to_csv(paths["qa"], index=False)

def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

manifest_rows = [
    {"artifact": key, "path": str(path.relative_to(PROJECT)), "sha256": sha256(path)}
    for key, path in paths.items()
]
manifest_rows.append({
    "artifact": "figure", "path": str(figure_path.relative_to(PROJECT)),
    "sha256": sha256(figure_path),
})
artifact_manifest = pd.DataFrame(manifest_rows)
artifact_manifest.to_csv(
    TABLES / "prediction_subgroup_artifact_manifest.csv", index=False
)

pd.DataFrame({"check": qa.keys(), "pass": qa.values()})
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Takeaways

- Interpret only groups that pass the prespecified support gate.
- Compare calibration and false-negative behavior separately; one cannot substitute for the other.
- Participant-cluster bootstrap intervals quantify uncertainty for the repeated-OOF consensus audit but do not turn the consensus into a deployable model.
- Continuous ITA residual calibration is a model audit, not evidence for adding pigmentation as a predictor.
- Any subgroup concern must be carried into enrichment testing and external transportability rather than repaired by post hoc threshold selection.
"""))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {
        "display_name": "Python (openox)", "language": "python", "name": "python3"
    },
    "language_info": {"name": "python", "version": "3"},
    "openox_analysis": {
        "stage": "secondary predictive modeling",
        "gate": "device and measured-pigmentation subgroup audit",
        "threshold": 0.05,
    },
}
nbf.write(nb, OUT)
print(OUT)
