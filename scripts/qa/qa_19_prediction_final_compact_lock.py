from pathlib import Path
import hashlib
import json

import joblib
import nbformat
import numpy as np
import pandas as pd


PROJECT = Path(r".")
TABLES = PROJECT / "outputs" / "tables"
MODELS = PROJECT / "outputs" / "models"
PROCESSED = PROJECT / "data" / "processed"
NOTEBOOK = Path(
    r"."
    r"\notebooks\19_prediction_final_compact_lock.ipynb"
)

COHORT = PROCESSED / "analytic_cohort_180s.csv.gz"
CONTEXT = PROCESSED / "context_covariates_by_pair.csv.gz"
TUNING = TABLES / "prediction_internal_tuning.csv"
MODEL = MODELS / "openox_compact_occult_ridge_v1.joblib"
SPEC = MODELS / "openox_compact_occult_ridge_v1_scoring_spec.json"
MANIFEST = TABLES / "prediction_final_artifact_manifest.csv"
OUT = TABLES / "prediction_final_independent_qa.csv"

spec = json.loads(SPEC.read_text(encoding="utf-8"))
pipeline = joblib.load(MODEL)

cohort = pd.read_csv(COHORT)
context = pd.read_csv(
    CONTEXT,
    usecols=[
        "pulse_row_id", "age_at_encounter", "assigned_sex_normalized",
        "heart_rate_consensus", "RR",
    ],
)
data = cohort.merge(context, on="pulse_row_id", how="left", validate="one_to_one")
data = data.loc[data["saturation"].between(92, 96, inclusive="both")].copy()
data["outcome"] = (data["so2"] < 88).astype(int)

features = spec["raw_feature_order"]
software_risk = pipeline.predict_proba(data[features])[:, 1]

# Independent direct implementation of the exported numeric and categorical map.
numeric = data[spec["numeric_features"]].to_numpy(dtype=float)
numeric_spec = spec["preprocessing"]["numeric_imputer"]
medians = np.asarray(numeric_spec["statistics"], dtype=float)
missing = np.isnan(numeric)
numeric_imputed = np.where(missing, medians, numeric)
indicators = missing[:, numeric_spec["indicator_feature_indices"]].astype(float)
numeric_augmented = np.column_stack([numeric_imputed, indicators])
scaler = spec["preprocessing"]["numeric_scaler"]
numeric_scaled = (
    numeric_augmented - np.asarray(scaler["mean"], dtype=float)
) / np.asarray(scaler["scale"], dtype=float)

sex = data["assigned_sex_normalized"].astype("object")
sex = sex.where(sex.notna(), spec["preprocessing"]["categorical_imputer"]["statistics"][0])
categories = spec["preprocessing"]["onehot"]["categories"][0]
assert categories == ["female", "male", "unknown"]
categorical_encoded = np.column_stack([
    sex.eq("male").astype(float).to_numpy(),
    sex.eq("unknown").astype(float).to_numpy(),
])
design = np.column_stack([numeric_scaled, categorical_encoded])
manual_logit = (
    float(spec["intercept"])
    + design @ np.asarray(spec["coefficients"], dtype=float)
)
manual_risk = 1 / (1 + np.exp(-manual_logit))

tuning = pd.read_csv(TUNING)
compact = tuning.loc[tuning["model"].eq("Compact transportable ridge")]
aggregate = (
    compact.groupby("C")
    .agg(
        mean_inner_log_loss=("inner_log_loss", "mean"),
        mean_inner_brier=("inner_brier", "mean"),
    )
    .reset_index()
    .sort_values(["mean_inner_log_loss", "mean_inner_brier", "C"])
)

manifest = pd.read_csv(MANIFEST)
hash_matches = []
for row in manifest.itertuples(index=False):
    actual = hashlib.sha256(Path(row.path).read_bytes()).hexdigest()
    hash_matches.append(actual == row.sha256)

notebook = nbformat.read(NOTEBOOK, as_version=4)
error_outputs = [
    output
    for cell in notebook.cells
    if cell.cell_type == "code"
    for output in cell.get("outputs", [])
    if output.get("output_type") == "error"
]

checks = {
    "development grain independently recovered": (
        len(data) == 6062
        and data["pulse_row_id"].is_unique
        and data["patient_id"].nunique() == 123
    ),
    "event support independently recovered": (
        int(data["outcome"].sum()) == 261
        and data.loc[data["outcome"].eq(1), "patient_id"].nunique() == 38
    ),
    "aggregate tuning independently selects C=0.1": (
        float(aggregate.iloc[0]["C"]) == 0.1
    ),
    "manual scoring matches serialized pipeline": np.allclose(
        manual_risk, software_risk, rtol=0, atol=1e-14
    ),
    "manual design width matches exported coefficients": (
        design.shape[1] == len(spec["coefficients"])
    ),
    "all artifact hashes match manifest": all(hash_matches),
    "executed notebook contains no error outputs": not error_outputs,
}
assert all(checks.values())

qa = pd.DataFrame({"check": checks.keys(), "pass": checks.values()})
qa.to_csv(OUT, index=False)
print(qa.to_string(index=False))
