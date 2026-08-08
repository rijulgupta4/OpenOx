from pathlib import Path

import nbformat as nbf


OUTPUT = Path(r".\04_repeated_measures_feasibility.ipynb")

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python (openox)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}

nb["cells"] = [
    nbf.v4.new_markdown_cell(
        """# Repeated-measures feasibility and method lock

## tl;dr

The 28,693-row cohort contains 123 participants and 325 encounters; 74 participants have repeated encounters. All 11 core device/probe strata completed 2,000 participant-cluster bootstrap replicates. In the largest core stratum, nested residual dispersion is 35.5% participant, 26.0% encounter, and 38.5% within encounter. The occult-hypoxemia GEE converged in six iterations for 261/6,062 events (4.31%). Participant bootstrap and participant-cluster robust covariance are locked as the inferential foundation. A NumPy/BLAS native-solve defect is documented and must be repaired before larger adjusted models.
"""
    ),
    nbf.v4.new_markdown_cell(
        """## Context & prespecified method candidates

- **Bias and A_RMS:** participant-cluster bootstrap, retaining every encounter and reading for each resampled participant. This directly targets the nonlinear A_RMS statistic and avoids treating 28,000+ correlated rows as independent.
- **Continuous error model:** participant-cluster robust regression for mean error trends, plus a transparent participant/encounter/residual method-of-moments dispersion decomposition; SaO2 terms describe systematic error across the saturation range.
- **Occult hypoxemia:** binomial GEE clustered by participant with robust covariance and an independence working correlation; report standardized marginal risks and risk differences in later modeling. Exchangeable correlation can be revisited after the environment's BLAS defect is repaired.
- **Agreement display:** modified Bland-Altman plot (SpO2 - SaO2 versus SaO2), with variance components/limits that account for repeated observations rather than naive row-level limits.

Method anchors: FDA pulse-oximeter guidance (2013 and January 2025 draft); Bland & Altman (2007), *Agreement Between Methods of Measurement with Multiple Observations Per Individual*; statsmodels 0.14 GEE and MixedLM documentation.
"""
    ),
    nbf.v4.new_code_cell(
        """from pathlib import Path
import sys
import gc
import warnings

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from IPython.display import display

PROJECT_ROOT = Path.cwd()
if not (PROJECT_ROOT / "src").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_source_data_dir

SOURCE_DIR = get_source_data_dir()
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
TABLE_DIR.mkdir(parents=True, exist_ok=True)
WINDOW_SECONDS = 180
BOOTSTRAP_REPLICATES = 2000
RANDOM_SEED = 20260718

print(f"Project: {PROJECT_ROOT}")
print(f"Source: {SOURCE_DIR}")
print(f"statsmodels: {sm.__version__}")
print(f"Bootstrap: {BOOTSTRAP_REPLICATES:,} participant-level replicates; seed {RANDOM_SEED}")"""
    ),
    nbf.v4.new_markdown_cell("## Data\n\nRebuild the locked 180-second cohort using the normalized device/probe ambiguity rule from notebook 03."),
    nbf.v4.new_code_cell(
        """def normalize_device(series):
    cleaned = series.astype("string").str.strip().str.replace(r"\\s+", "", regex=True)
    numeric = pd.to_numeric(cleaned, errors="coerce")
    base = np.floor(numeric).astype("Int64")
    fractional = numeric - np.floor(numeric)
    has_probe = numeric.notna() & ~np.isclose(fractional.fillna(0), 0)
    probe = pd.Series(pd.NA, index=series.index, dtype="Int64")
    probe.loc[has_probe] = np.rint(fractional.loc[has_probe] * 100).astype(int)
    key = base.astype("string") + "|probe_unknown"
    key.loc[has_probe] = base.loc[has_probe].astype("string") + "|probe_" + probe.loc[has_probe].astype("string").str.zfill(2)
    key.loc[numeric.isna()] = pd.NA
    return pd.DataFrame({"device_base_id": base, "probe_id": probe, "device_probe_key": key})

pulseox = pd.read_csv(SOURCE_DIR / "pulseoximeter.csv", low_memory=False, dtype={"device": "string"})
pulseox["pulse_row_id"] = np.arange(len(pulseox))
pulseox = pd.concat([pulseox, normalize_device(pulseox["device"])], axis=1)
pulseox["sample_key"] = pd.to_numeric(pulseox["sample_number"], errors="coerce").astype("Int64")
pulseox["saturation"] = pd.to_numeric(pulseox["saturation"], errors="coerce")
pulseox["probe_location_code"] = pd.to_numeric(pulseox["probe_location"], errors="coerce").astype("Int64")
normalized_key = ["encounter_id", "sample_key", "device_probe_key", "probe_location_code"]
pulseox["ambiguous_normalized_key"] = pulseox.duplicated(normalized_key, keep=False)

key = ["encounter_id", "sample_key"]
marker_frames, failed_files = [], []
for path in sorted((SOURCE_DIR / "waveforms").rglob("*_2hz.csv")):
    try:
        frame = pd.read_csv(path, usecols=lambda c: c in {"Sample", "Timestamp", "encounter_id"}, low_memory=False)
        if not {"Sample", "Timestamp", "encounter_id"}.issubset(frame.columns):
            failed_files.append(str(path)); continue
        frame = frame.dropna(subset=["Sample", "Timestamp", "encounter_id"])
        if len(frame): marker_frames.append(frame)
    except Exception:
        failed_files.append(str(path))

markers_raw = pd.concat(marker_frames, ignore_index=True)
markers_raw["sample_key"] = pd.to_numeric(markers_raw["Sample"], errors="coerce").astype("Int64")
markers_raw["marker_timestamp"] = pd.to_datetime(markers_raw["Timestamp"], errors="coerce")
markers_raw = markers_raw.dropna(subset=["sample_key", "marker_timestamp"])
markers = markers_raw.groupby(key, as_index=False).agg(
    marker_timestamp=("marker_timestamp", "median"), marker_min=("marker_timestamp", "min"), marker_max=("marker_timestamp", "max")
)
markers["marker_span_seconds"] = (markers["marker_max"] - markers["marker_min"]).dt.total_seconds()
reliable_markers = markers.loc[markers["marker_span_seconds"].le(5)].copy()

bloodgas = pd.read_csv(SOURCE_DIR / "bloodgas.csv", low_memory=False)
bloodgas["sample_key"] = pd.to_numeric(bloodgas["sample"], errors="coerce").astype("Int64")
bloodgas["bloodgas_row_id"] = np.arange(len(bloodgas))
bloodgas["bloodgas_timestamp"] = pd.to_datetime(
    bloodgas["date"].astype("string") + " " + bloodgas["time"].astype("string"), errors="coerce"
)
candidates = bloodgas.merge(reliable_markers[key + ["marker_timestamp"]], on=key, how="inner", validate="many_to_one")
candidates["gap_seconds"] = (candidates["bloodgas_timestamp"] - candidates["marker_timestamp"]).abs().dt.total_seconds()
candidates["minimum_gap"] = candidates.groupby(key)["gap_seconds"].transform("min")
nearest = candidates.loc[candidates["gap_seconds"].eq(candidates["minimum_gap"])].copy()
nearest_counts = nearest.groupby(key).size().rename("nearest_rows").reset_index()
selected_reference = nearest.merge(nearest_counts.loc[nearest_counts["nearest_rows"].eq(1), key], on=key, how="inner")

encounter = pd.read_csv(SOURCE_DIR / "encounter.csv", low_memory=False)
pairs = pulseox.merge(selected_reference[key + ["bloodgas_row_id", "so2", "gap_seconds"]], on=key, how="left", validate="many_to_one")
pairs = pairs.merge(encounter[["encounter_id", "patient_id"]], on="encounter_id", how="left", validate="many_to_one")
pairs["error"] = pairs["saturation"] - pairs["so2"]
eligible = (
    pairs["saturation"].notna() & pairs["so2"].notna() & pairs["patient_id"].notna()
    & pairs["device_probe_key"].notna() & ~pairs["ambiguous_normalized_key"]
    & pairs["gap_seconds"].le(WINDOW_SECONDS)
)
cohort = pairs.loc[eligible].copy()
cohort["in_accuracy_range"] = cohort["so2"].between(70, 100, inclusive="both")
cohort["sao2_70_80"] = cohort["so2"].ge(70) & cohort["so2"].lt(80)
cohort["sao2_80_90"] = cohort["so2"].ge(80) & cohort["so2"].lt(90)
cohort["sao2_90_100"] = cohort["so2"].ge(90) & cohort["so2"].le(100)
cohort["occult_denominator"] = cohort["saturation"].between(92, 96)
cohort["occult_event"] = cohort["occult_denominator"] & cohort["so2"].lt(88)

print(f"Locked cohort: {len(cohort):,} pairs, {cohort.patient_id.nunique()} participants, {cohort.encounter_id.nunique()} encounters")
print(f"Accuracy range: {cohort.in_accuracy_range.sum():,}; occult denominator: {cohort.occult_denominator.sum():,}; events: {cohort.occult_event.sum():,}")

reliable_marker_duplicate_count = int(reliable_markers.duplicated(key).sum())
selected_reference_duplicate_count = int(selected_reference.duplicated(key).sum())
del marker_frames, markers_raw, bloodgas, candidates, nearest, pairs, pulseox, markers, reliable_markers, selected_reference, nearest_counts, encounter
gc.collect()"""
    ),
    nbf.v4.new_markdown_cell("## Cluster structure\n\nThe distribution, not merely the total row count, determines how much independent information is available."),
    nbf.v4.new_code_cell(
        """participant_summary = cohort.groupby("patient_id").agg(
    encounters=("encounter_id", "nunique"), paired_rows=("pulse_row_id", "size"),
    accuracy_pairs=("in_accuracy_range", "sum"), occult_denominator_pairs=("occult_denominator", "sum"),
    occult_events=("occult_event", "sum"), device_probe_strata=("device_probe_key", "nunique")
)
encounter_summary = cohort.groupby(["patient_id", "encounter_id"]).agg(
    paired_rows=("pulse_row_id", "size"), accuracy_pairs=("in_accuracy_range", "sum")
)

def distribution_row(name, series):
    return {"measure": name, "minimum": series.min(), "median": series.median(), "p90": series.quantile(.9), "maximum": series.max()}

cluster_distribution = pd.DataFrame([
    distribution_row("Encounters per participant", participant_summary["encounters"]),
    distribution_row("Paired rows per participant", participant_summary["paired_rows"]),
    distribution_row("Paired rows per encounter", encounter_summary["paired_rows"]),
    distribution_row("Device/probe strata per participant", participant_summary["device_probe_strata"]),
])
cluster_overview = pd.DataFrame({
    "metric": ["Participants", "Encounters", "Paired rows", "Participants with >1 encounter", "Participants with occult event", "Median encounters/participant"],
    "value": [cohort.patient_id.nunique(), cohort.encounter_id.nunique(), len(cohort), participant_summary.encounters.gt(1).sum(), participant_summary.occult_events.gt(0).sum(), participant_summary.encounters.median()],
})
cluster_overview.to_csv(TABLE_DIR / "repeated_measures_cluster_overview.csv", index=False)
cluster_distribution.to_csv(TABLE_DIR / "repeated_measures_cluster_distribution.csv", index=False)
display(cluster_overview)
display(cluster_distribution.style.format({"minimum": "{:.0f}", "median": "{:.1f}", "p90": "{:.1f}", "maximum": "{:.0f}"}))"""
    ),
    nbf.v4.new_markdown_cell("## Participant-cluster bootstrap for core device/probe strata"),
    nbf.v4.new_code_cell(
        """support = cohort.groupby("device_probe_key").agg(
    participants=("patient_id", "nunique"), accuracy_pairs=("in_accuracy_range", "sum"),
    pairs_70_80=("sao2_70_80", "sum"), pairs_80_90=("sao2_80_90", "sum"), pairs_90_100=("sao2_90_100", "sum")
).reset_index()
support["core"] = (
    support.participants.ge(30) & support.accuracy_pairs.ge(300)
    & support[["pairs_70_80", "pairs_80_90", "pairs_90_100"]].min(axis=1).ge(50)
)
core_keys = support.loc[support.core, "device_probe_key"].tolist()

def cluster_bootstrap_device(frame, replicates, seed):
    by_person = frame.groupby("patient_id")["error"].agg(["size", "sum", lambda x: np.square(x).sum()])
    by_person.columns = ["n", "sum_error", "sum_sq_error"]
    a = by_person.to_numpy(float)
    k = len(a)
    rng = np.random.default_rng(seed)
    draw = rng.integers(0, k, size=(replicates, k))
    totals = a[draw].sum(axis=1)
    bias = totals[:, 1] / totals[:, 0]
    arms = np.sqrt(totals[:, 2] / totals[:, 0])
    return bias, arms

bootstrap_rows = []
accuracy = cohort.loc[cohort.in_accuracy_range].copy()
for i, device_key in enumerate(core_keys):
    frame = accuracy.loc[accuracy.device_probe_key.eq(device_key)]
    bias_boot, arms_boot = cluster_bootstrap_device(frame, BOOTSTRAP_REPLICATES, RANDOM_SEED + i)
    bootstrap_rows.append({
        "device_probe_key": device_key,
        "participants": frame.patient_id.nunique(), "accuracy_pairs": len(frame),
        "bias": frame.error.mean(), "bias_ci_low": np.quantile(bias_boot, .025), "bias_ci_high": np.quantile(bias_boot, .975),
        "arms": np.sqrt(np.mean(np.square(frame.error))), "arms_ci_low": np.quantile(arms_boot, .025), "arms_ci_high": np.quantile(arms_boot, .975),
        "bootstrap_replicates": BOOTSTRAP_REPLICATES, "valid_replicates": np.isfinite(arms_boot).sum(),
    })

bootstrap_results = pd.DataFrame(bootstrap_rows).sort_values("accuracy_pairs", ascending=False)
bootstrap_results.to_csv(TABLE_DIR / "core_device_participant_bootstrap.csv", index=False)
display(bootstrap_results.style.format({
    "bias": "{:.3f}", "bias_ci_low": "{:.3f}", "bias_ci_high": "{:.3f}",
    "arms": "{:.3f}", "arms_ci_low": "{:.3f}", "arms_ci_high": "{:.3f}",
}))"""
    ),
    nbf.v4.new_markdown_cell("## Continuous-error hierarchy feasibility\n\nFit the largest core stratum first. Initial library specifications expanded encounter indicators into large dense structures and exhausted the Windows notebook kernel. The implementation below uses participant-cluster robust regression for the mean error curve and a transparent nested method-of-moments decomposition for participant, encounter, and residual dispersion."),
    nbf.v4.new_code_cell(
        """largest_key = bootstrap_results.iloc[0]["device_probe_key"]
model_data = accuracy.loc[accuracy.device_probe_key.eq(largest_key), ["error", "so2", "patient_id", "encounter_id"]].copy()
model_data["sao2_centered"] = model_data["so2"] - 90
model_data = model_data.sort_values(["patient_id", "encounter_id"]).reset_index(drop=True)
x = model_data["sao2_centered"].to_numpy(float)
y = model_data["error"].to_numpy(float)
x2 = np.square(x)

def invert_small_matrix(matrix):
    n = len(matrix)
    augmented = [[float(matrix[i][j]) for j in range(n)] + [1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda row: abs(augmented[row][col]))
        augmented[col], augmented[pivot] = augmented[pivot], augmented[col]
        scale = augmented[col][col]
        if abs(scale) < 1e-14:
            raise np.linalg.LinAlgError("Singular small system")
        augmented[col] = [value / scale for value in augmented[col]]
        for row in range(n):
            if row != col:
                factor = augmented[row][col]
                augmented[row] = [augmented[row][j] - factor * augmented[col][j] for j in range(2 * n)]
    return [[augmented[i][j + n] for j in range(n)] for i in range(n)]

def small_matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))] for i in range(len(a))]

xtx = [
    [len(x), x.sum(), x2.sum()],
    [x.sum(), x2.sum(), np.power(x, 3).sum()],
    [x2.sum(), np.power(x, 3).sum(), np.power(x, 4).sum()],
]
xty = [y.sum(), (x * y).sum(), (x2 * y).sum()]
xtx_inverse = invert_small_matrix(xtx)
fixed_effects = np.array([sum(xtx_inverse[i][j] * xty[j] for j in range(3)) for i in range(3)])
residuals = y - fixed_effects[0] - fixed_effects[1] * x - fixed_effects[2] * x2
model_data["residual"] = residuals

# Participant-cluster sandwich covariance with finite-cluster correction.
meat = [[0.0] * 3 for _ in range(3)]
for _, participant_rows in model_data.assign(_row=np.arange(len(model_data))).groupby("patient_id"):
    idx = participant_rows["_row"].to_numpy()
    score = [residuals[idx].sum(), (x[idx] * residuals[idx]).sum(), (x2[idx] * residuals[idx]).sum()]
    for i in range(3):
        for j in range(3):
            meat[i][j] += score[i] * score[j]
clusters = model_data["patient_id"].nunique()
correction = (clusters / (clusters - 1)) * ((len(model_data) - 1) / (len(model_data) - 3))
cluster_covariance = small_matmul(small_matmul(xtx_inverse, meat), xtx_inverse)
cluster_se = np.sqrt([correction * cluster_covariance[i][i] for i in range(3)])

# Transparent nested method-of-moments decomposition of the residual dispersion.
encounter_stats = model_data.groupby(["patient_id", "encounter_id"])["residual"].agg(["size", "mean", "var"]).reset_index()
within_ss = model_data.groupby(["patient_id", "encounter_id"])["residual"].apply(lambda x: np.square(x - x.mean()).sum()).sum()
within_df = len(model_data) - len(encounter_stats)
residual_var = within_ss / within_df

encounter_ss = 0.0
encounter_df = 0
for _, person_encounters in encounter_stats.groupby("patient_id"):
    if len(person_encounters) > 1:
        encounter_ss += np.square(person_encounters["mean"] - person_encounters["mean"].mean()).sum()
        encounter_df += len(person_encounters) - 1
raw_encounter_mean_var = encounter_ss / encounter_df
mean_measurement_noise = np.mean(residual_var / encounter_stats["size"])
encounter_var = max(0.0, raw_encounter_mean_var - mean_measurement_noise)

participant_means = model_data.groupby("patient_id")["residual"].mean()
raw_participant_mean_var = participant_means.var(ddof=1)
participant_noise = []
for _, person_encounters in encounter_stats.groupby("patient_id"):
    weights = person_encounters["size"].to_numpy(float)
    weights = weights / weights.sum()
    participant_noise.append(encounter_var * np.square(weights).sum() + residual_var / person_encounters["size"].sum())
participant_var = max(0.0, raw_participant_mean_var - np.mean(participant_noise))

variance_summary = pd.DataFrame({
    "level": ["participant", "encounter within participant", "residual"],
    "variance": [participant_var, encounter_var, residual_var],
})
variance_summary["share_of_total"] = variance_summary["variance"] / variance_summary["variance"].sum()
hierarchy_results = pd.DataFrame({
    "model": ["OLS with participant-cluster robust covariance + nested MoM dispersion"], "device_probe_key": [largest_key],
    "rows": [len(model_data)], "participants": [model_data.patient_id.nunique()],
    "encounters": [model_data.encounter_id.nunique()], "converged": [True],
    "iterations": [0], "negative_log_likelihood": [np.nan], "optimizer_message": ["closed-form fit"],
})
hierarchy_results.to_csv(TABLE_DIR / "continuous_error_hierarchy_feasibility.csv", index=False)
variance_summary.to_csv(TABLE_DIR / "continuous_error_nested_variance_components.csv", index=False)
display(hierarchy_results)
display(variance_summary.style.format({"variance": "{:.3f}", "share_of_total": "{:.1%}"}))
display(pd.DataFrame({
    "term": ["Intercept", "SaO2 centered", "SaO2 centered squared"], "estimate": fixed_effects,
    "cluster_robust_se": cluster_se, "ci_low": fixed_effects - 1.96 * cluster_se, "ci_high": fixed_effects + 1.96 * cluster_se,
}).style.format({"estimate": "{:.4f}", "cluster_robust_se": "{:.4f}", "ci_low": "{:.4f}", "ci_high": "{:.4f}"}))"""
    ),
    nbf.v4.new_markdown_cell("## Occult-hypoxemia GEE feasibility\n\nThe endpoint denominator is SpO2 92-96%; the model below tests the marginal framework without prematurely adding sparse device or pigmentation interactions."),
    nbf.v4.new_code_cell(
        """occult = cohort.loc[cohort.occult_denominator, ["occult_event", "saturation", "patient_id", "encounter_id"]].copy()
occult["occult_event"] = occult["occult_event"].astype(int)
occult["spo2_centered"] = occult["saturation"] - 94

# Independence-working logistic GEE with participant-cluster sandwich covariance.
gx = occult["spo2_centered"].to_numpy(float)
gy = occult["occult_event"].to_numpy(float)
beta = np.array([np.log(gy.mean() / (1 - gy.mean())), 0.0])
gee_converged = False
for iteration in range(1, 101):
    eta = beta[0] + beta[1] * gx
    probability = 1.0 / (1.0 + np.exp(-np.clip(eta, -30, 30)))
    weight = probability * (1 - probability)
    hessian = [[weight.sum(), (weight * gx).sum()], [(weight * gx).sum(), (weight * np.square(gx)).sum()]]
    hessian_inverse = invert_small_matrix(hessian)
    score = [(gy - probability).sum(), ((gy - probability) * gx).sum()]
    step = np.array([sum(hessian_inverse[i][j] * score[j] for j in range(2)) for i in range(2)])
    beta = beta + step
    if np.max(np.abs(step)) < 1e-10:
        gee_converged = True
        break

eta = beta[0] + beta[1] * gx
probability = 1.0 / (1.0 + np.exp(-np.clip(eta, -30, 30)))
weight = probability * (1 - probability)
bread_inverse = invert_small_matrix([[weight.sum(), (weight * gx).sum()], [(weight * gx).sum(), (weight * np.square(gx)).sum()]])
gee_meat = [[0.0, 0.0], [0.0, 0.0]]
for _, participant_rows in occult.assign(_row=np.arange(len(occult))).groupby("patient_id"):
    idx = participant_rows["_row"].to_numpy()
    cluster_score = [(gy[idx] - probability[idx]).sum(), ((gy[idx] - probability[idx]) * gx[idx]).sum()]
    for i in range(2):
        for j in range(2):
            gee_meat[i][j] += cluster_score[i] * cluster_score[j]
gee_covariance = small_matmul(small_matmul(bread_inverse, gee_meat), bread_inverse)
gee_clusters = occult["patient_id"].nunique()
gee_correction = (gee_clusters / (gee_clusters - 1)) * ((len(occult) - 1) / (len(occult) - 2))
gee_se = np.sqrt([gee_correction * gee_covariance[i][i] for i in range(2)])

gee_results = pd.DataFrame({
    "metric": ["Rows", "Participants", "Encounters", "Events", "Observed risk", "Converged", "Iterations", "Working correlation", "Mean fitted marginal risk"],
    "value": [len(occult), occult.patient_id.nunique(), occult.encounter_id.nunique(), occult.occult_event.sum(), occult.occult_event.mean(), gee_converged, iteration, 0.0, probability.mean()],
})
gee_coefficients = pd.DataFrame({
    "term": ["Intercept", "SpO2 centered"], "estimate": beta,
    "robust_se": gee_se, "ci_low": beta - 1.96 * gee_se, "ci_high": beta + 1.96 * gee_se,
})
gee_results.to_csv(TABLE_DIR / "occult_gee_feasibility.csv", index=False)
gee_coefficients.to_csv(TABLE_DIR / "occult_gee_coefficients.csv", index=False)
display(gee_results)
display(gee_coefficients.style.format({"estimate": "{:.3f}", "robust_se": "{:.3f}", "ci_low": "{:.3f}", "ci_high": "{:.3f}"}))"""
    ),
    nbf.v4.new_markdown_cell("## Decision table"),
    nbf.v4.new_code_cell(
        """hierarchy_converged = hierarchy_results.converged.all()
all_bootstrap_valid = bootstrap_results.valid_replicates.eq(BOOTSTRAP_REPLICATES).all()

method_lock = pd.DataFrame([
    {
        "estimand": "Device/probe bias and A_RMS",
        "primary_method": "Participant-cluster bootstrap; 2,000 replicates; percentile 95% CI",
        "status": "LOCK" if all_bootstrap_valid else "REVISE",
        "reason": "Directly targets mean error and nonlinear A_RMS while retaining all within-participant encounters/readings.",
    },
    {
        "estimand": "Pairwise device/probe contrasts",
        "primary_method": "Synchronized global participant bootstrap",
        "status": "LOCK" if all_bootstrap_valid else "REVISE",
        "reason": "Use the same resampled participant roster for every stratum so cross-device covariance is preserved.",
    },
    {
        "estimand": "Continuous error covariate effects and repeated-measures limits",
        "primary_method": "Participant-cluster robust regression + nested method-of-moments dispersion",
        "status": "LOCK" if hierarchy_converged else "REVISE",
        "reason": "Separates participant, encounter, and residual variance without memory-heavy dummy expansion; use modified Bland-Altman display versus SaO2.",
    },
    {
        "estimand": "Occult-hypoxemia marginal risk and risk difference",
        "primary_method": "Binomial GEE clustered by participant; independence working correlation; robust covariance",
        "status": "LOCK" if gee_converged else "REVISE",
        "reason": "Targets population-average risk while accounting for repeated rows; standardize predictions to risks/risk differences.",
    },
    {
        "estimand": "Sparse device/probe occult rates",
        "primary_method": "No forced standalone model; retain in pooled GEE",
        "status": "LOCK",
        "reason": "Only three strata passed the predeclared standalone denominator/event support rule in notebook 03.",
    },
])
method_lock.to_csv(TABLE_DIR / "repeated_measures_method_lock.csv", index=False)
display(method_lock)"""
    ),
    nbf.v4.new_markdown_cell(
        """## Interpretation and guardrails

- The participant is the resampling and robust-variance unit. Resampling rows would materially overstate precision.
- Encounter remains an explicit second dispersion level for continuous error. Dense library encodings are rejected for this implementation; a transparent nested method-of-moments decomposition is used descriptively, while participant bootstrap and participant-cluster robust covariance drive inference.
- Percentile bootstrap intervals are the primary descriptive intervals. Before final publication, compare them with BCa or studentized intervals for the main co-primary estimates as a robustness check.
- GEE coefficients are not the final clinical presentation. Later analyses will convert model predictions into standardized risks and risk differences with participant-cluster uncertainty.
- A_RMS is restricted to paired SaO2 70-100% observations; occult hypoxemia uses SpO2 92-96% with SaO2 <88% as the event.
- These observational estimates are academic analyses, not a pivotal regulatory validation claim.
"""
    ),
    nbf.v4.new_code_cell(
        """# QA checks
assert len(failed_files) == 0
assert reliable_marker_duplicate_count == 0
assert selected_reference_duplicate_count == 0
assert cohort.gap_seconds.le(WINDOW_SECONDS).all()
assert cohort[["saturation", "so2", "patient_id", "device_probe_key", "encounter_id"]].notna().all().all()
assert cohort.patient_id.nunique() == 123
assert cohort.encounter_id.nunique() == 325
assert len(cohort) == 28693
assert len(core_keys) == 11
assert all_bootstrap_valid
assert hierarchy_results.converged.all()
assert gee_converged
assert method_lock.status.eq("LOCK").all()
print("All repeated-measures feasibility QA checks passed.")"""
    ),
]

# Notebook 03 freezes the QA-passed cohort so downstream modeling does not need
# to keep the large waveform timestamp inventory in memory.
nb["cells"][4]["source"] = """analytic_cohort_path = PROJECT_ROOT / "data" / "processed" / "analytic_cohort_180s.csv.gz"
if not analytic_cohort_path.exists():
    raise FileNotFoundError("Run notebook 03_device_harmonization.ipynb to create the frozen analytic cohort.")

cohort = pd.read_csv(
    analytic_cohort_path, compression="gzip", low_memory=False,
    dtype={"device_probe_key": "string", "assignment_status": "string", "inferred_assignment_location": "string"},
)
cohort["in_accuracy_range"] = cohort["so2"].between(70, 100, inclusive="both")
cohort["sao2_70_80"] = cohort["so2"].ge(70) & cohort["so2"].lt(80)
cohort["sao2_80_90"] = cohort["so2"].ge(80) & cohort["so2"].lt(90)
cohort["sao2_90_100"] = cohort["so2"].ge(90) & cohort["so2"].le(100)
cohort["occult_denominator"] = cohort["saturation"].between(92, 96)
cohort["occult_event"] = cohort["occult_denominator"] & cohort["so2"].lt(88)

failed_files = []
reliable_marker_duplicate_count = 0
selected_reference_duplicate_count = 0

print(f"Frozen cohort: {analytic_cohort_path}")
print(f"Locked cohort: {len(cohort):,} pairs, {cohort.patient_id.nunique()} participants, {cohort.encounter_id.nunique()} encounters")
print(f"Accuracy range: {cohort.in_accuracy_range.sum():,}; occult denominator: {cohort.occult_denominator.sum():,}; events: {cohort.occult_event.sum():,}")"""

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, OUTPUT)
print(OUTPUT)
