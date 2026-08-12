from pathlib import Path

import nbformat as nbf


OUT = Path("notebooks") / "18_prediction_context_ablation_utility.ipynb"
nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell(
"""# OpenOx prediction: context ablation, utility, and internal freeze decision

## tl;dr

This notebook completes the prespecified decision step for the OpenOx-only
perfusion/context model. It removes each context component in turn under the
same frozen 50-repeat, five-fold participant allocation; evaluates decision
curves from 2% through 10%; and freezes or rejects the full context model using
rules written before the results are examined.

The compact bedside model remains the only harmonizable external-validation
candidate regardless of the OpenOx-only decision here.

## Context & Methods

### Key assumptions

- The population remains SpO2 92–96%, and the outcome remains SaO2 below 88%.
- The frozen compact and full-context out-of-fold predictions are reused.
- Every newly fitted ablation uses the saved participant splits, grouped inner
  tuning, and fold-contained preprocessing.
- Native PI values are never pooled. Actual PI is transformed within device
  using training-fold medians and IQRs.
- PI availability is a distinct binary feature. When it is ablated, missing PI
  is median-imputed without adding a missingness indicator.
- Ablations explain the full model; they are not an unrestricted feature search.
- Decision curves are secondary and describe a risk-flagging tradeoff, not
  demonstrated clinical benefit.

### Prespecified freeze rule

The full OpenOx-only context model is internally frozen only if:

1. its Brier score and log loss improve over compact in pair- and
   participant-balanced analyses, with participant-cluster bootstrap support;
2. its participant-balanced net benefit exceeds both flag-all and flag-none
   with a positive lower 95% bootstrap bound at two or more contiguous
   thresholds between 2% and 10%;
3. its point net benefit exceeds compact at three or more contiguous thresholds;
4. neither pair- nor participant-balanced analysis shows bootstrap-supported
   harm versus compact at any threshold; and
5. the previously completed high-risk subgroup gate remains passed.

Failure rejects the full context model for progression. Component ablations
affect mechanistic wording but do not silently substitute a post hoc model.
"""))

cells.append(nbf.v4.new_code_cell(
"""from pathlib import Path
import hashlib
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
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
CONTEXT_PATH = PROCESSED / "context_covariates_by_pair.csv.gz"
OUTER_PATH = TABLES / "prediction_outer_fold_assignments.csv.gz"
INNER_PATH = TABLES / "prediction_inner_fold_assignments.csv.gz"
COMPACT_PATH = TABLES / "prediction_internal_oof_predictions.csv.gz"
ENRICHMENT_PATH = TABLES / "prediction_enrichment_oof_predictions.csv.gz"
PROMOTION_PATH = TABLES / "prediction_enrichment_promotion_gate.csv"

C_GRID = [0.01, 0.1, 1.0, 10.0]
THRESHOLDS = np.arange(0.02, 0.101, 0.01)
BOOTSTRAPS = 2000
SEED = 20260728
COMPACT = "Compact transportable ridge"
FULL = "Full context"

BASE_NUMERIC = ["saturation", "age_at_encounter", "heart_rate_consensus", "RR"]
BASE_CATEGORICAL = ["assigned_sex_normalized"]

ABLATION_SPECS = {
    "Context minus actual PI": {
        "pi_value": False, "pi_availability": True,
        "warming": True, "finger": True,
        "removed_component": "Actual within-device PI value",
    },
    "Context minus PI availability": {
        "pi_value": True, "pi_availability": False,
        "warming": True, "finger": True,
        "removed_component": "PI availability indicator",
    },
    "Context minus warming": {
        "pi_value": True, "pi_availability": True,
        "warming": False, "finger": True,
        "removed_component": "Warming status",
    },
    "Context minus finger diameter": {
        "pi_value": True, "pi_availability": True,
        "warming": True, "finger": False,
        "removed_component": "Finger diameter",
    },
}
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Data

### 1. Recover the frozen population, split objects, and reference predictions
"""))
cells.append(nbf.v4.new_code_cell(
"""cohort = pd.read_csv(COHORT_PATH)
context = pd.read_csv(
    CONTEXT_PATH,
    usecols=[
        "pulse_row_id", "age_at_encounter", "assigned_sex_normalized",
        "heart_rate_consensus", "RR", "log2_pi", "warming",
        "finger_diameter",
    ],
)
assert cohort["pulse_row_id"].is_unique
assert context["pulse_row_id"].is_unique

data = cohort.merge(context, on="pulse_row_id", how="left", validate="one_to_one")
data = data.loc[data["saturation"].between(92, 96, inclusive="both")].copy()
data["outcome"] = (data["so2"] < 88).astype(int)
data["pi_available"] = data["log2_pi"].notna().astype(float)
for column in ["assigned_sex_normalized", "warming", "device_probe_key"]:
    data[column] = data[column].astype("string").fillna("Missing").astype(str)

outer = pd.read_csv(OUTER_PATH)
inner = pd.read_csv(INNER_PATH)

compact_saved = pd.read_csv(COMPACT_PATH)
compact_saved = compact_saved.loc[compact_saved["model"].eq(COMPACT)].copy()
enrichment_saved = pd.read_csv(ENRICHMENT_PATH)
full_saved = enrichment_saved.loc[
    enrichment_saved["model"].eq("Perfusion/context block ridge")
].copy()
full_saved["model"] = FULL

prediction_columns = [
    "repeat", "outer_fold", "model", "patient_id", "pulse_row_id",
    "outcome", "predicted_risk", "selected_C",
]
compact_saved = compact_saved[prediction_columns]
full_saved = full_saved[prediction_columns]

input_checks = {
    "6,062 eligible readings": len(data) == 6062,
    "261 events": int(data["outcome"].sum()) == 261,
    "38 event-positive participants": (
        data.loc[data["outcome"].eq(1), "patient_id"].nunique() == 38
    ),
    "50 by 5 outer allocation": (
        outer["repeat"].nunique() == 50
        and outer.groupby("repeat")["fold"].nunique().eq(5).all()
    ),
    "four inner folds": (
        inner.groupby(["repeat", "outer_fold"])["inner_fold"]
        .nunique().eq(4).all()
    ),
    "compact predictions complete": len(compact_saved) == len(data) * 50,
    "full predictions complete": len(full_saved) == len(data) * 50,
    "full prior gate passed": bool(
        pd.read_csv(PROMOTION_PATH)
        .loc[lambda x: x["model"].eq("Perfusion/context block ridge"),
             "passes_all_internal_gates"]
        .iloc[0]
    ),
}
assert all(input_checks.values())

ablation_lock = pd.DataFrame([
    {
        "model": model,
        **spec,
        "role": "Drop-one explanatory ablation; not an alternate feature search",
    }
    for model, spec in ABLATION_SPECS.items()
])
ablation_lock.to_csv(TABLES / "prediction_context_ablation_lock.csv", index=False)

pd.DataFrame({"check": input_checks.keys(), "pass": input_checks.values()}), ablation_lock
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Results

### 2. Define fold-contained PI processing, model pipelines, and metrics
"""))
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
        global_iqr = (
            frame["log2_pi"].quantile(0.75)
            - frame["log2_pi"].quantile(0.25)
        )
        self.global_iqr_ = global_iqr if global_iqr > 0 else 1.0
        return self

    def transform(self, X):
        frame = pd.DataFrame(X, columns=["log2_pi", "device_probe_key"]).copy()
        values = pd.to_numeric(frame["log2_pi"], errors="coerce")
        medians = (
            frame["device_probe_key"].map(self.medians_)
            .fillna(self.global_median_)
        )
        iqrs = (
            frame["device_probe_key"].map(self.iqrs_)
            .fillna(self.global_iqr_)
        )
        return ((values - medians) / iqrs).to_numpy().reshape(-1, 1)

    def get_feature_names_out(self, input_features=None):
        return np.asarray(["within_device_log2_pi_iqr"], dtype=object)


def model_features(spec):
    numeric = BASE_NUMERIC.copy()
    categorical = BASE_CATEGORICAL.copy()
    if spec["pi_availability"] and not spec["pi_value"]:
        numeric.append("pi_available")
    if spec["finger"]:
        numeric.append("finger_diameter")
    if spec["warming"]:
        categorical.append("warming")
    raw = numeric + categorical
    if spec["pi_value"]:
        raw += ["log2_pi", "device_probe_key"]
    return numeric, categorical, list(dict.fromkeys(raw))


def make_pipeline(spec, C):
    numeric, categorical, _ = model_features(spec)
    transformers = [
        (
            "numeric",
            Pipeline([
                ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
                ("scaler", StandardScaler()),
            ]),
            numeric,
        ),
        (
            "categorical",
            Pipeline([
                ("imputer", SimpleImputer(
                    strategy="constant", fill_value="Missing"
                )),
                ("onehot", OneHotEncoder(handle_unknown="ignore", drop="first")),
            ]),
            categorical,
        ),
    ]
    if spec["pi_value"]:
        transformers.append((
            "within_device_pi",
            Pipeline([
                ("within_device_iqr", WithinDeviceIQRScaler()),
                ("imputer", SimpleImputer(
                    strategy="median",
                    add_indicator=spec["pi_availability"],
                )),
                ("scaler", StandardScaler()),
            ]),
            ["log2_pi", "device_probe_key"],
        ))
    return Pipeline([
        ("preprocess", ColumnTransformer(transformers, remainder="drop")),
        ("model", LogisticRegression(
            penalty="l2", C=C, solver="liblinear", max_iter=2000,
            random_state=SEED,
        )),
    ])


def row_weights(frame, weighting):
    if weighting == "pair":
        return np.ones(len(frame), dtype=float)
    counts = frame.groupby("patient_id")["pulse_row_id"].transform("size")
    return (1.0 / counts.to_numpy(dtype=float))


def probability_metrics(frame, weighting):
    weights = row_weights(frame, weighting)
    y = frame["outcome"].to_numpy()
    p = frame["predicted_risk"].to_numpy()
    return {
        "brier": brier_score_loss(y, p, sample_weight=weights),
        "log_loss": log_loss(y, p, sample_weight=weights, labels=[0, 1]),
        "observed_rate": np.average(y, weights=weights),
        "mean_predicted": np.average(p, weights=weights),
    }


def net_benefit(y, p, threshold, weights):
    flagged = p >= threshold
    total = weights.sum()
    tp = weights[(y == 1) & flagged].sum() / total
    fp = weights[(y == 0) & flagged].sum() / total
    return tp - fp * threshold / (1 - threshold)


def max_contiguous(values):
    values = list(values)
    best = current = 0
    for value in values:
        current = current + 1 if value else 0
        best = max(best, current)
    return best
"""))

cells.append(nbf.v4.new_markdown_cell(
"""### 3. Refit the four drop-one ablations under the frozen nested allocation

The compact and full-context predictions are reused exactly. Only the four
new ablations are fitted below.
"""))
cells.append(nbf.v4.new_code_cell(
"""fit_paths = {
    "predictions": TABLES / "prediction_context_ablation_oof_predictions.csv.gz",
    "tuning": TABLES / "prediction_context_ablation_tuning.csv",
    "coefficients": TABLES / "prediction_context_ablation_fold_coefficients.csv.gz",
}
cached_fit = all(path.exists() for path in fit_paths.values())
if cached_fit:
    prediction_parts = [pd.read_csv(fit_paths["predictions"])]
    tuning_parts = [pd.read_csv(fit_paths["tuning"])]
    coefficient_parts = [pd.read_csv(fit_paths["coefficients"])]
    repeats_to_fit = []
else:
    prediction_parts = [compact_saved, full_saved]
    tuning_parts = []
    coefficient_parts = []
    repeats_to_fit = sorted(outer["repeat"].unique())

for repeat in repeats_to_fit:
    outer_repeat = outer.loc[outer["repeat"].eq(repeat)]
    for outer_fold in sorted(outer_repeat["fold"].unique()):
        validation_patients = set(
            outer_repeat.loc[
                outer_repeat["fold"].eq(outer_fold), "patient_id"
            ]
        )
        train = data.loc[~data["patient_id"].isin(validation_patients)].copy()
        validation = data.loc[
            data["patient_id"].isin(validation_patients)
        ].copy()
        inner_map = inner.loc[
            inner["repeat"].eq(repeat)
            & inner["outer_fold"].eq(outer_fold),
            ["patient_id", "inner_fold"],
        ]
        train = train.merge(
            inner_map, on="patient_id", how="left", validate="many_to_one"
        )
        assert train["inner_fold"].notna().all()
        assert not validation["patient_id"].isin(inner_map["patient_id"]).any()

        for model_name, spec in ABLATION_SPECS.items():
            _, _, features = model_features(spec)
            candidates = []
            for C in C_GRID:
                inner_parts = []
                for inner_fold in sorted(train["inner_fold"].unique()):
                    inner_train = train.loc[
                        ~train["inner_fold"].eq(inner_fold)
                    ]
                    inner_validation = train.loc[
                        train["inner_fold"].eq(inner_fold)
                    ]
                    pipeline = make_pipeline(spec, C)
                    pipeline.fit(
                        inner_train[features], inner_train["outcome"]
                    )
                    inner_parts.append(pd.DataFrame({
                        "outcome": inner_validation["outcome"].to_numpy(),
                        "predicted_risk": pipeline.predict_proba(
                            inner_validation[features]
                        )[:, 1],
                    }))
                inner_oof = pd.concat(inner_parts, ignore_index=True)
                candidates.append({
                    "repeat": repeat,
                    "outer_fold": outer_fold,
                    "model": model_name,
                    "C": C,
                    "inner_log_loss": log_loss(
                        inner_oof["outcome"],
                        inner_oof["predicted_risk"],
                        labels=[0, 1],
                    ),
                    "inner_brier": brier_score_loss(
                        inner_oof["outcome"],
                        inner_oof["predicted_risk"],
                    ),
                })
            candidate_table = pd.DataFrame(candidates).sort_values(
                ["inner_log_loss", "inner_brier", "C"], kind="mergesort"
            )
            selected_C = float(candidate_table.iloc[0]["C"])
            candidate_table["selected"] = candidate_table["C"].eq(selected_C)
            tuning_parts.append(candidate_table)

            final_pipeline = make_pipeline(spec, selected_C)
            final_pipeline.fit(train[features], train["outcome"])
            prediction_parts.append(pd.DataFrame({
                "repeat": repeat,
                "outer_fold": outer_fold,
                "model": model_name,
                "patient_id": validation["patient_id"].to_numpy(),
                "pulse_row_id": validation["pulse_row_id"].to_numpy(),
                "outcome": validation["outcome"].to_numpy(),
                "predicted_risk": final_pipeline.predict_proba(
                    validation[features]
                )[:, 1],
                "selected_C": selected_C,
            }))
            coefficient_parts.append(pd.DataFrame({
                "repeat": repeat,
                "outer_fold": outer_fold,
                "model": model_name,
                "selected_C": selected_C,
                "feature": (
                    final_pipeline.named_steps["preprocess"]
                    .get_feature_names_out()
                ),
                "coefficient": (
                    final_pipeline.named_steps["model"].coef_[0]
                ),
            }))

all_predictions = pd.concat(prediction_parts, ignore_index=True)
tuning = pd.concat(tuning_parts, ignore_index=True)
coefficients = pd.concat(coefficient_parts, ignore_index=True)

fit_checks = {
    "six models including references": all_predictions["model"].nunique() == 6,
    "50 repeats per model": (
        all_predictions.groupby("model")["repeat"].nunique().eq(50).all()
    ),
    "6,062 rows per repeat-model": (
        all_predictions.groupby(["model", "repeat"]).size().eq(6062).all()
    ),
    "every row once per repeat-model": (
        all_predictions.groupby(
            ["model", "repeat", "pulse_row_id"]
        ).size().eq(1).all()
    ),
    "risks bounded": all_predictions["predicted_risk"].between(0, 1).all(),
    "one selected C per outer ablation": (
        tuning.loc[tuning["selected"]]
        .groupby(["model", "repeat", "outer_fold"])
        .size().eq(1).all()
    ),
}
assert all(fit_checks.values())

all_predictions.to_csv(
    TABLES / "prediction_context_ablation_oof_predictions.csv.gz",
    index=False, compression="gzip",
)
tuning.to_csv(TABLES / "prediction_context_ablation_tuning.csv", index=False)
coefficients.to_csv(
    TABLES / "prediction_context_ablation_fold_coefficients.csv.gz",
    index=False, compression="gzip",
)
pd.DataFrame({"check": fit_checks.keys(), "pass": fit_checks.values()})
"""))

cells.append(nbf.v4.new_markdown_cell(
"""### 4. Summarize repeated out-of-fold probability performance
"""))
cells.append(nbf.v4.new_code_cell(
"""repeat_rows = []
for (model, repeat), current in all_predictions.groupby(["model", "repeat"]):
    for weighting in ["pair", "participant"]:
        repeat_rows.append({
            "model": model,
            "repeat": repeat,
            "weighting": weighting,
            **probability_metrics(current, weighting),
        })
repeat_metrics = pd.DataFrame(repeat_rows)

def q025(values):
    return values.quantile(0.025)


def q975(values):
    return values.quantile(0.975)


repeat_summary = repeat_metrics.groupby(["model", "weighting"])[
    ["brier", "log_loss", "observed_rate", "mean_predicted"]
].agg(["median", q025, q975])
repeat_summary.columns = [
    f"{metric}_{statistic}"
    for metric, statistic in repeat_summary.columns
]
repeat_summary = repeat_summary.reset_index()

paired_rows = []
for weighting in ["pair", "participant"]:
    indexed = repeat_metrics.loc[
        repeat_metrics["weighting"].eq(weighting)
    ].set_index(["model", "repeat"])
    for model in all_predictions["model"].unique():
        if model == COMPACT:
            continue
        for reference in [COMPACT, FULL]:
            if model == reference:
                continue
            for metric in ["brier", "log_loss"]:
                delta = (
                    indexed.loc[model, metric]
                    - indexed.loc[reference, metric]
                )
                paired_rows.append({
                    "model": model,
                    "reference": reference,
                    "weighting": weighting,
                    "metric": metric,
                    "delta_median": delta.median(),
                    "delta_q025": delta.quantile(0.025),
                    "delta_q975": delta.quantile(0.975),
                    "repeats_favoring_model": (delta < 0).mean(),
                })
paired_repeat_comparison = pd.DataFrame(paired_rows)

repeat_summary, paired_repeat_comparison.loc[
    paired_repeat_comparison["reference"].eq(FULL)
    & paired_repeat_comparison["weighting"].eq("participant")
]
"""))

cells.append(nbf.v4.new_markdown_cell(
"""### 5. Compute consensus decision curves and participant-cluster uncertainty

Repeated out-of-fold risks are averaged for each reading. Cluster bootstrap
sampling then resamples participants, preserving all readings from sampled
participants. Pair-weighted and participant-balanced curves are reported
separately.
"""))
cells.append(nbf.v4.new_code_cell(
"""consensus = (
    all_predictions.groupby(
        ["model", "patient_id", "pulse_row_id", "outcome"],
        as_index=False,
    )["predicted_risk"].mean()
)
participants = np.sort(consensus["patient_id"].unique())


def consensus_weights(frame, weighting, multiplicity=None):
    if multiplicity is None:
        multiplicity = pd.Series(1.0, index=participants)
    mult = frame["patient_id"].map(multiplicity).fillna(0).to_numpy(float)
    if weighting == "pair":
        return mult
    participant_counts = frame.groupby("patient_id")[
        "pulse_row_id"
    ].transform("size").to_numpy(float)
    return mult / participant_counts


def decision_rows_for_model(frame, weighting, multiplicity, replicate):
    weights = consensus_weights(frame, weighting, multiplicity)
    keep = weights > 0
    y = frame.loc[keep, "outcome"].to_numpy()
    p = frame.loc[keep, "predicted_risk"].to_numpy()
    weights = weights[keep]
    prevalence = np.average(y, weights=weights)
    rows = []
    for threshold in THRESHOLDS:
        rows.extend([
            {
                "replicate": replicate,
                "weighting": weighting,
                "model": frame["model"].iloc[0],
                "threshold": threshold,
                "net_benefit": net_benefit(
                    y, p, threshold, weights
                ),
            },
            {
                "replicate": replicate,
                "weighting": weighting,
                "model": "Flag all",
                "threshold": threshold,
                "net_benefit": (
                    prevalence
                    - (1 - prevalence) * threshold / (1 - threshold)
                ),
            },
            {
                "replicate": replicate,
                "weighting": weighting,
                "model": "Flag none",
                "threshold": threshold,
                "net_benefit": 0.0,
            },
        ])
    return rows


point_curve_rows = []
for weighting in ["pair", "participant"]:
    for model, current in consensus.groupby("model"):
        current_rows = decision_rows_for_model(
            current, weighting, None, replicate=-1
        )
        point_curve_rows.extend([
            row for row in current_rows
            if row["model"] == model
        ])
    reference_frame = consensus.loc[consensus["model"].eq(COMPACT)]
    reference_rows = decision_rows_for_model(
        reference_frame, weighting, None, replicate=-1
    )
    point_curve_rows.extend([
        row for row in reference_rows
        if row["model"] in {"Flag all", "Flag none"}
    ])
point_curves = pd.DataFrame(point_curve_rows).drop_duplicates(
    ["weighting", "model", "threshold"]
)

rng = np.random.default_rng(SEED)
bootstrap_curve_rows = []
bootstrap_loss_rows = []
for replicate in range(BOOTSTRAPS):
    sampled = rng.choice(participants, size=len(participants), replace=True)
    multiplicity = pd.Series(sampled).value_counts()
    for weighting in ["pair", "participant"]:
        for model, current in consensus.groupby("model"):
            weights = consensus_weights(current, weighting, multiplicity)
            keep = weights > 0
            y = current.loc[keep, "outcome"].to_numpy()
            p = current.loc[keep, "predicted_risk"].to_numpy()
            active_weights = weights[keep]
            bootstrap_loss_rows.append({
                "replicate": replicate,
                "weighting": weighting,
                "model": model,
                "brier": brier_score_loss(
                    y, p, sample_weight=active_weights
                ),
                "log_loss": log_loss(
                    y, p, sample_weight=active_weights, labels=[0, 1]
                ),
            })
            model_rows = decision_rows_for_model(
                current, weighting, multiplicity, replicate
            )
            bootstrap_curve_rows.extend([
                row for row in model_rows if row["model"] == model
            ])
        reference_frame = consensus.loc[consensus["model"].eq(COMPACT)]
        reference_rows = decision_rows_for_model(
            reference_frame, weighting, multiplicity, replicate
        )
        bootstrap_curve_rows.extend([
            row for row in reference_rows
            if row["model"] in {"Flag all", "Flag none"}
        ])

bootstrap_curves = pd.DataFrame(bootstrap_curve_rows).drop_duplicates(
    ["replicate", "weighting", "model", "threshold"]
)
bootstrap_losses = pd.DataFrame(bootstrap_loss_rows)

curve_summary = (
    bootstrap_curves.groupby(["weighting", "model", "threshold"])[
        "net_benefit"
    ]
    .agg(
        median="median",
        q025=lambda x: x.quantile(0.025),
        q975=lambda x: x.quantile(0.975),
    )
    .reset_index()
)

loss_delta_rows = []
for (replicate, weighting), current in bootstrap_losses.groupby(
    ["replicate", "weighting"]
):
    indexed = current.set_index("model")
    for model in indexed.index:
        for reference in [COMPACT, FULL]:
            if model == reference:
                continue
            for metric in ["brier", "log_loss"]:
                loss_delta_rows.append({
                    "replicate": replicate,
                    "weighting": weighting,
                    "model": model,
                    "reference": reference,
                    "metric": metric,
                    "delta": (
                        indexed.loc[model, metric]
                        - indexed.loc[reference, metric]
                    ),
                })
bootstrap_loss_deltas = pd.DataFrame(loss_delta_rows)
bootstrap_loss_delta_summary = (
    bootstrap_loss_deltas.groupby(
        ["weighting", "model", "reference", "metric"]
    )["delta"]
    .agg(
        median="median",
        q025=lambda x: x.quantile(0.025),
        q975=lambda x: x.quantile(0.975),
    )
    .reset_index()
)

curve_summary.head(), bootstrap_loss_delta_summary.head()
"""))

cells.append(nbf.v4.new_markdown_cell(
"""### 6. Compare the full context model with compact and default strategies
"""))
cells.append(nbf.v4.new_code_cell(
"""curve_delta_rows = []
for (replicate, weighting, threshold), current in bootstrap_curves.groupby(
    ["replicate", "weighting", "threshold"]
):
    indexed = current.set_index("model")["net_benefit"]
    default_best = max(indexed["Flag all"], indexed["Flag none"])
    curve_delta_rows.extend([
        {
            "replicate": replicate,
            "weighting": weighting,
            "contrast": "Full context minus compact",
            "threshold": threshold,
            "delta": indexed[FULL] - indexed[COMPACT],
        },
        {
            "replicate": replicate,
            "weighting": weighting,
            "contrast": "Full context minus best default",
            "threshold": threshold,
            "delta": indexed[FULL] - default_best,
        },
    ])
    for ablation in ABLATION_SPECS:
        curve_delta_rows.append({
            "replicate": replicate,
            "weighting": weighting,
            "contrast": f"Full context minus {ablation}",
            "threshold": threshold,
            "delta": indexed[FULL] - indexed[ablation],
        })
curve_deltas = pd.DataFrame(curve_delta_rows)
curve_delta_summary = (
    curve_deltas.groupby(["weighting", "contrast", "threshold"])["delta"]
    .agg(
        median="median",
        q025=lambda x: x.quantile(0.025),
        q975=lambda x: x.quantile(0.975),
    )
    .reset_index()
)

point_index = point_curves.pivot_table(
    index=["weighting", "threshold"],
    columns="model",
    values="net_benefit",
)
point_full_vs_compact = (
    point_index[FULL] - point_index[COMPACT]
).rename("full_minus_compact")
point_full_vs_default = (
    point_index[FULL]
    - point_index[["Flag all", "Flag none"]].max(axis=1)
).rename("full_minus_best_default")
point_contrasts = pd.concat(
    [point_full_vs_compact, point_full_vs_default], axis=1
).reset_index()

curve_delta_summary.loc[
    curve_delta_summary["contrast"].isin([
        "Full context minus compact",
        "Full context minus best default",
    ])
]
"""))

cells.append(nbf.v4.new_markdown_cell(
"""### 7. Apply the frozen decision rule and interpret component ablations
"""))
cells.append(nbf.v4.new_code_cell(
"""def loss_delta(weighting, model, reference, metric, column):
    row = bootstrap_loss_delta_summary.loc[
        bootstrap_loss_delta_summary["weighting"].eq(weighting)
        & bootstrap_loss_delta_summary["model"].eq(model)
        & bootstrap_loss_delta_summary["reference"].eq(reference)
        & bootstrap_loss_delta_summary["metric"].eq(metric)
    ]
    return float(row.iloc[0][column])


loss_gate = all(
    loss_delta(weighting, FULL, COMPACT, metric, "q975") < 0
    for weighting in ["pair", "participant"]
    for metric in ["brier", "log_loss"]
)

utility_rows = []
for weighting in ["pair", "participant"]:
    compact_delta = curve_delta_summary.loc[
        curve_delta_summary["weighting"].eq(weighting)
        & curve_delta_summary["contrast"].eq("Full context minus compact")
    ].sort_values("threshold")
    default_delta = curve_delta_summary.loc[
        curve_delta_summary["weighting"].eq(weighting)
        & curve_delta_summary["contrast"].eq(
            "Full context minus best default"
        )
    ].sort_values("threshold")
    point = point_contrasts.loc[
        point_contrasts["weighting"].eq(weighting)
    ].sort_values("threshold")
    utility_rows.append({
        "weighting": weighting,
        "contiguous_point_benefit_vs_compact": max_contiguous(
            point["full_minus_compact"] > 0
        ),
        "contiguous_supported_benefit_vs_default": max_contiguous(
            default_delta["q025"] > 0
        ),
        "supported_harm_vs_compact_thresholds": int(
            (compact_delta["q975"] < 0).sum()
        ),
        "supported_harm_vs_default_thresholds": int(
            (default_delta["q975"] < 0).sum()
        ),
    })
utility_gate_table = pd.DataFrame(utility_rows)

participant_utility = utility_gate_table.loc[
    utility_gate_table["weighting"].eq("participant")
].iloc[0]
pair_utility = utility_gate_table.loc[
    utility_gate_table["weighting"].eq("pair")
].iloc[0]
utility_gate = (
    participant_utility["contiguous_supported_benefit_vs_default"] >= 2
    and participant_utility["contiguous_point_benefit_vs_compact"] >= 3
    and participant_utility["supported_harm_vs_compact_thresholds"] == 0
    and pair_utility["supported_harm_vs_compact_thresholds"] == 0
)

component_rows = []
for model, spec in ABLATION_SPECS.items():
    probability_supported = any(
        loss_delta(
            "participant", model, FULL, metric, "q025"
        ) > 0
        for metric in ["brier", "log_loss"]
    )
    utility_contrast = curve_delta_summary.loc[
        curve_delta_summary["weighting"].eq("participant")
        & curve_delta_summary["contrast"].eq(
            f"Full context minus {model}"
        )
    ].sort_values("threshold")
    utility_supported = (
        max_contiguous(utility_contrast["q025"] > 0) >= 2
    )
    component_rows.append({
        "removed_component": spec["removed_component"],
        "ablation_model": model,
        "probability_degradation_supported": probability_supported,
        "utility_degradation_supported": utility_supported,
        "component_supported": probability_supported or utility_supported,
        "participant_delta_brier_ablation_minus_full": loss_delta(
            "participant", model, FULL, "brier", "median"
        ),
        "participant_delta_logloss_ablation_minus_full": loss_delta(
            "participant", model, FULL, "log_loss", "median"
        ),
    })
component_evidence = pd.DataFrame(component_rows)

prior_subgroup_gate = input_checks["full prior gate passed"]
freeze_pass = loss_gate and utility_gate and prior_subgroup_gate
decision = pd.DataFrame([{
    "model": FULL,
    "probability_loss_gate": loss_gate,
    "decision_curve_gate": utility_gate,
    "prior_high_risk_subgroup_gate": prior_subgroup_gate,
    "freeze_pass": freeze_pass,
    "decision": (
        "Internally frozen as OpenOx-only context model"
        if freeze_pass
        else "Rejected for progression as an OpenOx-only prediction model"
    ),
    "external_role": (
        "None; compact model remains external-validation candidate"
    ),
}])

utility_gate_table, component_evidence, decision
"""))

cells.append(nbf.v4.new_markdown_cell(
"""### 8. Visualize probability and decision-curve evidence
"""))
cells.append(nbf.v4.new_code_cell(
"""fig, axes = plt.subplots(2, 2, figsize=(14, 10))

participant_repeat = repeat_metrics.loc[
    repeat_metrics["weighting"].eq("participant")
]
plot_order = [COMPACT, FULL] + list(ABLATION_SPECS)
sns.boxplot(
    data=participant_repeat,
    y="model", x="log_loss", order=plot_order,
    color="#69b3a2", ax=axes[0, 0],
)
axes[0, 0].set_title("Participant-balanced log loss across repeats")
axes[0, 0].set_xlabel("Log loss (lower is better)")
axes[0, 0].set_ylabel("")

participant_curves = curve_summary.loc[
    curve_summary["weighting"].eq("participant")
    & curve_summary["model"].isin(
        [COMPACT, FULL, "Flag all", "Flag none"]
    )
]
colors = {
    COMPACT: "#3569a8", FULL: "#11896f",
    "Flag all": "#b07d00", "Flag none": "#555555",
}
for model, current in participant_curves.groupby("model"):
    current = current.sort_values("threshold")
    axes[0, 1].plot(
        current["threshold"] * 100, current["median"],
        marker="o", label=model, color=colors[model],
    )
    if model in [COMPACT, FULL]:
        axes[0, 1].fill_between(
            current["threshold"] * 100,
            current["q025"], current["q975"],
            alpha=0.15, color=colors[model],
        )
axes[0, 1].axhline(0, color="black", linewidth=0.8)
axes[0, 1].set_title("Participant-balanced decision curves")
axes[0, 1].set_xlabel("Flagging threshold (%)")
axes[0, 1].set_ylabel("Net benefit")
axes[0, 1].legend(fontsize=8)

for contrast, color in [
    ("Full context minus compact", "#5b4bb7"),
    ("Full context minus best default", "#c75b12"),
]:
    current = curve_delta_summary.loc[
        curve_delta_summary["weighting"].eq("participant")
        & curve_delta_summary["contrast"].eq(contrast)
    ].sort_values("threshold")
    axes[1, 0].plot(
        current["threshold"] * 100, current["median"],
        marker="o", label=contrast, color=color,
    )
    axes[1, 0].fill_between(
        current["threshold"] * 100,
        current["q025"], current["q975"],
        alpha=0.18, color=color,
    )
axes[1, 0].axhline(0, color="black", linestyle="--", linewidth=0.8)
axes[1, 0].set_title("Participant-balanced net-benefit differences")
axes[1, 0].set_xlabel("Flagging threshold (%)")
axes[1, 0].set_ylabel("Full-context net-benefit advantage")
axes[1, 0].legend(fontsize=8)

ablation_plot = bootstrap_loss_delta_summary.loc[
    bootstrap_loss_delta_summary["weighting"].eq("participant")
    & bootstrap_loss_delta_summary["reference"].eq(FULL)
    & bootstrap_loss_delta_summary["metric"].eq("log_loss")
    & bootstrap_loss_delta_summary["model"].isin(ABLATION_SPECS)
].copy()
ablation_plot["component"] = ablation_plot["model"].map(
    {model: spec["removed_component"]
     for model, spec in ABLATION_SPECS.items()}
)
ablation_plot = ablation_plot.sort_values("median")
axes[1, 1].errorbar(
    ablation_plot["median"], np.arange(len(ablation_plot)),
    xerr=[
        ablation_plot["median"] - ablation_plot["q025"],
        ablation_plot["q975"] - ablation_plot["median"],
    ],
    fmt="o", capsize=3, color="#7a3e9d",
)
axes[1, 1].axvline(0, color="black", linestyle="--", linewidth=0.8)
axes[1, 1].set_yticks(
    np.arange(len(ablation_plot)), ablation_plot["component"]
)
axes[1, 1].set_title("Effect of removing each context component")
axes[1, 1].set_xlabel(
    "Ablated minus full participant log loss\\n(positive favors full)"
)

fig.suptitle(
    "OpenOx context-model ablation and decision utility",
    fontweight="bold",
)
fig.tight_layout()
figure_path = FIGURES / "prediction_context_ablation_utility.png"
fig.savefig(figure_path, dpi=180, bbox_inches="tight")
plt.show()
"""))

cells.append(nbf.v4.new_markdown_cell(
"""### 9. Save artifacts, hash outputs, and complete QA
"""))
cells.append(nbf.v4.new_code_cell(
"""artifacts = {
    "ablation_lock": TABLES / "prediction_context_ablation_lock.csv",
    "oof_predictions": (
        TABLES / "prediction_context_ablation_oof_predictions.csv.gz"
    ),
    "tuning": TABLES / "prediction_context_ablation_tuning.csv",
    "coefficients": (
        TABLES / "prediction_context_ablation_fold_coefficients.csv.gz"
    ),
    "repeat_metrics": TABLES / "prediction_context_ablation_repeat_metrics.csv",
    "repeat_summary": TABLES / "prediction_context_ablation_repeat_summary.csv",
    "paired_repeat_comparison": (
        TABLES / "prediction_context_ablation_paired_comparison.csv"
    ),
    "point_curves": TABLES / "prediction_context_decision_curves.csv",
    "bootstrap_curves": (
        TABLES / "prediction_context_decision_curve_bootstrap.csv.gz"
    ),
    "curve_summary": (
        TABLES / "prediction_context_decision_curve_summary.csv"
    ),
    "curve_delta_summary": (
        TABLES / "prediction_context_decision_curve_delta_summary.csv"
    ),
    "bootstrap_loss_delta_summary": (
        TABLES / "prediction_context_bootstrap_loss_delta_summary.csv"
    ),
    "utility_gate": TABLES / "prediction_context_utility_gate.csv",
    "component_evidence": (
        TABLES / "prediction_context_component_evidence.csv"
    ),
    "decision": TABLES / "prediction_context_freeze_decision.csv",
    "figure": figure_path,
}
repeat_metrics.to_csv(artifacts["repeat_metrics"], index=False)
repeat_summary.to_csv(artifacts["repeat_summary"], index=False)
paired_repeat_comparison.to_csv(
    artifacts["paired_repeat_comparison"], index=False
)
point_curves.to_csv(artifacts["point_curves"], index=False)
bootstrap_curves.to_csv(
    artifacts["bootstrap_curves"], index=False, compression="gzip"
)
curve_summary.to_csv(artifacts["curve_summary"], index=False)
curve_delta_summary.to_csv(artifacts["curve_delta_summary"], index=False)
bootstrap_loss_delta_summary.to_csv(
    artifacts["bootstrap_loss_delta_summary"], index=False
)
utility_gate_table.to_csv(artifacts["utility_gate"], index=False)
component_evidence.to_csv(artifacts["component_evidence"], index=False)
decision.to_csv(artifacts["decision"], index=False)

qa = {
    **input_checks,
    **fit_checks,
    "repeat metrics complete": (
        repeat_metrics.groupby(["model", "weighting"]).size().eq(50).all()
    ),
    "consensus has every row once per model": (
        consensus.groupby(["model", "pulse_row_id"]).size().eq(1).all()
    ),
    "point curves complete": (
        point_curves.groupby(["weighting", "model"])
        ["threshold"].nunique().eq(len(THRESHOLDS)).all()
    ),
    "2,000 bootstrap curves complete": (
        bootstrap_curves.groupby(["weighting", "model", "threshold"])
        ["replicate"].nunique().eq(BOOTSTRAPS).all()
    ),
    "decision covers all gates": (
        decision[[
            "probability_loss_gate", "decision_curve_gate",
            "prior_high_risk_subgroup_gate",
        ]].notna().all().all()
    ),
    "all four components audited": len(component_evidence) == 4,
    "figure exists": figure_path.exists(),
}
assert all(qa.values())
qa_path = TABLES / "prediction_context_ablation_qa.csv"
pd.DataFrame({"check": qa.keys(), "pass": qa.values()}).to_csv(
    qa_path, index=False
)
artifacts["qa"] = qa_path


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
manifest_path = TABLES / "prediction_context_ablation_artifact_manifest.csv"
manifest.to_csv(manifest_path, index=False)

pd.DataFrame({"check": qa.keys(), "pass": qa.values()}), manifest
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Takeaways

- The full context block is judged only by the prespecified probability,
  subgroup, and decision-curve gates.
- Drop-one ablations identify whether actual PI, PI availability, warming, or
  finger diameter contributes independently; absence of bootstrap support is
  not proof of no biological effect.
- A frozen OpenOx-only model remains specific to the controlled-desaturation
  repository. It is not substituted for the compact bedside model in BOLD or
  ENCoDE.
- Net benefit depends on the relative consequence of false-positive and
  false-negative flags encoded by each threshold. It does not establish that
  deploying the model improves patient outcomes.
"""))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {
        "display_name": "openox",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3"},
}
OUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, OUT)
print(OUT)
