from pathlib import Path
import nbformat as nbf


OUT = Path("notebooks") / "19_prediction_final_compact_lock.ipynb"
nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell(
"""# OpenOx prediction: final compact-model lock and serialization

## tl;dr

This notebook implements D028. It derives one research-use compact occult-hypoxemia model from the full locked OpenOx development sample, serializes the complete preprocessing-and-model pipeline, and creates a portable scoring specification. It does not estimate new generalization performance and does not reopen feature selection.
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Context & Methods

### Key assumptions and locked decisions

- Eligibility remains paired readings with SpO2 92-96% inclusive.
- The outcome remains SaO2 below 88%.
- The compact predictors remain SpO2, age, assigned sex, heart rate, and respiratory rate.
- The preprocessing and ridge-logistic implementation exactly match the internally validated compact pipeline.
- The final penalty is selected from the original fixed grid by the lowest mean inner-fold pooled log loss across all 250 frozen outer-training contexts; mean Brier score and then smaller `C` are deterministic tie-breakers.
- The model is refit once on all 6,062 eligible OpenOx rows. Fold-specific models are neither averaged nor ensembled.
- Internal performance claims remain those from frozen nested cross-validation. Apparent full-sample fit is recorded only as a software sanity check.
- External data may be scored only after a frozen source-specific feature, units, timing, coding, and missingness crosswalk passes.
- This is a pilot research risk-flagging model, not a diagnostic product and not a replacement for arterial blood-gas measurement.

### Chronology note

D020 locked probability accuracy and calibration above decision-curve utility. The exact D027 intersection rule was formalized at the start of Notebook 18 after the D026 block result, but before the four ablations and decision-curve bootstrap results. This distinction must be retained in reporting.
"""))

cells.append(nbf.v4.new_code_cell(
"""import os
os.environ["MKL_THREADING_LAYER"] = "SEQUENTIAL"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

from pathlib import Path
import hashlib
import json
import platform

import joblib
import numpy as np
import pandas as pd
import sklearn

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, log_loss, roc_auc_score
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

PROJECT = Path(r".")
TABLES = PROJECT / "outputs" / "tables"
MODELS = PROJECT / "outputs" / "models"
PROCESSED = PROJECT / "data" / "processed"
TABLES.mkdir(parents=True, exist_ok=True)
MODELS.mkdir(parents=True, exist_ok=True)

COHORT_PATH = PROCESSED / "analytic_cohort_180s.csv.gz"
CONTEXT_PATH = PROCESSED / "context_covariates_by_pair.csv.gz"
TUNING_PATH = TABLES / "prediction_internal_tuning.csv"

MODEL_PATH = MODELS / "openox_compact_occult_ridge_v1.joblib"
SPEC_PATH = MODELS / "openox_compact_occult_ridge_v1_scoring_spec.json"

C_GRID = [0.01, 0.1, 1.0, 10.0]
NUMERIC = ["saturation", "age_at_encounter", "heart_rate_consensus", "RR"]
CATEGORICAL = ["assigned_sex_normalized"]
FEATURES = NUMERIC + CATEGORICAL
RANDOM_STATE = 20260726
"""))

cells.append(nbf.v4.new_markdown_cell("## Data\n\n### 1. Reconstruct and seal the full development sample"))
cells.append(nbf.v4.new_code_cell(
"""cohort = pd.read_csv(COHORT_PATH)
context = pd.read_csv(
    CONTEXT_PATH,
    usecols=["pulse_row_id", "patient_id"] + FEATURES[1:],
)
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

development_summary = pd.DataFrame({
    "item": [
        "eligible_readings", "events", "event_rate", "participants",
        "event_positive_participants"
    ],
    "value": [
        len(data), int(data["outcome"].sum()), data["outcome"].mean(),
        data["patient_id"].nunique(),
        data.loc[data["outcome"].eq(1), "patient_id"].nunique(),
    ],
})

input_checks = {
    "6,062 eligible readings": len(data) == 6062,
    "261 events": int(data["outcome"].sum()) == 261,
    "123 participants": data["patient_id"].nunique() == 123,
    "38 event-positive participants": (
        data.loc[data["outcome"].eq(1), "patient_id"].nunique() == 38
    ),
    "one row per pulse_row_id": data["pulse_row_id"].is_unique,
    "binary outcome": set(data["outcome"].unique()) == {0, 1},
    "locked feature list": FEATURES == [
        "saturation", "age_at_encounter", "heart_rate_consensus", "RR",
        "assigned_sex_normalized"
    ],
}
assert all(input_checks.values())
development_summary, pd.DataFrame(
    {"check": input_checks.keys(), "pass": input_checks.values()}
)
"""))

cells.append(nbf.v4.new_markdown_cell("## Results\n\n### 2. Select the final penalty from the frozen tuning record"))
cells.append(nbf.v4.new_code_cell(
"""tuning = pd.read_csv(TUNING_PATH)
compact_tuning = tuning.loc[
    tuning["model"].eq("Compact transportable ridge")
].copy()

penalty_selection = (
    compact_tuning.groupby("C")
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
penalty_selection["selected_for_final_fit"] = False
penalty_selection.loc[penalty_selection.index[0], "selected_for_final_fit"] = True
SELECTED_C = float(
    penalty_selection.loc[penalty_selection["selected_for_final_fit"], "C"].iloc[0]
)

assert set(penalty_selection["C"]) == set(C_GRID)
assert penalty_selection["frozen_contexts"].eq(250).all()
assert SELECTED_C == 0.1
penalty_selection
"""))

cells.append(nbf.v4.new_markdown_cell("### 3. Recreate the validated pipeline and fit once on all development rows"))
cells.append(nbf.v4.new_code_cell(
"""def make_compact_pipeline(C):
    numeric_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scaler", StandardScaler()),
    ])
    categorical_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", drop="first")),
    ])
    preprocessing = ColumnTransformer([
        ("numeric", numeric_pipe, NUMERIC),
        ("categorical", categorical_pipe, CATEGORICAL),
    ], remainder="drop")
    model = LogisticRegression(
        penalty="l2",
        C=C,
        solver="liblinear",
        max_iter=2000,
        random_state=RANDOM_STATE,
    )
    return Pipeline([("preprocess", preprocessing), ("model", model)])


final_pipeline = make_compact_pipeline(SELECTED_C)
final_pipeline.fit(data[FEATURES], data["outcome"])
apparent_risk = final_pipeline.predict_proba(data[FEATURES])[:, 1]

apparent_checks_only = pd.DataFrame([{
    "label": "apparent full-development fit; not validation performance",
    "observed_rate": data["outcome"].mean(),
    "mean_predicted": apparent_risk.mean(),
    "brier": brier_score_loss(data["outcome"], apparent_risk),
    "log_loss": log_loss(data["outcome"], apparent_risk, labels=[0, 1]),
    "pr_auc": average_precision_score(data["outcome"], apparent_risk),
    "roc_auc": roc_auc_score(data["outcome"], apparent_risk),
}])
apparent_checks_only
"""))

cells.append(nbf.v4.new_markdown_cell("### 4. Export coefficients, preprocessing state, and scoring contract"))
cells.append(nbf.v4.new_code_cell(
"""preprocess = final_pipeline.named_steps["preprocess"]
model = final_pipeline.named_steps["model"]
feature_names = preprocess.get_feature_names_out()
coefficients = pd.DataFrame({
    "transformed_feature": feature_names,
    "coefficient": model.coef_[0],
})
coefficients = pd.concat([
    pd.DataFrame({
        "transformed_feature": ["__intercept__"],
        "coefficient": [float(model.intercept_[0])],
    }),
    coefficients,
], ignore_index=True)

numeric_imputer = preprocess.named_transformers_["numeric"].named_steps["imputer"]
numeric_scaler = preprocess.named_transformers_["numeric"].named_steps["scaler"]
categorical_imputer = preprocess.named_transformers_["categorical"].named_steps["imputer"]
onehot = preprocess.named_transformers_["categorical"].named_steps["onehot"]

feature_contract = pd.DataFrame([
    {
        "field": "saturation", "role": "predictor and eligibility field",
        "type": "numeric", "unit": "percentage points",
        "missing_policy": "ineligible if missing",
        "external_gate": "must be charted pre-ABG SpO2 and within 92-96 inclusive",
    },
    {
        "field": "age_at_encounter", "role": "predictor", "type": "numeric",
        "unit": "years", "missing_policy": "training-median imputation plus indicator",
        "external_gate": "same encounter-time definition and plausible units",
    },
    {
        "field": "heart_rate_consensus", "role": "predictor", "type": "numeric",
        "unit": "beats per minute",
        "missing_policy": "training-median imputation plus indicator",
        "external_gate": "pre-ABG value under frozen source-specific timing rule",
    },
    {
        "field": "RR", "role": "predictor", "type": "numeric",
        "unit": "breaths per minute",
        "missing_policy": "training-median imputation plus indicator",
        "external_gate": "pre-ABG value under frozen source-specific timing rule",
    },
    {
        "field": "assigned_sex_normalized", "role": "predictor",
        "type": "categorical", "unit": "locked OpenOx coding",
        "missing_policy": "training-mode imputation",
        "external_gate": "source categories must be mapped before outcomes are examined",
    },
])

model_lock = pd.DataFrame([
    {"item": "decision_id", "value": "D028"},
    {"item": "model_name", "value": "OpenOx compact occult ridge v1"},
    {"item": "status", "value": "Frozen for unchanged external evaluation"},
    {"item": "development_population", "value": "SpO2 92-96 inclusive"},
    {"item": "outcome", "value": "SaO2 <88"},
    {"item": "development_rows", "value": str(len(data))},
    {"item": "development_participants", "value": str(data["patient_id"].nunique())},
    {"item": "event_rows", "value": str(int(data["outcome"].sum()))},
    {"item": "event_positive_participants", "value": "38"},
    {"item": "predictors", "value": "|".join(FEATURES)},
    {"item": "penalty_grid", "value": "|".join(map(str, C_GRID))},
    {"item": "penalty_selection", "value": "minimum mean inner pooled log loss across 250 frozen tuning contexts; mean Brier then smaller C tie-break"},
    {"item": "selected_C", "value": str(SELECTED_C)},
    {"item": "estimator", "value": "L2 logistic regression; liblinear"},
    {"item": "derivation", "value": "single full-development refit; no fold averaging or ensemble"},
    {"item": "claim_boundary", "value": "pilot research risk flag; not a diagnostic product or ABG replacement"},
])

scoring_spec = {
    "name": "OpenOx compact occult ridge v1",
    "decision_id": "D028",
    "intended_use": "research-only occult-hypoxemia risk flagging",
    "eligibility": {"saturation_min": 92, "saturation_max": 96, "inclusive": True},
    "outcome_definition_for_validation": "SaO2 < 88%",
    "raw_feature_order": FEATURES,
    "numeric_features": NUMERIC,
    "categorical_features": CATEGORICAL,
    "selected_C": SELECTED_C,
    "estimator": {
        "class": "sklearn.linear_model.LogisticRegression",
        "penalty": "l2",
        "solver": "liblinear",
        "max_iter": 2000,
        "random_state": RANDOM_STATE,
    },
    "preprocessing": {
        "numeric_imputer": {
            "strategy": "median",
            "add_indicator": True,
            "statistics": [None if np.isnan(x) else float(x) for x in numeric_imputer.statistics_],
            "indicator_feature_indices": (
                numeric_imputer.indicator_.features_.astype(int).tolist()
                if hasattr(numeric_imputer, "indicator_") else []
            ),
        },
        "numeric_scaler": {
            "mean": numeric_scaler.mean_.astype(float).tolist(),
            "scale": numeric_scaler.scale_.astype(float).tolist(),
        },
        "categorical_imputer": {
            "strategy": "most_frequent",
            "statistics": categorical_imputer.statistics_.astype(str).tolist(),
        },
        "onehot": {
            "handle_unknown": "ignore",
            "drop": "first",
            "categories": [x.astype(str).tolist() for x in onehot.categories_],
            "external_constraint": "unknown external categories are not authorized merely because the software can encode them; mapping audit must pass first",
        },
    },
    "transformed_feature_order": feature_names.astype(str).tolist(),
    "intercept": float(model.intercept_[0]),
    "coefficients": model.coef_[0].astype(float).tolist(),
    "claim_boundaries": {
        "pilot": "Only 38 development participants experienced the target event.",
        "subgroups": "Overall external performance cannot resolve the known OpenOx device 60 or MST 8-10 calibration deficits.",
        "BOLD": "No OpenOx device identity or measured pigmentation; race/ethnicity is audit-only.",
        "ENCoDE": "Measured-pigmentation assessment is conditional on harmonization and event support; device 60 cannot be tested.",
        "recalibration": "Any recalibration is model updating and must be reported separately from raw transfer.",
    },
}
coefficients, feature_contract, model_lock
"""))

cells.append(nbf.v4.new_markdown_cell("### 5. Serialize, reload, and verify exact prediction equivalence"))
cells.append(nbf.v4.new_code_cell(
"""joblib.dump(final_pipeline, MODEL_PATH, compress=3)
SPEC_PATH.write_text(json.dumps(scoring_spec, indent=2), encoding="utf-8")

reloaded_pipeline = joblib.load(MODEL_PATH)
reloaded_risk = reloaded_pipeline.predict_proba(data[FEATURES])[:, 1]

qa_checks = {
    **input_checks,
    "selected C is 0.1": SELECTED_C == 0.1,
    "one selected penalty": penalty_selection["selected_for_final_fit"].sum() == 1,
    "pipeline exposes five raw inputs": len(FEATURES) == 5,
    "all coefficients finite": np.isfinite(coefficients["coefficient"]).all(),
    "all apparent risks strictly between zero and one": (
        np.all((apparent_risk > 0) & (apparent_risk < 1))
    ),
    "serialized predictions exactly reproduce": np.array_equal(
        apparent_risk, reloaded_risk
    ),
    "scoring specification matches transformed width": (
        len(scoring_spec["transformed_feature_order"])
        == len(scoring_spec["coefficients"])
    ),
}
assert all(qa_checks.values())
pd.DataFrame({"check": qa_checks.keys(), "pass": qa_checks.values()})
"""))

cells.append(nbf.v4.new_markdown_cell("### 6. Save authoritative lock artifacts and hashes"))
cells.append(nbf.v4.new_code_cell(
"""paths = {
    "model_lock": TABLES / "prediction_final_model_lock.csv",
    "penalty_selection": TABLES / "prediction_final_penalty_selection.csv",
    "coefficients": TABLES / "prediction_final_coefficients.csv",
    "feature_contract": TABLES / "prediction_final_feature_contract.csv",
    "development_summary": TABLES / "prediction_final_development_summary.csv",
    "apparent_checks_only": TABLES / "prediction_final_apparent_checks_only.csv",
    "qa": TABLES / "prediction_final_qa.csv",
    "serialized_pipeline": MODEL_PATH,
    "portable_scoring_spec": SPEC_PATH,
}

model_lock.to_csv(paths["model_lock"], index=False)
penalty_selection.to_csv(paths["penalty_selection"], index=False)
coefficients.to_csv(paths["coefficients"], index=False)
feature_contract.to_csv(paths["feature_contract"], index=False)
development_summary.to_csv(paths["development_summary"], index=False)
apparent_checks_only.to_csv(paths["apparent_checks_only"], index=False)
pd.DataFrame({"check": qa_checks.keys(), "pass": qa_checks.values()}).to_csv(
    paths["qa"], index=False
)

environment = {
    "python": platform.python_version(),
    "numpy": np.__version__,
    "pandas": pd.__version__,
    "scikit_learn": sklearn.__version__,
    "joblib": joblib.__version__,
}
environment_path = MODELS / "openox_compact_occult_ridge_v1_environment.json"
environment_path.write_text(json.dumps(environment, indent=2), encoding="utf-8")
paths["environment"] = environment_path

source_hashes = {
    "analytic_cohort_180s": hashlib.sha256(COHORT_PATH.read_bytes()).hexdigest(),
    "context_covariates_by_pair": hashlib.sha256(CONTEXT_PATH.read_bytes()).hexdigest(),
    "prediction_internal_tuning": hashlib.sha256(TUNING_PATH.read_bytes()).hexdigest(),
}
source_hash_path = TABLES / "prediction_final_source_hashes.csv"
pd.DataFrame(
    [{"source": k, "sha256": v} for k, v in source_hashes.items()]
).to_csv(source_hash_path, index=False)
paths["source_hashes"] = source_hash_path

artifact_manifest = pd.DataFrame([
    {
        "artifact": key,
        "path": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    for key, path in paths.items()
])
manifest_path = TABLES / "prediction_final_artifact_manifest.csv"
artifact_manifest.to_csv(manifest_path, index=False)
artifact_manifest
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Takeaways

- D028 freezes one compact pipeline refit on the complete locked OpenOx development population using `C=0.1`.
- `C=0.1` is selected by aggregate loss across the original 250 frozen inner-validation contexts, not by fold-win plurality and not by external outcomes.
- The serialized pipeline reproduces its in-memory predictions exactly. Its apparent full-sample metrics are software checks only; all internal-performance claims continue to come from nested participant validation.
- No enriched feature, PI-only model, group-specific threshold, or post hoc recalibration is introduced.
- Overall BOLD performance cannot adjudicate the known device 60 or measured-pigmentation calibration deficits. ENCoDE can examine pigmentation only conditionally and cannot test device 60.
- Perfusion evidence is described as cross-analysis convergence, not replicated causality.
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
