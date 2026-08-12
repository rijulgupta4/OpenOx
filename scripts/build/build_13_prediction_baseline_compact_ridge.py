from pathlib import Path
import nbformat as nbf


OUT = Path("notebooks") / "13_prediction_baseline_compact_ridge.ipynb"
nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell(
"""# OpenOx prediction: baseline and compact ridge internal validation

## tl;dr

This notebook fits the first two authorized prediction models using the frozen nested participant-level resampling allocation. It compares an SpO2-only baseline with the compact transportable bedside model. The summary below is populated by executed outputs; no external dataset is used and no final deployment model is created here.
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Context & Methods

### Key assumptions

- The prediction population is restricted to paired readings with SpO2 92–96%.
- The outcome is SaO2 below 88%.
- Participants—not readings—define every resampling boundary.
- The saved 50-repeat, five-fold outer allocation and four-fold inner allocation are authoritative.
- Ridge logistic regression is used for both models. The fixed grid is `C = [0.01, 0.1, 1, 10]`.
- Inner-fold pooled log loss selects `C`; Brier score is the deterministic tie-breaker.
- Imputation, missingness indicators, scaling, and categorical encoding are learned within each training fold.
- Pair-weighted performance is primary. Participant-balanced performance is a prespecified sensitivity analysis.
- Repeats are overlapping resampling estimates, so their distributions are descriptive—not 50 independent experiments.
"""))

cells.append(nbf.v4.new_code_cell(
"""import os
os.environ["MKL_THREADING_LAYER"] = "SEQUENTIAL"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

from pathlib import Path
import hashlib
import json
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.api as sm

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, log_loss, roc_auc_score,
    confusion_matrix
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)
sns.set_theme(style="whitegrid")
pd.set_option("display.max_columns", 100)

PROJECT = Path(r".")
TABLES = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
PROCESSED = PROJECT / "data" / "processed"
TABLES.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

COHORT_PATH = PROCESSED / "analytic_cohort_180s.csv.gz"
CONTEXT_PATH = PROCESSED / "context_covariates_by_pair.csv.gz"
OUTER_PATH = TABLES / "prediction_outer_fold_assignments.csv.gz"
INNER_PATH = TABLES / "prediction_inner_fold_assignments.csv.gz"
MANIFEST_PATH = TABLES / "prediction_resampling_manifest.csv"

C_GRID = [0.01, 0.1, 1.0, 10.0]
THRESHOLDS = [0.02, 0.05, 0.10]
MODEL_SPECS = {
    "SpO2-only baseline": {
        "numeric": ["saturation"],
        "categorical": [],
    },
    "Compact transportable ridge": {
        "numeric": ["saturation", "age_at_encounter", "heart_rate_consensus", "RR"],
        "categorical": ["assigned_sex_normalized"],
    },
}
"""))

cells.append(nbf.v4.new_markdown_cell("## Data\n\n### 1. Load and seal the restricted prediction population"))
cells.append(nbf.v4.new_code_cell(
"""cohort = pd.read_csv(COHORT_PATH)
context_cols = [
    "pulse_row_id", "patient_id", "age_at_encounter",
    "assigned_sex_normalized", "heart_rate_consensus", "RR"
]
context = pd.read_csv(CONTEXT_PATH, usecols=context_cols)

assert cohort["pulse_row_id"].is_unique
assert context["pulse_row_id"].is_unique

data = cohort.merge(
    context.drop(columns=["patient_id"]),
    on="pulse_row_id",
    how="left",
    validate="one_to_one",
)
data = data.loc[data["saturation"].between(92, 96, inclusive="both")].copy()
data["outcome"] = (data["so2"] < 88).astype(int)

outer = pd.read_csv(OUTER_PATH)
inner = pd.read_csv(INNER_PATH)
manifest = pd.read_csv(MANIFEST_PATH).iloc[0]

summary = pd.DataFrame({
    "item": ["eligible readings", "events", "event rate (%)", "participants",
             "event-positive participants"],
    "value": [
        len(data), int(data["outcome"].sum()), 100 * data["outcome"].mean(),
        data["patient_id"].nunique(),
        data.loc[data["outcome"].eq(1), "patient_id"].nunique(),
    ],
})
summary
"""))

cells.append(nbf.v4.new_markdown_cell("### 2. Verify frozen assignments and feature availability"))
cells.append(nbf.v4.new_code_cell(
"""assignment_checks = {
    "data participants match outer participants": (
        set(data["patient_id"]) == set(outer["patient_id"])
    ),
    "50 outer repeats": outer["repeat"].nunique() == 50,
    "5 outer folds per repeat": outer.groupby("repeat")["fold"].nunique().eq(5).all(),
    "participant once per outer repeat": (
        outer.groupby(["repeat", "patient_id"]).size().eq(1).all()
    ),
    "4 inner folds per outer training set": (
        inner.groupby(["repeat", "outer_fold"])["inner_fold"].nunique().eq(4).all()
    ),
}
assert all(assignment_checks.values())

feature_coverage = (
    data[["saturation", "age_at_encounter", "assigned_sex_normalized",
          "heart_rate_consensus", "RR"]]
    .notna().mean().mul(100).rename("coverage_pct").to_frame()
)
pd.DataFrame({"check": assignment_checks.keys(), "pass": assignment_checks.values()}), feature_coverage
"""))

cells.append(nbf.v4.new_markdown_cell("## Results\n\n### 3. Define fold-contained preprocessing, calibration, and metric functions"))
cells.append(nbf.v4.new_code_cell(
"""def make_pipeline(numeric, categorical, C):
    transformers = []
    if numeric:
        numeric_pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
        ])
        transformers.append(("numeric", numeric_pipe, numeric))
    if categorical:
        categorical_pipe = Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", drop="first")),
        ])
        transformers.append(("categorical", categorical_pipe, categorical))
    preprocessing = ColumnTransformer(transformers, remainder="drop")
    model = LogisticRegression(
        penalty="l2", C=C, solver="liblinear", max_iter=2000, random_state=20260726
    )
    return Pipeline([("preprocess", preprocessing), ("model", model)])


def calibration_stats(y, p, weights=None):
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    logit_p = np.log(p / (1 - p))
    try:
        citl_fit = sm.GLM(
            y, np.ones((len(y), 1)), family=sm.families.Binomial(),
            offset=logit_p, freq_weights=weights
        ).fit()
        slope_fit = sm.GLM(
            y, sm.add_constant(logit_p), family=sm.families.Binomial(),
            freq_weights=weights
        ).fit()
        return float(citl_fit.params[0]), float(slope_fit.params[1])
    except Exception:
        return np.nan, np.nan


def performance_metrics(frame, weight_mode):
    y = frame["outcome"].to_numpy()
    p = frame["predicted_risk"].to_numpy()
    if weight_mode == "pair":
        w = None
    else:
        counts = frame.groupby("patient_id")["patient_id"].transform("size")
        w = (1 / counts).to_numpy()
    citl, slope = calibration_stats(y, p, w)
    return {
        "weighting": weight_mode,
        "observed_rate": np.average(y, weights=w),
        "mean_predicted": np.average(p, weights=w),
        "calibration_in_the_large": citl,
        "calibration_slope": slope,
        "brier": brier_score_loss(y, p, sample_weight=w),
        "log_loss": log_loss(y, p, sample_weight=w, labels=[0, 1]),
        "pr_auc": average_precision_score(y, p, sample_weight=w),
        "roc_auc": roc_auc_score(y, p, sample_weight=w),
    }


def threshold_metrics(frame, threshold):
    y = frame["outcome"].to_numpy()
    p = frame["predicted_risk"].to_numpy()
    pred = p >= threshold
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    n = len(y)
    odds = threshold / (1 - threshold)
    return {
        "threshold": threshold,
        "sensitivity": tp / (tp + fn) if tp + fn else np.nan,
        "specificity": tn / (tn + fp) if tn + fp else np.nan,
        "ppv": tp / (tp + fp) if tp + fp else np.nan,
        "npv": tn / (tn + fn) if tn + fn else np.nan,
        "flag_rate": (tp + fp) / n,
        "net_benefit": tp / n - fp / n * odds,
    }
"""))

cells.append(nbf.v4.new_markdown_cell("### 4. Run frozen nested validation"))
cells.append(nbf.v4.new_code_cell(
"""prediction_parts = []
tuning_rows = []
coefficient_rows = []

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
            features = spec["numeric"] + spec["categorical"]
            candidate_rows = []
            for C in C_GRID:
                inner_predictions = []
                for inner_fold in sorted(train["inner_fold"].unique()):
                    inner_train = train.loc[~train["inner_fold"].eq(inner_fold)]
                    inner_validation = train.loc[train["inner_fold"].eq(inner_fold)]
                    pipe = make_pipeline(spec["numeric"], spec["categorical"], C)
                    pipe.fit(inner_train[features], inner_train["outcome"])
                    inner_predictions.append(pd.DataFrame({
                        "outcome": inner_validation["outcome"].to_numpy(),
                        "predicted_risk": pipe.predict_proba(
                            inner_validation[features]
                        )[:, 1],
                    }))
                inner_oof = pd.concat(inner_predictions, ignore_index=True)
                candidate_rows.append({
                    "repeat": repeat,
                    "outer_fold": outer_fold,
                    "model": model_name,
                    "C": C,
                    "inner_log_loss": log_loss(
                        inner_oof["outcome"], inner_oof["predicted_risk"], labels=[0, 1]
                    ),
                    "inner_brier": brier_score_loss(
                        inner_oof["outcome"], inner_oof["predicted_risk"]
                    ),
                })

            candidate = pd.DataFrame(candidate_rows).sort_values(
                ["inner_log_loss", "inner_brier", "C"], kind="mergesort"
            )
            selected_C = float(candidate.iloc[0]["C"])
            candidate["selected"] = candidate["C"].eq(selected_C)
            tuning_rows.append(candidate)

            final_pipe = make_pipeline(spec["numeric"], spec["categorical"], selected_C)
            final_pipe.fit(train[features], train["outcome"])
            predicted_risk = final_pipe.predict_proba(validation[features])[:, 1]
            prediction_parts.append(pd.DataFrame({
                "repeat": repeat,
                "outer_fold": outer_fold,
                "model": model_name,
                "patient_id": validation["patient_id"].to_numpy(),
                "pulse_row_id": validation["pulse_row_id"].to_numpy(),
                "outcome": validation["outcome"].to_numpy(),
                "predicted_risk": predicted_risk,
                "selected_C": selected_C,
            }))

            feature_names = final_pipe.named_steps["preprocess"].get_feature_names_out()
            coefficients = final_pipe.named_steps["model"].coef_[0]
            coefficient_rows.append(pd.DataFrame({
                "repeat": repeat,
                "outer_fold": outer_fold,
                "model": model_name,
                "selected_C": selected_C,
                "feature": feature_names,
                "coefficient": coefficients,
            }))

predictions = pd.concat(prediction_parts, ignore_index=True)
tuning = pd.concat(tuning_rows, ignore_index=True)
coefficients = pd.concat(coefficient_rows, ignore_index=True)
predictions.shape, tuning.shape, coefficients.shape
"""))

cells.append(nbf.v4.new_markdown_cell("### 5. Audit prediction completeness and participant leakage"))
cells.append(nbf.v4.new_code_cell(
"""prediction_qa = {
    "two models present": predictions["model"].nunique() == 2,
    "50 repeats per model": (
        predictions.groupby("model")["repeat"].nunique().eq(50).all()
    ),
    "every row predicted once per repeat and model": (
        predictions.groupby(["model", "repeat", "pulse_row_id"]).size().eq(1).all()
    ),
    "every repeat-model has 6,062 predictions": (
        predictions.groupby(["model", "repeat"]).size().eq(len(data)).all()
    ),
    "outcomes agree across models": (
        predictions.groupby(["repeat", "pulse_row_id"])["outcome"].nunique().eq(1).all()
    ),
    "risks strictly between zero and one": (
        predictions["predicted_risk"].between(0, 1, inclusive="neither").all()
    ),
    "one C selected per outer fold and model": (
        tuning.loc[tuning["selected"]]
        .groupby(["repeat", "outer_fold", "model"]).size().eq(1).all()
    ),
}
assert all(prediction_qa.values())
pd.DataFrame({"check": prediction_qa.keys(), "pass": prediction_qa.values()})
"""))

cells.append(nbf.v4.new_markdown_cell("### 6. Calculate pooled out-of-fold performance within each repeat"))
cells.append(nbf.v4.new_code_cell(
"""metric_rows = []
threshold_rows = []
for (model_name, repeat), frame in predictions.groupby(["model", "repeat"]):
    for weight_mode in ["pair", "participant_balanced"]:
        row = performance_metrics(frame, weight_mode)
        row.update({"model": model_name, "repeat": repeat})
        metric_rows.append(row)
    for threshold in THRESHOLDS:
        row = threshold_metrics(frame, threshold)
        row.update({"model": model_name, "repeat": repeat})
        threshold_rows.append(row)

repeat_metrics = pd.DataFrame(metric_rows)
threshold_results = pd.DataFrame(threshold_rows)

metric_summary = (
    repeat_metrics.groupby(["model", "weighting"])
    .agg(
        brier_median=("brier", "median"),
        brier_p025=("brier", lambda x: x.quantile(.025)),
        brier_p975=("brier", lambda x: x.quantile(.975)),
        log_loss_median=("log_loss", "median"),
        pr_auc_median=("pr_auc", "median"),
        roc_auc_median=("roc_auc", "median"),
        citl_median=("calibration_in_the_large", "median"),
        slope_median=("calibration_slope", "median"),
    )
    .reset_index()
)
metric_summary
"""))

cells.append(nbf.v4.new_markdown_cell("### 7. Compare models within identical repeats"))
cells.append(nbf.v4.new_code_cell(
"""pair_metrics = repeat_metrics.loc[repeat_metrics["weighting"].eq("pair")]
wide = pair_metrics.pivot(index="repeat", columns="model")
comparison = pd.DataFrame({
    "repeat": wide.index,
    "delta_brier_compact_minus_baseline": (
        wide["brier"]["Compact transportable ridge"]
        - wide["brier"]["SpO2-only baseline"]
    ),
    "delta_log_loss_compact_minus_baseline": (
        wide["log_loss"]["Compact transportable ridge"]
        - wide["log_loss"]["SpO2-only baseline"]
    ),
    "delta_pr_auc_compact_minus_baseline": (
        wide["pr_auc"]["Compact transportable ridge"]
        - wide["pr_auc"]["SpO2-only baseline"]
    ),
    "delta_roc_auc_compact_minus_baseline": (
        wide["roc_auc"]["Compact transportable ridge"]
        - wide["roc_auc"]["SpO2-only baseline"]
    ),
})
comparison_summary = comparison.drop(columns="repeat").agg(
    ["median", lambda x: x.quantile(.025), lambda x: x.quantile(.975),
     lambda x: np.mean(x < 0), lambda x: np.mean(x > 0)]
)
comparison_summary.index = ["median", "p025", "p975", "proportion_below_zero", "proportion_above_zero"]
comparison_summary
"""))

cells.append(nbf.v4.new_markdown_cell("### 8. Summarize tuning and fixed-threshold behavior"))
cells.append(nbf.v4.new_code_cell(
"""tuning_frequency = (
    tuning.loc[tuning["selected"]]
    .groupby(["model", "C"]).size().rename("outer_fits").reset_index()
)
threshold_summary = (
    threshold_results.groupby(["model", "threshold"])
    .agg(
        sensitivity=("sensitivity", "median"),
        specificity=("specificity", "median"),
        ppv=("ppv", "median"),
        npv=("npv", "median"),
        flag_rate=("flag_rate", "median"),
        net_benefit=("net_benefit", "median"),
    ).reset_index()
)
tuning_frequency, threshold_summary
"""))

cells.append(nbf.v4.new_markdown_cell("### 9. Create calibration and comparison displays"))
cells.append(nbf.v4.new_code_cell(
"""mean_oof = (
    predictions.groupby(["model", "patient_id", "pulse_row_id", "outcome"], as_index=False)
    ["predicted_risk"].mean()
)

calibration_rows = []
for model_name, frame in mean_oof.groupby("model"):
    ranked = frame["predicted_risk"].rank(method="first")
    frame = frame.assign(bin=pd.qcut(ranked, q=10, labels=False))
    bins = frame.groupby("bin").agg(
        mean_predicted=("predicted_risk", "mean"),
        observed_rate=("outcome", "mean"),
        readings=("outcome", "size"),
        events=("outcome", "sum"),
    ).reset_index()
    bins["model"] = model_name
    calibration_rows.append(bins)
calibration_bins = pd.concat(calibration_rows, ignore_index=True)

fig, axes = plt.subplots(2, 2, figsize=(12, 9))
for model_name, frame in calibration_bins.groupby("model"):
    axes[0, 0].plot(frame["mean_predicted"], frame["observed_rate"], marker="o", label=model_name)
axes[0, 0].plot([0, .20], [0, .20], "--", color="gray", linewidth=1)
axes[0, 0].set(xlim=(0, .20), ylim=(0, .20), xlabel="Mean predicted risk",
            ylabel="Observed event rate", title="Repeated-OOF calibration display")
axes[0, 0].legend(fontsize=8)

sns.boxplot(
    data=repeat_metrics.loc[repeat_metrics["weighting"].eq("pair")],
    x="model", y="brier", ax=axes[0, 1], color="#5b8db8"
)
axes[0, 1].set(title="Pair-weighted Brier score across repeats", xlabel="", ylabel="Brier score")
axes[0, 1].tick_params(axis="x", rotation=15)

plot_comparison = comparison.melt(id_vars="repeat", var_name="metric", value_name="delta")
loss_delta = plot_comparison.loc[
    plot_comparison["metric"].isin([
        "delta_brier_compact_minus_baseline",
        "delta_log_loss_compact_minus_baseline",
    ])
]
auc_delta = plot_comparison.loc[
    plot_comparison["metric"].isin([
        "delta_pr_auc_compact_minus_baseline",
        "delta_roc_auc_compact_minus_baseline",
    ])
]
sns.boxplot(data=loss_delta, x="metric", y="delta", ax=axes[1, 0], color="#7b6fc2")
axes[1, 0].axhline(0, color="gray", linestyle="--", linewidth=1)
axes[1, 0].set(title="Compact minus baseline: prediction loss", xlabel="",
               ylabel="Difference (negative favors compact)")
axes[1, 0].set_xticklabels(["Brier", "Log loss"])

sns.boxplot(data=auc_delta, x="metric", y="delta", ax=axes[1, 1], color="#4f9d82")
axes[1, 1].axhline(0, color="gray", linestyle="--", linewidth=1)
axes[1, 1].set(title="Compact minus baseline: ranking", xlabel="",
               ylabel="Difference (positive favors compact)")
axes[1, 1].set_xticklabels(["PR-AUC", "ROC-AUC"])

fig.suptitle("OpenOx baseline and compact ridge: frozen internal validation", fontweight="bold")
fig.tight_layout()
figure_path = FIGURES / "prediction_internal_baseline_compact.png"
fig.savefig(figure_path, dpi=180, bbox_inches="tight")
plt.show()
"""))

cells.append(nbf.v4.new_markdown_cell("### 10. Save authoritative internal-validation artifacts"))
cells.append(nbf.v4.new_code_cell(
"""paths = {
    "predictions": TABLES / "prediction_internal_oof_predictions.csv.gz",
    "repeat_metrics": TABLES / "prediction_internal_repeat_metrics.csv",
    "threshold_metrics": TABLES / "prediction_internal_threshold_metrics.csv",
    "tuning": TABLES / "prediction_internal_tuning.csv",
    "coefficients": TABLES / "prediction_internal_fold_coefficients.csv.gz",
    "comparison": TABLES / "prediction_internal_model_comparison.csv",
    "calibration_bins": TABLES / "prediction_internal_calibration_bins.csv",
    "qa": TABLES / "prediction_internal_qa.csv",
    "summary": TABLES / "prediction_internal_metric_summary.csv",
}
predictions.to_csv(paths["predictions"], index=False, compression="gzip")
repeat_metrics.to_csv(paths["repeat_metrics"], index=False)
threshold_results.to_csv(paths["threshold_metrics"], index=False)
tuning.to_csv(paths["tuning"], index=False)
coefficients.to_csv(paths["coefficients"], index=False, compression="gzip")
comparison.to_csv(paths["comparison"], index=False)
calibration_bins.to_csv(paths["calibration_bins"], index=False)
pd.DataFrame({"check": prediction_qa.keys(), "pass": prediction_qa.values()}).to_csv(
    paths["qa"], index=False
)
metric_summary.to_csv(paths["summary"], index=False)

artifact_manifest = pd.DataFrame([
    {"artifact": key, "path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    for key, path in paths.items()
])
artifact_manifest.to_csv(TABLES / "prediction_internal_artifact_manifest.csv", index=False)
artifact_manifest
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Takeaways

- This notebook estimates internal validation performance only. It does not establish clinical utility or external transportability.
- The comparison is paired within identical outer repeats. Negative compact-minus-baseline Brier and log-loss differences favor the compact model; positive PR-AUC and ROC-AUC differences favor it.
- Calibration and discrimination must be interpreted separately.
- Threshold results describe the tradeoff of prespecified flagging thresholds; decision-curve net benefit is secondary.
- The next step is an independent audit of saved predictions and a decision on whether the compact model meaningfully improves on the SpO2-only baseline before enriched models are considered.
"""))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {
        "display_name": "Python (openox)",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3"},
}
nbf.write(nb, OUT)
print(OUT)
