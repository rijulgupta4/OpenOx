from pathlib import Path

import nbformat as nbf


OUT = Path(r".\notebooks\17_prediction_enrichment_blocks.ipynb")
nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell(
"""# OpenOx prediction: incremental enrichment blocks

## tl;dr

This notebook tests three prespecified OpenOx-only additions to the compact occult-hypoxemia model: device/probe identity, directly measured pigmentation, and perfusion/physiologic context. Each block is evaluated separately under the frozen participant-level nested validation allocation. The saved compact-model predictions are reused as the paired reference; no external data, post hoc threshold, or unrestricted full model is used.

## Context & Methods

### Key Assumptions

- The population remains readings with SpO2 92-96%; the outcome remains SaO2 below 88%.
- The compact reference remains SpO2, age, assigned sex, heart rate, and respiratory rate.
- Device identity is high-cardinality, so categories below 2% of an outer-training sample are grouped inside that training fold.
- Pigmentation and device blocks are deliberately separate. Predictive feature value is not the same question as disparate device performance.
- Native perfusion-index scales are not pooled. The context block uses the existing within-device robust standardization of log2 PI.
- The fixed 5% threshold is audited but never optimized here.
"""))

cells.append(nbf.v4.new_code_cell(
"""from pathlib import Path
import hashlib
import json
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from sklearn.compose import ColumnTransformer
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, confusion_matrix,
    log_loss, roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore")
sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", 100)

PROJECT = Path(r".")
TABLES = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
PROCESSED = PROJECT / "data" / "processed"

COHORT_PATH = PROCESSED / "analytic_cohort_180s.csv.gz"
PIGMENT_PATH = PROCESSED / "pigmentation_covariates_by_pair.csv.gz"
CONTEXT_PATH = PROCESSED / "context_covariates_by_pair.csv.gz"
OUTER_PATH = TABLES / "prediction_outer_fold_assignments.csv.gz"
INNER_PATH = TABLES / "prediction_inner_fold_assignments.csv.gz"
COMPACT_PATH = TABLES / "prediction_internal_oof_predictions.csv.gz"

C_GRID = [0.01, 0.1, 1.0, 10.0]
THRESHOLD = 0.05
BOOTSTRAPS = 1000
SEED = 20260727
COMPACT = "Compact transportable ridge"

BASE_NUMERIC = ["saturation", "age_at_encounter", "heart_rate_consensus", "RR"]
BASE_CATEGORICAL = ["assigned_sex_normalized"]
MODEL_SPECS = {
    "Device block ridge": {
        "numeric": BASE_NUMERIC,
        "categorical": BASE_CATEGORICAL,
        "high_cardinality": ["device_probe_key"],
    },
    "Pigmentation block ridge": {
        "numeric": BASE_NUMERIC + ["emitter_site_ita"],
        "categorical": BASE_CATEGORICAL + ["mst_group"],
        "high_cardinality": [],
    },
    "Perfusion/context block ridge": {
        "numeric": BASE_NUMERIC + ["finger_diameter"],
        "categorical": BASE_CATEGORICAL + ["warming"],
        "high_cardinality": [],
        "within_device_pi": ["log2_pi", "device_probe_key"],
    },
}
"""))

cells.append(nbf.v4.new_markdown_cell("## Data\n\n### 1. Load the frozen population and feature maps"))
cells.append(nbf.v4.new_code_cell(
"""cohort = pd.read_csv(COHORT_PATH)
pigment = pd.read_csv(
    PIGMENT_PATH,
    usecols=["pulse_row_id", "mst_group", "emitter_site_ita"],
)
context = pd.read_csv(
    CONTEXT_PATH,
    usecols=[
        "pulse_row_id", "age_at_encounter", "assigned_sex_normalized",
        "heart_rate_consensus", "RR", "log2_pi",
        "warming", "finger_diameter",
    ],
)
assert cohort["pulse_row_id"].is_unique
assert pigment["pulse_row_id"].is_unique
assert context["pulse_row_id"].is_unique

data = (
    cohort.merge(pigment, on="pulse_row_id", how="left", validate="one_to_one")
    .merge(context, on="pulse_row_id", how="left", validate="one_to_one")
)
data = data.loc[data["saturation"].between(92, 96, inclusive="both")].copy()
data["outcome"] = (data["so2"] < 88).astype(int)
for categorical_column in [
    "assigned_sex_normalized", "device_probe_key", "mst_group", "warming"
]:
    data[categorical_column] = (
        data[categorical_column].astype("string").fillna("Missing").astype(str)
    )

outer = pd.read_csv(OUTER_PATH)
inner = pd.read_csv(INNER_PATH)
compact_predictions = pd.read_csv(COMPACT_PATH)
compact_predictions = compact_predictions.loc[
    compact_predictions["model"].eq(COMPACT)
].copy()

feature_lock = pd.DataFrame([
    {
        "model": model,
        "incremental_block": (
            ", ".join(spec["high_cardinality"] + spec.get("within_device_pi", []) + [
                col for col in spec["numeric"] + spec["categorical"]
                if col not in BASE_NUMERIC + BASE_CATEGORICAL
            ])
        ),
        "reference": COMPACT,
        "role": "Exploratory OpenOx-only incremental value",
    }
    for model, spec in MODEL_SPECS.items()
])
feature_lock.to_csv(TABLES / "prediction_enrichment_block_lock.csv", index=False)

coverage_columns = sorted(set(
    sum((s["numeric"] + s["categorical"] + s["high_cardinality"]
         + s.get("within_device_pi", [])
         for s in MODEL_SPECS.values()), [])
))
coverage = data[coverage_columns].notna().mean().mul(100).rename("coverage_pct")

summary = pd.DataFrame({
    "item": ["eligible readings", "events", "participants",
             "event-positive participants", "device/probe levels"],
    "value": [len(data), int(data["outcome"].sum()), data["patient_id"].nunique(),
              data.loc[data["outcome"].eq(1), "patient_id"].nunique(),
              data["device_probe_key"].nunique()],
})
summary, coverage.to_frame(), feature_lock
"""))

cells.append(nbf.v4.new_markdown_cell("### 2. Verify the frozen assignments and compact reference"))
cells.append(nbf.v4.new_code_cell(
"""input_checks = {
    "6,062 eligible readings": len(data) == 6062,
    "261 events": int(data["outcome"].sum()) == 261,
    "38 event-positive participants": (
        data.loc[data["outcome"].eq(1), "patient_id"].nunique() == 38
    ),
    "participants match outer allocation": set(data["patient_id"]) == set(outer["patient_id"]),
    "50 by 5 outer allocation": (
        outer["repeat"].nunique() == 50
        and outer.groupby("repeat")["fold"].nunique().eq(5).all()
    ),
    "four inner folds per outer training set": (
        inner.groupby(["repeat", "outer_fold"])["inner_fold"].nunique().eq(4).all()
    ),
    "compact prediction count": len(compact_predictions) == len(data) * 50,
    "compact outcomes reconstruct": (
        compact_predictions.merge(
            data[["pulse_row_id", "outcome"]],
            on="pulse_row_id", suffixes=("_saved", "_source"),
            validate="many_to_one",
        ).eval("outcome_saved == outcome_source").all()
    ),
}
assert all(input_checks.values())
pd.DataFrame({"check": input_checks.keys(), "pass": input_checks.values()})
"""))

cells.append(nbf.v4.new_markdown_cell("## Results\n\n### 3. Define fold-contained pipelines and metrics"))
cells.append(nbf.v4.new_code_cell(
"""class WithinDeviceIQRScaler(BaseEstimator, TransformerMixin):
    def fit(self, X, y=None):
        frame = pd.DataFrame(X, columns=["log2_pi", "device_probe_key"]).copy()
        frame["log2_pi"] = pd.to_numeric(frame["log2_pi"], errors="coerce")
        stats = frame.groupby("device_probe_key")["log2_pi"].agg(
            median="median",
            q25=lambda x: x.quantile(0.25),
            q75=lambda x: x.quantile(0.75),
        )
        stats["iqr"] = stats["q75"] - stats["q25"]
        self.medians_ = stats["median"].to_dict()
        self.iqrs_ = stats["iqr"].where(stats["iqr"] > 0).to_dict()
        self.global_median_ = frame["log2_pi"].median()
        global_iqr = frame["log2_pi"].quantile(0.75) - frame["log2_pi"].quantile(0.25)
        self.global_iqr_ = global_iqr if global_iqr > 0 else 1.0
        return self

    def transform(self, X):
        frame = pd.DataFrame(X, columns=["log2_pi", "device_probe_key"]).copy()
        values = pd.to_numeric(frame["log2_pi"], errors="coerce")
        medians = frame["device_probe_key"].map(self.medians_).fillna(self.global_median_)
        iqrs = frame["device_probe_key"].map(self.iqrs_).fillna(self.global_iqr_)
        return ((values - medians) / iqrs).to_numpy().reshape(-1, 1)

    def get_feature_names_out(self, input_features=None):
        return np.asarray(["within_device_log2_pi_iqr"], dtype=object)


def make_pipeline(spec, C):
    transformers = []
    if spec["numeric"]:
        transformers.append((
            "numeric",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("scaler", StandardScaler()),
            ]),
            spec["numeric"],
        ))
    if spec["categorical"]:
        transformers.append((
            "categorical",
            Pipeline([
                ("imputer", SimpleImputer(strategy="constant", fill_value="Missing")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", drop="first")),
            ]),
            spec["categorical"],
        ))
    if spec["high_cardinality"]:
        transformers.append((
            "high_cardinality",
            Pipeline([
                ("imputer", SimpleImputer(strategy="constant", fill_value="Missing")),
                ("onehot", OneHotEncoder(
                    handle_unknown="infrequent_if_exist",
                    min_frequency=0.02,
                    drop="first",
                )),
            ]),
            spec["high_cardinality"],
        ))
    if spec.get("within_device_pi"):
        transformers.append((
            "within_device_pi",
            Pipeline([
                ("within_device_iqr", WithinDeviceIQRScaler()),
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("scaler", StandardScaler()),
            ]),
            spec["within_device_pi"],
        ))
    return Pipeline([
        ("preprocess", ColumnTransformer(transformers, remainder="drop")),
        ("model", LogisticRegression(
            penalty="l2", C=C, solver="liblinear", max_iter=2000,
            random_state=SEED,
        )),
    ])


def calibration_stats(y, p, weights=None):
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    lp = np.log(p / (1 - p))
    try:
        citl = sm.GLM(
            y, np.ones((len(y), 1)), family=sm.families.Binomial(),
            offset=lp, freq_weights=weights,
        ).fit().params[0]
        slope = sm.GLM(
            y, sm.add_constant(lp), family=sm.families.Binomial(),
            freq_weights=weights,
        ).fit().params[1]
        return float(citl), float(slope)
    except Exception:
        return np.nan, np.nan


def metric_row(frame, weighting="pair"):
    y = frame["outcome"].to_numpy()
    p = frame["predicted_risk"].to_numpy()
    if weighting == "participant":
        counts = frame.groupby("patient_id")["pulse_row_id"].transform("size")
        weights = (1 / counts).to_numpy()
    else:
        weights = None
    citl, slope = calibration_stats(y, p, weights)
    flagged = p >= THRESHOLD
    metric_weights = np.ones(len(y)) if weights is None else weights
    tp = metric_weights[(y == 1) & flagged].sum()
    fn = metric_weights[(y == 1) & ~flagged].sum()
    tn = metric_weights[(y == 0) & ~flagged].sum()
    fp = metric_weights[(y == 0) & flagged].sum()
    return {
        "weighting": weighting,
        "observed_rate": np.average(y, weights=weights),
        "mean_predicted": np.average(p, weights=weights),
        "calibration_gap": np.average(p - y, weights=weights),
        "calibration_in_the_large": citl,
        "calibration_slope": slope,
        "brier": brier_score_loss(y, p, sample_weight=weights),
        "log_loss": log_loss(y, p, sample_weight=weights, labels=[0, 1]),
        "pr_auc": average_precision_score(y, p, sample_weight=weights),
        "roc_auc": roc_auc_score(y, p, sample_weight=weights),
        "sensitivity_5pct": tp / (tp + fn),
        "false_negative_rate_5pct": fn / (tp + fn),
        "specificity_5pct": tn / (tn + fp),
        "flag_rate_5pct": (tp + fp) / len(y),
    }
"""))

cells.append(nbf.v4.new_markdown_cell("### 4. Fit the three enrichment blocks under the frozen nested allocation"))
cells.append(nbf.v4.new_code_cell(
"""prediction_parts = []
tuning_parts = []
coefficient_parts = []

reusable_models = {"Device block ridge", "Pigmentation block ridge"}
fit_paths = {
    "predictions": TABLES / "prediction_enrichment_oof_predictions.csv.gz",
    "tuning": TABLES / "prediction_enrichment_tuning.csv",
    "coefficients": TABLES / "prediction_enrichment_fold_coefficients.csv.gz",
}
if all(path.exists() for path in fit_paths.values()):
    cached_predictions = pd.read_csv(fit_paths["predictions"])
    cached_tuning = pd.read_csv(fit_paths["tuning"])
    cached_coefficients = pd.read_csv(fit_paths["coefficients"])
    prediction_parts.append(cached_predictions.loc[
        cached_predictions["model"].isin(reusable_models)
    ])
    tuning_parts.append(cached_tuning.loc[cached_tuning["model"].isin(reusable_models)])
    coefficient_parts.append(cached_coefficients.loc[
        cached_coefficients["model"].isin(reusable_models)
    ])
else:
    reusable_models = set()

for repeat in sorted(outer["repeat"].unique()):
    outer_repeat = outer.loc[outer["repeat"].eq(repeat)]
    for outer_fold in sorted(outer_repeat["fold"].unique()):
        validation_patients = set(
            outer_repeat.loc[outer_repeat["fold"].eq(outer_fold), "patient_id"]
        )
        train = data.loc[~data["patient_id"].isin(validation_patients)].copy()
        validation = data.loc[data["patient_id"].isin(validation_patients)].copy()
        inner_map = inner.loc[
            inner["repeat"].eq(repeat) & inner["outer_fold"].eq(outer_fold),
            ["patient_id", "inner_fold"],
        ]
        assert not validation["patient_id"].isin(inner_map["patient_id"]).any()
        train = train.merge(inner_map, on="patient_id", how="left", validate="many_to_one")
        assert train["inner_fold"].notna().all()

        for model_name, spec in MODEL_SPECS.items():
            if model_name in reusable_models:
                continue
            features = (
                spec["numeric"] + spec["categorical"] + spec["high_cardinality"]
                + spec.get("within_device_pi", [])
            )
            candidates = []
            for C in C_GRID:
                inner_parts = []
                for inner_fold in sorted(train["inner_fold"].unique()):
                    inner_train = train.loc[~train["inner_fold"].eq(inner_fold)]
                    inner_validation = train.loc[train["inner_fold"].eq(inner_fold)]
                    pipe = make_pipeline(spec, C)
                    pipe.fit(inner_train[features], inner_train["outcome"])
                    inner_parts.append(pd.DataFrame({
                        "outcome": inner_validation["outcome"].to_numpy(),
                        "predicted_risk": pipe.predict_proba(
                            inner_validation[features]
                        )[:, 1],
                    }))
                inner_oof = pd.concat(inner_parts, ignore_index=True)
                candidates.append({
                    "repeat": repeat, "outer_fold": outer_fold,
                    "model": model_name, "C": C,
                    "inner_log_loss": log_loss(
                        inner_oof["outcome"], inner_oof["predicted_risk"], labels=[0, 1]
                    ),
                    "inner_brier": brier_score_loss(
                        inner_oof["outcome"], inner_oof["predicted_risk"]
                    ),
                })
            candidate = pd.DataFrame(candidates).sort_values(
                ["inner_log_loss", "inner_brier", "C"], kind="mergesort"
            )
            selected_C = float(candidate.iloc[0]["C"])
            candidate["selected"] = candidate["C"].eq(selected_C)
            tuning_parts.append(candidate)

            final_pipe = make_pipeline(spec, selected_C)
            final_pipe.fit(train[features], train["outcome"])
            prediction_parts.append(pd.DataFrame({
                "repeat": repeat,
                "outer_fold": outer_fold,
                "model": model_name,
                "patient_id": validation["patient_id"].to_numpy(),
                "pulse_row_id": validation["pulse_row_id"].to_numpy(),
                "outcome": validation["outcome"].to_numpy(),
                "predicted_risk": final_pipe.predict_proba(validation[features])[:, 1],
                "selected_C": selected_C,
            }))
            coefficient_parts.append(pd.DataFrame({
                "repeat": repeat,
                "outer_fold": outer_fold,
                "model": model_name,
                "selected_C": selected_C,
                "feature": final_pipe.named_steps["preprocess"].get_feature_names_out(),
                "coefficient": final_pipe.named_steps["model"].coef_[0],
            }))

enriched_predictions = pd.concat(prediction_parts, ignore_index=True)
tuning = pd.concat(tuning_parts, ignore_index=True)
coefficients = pd.concat(coefficient_parts, ignore_index=True)
enriched_predictions.to_csv(
    TABLES / "prediction_enrichment_oof_predictions.csv.gz",
    index=False, compression="gzip",
)
tuning.to_csv(TABLES / "prediction_enrichment_tuning.csv", index=False)
coefficients.to_csv(
    TABLES / "prediction_enrichment_fold_coefficients.csv.gz",
    index=False, compression="gzip",
)

prediction_checks = {
    "three enrichment models": enriched_predictions["model"].nunique() == 3,
    "50 repeats per model": enriched_predictions.groupby("model")["repeat"].nunique().eq(50).all(),
    "every row once per repeat-model": enriched_predictions.groupby(
        ["model", "repeat", "pulse_row_id"]
    ).size().eq(1).all(),
    "6,062 rows per repeat-model": enriched_predictions.groupby(
        ["model", "repeat"]
    ).size().eq(6062).all(),
    "risks bounded": enriched_predictions["predicted_risk"].between(0, 1).all(),
    "one selected C per outer model": tuning.loc[tuning["selected"]].groupby(
        ["model", "repeat", "outer_fold"]
    ).size().eq(1).all(),
}
assert all(prediction_checks.values())
pd.DataFrame({"check": prediction_checks.keys(), "pass": prediction_checks.values()})
"""))

cells.append(nbf.v4.new_markdown_cell("### 5. Compare overall and supported-subgroup performance"))
cells.append(nbf.v4.new_code_cell(
"""all_predictions = pd.concat([
    compact_predictions[enriched_predictions.columns],
    enriched_predictions,
], ignore_index=True)

repeat_rows = []
for (model, repeat), current in all_predictions.groupby(["model", "repeat"]):
    for weighting in ["pair", "participant"]:
        repeat_rows.append({
            "model": model, "repeat": repeat,
            **metric_row(current, weighting),
        })
repeat_metrics = pd.DataFrame(repeat_rows)

metric_columns = [
    "observed_rate", "mean_predicted", "calibration_gap",
    "calibration_in_the_large", "calibration_slope", "brier",
    "log_loss", "pr_auc", "roc_auc", "sensitivity_5pct",
    "false_negative_rate_5pct", "specificity_5pct", "flag_rate_5pct",
]
overall_summary = (
    repeat_metrics.groupby(["model", "weighting"])[metric_columns]
    .agg(["median", lambda x: x.quantile(0.025), lambda x: x.quantile(0.975)])
)
overall_summary.columns = [
    f"{metric}_{suffix}" for metric, suffix in overall_summary.columns
]
overall_summary = overall_summary.reset_index()

audit_data = data[[
    "pulse_row_id", "device_probe_key", "mst_group"
]].copy()
analysis_predictions = all_predictions.merge(
    audit_data, on="pulse_row_id", how="left", validate="many_to_one"
)

def subgroup_support(frame, group_col):
    rows = []
    for group, current in frame.groupby(group_col, dropna=False):
        events = int(current["outcome"].sum())
        positive = current.loc[current["outcome"].eq(1), "patient_id"].nunique()
        rows.append({
            "group": "Missing" if pd.isna(group) else str(group),
            "readings": len(current),
            "events": events,
            "participants": current["patient_id"].nunique(),
            "positive_participants": positive,
        })
    result = pd.DataFrame(rows)
    result["supported"] = (
        result["readings"].ge(100) & result["events"].ge(10)
        & result["participants"].ge(10) & result["positive_participants"].ge(5)
    )
    return result

source_once = analysis_predictions.loc[
    analysis_predictions["model"].eq(COMPACT) & analysis_predictions["repeat"].eq(0)
]
device_support = subgroup_support(source_once, "device_probe_key")
mst_support = subgroup_support(source_once, "mst_group")
supported_devices = set(device_support.loc[device_support["supported"], "group"])
supported_mst = set(mst_support.loc[
    mst_support["supported"] & mst_support["group"].isin(["1-4", "5-7", "8-10"]),
    "group",
])

subgroup_rows = []
for (model, repeat), current in analysis_predictions.groupby(["model", "repeat"]):
    for dimension, group_col, allowed in [
        ("Device/probe", "device_probe_key", supported_devices),
        ("Forehead MST", "mst_group", supported_mst),
    ]:
        for group in sorted(allowed):
            subset = current.loc[current[group_col].astype(str).eq(group)]
            for weighting in ["pair", "participant"]:
                subgroup_rows.append({
                    "model": model, "repeat": repeat,
                    "dimension": dimension, "group": group,
                    **metric_row(subset, weighting),
                })
subgroup_metrics = pd.DataFrame(subgroup_rows)

comparison_rows = []
for model in MODEL_SPECS:
    for weighting in ["pair", "participant"]:
        reference = repeat_metrics.loc[
            repeat_metrics["model"].eq(COMPACT)
            & repeat_metrics["weighting"].eq(weighting)
        ].set_index("repeat")
        candidate = repeat_metrics.loc[
            repeat_metrics["model"].eq(model)
            & repeat_metrics["weighting"].eq(weighting)
        ].set_index("repeat")
        for metric in metric_columns:
            delta = candidate[metric] - reference[metric]
            comparison_rows.append({
                "model": model, "weighting": weighting, "metric": metric,
                "delta_median": delta.median(),
                "delta_q025": delta.quantile(0.025),
                "delta_q975": delta.quantile(0.975),
                "repeats_delta_below_zero": (delta < 0).mean(),
            })
model_comparison = pd.DataFrame(comparison_rows)
overall_summary, model_comparison.loc[
    model_comparison["weighting"].eq("pair")
    & model_comparison["metric"].isin(["brier", "log_loss", "pr_auc", "roc_auc"])
]
"""))

cells.append(nbf.v4.new_markdown_cell("### 6. Participant-cluster bootstrap the repeated-OOF consensus audit"))
cells.append(nbf.v4.new_code_cell(
"""consensus = (
    analysis_predictions.groupby(
        ["model", "patient_id", "pulse_row_id", "outcome",
         "device_probe_key", "mst_group"],
        dropna=False, as_index=False,
    )["predicted_risk"].mean()
)
participants = sorted(consensus["patient_id"].unique())
rng = np.random.default_rng(SEED)
bootstrap_rows = []

def bootstrap_metric_row(frame, multiplicity, include_ranking):
    weights = frame["patient_id"].map(multiplicity).fillna(0).to_numpy(dtype=float)
    keep = weights > 0
    y = frame.loc[keep, "outcome"].to_numpy()
    p = frame.loc[keep, "predicted_risk"].to_numpy()
    weights = weights[keep]
    flagged = p >= THRESHOLD
    event_weight = weights[y == 1].sum()
    result = {
        "observed_rate": np.average(y, weights=weights),
        "mean_predicted": np.average(p, weights=weights),
        "calibration_gap": np.average(p - y, weights=weights),
        "brier": brier_score_loss(y, p, sample_weight=weights),
        "log_loss": log_loss(y, p, sample_weight=weights, labels=[0, 1]),
        "sensitivity_5pct": weights[(y == 1) & flagged].sum() / event_weight,
        "false_negative_rate_5pct": weights[(y == 1) & ~flagged].sum() / event_weight,
    }
    if include_ranking:
        result["pr_auc"] = average_precision_score(y, p, sample_weight=weights)
        result["roc_auc"] = roc_auc_score(y, p, sample_weight=weights)
    else:
        result["pr_auc"] = np.nan
        result["roc_auc"] = np.nan
    return result


for replicate in range(BOOTSTRAPS):
    sampled = rng.choice(participants, size=len(participants), replace=True)
    multiplicity = pd.Series(sampled).value_counts()

    for model, current in consensus.groupby("model"):
        bootstrap_rows.append({
            "replicate": replicate, "model": model,
            "dimension": "Overall", "group": "Overall",
            **bootstrap_metric_row(current, multiplicity, include_ranking=True),
        })
        for dimension, group_col, allowed in [
            ("Device/probe", "device_probe_key", supported_devices),
            ("Forehead MST", "mst_group", supported_mst),
        ]:
            for group in sorted(allowed):
                subset = current.loc[current[group_col].astype(str).eq(group)]
                bootstrap_rows.append({
                    "replicate": replicate, "model": model,
                    "dimension": dimension, "group": group,
                    **bootstrap_metric_row(subset, multiplicity, include_ranking=False),
                })

bootstrap = pd.DataFrame(bootstrap_rows)
bootstrap_metric_columns = [
    "observed_rate", "mean_predicted", "calibration_gap", "brier",
    "log_loss", "pr_auc", "roc_auc", "sensitivity_5pct",
    "false_negative_rate_5pct",
]
bootstrap_summary = (
    bootstrap.groupby(["model", "dimension", "group"])[bootstrap_metric_columns]
    .agg(["median", lambda x: x.quantile(0.025), lambda x: x.quantile(0.975)])
)
bootstrap_summary.columns = [
    f"{metric}_{suffix}" for metric, suffix in bootstrap_summary.columns
]
bootstrap_summary = bootstrap_summary.reset_index()

delta_rows = []
for (replicate, dimension, group), current in bootstrap.groupby(
    ["replicate", "dimension", "group"]
):
    indexed = current.set_index("model")
    if COMPACT not in indexed.index:
        continue
    for model in MODEL_SPECS:
        for metric in bootstrap_metric_columns:
            delta_rows.append({
                "replicate": replicate, "model": model,
                "dimension": dimension, "group": group, "metric": metric,
                "delta": indexed.loc[model, metric] - indexed.loc[COMPACT, metric],
            })
bootstrap_deltas = pd.DataFrame(delta_rows)
bootstrap_delta_summary = (
    bootstrap_deltas.groupby(["model", "dimension", "group", "metric"])["delta"]
    .agg(
        delta_median="median",
        delta_q025=lambda x: x.quantile(0.025),
        delta_q975=lambda x: x.quantile(0.975),
        probability_delta_below_zero=lambda x: (x < 0).mean(),
    )
    .reset_index()
)
bootstrap_summary
"""))

cells.append(nbf.v4.new_markdown_cell("### 7. Apply the prespecified promotion gate and visualize decision-relevant results"))
cells.append(nbf.v4.new_code_cell(
"""def delta_value(model, dimension, group, metric, column="delta_median"):
    row = bootstrap_delta_summary.loc[
        bootstrap_delta_summary["model"].eq(model)
        & bootstrap_delta_summary["dimension"].eq(dimension)
        & bootstrap_delta_summary["group"].eq(group)
        & bootstrap_delta_summary["metric"].eq(metric)
    ]
    return float(row.iloc[0][column])


gate_rows = []
for model in MODEL_SPECS:
    overall_brier = delta_value(model, "Overall", "Overall", "brier")
    overall_logloss = delta_value(model, "Overall", "Overall", "log_loss")
    mst_gap = delta_value(model, "Forehead MST", "8-10", "calibration_gap")
    device_gap = delta_value(model, "Device/probe", "60|probe_unknown", "calibration_gap")
    mst_sens = delta_value(model, "Forehead MST", "8-10", "sensitivity_5pct")
    device_sens = delta_value(model, "Device/probe", "60|probe_unknown", "sensitivity_5pct")
    mst_gap_lower = delta_value(
        model, "Forehead MST", "8-10", "calibration_gap", "delta_q025"
    )
    device_gap_lower = delta_value(
        model, "Device/probe", "60|probe_unknown", "calibration_gap", "delta_q025"
    )
    participant_brier = float(model_comparison.loc[
        model_comparison["model"].eq(model)
        & model_comparison["weighting"].eq("participant")
        & model_comparison["metric"].eq("brier"),
        "delta_median",
    ].iloc[0])
    participant_logloss = float(model_comparison.loc[
        model_comparison["model"].eq(model)
        & model_comparison["weighting"].eq("participant")
        & model_comparison["metric"].eq("log_loss"),
        "delta_median",
    ].iloc[0])
    gate_rows.append({
        "model": model,
        "delta_brier": overall_brier,
        "delta_log_loss": overall_logloss,
        "delta_calibration_gap_mst_8_10": mst_gap,
        "delta_calibration_gap_device_60": device_gap,
        "delta_sensitivity_mst_8_10": mst_sens,
        "delta_sensitivity_device_60": device_sens,
        "participant_delta_brier": participant_brier,
        "participant_delta_log_loss": participant_logloss,
        "overall_loss_not_worse": (
            overall_brier <= 0 and overall_logloss <= 0
            and participant_brier <= 0 and participant_logloss <= 0
        ),
        "high_risk_underprediction_reduced": (
            mst_gap_lower > 0 and device_gap_lower > 0
        ),
        "high_risk_sensitivity_not_materially_worse": mst_sens >= -0.05 and device_sens >= -0.05,
    })
promotion_gate = pd.DataFrame(gate_rows)
promotion_gate["passes_all_internal_gates"] = (
    promotion_gate["overall_loss_not_worse"]
    & promotion_gate["high_risk_underprediction_reduced"]
    & promotion_gate["high_risk_sensitivity_not_materially_worse"]
)

pair_delta = model_comparison.loc[
    model_comparison["weighting"].eq("pair")
    & model_comparison["metric"].isin(["brier", "log_loss", "pr_auc", "roc_auc"])
].copy()
metric_order = ["brier", "log_loss", "pr_auc", "roc_auc"]

fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
sns.barplot(
    data=pair_delta, x="metric", y="delta_median", hue="model",
    order=metric_order, ax=axes[0],
)
axes[0].axhline(0, color="black", linestyle="--", linewidth=1)
axes[0].set_title("Median repeat-level change versus compact")
axes[0].set_xlabel("")
axes[0].set_ylabel("Enriched minus compact")
axes[0].legend(fontsize=8)

gap_plot = bootstrap_delta_summary.loc[
    bootstrap_delta_summary["metric"].eq("calibration_gap")
    & (
        (bootstrap_delta_summary["dimension"].eq("Forehead MST")
         & bootstrap_delta_summary["group"].eq("8-10"))
        | (bootstrap_delta_summary["dimension"].eq("Device/probe")
           & bootstrap_delta_summary["group"].eq("60|probe_unknown"))
    )
].copy()
gap_plot["audit_group"] = gap_plot["group"].replace({
    "8-10": "MST 8-10", "60|probe_unknown": "Device 60"
})
for index, model in enumerate(MODEL_SPECS):
    current = gap_plot.loc[gap_plot["model"].eq(model)].set_index("audit_group")
    x = current.loc[["MST 8-10", "Device 60"], "delta_median"].to_numpy()
    lo = current.loc[["MST 8-10", "Device 60"], "delta_q025"].to_numpy()
    hi = current.loc[["MST 8-10", "Device 60"], "delta_q975"].to_numpy()
    y = np.arange(2) + (index - 1) * 0.18
    axes[1].errorbar(x, y, xerr=[x - lo, hi - x], fmt="o", capsize=3, label=model)
axes[1].axvline(0, color="black", linestyle="--", linewidth=1)
axes[1].set_yticks(np.arange(2), ["MST 8-10", "Device 60"])
axes[1].set_title("Change in calibration gap\\n(positive reduces underprediction)")
axes[1].set_xlabel("Enriched minus compact mean-risk gap")
axes[1].legend(fontsize=8)

fig.suptitle("OpenOx incremental enrichment blocks", fontweight="bold")
fig.tight_layout()
figure_path = FIGURES / "prediction_enrichment_blocks.png"
fig.savefig(figure_path, dpi=180, bbox_inches="tight")
plt.show()

promotion_gate
"""))

cells.append(nbf.v4.new_markdown_cell("### 8. Save artifacts and complete QA"))
cells.append(nbf.v4.new_code_cell(
"""artifacts = {
    "block_lock": TABLES / "prediction_enrichment_block_lock.csv",
    "oof_predictions": TABLES / "prediction_enrichment_oof_predictions.csv.gz",
    "tuning": TABLES / "prediction_enrichment_tuning.csv",
    "coefficients": TABLES / "prediction_enrichment_fold_coefficients.csv.gz",
    "repeat_metrics": TABLES / "prediction_enrichment_repeat_metrics.csv",
    "overall_summary": TABLES / "prediction_enrichment_overall_summary.csv",
    "subgroup_metrics": TABLES / "prediction_enrichment_subgroup_repeat_metrics.csv.gz",
    "bootstrap": TABLES / "prediction_enrichment_cluster_bootstrap.csv.gz",
    "bootstrap_summary": TABLES / "prediction_enrichment_bootstrap_summary.csv",
    "bootstrap_delta_summary": TABLES / "prediction_enrichment_bootstrap_delta_summary.csv",
    "model_comparison": TABLES / "prediction_enrichment_model_comparison.csv",
    "promotion_gate": TABLES / "prediction_enrichment_promotion_gate.csv",
}
enriched_predictions.to_csv(artifacts["oof_predictions"], index=False, compression="gzip")
tuning.to_csv(artifacts["tuning"], index=False)
coefficients.to_csv(artifacts["coefficients"], index=False, compression="gzip")
repeat_metrics.to_csv(artifacts["repeat_metrics"], index=False)
overall_summary.to_csv(artifacts["overall_summary"], index=False)
subgroup_metrics.to_csv(artifacts["subgroup_metrics"], index=False, compression="gzip")
bootstrap.to_csv(artifacts["bootstrap"], index=False, compression="gzip")
bootstrap_summary.to_csv(artifacts["bootstrap_summary"], index=False)
bootstrap_delta_summary.to_csv(artifacts["bootstrap_delta_summary"], index=False)
model_comparison.to_csv(artifacts["model_comparison"], index=False)
promotion_gate.to_csv(artifacts["promotion_gate"], index=False)

qa = {
    **input_checks,
    **prediction_checks,
    "all repeat metrics complete": repeat_metrics.groupby(
        ["model", "weighting"]
    ).size().eq(50).all(),
    "all subgroup repeat metrics complete": subgroup_metrics.groupby(
        ["model", "dimension", "group", "weighting"]
    ).size().eq(50).all(),
    "all bootstrap cells have 1,000 replicates": bootstrap.groupby(
        ["model", "dimension", "group"]
    )["replicate"].nunique().eq(BOOTSTRAPS).all(),
    "promotion gate covers three blocks": len(promotion_gate) == 3,
    "figure exists": figure_path.exists(),
}
assert all(qa.values())
qa_path = TABLES / "prediction_enrichment_qa.csv"
pd.DataFrame({"check": qa.keys(), "pass": qa.values()}).to_csv(qa_path, index=False)
artifacts["qa"] = qa_path
artifacts["figure"] = figure_path

def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

manifest = pd.DataFrame([
    {"artifact": name, "path": str(path), "sha256": sha256(path)}
    for name, path in artifacts.items()
])
manifest_path = TABLES / "prediction_enrichment_artifact_manifest.csv"
manifest.to_csv(manifest_path, index=False)

pd.DataFrame({"check": qa.keys(), "pass": qa.values()}), manifest
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Takeaways

- Judge each block against the saved compact model on paired frozen repeats and participant-cluster bootstrap differences.
- Promotion requires no deterioration in overall probability loss, reduction of underprediction in both supported high-risk audit groups, and no sensitivity loss greater than five percentage points.
- A pigmentation block can improve prediction without resolving the earlier device-performance disparity question; the two claims remain separate.
- A context-block result partly reflects structured missingness and device availability because PI is recorded for only about half of eligible readings.
- No block is externally transportable unless its exact inputs can be reconstructed in the external dataset. The compact model remains the external candidate unless a later explicit decision changes that role.
"""))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "openox", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}
OUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, OUT)
print(OUT)
