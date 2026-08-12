from pathlib import Path
import nbformat as nbf


OUT = Path("notebooks") / "14_prediction_small_sample_safeguards.ipynb"
nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell(
"""# OpenOx prediction: rare-event and small-sample safeguards

## tl;dr

This notebook stress-tests the provisional compact occult-hypoxemia model under the frozen participant splits. It evaluates fixed ridge penalties, intercept-corrected Firth logistic regression (FLIC), and 500-replicate participant-cluster bootstrap optimism correction. These are sensitivity analyses; FLIC does not correct within-participant dependence and the bootstrap results are a fixed-specification cross-check rather than a replacement for the primary nested validation.
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Context & Methods

### Key assumptions

- Population and target remain `SpO2 92-96%` and `SaO2 <88%`.
- The compact predictors remain SpO2, age, assigned sex, heart rate, and respiratory rate.
- All outer-fold comparisons use the saved 50-repeat participant allocation.
- Fixed-penalty sensitivity uses `C = 0.01, 0.1, 1, 10` without inner tuning.
- FLIC uses Firth's adjusted score and a post-fit intercept correction that forces mean training prediction to equal training event frequency.
- The cluster bootstrap samples participants with replacement and carries all of each sampled participant's readings.
- Bootstrap optimism is calculated for fixed `C=0.1` and `C=1` specifications because the nested run selected both frequently; this avoids pretending that one penalty was already final.

Method anchors: Puhr et al., *Statistics in Medicine* 2017, DOI 10.1002/sim.7273; TRIPOD explanation and elaboration, *Annals of Internal Medicine* 2015.
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

from scipy.optimize import brentq, minimize
from scipy.special import expit
from scipy import sparse
from scipy.linalg import qr
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, log_loss, roc_auc_score
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
sns.set_theme(style="whitegrid")

PROJECT = Path(r".")
TABLES = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
PROCESSED = PROJECT / "data" / "processed"

COHORT_PATH = PROCESSED / "analytic_cohort_180s.csv.gz"
CONTEXT_PATH = PROCESSED / "context_covariates_by_pair.csv.gz"
OUTER_PATH = TABLES / "prediction_outer_fold_assignments.csv.gz"
PRIMARY_PREDICTIONS_PATH = TABLES / "prediction_internal_oof_predictions.csv.gz"

C_GRID = [0.01, 0.1, 1.0, 10.0]
BOOTSTRAP_C = [0.1, 1.0]
BOOTSTRAP_REPLICATES = 500
BOOTSTRAP_SEED = 20260727
NUMERIC = ["saturation", "age_at_encounter", "heart_rate_consensus", "RR"]
CATEGORICAL = ["assigned_sex_normalized"]
FEATURES = NUMERIC + CATEGORICAL
"""))

cells.append(nbf.v4.new_markdown_cell("## Data\n\n### 1. Reconstruct and verify the sealed prediction population"))
cells.append(nbf.v4.new_code_cell(
"""cohort = pd.read_csv(COHORT_PATH)
context = pd.read_csv(
    CONTEXT_PATH,
    usecols=["pulse_row_id", "age_at_encounter", "assigned_sex_normalized",
             "heart_rate_consensus", "RR"],
)
assert cohort["pulse_row_id"].is_unique and context["pulse_row_id"].is_unique
data = cohort.merge(context, on="pulse_row_id", how="left", validate="one_to_one")
data = data.loc[data["saturation"].between(92, 96, inclusive="both")].copy()
data["outcome"] = (data["so2"] < 88).astype(int)

outer = pd.read_csv(OUTER_PATH)
primary_predictions = pd.read_csv(PRIMARY_PREDICTIONS_PATH)
primary_compact = primary_predictions.loc[
    primary_predictions["model"].eq("Compact transportable ridge")
].copy()

assert len(data) == 6062
assert data["outcome"].sum() == 261
assert data["patient_id"].nunique() == 123
assert primary_compact.groupby("repeat").size().eq(len(data)).all()

pd.DataFrame({
    "item": ["readings", "events", "participants", "event-positive participants"],
    "value": [len(data), data["outcome"].sum(), data["patient_id"].nunique(),
              data.loc[data["outcome"].eq(1), "patient_id"].nunique()],
})
"""))

cells.append(nbf.v4.new_markdown_cell("## Results\n\n### 2. Define fold-contained ridge and FLIC estimators"))
cells.append(nbf.v4.new_code_cell(
"""def make_preprocessor():
    return ColumnTransformer([
        ("numeric", Pipeline([
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
        ]), NUMERIC),
        ("categorical", Pipeline([
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", drop="first")),
        ]), CATEGORICAL),
    ])


def make_ridge(C):
    return Pipeline([
        ("preprocess", make_preprocessor()),
        ("model", LogisticRegression(
            penalty="l2", C=C, solver="liblinear", max_iter=2000,
            random_state=20260727
        )),
    ])


def dense(matrix):
    return matrix.toarray() if sparse.issparse(matrix) else np.asarray(matrix)


def firth_penalized_loglik(X, y, beta):
    eta = X @ beta
    p = np.clip(expit(eta), 1e-12, 1 - 1e-12)
    w = p * (1 - p)
    info = X.T @ (w[:, None] * X)
    sign, logdet = np.linalg.slogdet(info)
    if sign <= 0:
        return -np.inf
    return float(np.sum(y * eta - np.logaddexp(0, eta)) + 0.5 * logdet)


def firth_adjusted_score(X, y, beta):
    eta = X @ beta
    p = np.clip(expit(eta), 1e-10, 1 - 1e-10)
    w = p * (1 - p)
    info_inv = np.linalg.pinv(X.T @ (w[:, None] * X), rcond=1e-10)
    leverage = w * np.einsum("ij,jk,ik->i", X, info_inv, X)
    return X.T @ (y - p + leverage * (0.5 - p))


def fit_firth(X, y, score_tolerance=1e-3, max_iter=2000):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    result = minimize(
        fun=lambda beta: -firth_penalized_loglik(X, y, beta),
        x0=np.zeros(X.shape[1]),
        jac=lambda beta: -firth_adjusted_score(X, y, beta),
        method="L-BFGS-B",
        options={"maxiter": max_iter, "ftol": 1e-12, "gtol": 1e-8, "maxls": 100},
    )
    beta = result.x
    score = firth_adjusted_score(X, y, beta)
    max_adjusted_score = float(np.max(np.abs(score)))
    converged = bool(np.isfinite(beta).all() and max_adjusted_score < score_tolerance)
    return {
        "beta": beta, "converged": converged, "iterations": result.nit,
        "max_adjusted_score": max_adjusted_score,
    }


def fit_flic(preprocessor, train):
    Z_full = dense(preprocessor.fit_transform(train[FEATURES]))
    # Fold-specific imputers can emit an all-zero missingness indicator.
    # Remove zero-variance columns so the Jeffreys information determinant is
    # defined on a full-rank design.
    nonconstant = np.flatnonzero(np.nanstd(Z_full, axis=0) > 1e-12)
    centered = Z_full[:, nonconstant] - Z_full[:, nonconstant].mean(axis=0)
    _, r_matrix, pivots = qr(centered, mode="economic", pivoting=True)
    tolerance = np.max(centered.shape) * np.finfo(float).eps * abs(r_matrix[0, 0])
    rank = int(np.sum(np.abs(np.diag(r_matrix)) > tolerance))
    selected = nonconstant[pivots[:rank]]
    active_columns = np.zeros(Z_full.shape[1], dtype=bool)
    active_columns[selected] = True
    Z = Z_full[:, active_columns]
    X = np.column_stack([np.ones(len(Z)), Z])
    fitted = fit_firth(X, train["outcome"].to_numpy())
    slopes = fitted["beta"][1:]
    linear_without_intercept = Z @ slopes
    target_events = train["outcome"].sum()
    intercept = brentq(
        lambda value: expit(value + linear_without_intercept).sum() - target_events,
        -50, 50
    )
    fitted["intercept_flic"] = float(intercept)
    fitted["training_mean_prediction"] = float(
        expit(intercept + linear_without_intercept).mean()
    )
    fitted["active_columns"] = active_columns
    return fitted


def predict_flic(preprocessor, fitted, frame):
    Z = dense(preprocessor.transform(frame[FEATURES]))[:, fitted["active_columns"]]
    return expit(fitted["intercept_flic"] + Z @ fitted["beta"][1:])


def metrics(y, p):
    return {
        "brier": brier_score_loss(y, p),
        "log_loss": log_loss(y, p, labels=[0, 1]),
        "pr_auc": average_precision_score(y, p),
        "roc_auc": roc_auc_score(y, p),
        "mean_predicted": float(np.mean(p)),
    }
"""))

cells.append(nbf.v4.new_markdown_cell("### 3. Unit-test the Firth and FLIC implementation"))
cells.append(nbf.v4.new_code_cell(
"""synthetic_X = np.column_stack([
    np.ones(12),
    np.array([-3, -2, -1.5, -1, -.5, -.2, .2, .5, 1, 1.5, 2, 3]),
])
synthetic_y = np.array([0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1])
synthetic_fit = fit_firth(synthetic_X, synthetic_y)
synthetic_slopes = synthetic_fit["beta"][1:]
synthetic_lp = synthetic_X[:, 1:] @ synthetic_slopes
synthetic_intercept = brentq(
    lambda a: expit(a + synthetic_lp).sum() - synthetic_y.sum(), -50, 50
)
synthetic_mean = expit(synthetic_intercept + synthetic_lp).mean()

algorithm_qa = {
    "separated synthetic fit converges": synthetic_fit["converged"],
    "synthetic coefficients are finite": np.isfinite(synthetic_fit["beta"]).all(),
    "adjusted score is small": synthetic_fit["max_adjusted_score"] < 1e-5,
    "FLIC mean equals event rate": abs(synthetic_mean - synthetic_y.mean()) < 1e-10,
}
assert all(algorithm_qa.values())
pd.DataFrame({"check": algorithm_qa.keys(), "pass": algorithm_qa.values()})
"""))

cells.append(nbf.v4.new_markdown_cell("### 4. Run fixed-penalty and FLIC outer validation"))
cells.append(nbf.v4.new_code_cell(
"""fixed_parts = []
flic_parts = []
flic_diagnostics = []

for repeat in sorted(outer["repeat"].unique()):
    repeat_map = outer.loc[outer["repeat"].eq(repeat)]
    for fold in sorted(repeat_map["fold"].unique()):
        validation_patients = set(
            repeat_map.loc[repeat_map["fold"].eq(fold), "patient_id"]
        )
        train = data.loc[~data["patient_id"].isin(validation_patients)]
        validation = data.loc[data["patient_id"].isin(validation_patients)]

        for C in C_GRID:
            ridge = make_ridge(C)
            ridge.fit(train[FEATURES], train["outcome"])
            fixed_parts.append(pd.DataFrame({
                "repeat": repeat, "outer_fold": fold, "C": C,
                "patient_id": validation["patient_id"].to_numpy(),
                "pulse_row_id": validation["pulse_row_id"].to_numpy(),
                "outcome": validation["outcome"].to_numpy(),
                "predicted_risk": ridge.predict_proba(validation[FEATURES])[:, 1],
            }))

        preprocessor = make_preprocessor()
        flic_fit = fit_flic(preprocessor, train)
        flic_parts.append(pd.DataFrame({
            "repeat": repeat, "outer_fold": fold,
            "patient_id": validation["patient_id"].to_numpy(),
            "pulse_row_id": validation["pulse_row_id"].to_numpy(),
            "outcome": validation["outcome"].to_numpy(),
            "predicted_risk": predict_flic(preprocessor, flic_fit, validation),
        }))
        flic_diagnostics.append({
            "repeat": repeat, "outer_fold": fold,
            "converged": flic_fit["converged"],
            "iterations": flic_fit["iterations"],
            "max_adjusted_score": flic_fit["max_adjusted_score"],
            "training_event_rate": train["outcome"].mean(),
            "training_mean_prediction": flic_fit["training_mean_prediction"],
        })

fixed_predictions = pd.concat(fixed_parts, ignore_index=True)
flic_predictions = pd.concat(flic_parts, ignore_index=True)
flic_diagnostics = pd.DataFrame(flic_diagnostics)

assert fixed_predictions.groupby(["C", "repeat"]).size().eq(len(data)).all()
assert flic_predictions.groupby("repeat").size().eq(len(data)).all()
assert flic_diagnostics["converged"].all()
assert np.allclose(
    flic_diagnostics["training_event_rate"],
    flic_diagnostics["training_mean_prediction"],
    atol=1e-10,
)
fixed_predictions.shape, flic_predictions.shape, flic_diagnostics.describe()
"""))

cells.append(nbf.v4.new_markdown_cell("### 5. Compare fixed penalties, nested ridge, and FLIC"))
cells.append(nbf.v4.new_code_cell(
"""repeat_rows = []
for (C, repeat), frame in fixed_predictions.groupby(["C", "repeat"]):
    row = metrics(frame["outcome"], frame["predicted_risk"])
    row.update({"method": f"Fixed ridge C={C:g}", "repeat": repeat})
    repeat_rows.append(row)
for repeat, frame in flic_predictions.groupby("repeat"):
    row = metrics(frame["outcome"], frame["predicted_risk"])
    row.update({"method": "FLIC", "repeat": repeat})
    repeat_rows.append(row)
for repeat, frame in primary_compact.groupby("repeat"):
    row = metrics(frame["outcome"], frame["predicted_risk"])
    row.update({"method": "Nested-tuned ridge", "repeat": repeat})
    repeat_rows.append(row)
safeguard_metrics = pd.DataFrame(repeat_rows)

safeguard_summary = (
    safeguard_metrics.groupby("method")
    .agg(
        brier=("brier", "median"),
        log_loss=("log_loss", "median"),
        pr_auc=("pr_auc", "median"),
        roc_auc=("roc_auc", "median"),
        mean_predicted=("mean_predicted", "median"),
    )
    .sort_values("log_loss")
)
safeguard_summary
"""))

cells.append(nbf.v4.new_markdown_cell("### 6. Run 500-replicate participant-cluster bootstrap optimism checks"))
cells.append(nbf.v4.new_code_cell(
"""rng = np.random.default_rng(BOOTSTRAP_SEED)
participants = data["patient_id"].drop_duplicates().to_numpy()
rows_by_participant = {
    patient: data.index[data["patient_id"].eq(patient)].to_numpy()
    for patient in participants
}

bootstrap_rows = []
full_fit_rows = []
for C in BOOTSTRAP_C:
    original_model = make_ridge(C)
    original_model.fit(data[FEATURES], data["outcome"])
    original_prediction = original_model.predict_proba(data[FEATURES])[:, 1]
    apparent = metrics(data["outcome"], original_prediction)
    full_fit_rows.append({"C": C, **apparent})

    for replicate in range(BOOTSTRAP_REPLICATES):
        sampled = rng.choice(participants, size=len(participants), replace=True)
        bootstrap_indices = np.concatenate([rows_by_participant[p] for p in sampled])
        bootstrap_data = data.loc[bootstrap_indices]
        model = make_ridge(C)
        model.fit(bootstrap_data[FEATURES], bootstrap_data["outcome"])
        bootstrap_prediction = model.predict_proba(bootstrap_data[FEATURES])[:, 1]
        test_prediction = model.predict_proba(data[FEATURES])[:, 1]
        apparent_boot = metrics(bootstrap_data["outcome"], bootstrap_prediction)
        test_original = metrics(data["outcome"], test_prediction)
        bootstrap_rows.append({
            "C": C, "replicate": replicate,
            **{f"bootstrap_{key}": value for key, value in apparent_boot.items()},
            **{f"test_{key}": value for key, value in test_original.items()},
        })

bootstrap_results = pd.DataFrame(bootstrap_rows)
full_fit = pd.DataFrame(full_fit_rows)

optimism_rows = []
for C, frame in bootstrap_results.groupby("C"):
    apparent = full_fit.loc[full_fit["C"].eq(C)].iloc[0]
    row = {"C": C}
    for metric in ["brier", "log_loss", "pr_auc", "roc_auc"]:
        optimism = (frame[f"bootstrap_{metric}"] - frame[f"test_{metric}"]).mean()
        row[f"apparent_{metric}"] = apparent[metric]
        row[f"mean_optimism_{metric}"] = optimism
        row[f"corrected_{metric}"] = apparent[metric] - optimism
    optimism_rows.append(row)
optimism_summary = pd.DataFrame(optimism_rows)
optimism_summary
"""))

cells.append(nbf.v4.new_markdown_cell("### 7. QA and visualization"))
cells.append(nbf.v4.new_code_cell(
"""qa = {
    "fixed predictions complete": (
        fixed_predictions.groupby(["C", "repeat", "pulse_row_id"]).size().eq(1).all()
    ),
    "FLIC predictions complete": (
        flic_predictions.groupby(["repeat", "pulse_row_id"]).size().eq(1).all()
    ),
    "all FLIC fits converged": flic_diagnostics["converged"].all(),
    "FLIC training means corrected": np.allclose(
        flic_diagnostics["training_event_rate"],
        flic_diagnostics["training_mean_prediction"], atol=1e-10
    ),
    "1,000 bootstrap refits complete": len(bootstrap_results) == 1000,
    "bootstrap metrics finite": np.isfinite(
        bootstrap_results.select_dtypes(include=[np.number])
    ).all().all(),
}
assert all(qa.values())

fig, axes = plt.subplots(2, 2, figsize=(12, 9))
order = safeguard_summary.index.tolist()
sns.boxplot(data=safeguard_metrics, x="method", y="log_loss", order=order,
            ax=axes[0, 0], color="#5b8db8")
axes[0, 0].set(title="Repeat-level log loss", xlabel="", ylabel="Log loss")
axes[0, 0].tick_params(axis="x", rotation=25)
sns.boxplot(data=safeguard_metrics, x="method", y="pr_auc", order=order,
            ax=axes[0, 1], color="#4f9d82")
axes[0, 1].set(title="Repeat-level PR-AUC", xlabel="", ylabel="PR-AUC")
axes[0, 1].tick_params(axis="x", rotation=25)

loss_plot = optimism_summary.melt(
    id_vars="C",
    value_vars=["apparent_brier", "corrected_brier",
                "apparent_log_loss", "corrected_log_loss"],
    var_name="estimate", value_name="value"
)
sns.barplot(data=loss_plot, x="estimate", y="value", hue="C", ax=axes[1, 0])
axes[1, 0].set(title="Cluster-bootstrap optimism correction: loss", xlabel="", ylabel="Value")
axes[1, 0].tick_params(axis="x", rotation=25)

auc_plot = optimism_summary.melt(
    id_vars="C",
    value_vars=["apparent_pr_auc", "corrected_pr_auc",
                "apparent_roc_auc", "corrected_roc_auc"],
    var_name="estimate", value_name="value"
)
sns.barplot(data=auc_plot, x="estimate", y="value", hue="C", ax=axes[1, 1])
axes[1, 1].set(title="Cluster-bootstrap optimism correction: ranking", xlabel="", ylabel="Value")
axes[1, 1].tick_params(axis="x", rotation=25)

fig.suptitle("OpenOx compact model: rare-event and small-sample safeguards",
             fontweight="bold")
fig.tight_layout()
figure_path = FIGURES / "prediction_small_sample_safeguards.png"
fig.savefig(figure_path, dpi=180, bbox_inches="tight")
plt.show()

pd.DataFrame({"check": qa.keys(), "pass": qa.values()})
"""))

cells.append(nbf.v4.new_markdown_cell("### 8. Save authoritative safeguard artifacts"))
cells.append(nbf.v4.new_code_cell(
"""paths = {
    "fixed_predictions": TABLES / "prediction_safeguard_fixed_penalty_oof.csv.gz",
    "flic_predictions": TABLES / "prediction_safeguard_flic_oof.csv.gz",
    "flic_diagnostics": TABLES / "prediction_safeguard_flic_diagnostics.csv",
    "repeat_metrics": TABLES / "prediction_safeguard_repeat_metrics.csv",
    "summary": TABLES / "prediction_safeguard_summary.csv",
    "bootstrap_results": TABLES / "prediction_safeguard_cluster_bootstrap.csv.gz",
    "optimism_summary": TABLES / "prediction_safeguard_optimism_summary.csv",
    "qa": TABLES / "prediction_safeguard_qa.csv",
}
fixed_predictions.to_csv(paths["fixed_predictions"], index=False, compression="gzip")
flic_predictions.to_csv(paths["flic_predictions"], index=False, compression="gzip")
flic_diagnostics.to_csv(paths["flic_diagnostics"], index=False)
safeguard_metrics.to_csv(paths["repeat_metrics"], index=False)
safeguard_summary.reset_index().to_csv(paths["summary"], index=False)
bootstrap_results.to_csv(paths["bootstrap_results"], index=False, compression="gzip")
optimism_summary.to_csv(paths["optimism_summary"], index=False)
pd.DataFrame({"check": qa.keys(), "pass": qa.values()}).to_csv(paths["qa"], index=False)

manifest = pd.DataFrame([
    {"artifact": name, "path": str(path),
     "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    for name, path in paths.items()
])
manifest.to_csv(TABLES / "prediction_safeguard_artifact_manifest.csv", index=False)
manifest
"""))

cells.append(nbf.v4.new_markdown_cell(
"""## Takeaways

- Stability across fixed ridge penalties indicates whether the nested result depends on tuning noise.
- FLIC is a finite-sample/separation sensitivity. Agreement with ridge strengthens the direction of evidence; disagreement is diagnostically important.
- Participant-cluster bootstrap correction estimates optimism for two fixed ridge specifications and preserves the participant as the resampling unit.
- Neither FLIC nor bootstrap transforms this controlled-desaturation pilot model into a clinically validated diagnostic tool.
"""))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {"display_name": "Python (openox)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}
nbf.write(nb, OUT)
print(OUT)
