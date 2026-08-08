from pathlib import Path

import nbformat as nbf


OUT = Path(r".\09_pigmentation_non_disparate.ipynb")

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12"},
}

cells = []
cells.append(
    nbf.v4.new_markdown_cell(
        r"""# Pigmentation and non-disparate-performance analysis

## tl;dr

This notebook opens the outcomes only after the D013 pigmentation measures, saturation intervals, support rules, estimands, and research benchmark margins were frozen. It estimates:

1. the largest adjusted absolute mean-bias difference among forehead Monk Skin Tone (MST) groups 1-4, 5-7, and 8-10; and
2. the adjusted mean-bias difference over a 100-degree emitter-site Individual Typology Angle (ITA) change.

Both are estimated separately at SaO2 70-85% and >85-100%. Models adjust for a quadratic SaO2 mean curve and use participant-cluster robust covariance. A complete device-level non-disparate-performance conclusion is available only when all four prespecified components are supported and each simultaneous/two-sided 95% upper bound falls below its interval-specific margin (3.5 points at SaO2 70-85%; 1.5 points at >85-100%).

These are retrospective academic research benchmarks, not regulatory determinations."""
    )
)

cells.append(
    nbf.v4.new_markdown_cell(
        r"""## Locked interpretation safeguards

- Error remains `SpO2 - SaO2`; positive values mean pulse-oximeter overestimation.
- Primary estimates are pair-weighted. Participant-balanced models are sensitivity analyses under D015.
- MST inference uses a simultaneous confidence bound across its three pairwise contrasts so the largest observed contrast is not selected without multiplicity protection.
- The final intersection-union conclusion requires all four co-primary components to meet their benchmark.
- Failure to demonstrate the benchmark is separated into **difference exceeds benchmark** versus **inconclusive**.
- Device codes remain opaque, and results are conditional on a recorded, time-pairable SpO2 reading."""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        r"""from pathlib import Path
import itertools
import warnings

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.formula.api as smf
from patsy import build_design_matrices

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.max_columns", 100)
pd.set_option("display.width", 180)

PROJECT = Path(r".")
PROCESSED = PROJECT / "data" / "processed"
TABLES = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
TABLES.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

COHORT_PATH = PROCESSED / "analytic_cohort_180s.csv.gz"
PIGMENT_PATH = PROCESSED / "pigmentation_covariates_by_pair.csv.gz"
SUPPORT_PATH = TABLES / "pigmentation_device_support.csv"

CORE_DEVICES = [
    "21|probe_unknown", "55|probe_03", "59|probe_unknown", "60|probe_unknown",
    "64|probe_unknown", "71|probe_unknown", "73|probe_unknown", "75|probe_01",
    "78|probe_unknown", "79|probe_unknown", "81|probe_unknown",
]
MST_LEVELS = ["1-4", "5-7", "8-10"]
INTERVALS = {
    "SaO2 70-85%": (70, 85, 3.5),
    "SaO2 >85-100%": (85, 100, 1.5),
}
RNG_SEED = 20260723

print("Project:", PROJECT)
print("Primary estimand: pair-weighted adjusted mean SpO2 - SaO2 error")
print("Cluster unit: participant")"""
    )
)

cells.append(
    nbf.v4.new_markdown_cell(
        r"""## Merge the frozen cohort and predictor-only pigmentation map

The merge must preserve exactly one row per frozen `pulse_row_id`. The stored error identity is also rechecked before any model is fit."""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        r"""cohort = pd.read_csv(COHORT_PATH)
pig = pd.read_csv(PIGMENT_PATH)
support = pd.read_csv(SUPPORT_PATH)

assert len(cohort) == 28_693
assert cohort["pulse_row_id"].is_unique
assert len(pig) == 28_693
assert pig["pulse_row_id"].is_unique

pig_predictors = pig.drop(columns=["patient_id", "encounter_id"], errors="ignore")
df = cohort.merge(pig_predictors, on="pulse_row_id", how="left", validate="one_to_one")

assert len(df) == len(cohort)
assert df["pulse_row_id"].is_unique
assert np.allclose(df["error"], df["saturation"] - df["so2"], equal_nan=True)
assert df["patient_id"].equals(cohort["patient_id"])
assert df["encounter_id"].equals(cohort["encounter_id"])

accuracy = df.loc[
    df["device_probe_key"].isin(CORE_DEVICES) & df["so2"].between(70, 100, inclusive="both")
].copy()
accuracy["mst_group"] = pd.Categorical(accuracy["mst_group"], categories=MST_LEVELS, ordered=True)

merge_summary = pd.DataFrame({
    "check": [
        "Frozen rows preserved", "Pair key unique", "Error identity preserved",
        "Participant identity preserved", "Core devices reproduced"
    ],
    "passed": [
        len(df) == 28_693,
        df["pulse_row_id"].is_unique,
        bool(np.allclose(df["error"], df["saturation"] - df["so2"], equal_nan=True)),
        df["patient_id"].equals(cohort["patient_id"]),
        set(accuracy["device_probe_key"].unique()) == set(CORE_DEVICES),
    ],
})
display(merge_summary)
print(f"Core accuracy rows: {len(accuracy):,}; participants: {accuracy.patient_id.nunique():,}")"""
    )
)

cells.append(
    nbf.v4.new_markdown_cell(
        r"""## Modeling functions

Within each supported device/probe stratum and saturation interval, the mean error curve is adjusted with centered linear and quadratic SaO2 terms. Ordinary least squares point estimates are paired with participant-cluster robust covariance. Standardized MST group means are averaged over the device/interval's empirical SaO2 distribution.

For MST, a correlated-normal simulation of the participant-cluster covariance produces a simultaneous critical value across all three pairwise contrasts. The benchmark comparison therefore uses the upper bound for the maximum absolute contrast, not the most favorable individual comparison."""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        r"""def interval_subset(data, label):
    lo, hi, margin = INTERVALS[label]
    if label == "SaO2 70-85%":
        out = data.loc[data["so2"].between(lo, hi, inclusive="both")].copy()
    else:
        out = data.loc[(data["so2"] > lo) & (data["so2"] <= hi)].copy()
    out["so2_c"] = out["so2"] - out["so2"].mean()
    return out, margin


def fit_cluster_formula(formula, data, participant_balanced=False):
    if participant_balanced:
        counts = data.groupby("patient_id")["patient_id"].transform("size")
        model = smf.wls(formula, data=data, weights=1.0 / counts)
    else:
        model = smf.ols(formula, data=data)
    return model.fit(
        cov_type="cluster",
        cov_kwds={"groups": data["patient_id"], "use_correction": True},
    )


def design_average(result, new_data):
    design = np.asarray(
        build_design_matrices([result.model.data.design_info], new_data, return_type="dataframe")[0]
    )
    return design.mean(axis=0)


def safe_cov(cov):
    cov = np.asarray(cov, dtype=float)
    cov = (cov + cov.T) / 2
    vals, vecs = np.linalg.eigh(cov)
    vals = np.clip(vals, 1e-12, None)
    return (vecs * vals) @ vecs.T


def status_from_bounds(lower_abs, upper_abs, margin):
    if upper_abs < margin:
        return "Meets benchmark"
    if lower_abs > margin:
        return "Difference exceeds benchmark"
    return "Inconclusive"


def fit_mst(data, device, interval, participant_balanced=False, simulations=50_000):
    sub, margin = interval_subset(data.loc[data["device_probe_key"] == device], interval)
    sub = sub.dropna(subset=["mst_group", "error", "so2", "patient_id"]).copy()
    sub["mst_group"] = pd.Categorical(sub["mst_group"], categories=MST_LEVELS, ordered=True)
    result = fit_cluster_formula(
        'error ~ C(mst_group, Treatment(reference="1-4")) + so2_c + I(so2_c ** 2)',
        sub,
        participant_balanced=participant_balanced,
    )

    group_rows = []
    Ls = {}
    params = np.asarray(result.params)
    cov = np.asarray(result.cov_params())
    for group in MST_LEVELS:
        counterfactual = sub.copy()
        counterfactual["mst_group"] = pd.Categorical(
            [group] * len(counterfactual), categories=MST_LEVELS, ordered=True
        )
        L = design_average(result, counterfactual)
        Ls[group] = L
        estimate = float(L @ params)
        se = float(np.sqrt(max(L @ cov @ L, 0)))
        group_rows.append({
            "device_probe_key": device, "interval": interval, "mst_group": group,
            "adjusted_bias": estimate, "se": se,
            "ci_low": estimate - 1.96 * se, "ci_high": estimate + 1.96 * se,
            "pairs": len(sub), "participants": sub["patient_id"].nunique(),
            "weighting": "participant-balanced" if participant_balanced else "pair-weighted",
        })

    pair_names, C = [], []
    for a, b in itertools.combinations(MST_LEVELS, 2):
        pair_names.append(f"{a} minus {b}")
        C.append(Ls[a] - Ls[b])
    C = np.vstack(C)
    deltas = C @ params
    contrast_cov = safe_cov(C @ cov @ C.T)
    ses = np.sqrt(np.diag(contrast_cov))

    corr = contrast_cov / np.outer(ses, ses)
    corr = safe_cov(corr)
    rng = np.random.default_rng(RNG_SEED + sum(map(ord, device + interval)) + int(participant_balanced))
    z = rng.multivariate_normal(np.zeros(len(pair_names)), corr, size=simulations)
    critical = float(np.quantile(np.max(np.abs(z), axis=1), 0.95))
    max_abs = float(np.max(np.abs(deltas)))
    simultaneous_upper = float(np.max(np.abs(deltas) + critical * ses))
    simultaneous_lower = float(np.max(np.maximum(0, np.abs(deltas) - critical * ses)))

    pair_rows = []
    for name, delta, se in zip(pair_names, deltas, ses):
        pair_rows.append({
            "device_probe_key": device, "interval": interval, "contrast": name,
            "difference": float(delta), "se": float(se),
            "ci_low": float(delta - 1.96 * se), "ci_high": float(delta + 1.96 * se),
            "weighting": "participant-balanced" if participant_balanced else "pair-weighted",
        })

    summary = {
        "device_probe_key": device, "interval": interval,
        "pairs": len(sub), "participants": sub["patient_id"].nunique(),
        "max_abs_difference": max_abs,
        "simultaneous_lower_abs": simultaneous_lower,
        "simultaneous_upper_abs": simultaneous_upper,
        "simultaneous_critical_value": critical,
        "margin": margin,
        "status": status_from_bounds(simultaneous_lower, simultaneous_upper, margin),
        "weighting": "participant-balanced" if participant_balanced else "pair-weighted",
        "model_converged": True,
    }
    return group_rows, pair_rows, summary


def fit_ita(data, device, interval, ita_col="emitter_site_ita", participant_balanced=False):
    sub, margin = interval_subset(data.loc[data["device_probe_key"] == device], interval)
    sub = sub.dropna(subset=[ita_col, "error", "so2", "patient_id"]).copy()
    sub["ita_per_100"] = sub[ita_col] / 100.0
    result = fit_cluster_formula(
        "error ~ ita_per_100 + so2_c + I(so2_c ** 2)",
        sub,
        participant_balanced=participant_balanced,
    )
    beta = float(result.params["ita_per_100"])
    se = float(result.bse["ita_per_100"])
    lower_abs = max(0.0, abs(beta) - 1.96 * se)
    upper_abs = abs(beta) + 1.96 * se
    return {
        "device_probe_key": device, "interval": interval, "ita_measure": ita_col,
        "pairs": len(sub), "participants": sub["patient_id"].nunique(),
        "ita_min": sub[ita_col].min(), "ita_max": sub[ita_col].max(),
        "difference_per_100_degrees": beta, "se": se,
        "ci_low": beta - 1.96 * se, "ci_high": beta + 1.96 * se,
        "lower_abs": lower_abs, "upper_abs": upper_abs, "margin": margin,
        "status": status_from_bounds(lower_abs, upper_abs, margin),
        "weighting": "participant-balanced" if participant_balanced else "pair-weighted",
        "model_converged": True,
    }"""
    )
)

cells.append(
    nbf.v4.new_markdown_cell(
        r"""## Primary device-specific MST analysis

Only the seven strata that passed the predictor-only D013 support rule receive standalone MST benchmark estimates."""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        r"""mst_devices = support.loc[support["standalone_mst_supported"], "device_probe_key"].tolist()
mst_group_rows, mst_pair_rows, mst_summary_rows = [], [], []
for device in mst_devices:
    for interval in INTERVALS:
        groups, pairs, summary = fit_mst(accuracy, device, interval)
        mst_group_rows.extend(groups)
        mst_pair_rows.extend(pairs)
        mst_summary_rows.append(summary)

mst_group_estimates = pd.DataFrame(mst_group_rows)
mst_pairwise = pd.DataFrame(mst_pair_rows)
mst_primary = pd.DataFrame(mst_summary_rows)

display(mst_primary[[
    "device_probe_key", "interval", "participants", "max_abs_difference",
    "simultaneous_upper_abs", "margin", "status"
]].round(3))"""
    )
)

cells.append(
    nbf.v4.new_markdown_cell(
        r"""## Primary device-specific emitter-site ITA analysis

Only the nine strata that passed the D013 coverage, range, participant, and interval-support requirements receive standalone continuous ITA benchmark estimates. A negative difference per 100 degrees means bias increases as ITA decreases—that is, toward darker measured pigmentation."""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        r"""ita_devices = support.loc[support["standalone_ita_supported"], "device_probe_key"].tolist()
ita_primary = pd.DataFrame([
    fit_ita(accuracy, device, interval)
    for device in ita_devices
    for interval in INTERVALS
])

display(ita_primary[[
    "device_probe_key", "interval", "participants", "difference_per_100_degrees",
    "ci_low", "ci_high", "upper_abs", "margin", "status"
]].round(3))"""
    )
)

cells.append(
    nbf.v4.new_markdown_cell(
        r"""## Intersection-union device conclusions

A complete conclusion is limited to devices supporting both pigmentation specifications in both saturation intervals. Every component must meet its benchmark. If at least one component's lower confidence bound exceeds its margin, the device is labeled as having evidence that a difference exceeds the benchmark. Otherwise, failure of the conjunction is labeled inconclusive."""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        r"""full_support_devices = sorted(set(mst_devices) & set(ita_devices))
component_rows = []
for device in full_support_devices:
    for interval in INTERVALS:
        m = mst_primary.query("device_probe_key == @device and interval == @interval").iloc[0]
        t = ita_primary.query("device_probe_key == @device and interval == @interval").iloc[0]
        component_rows.extend([
            {
                "device_probe_key": device, "component": f"MST | {interval}",
                "estimate_abs": m["max_abs_difference"], "lower_abs": m["simultaneous_lower_abs"],
                "upper_abs": m["simultaneous_upper_abs"], "margin": m["margin"], "status": m["status"],
            },
            {
                "device_probe_key": device, "component": f"Emitter ITA | {interval}",
                "estimate_abs": abs(t["difference_per_100_degrees"]), "lower_abs": t["lower_abs"],
                "upper_abs": t["upper_abs"], "margin": t["margin"], "status": t["status"],
            },
        ])
components = pd.DataFrame(component_rows)

iut_rows = []
for device, group in components.groupby("device_probe_key", sort=True):
    statuses = set(group["status"])
    if statuses == {"Meets benchmark"}:
        conclusion = "Benchmark demonstrated"
    elif "Difference exceeds benchmark" in statuses:
        conclusion = "At least one difference exceeds benchmark"
    else:
        conclusion = "Inconclusive"
    iut_rows.append({
        "device_probe_key": device,
        "components_meeting": int((group["status"] == "Meets benchmark").sum()),
        "components_inconclusive": int((group["status"] == "Inconclusive").sum()),
        "components_exceeding": int((group["status"] == "Difference exceeds benchmark").sum()),
        "all_four_supported": len(group) == 4,
        "intersection_union_conclusion": conclusion,
    })
iut_summary = pd.DataFrame(iut_rows)
display(iut_summary)"""
    )
)

cells.append(
    nbf.v4.new_markdown_cell(
        r"""## Prespecified sensitivity analyses

The D015 participant-balanced sensitivity gives each participant equal total weight within a device/interval. Forehead ITA is also evaluated as a common-site continuous measure, including sensor placements without matched emitter-site colorimetry. Fitzpatrick remains descriptive/sensitivity-only and cannot establish pigmentation equivalence."""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        r"""mst_balanced_rows = []
for device in mst_devices:
    for interval in INTERVALS:
        _, _, summary = fit_mst(accuracy, device, interval, participant_balanced=True, simulations=20_000)
        mst_balanced_rows.append(summary)
mst_balanced = pd.DataFrame(mst_balanced_rows)

ita_balanced = pd.DataFrame([
    fit_ita(accuracy, device, interval, participant_balanced=True)
    for device in ita_devices
    for interval in INTERVALS
])

forehead_ita_sensitivity = pd.DataFrame([
    fit_ita(accuracy, device, interval, ita_col="ita_forehead")
    for device in ita_devices
    for interval in INTERVALS
])

weighting_sensitivity = (
    mst_primary[["device_probe_key", "interval", "max_abs_difference", "simultaneous_upper_abs"]]
    .merge(
        mst_balanced[["device_probe_key", "interval", "max_abs_difference", "simultaneous_upper_abs"]],
        on=["device_probe_key", "interval"], suffixes=("_pair_weighted", "_participant_balanced")
    )
)
weighting_sensitivity["estimate_shift"] = (
    weighting_sensitivity["max_abs_difference_participant_balanced"]
    - weighting_sensitivity["max_abs_difference_pair_weighted"]
)

ita_weighting = (
    ita_primary[["device_probe_key", "interval", "difference_per_100_degrees", "upper_abs"]]
    .merge(
        ita_balanced[["device_probe_key", "interval", "difference_per_100_degrees", "upper_abs"]],
        on=["device_probe_key", "interval"], suffixes=("_pair_weighted", "_participant_balanced")
    )
)
ita_weighting["estimate_shift"] = (
    ita_weighting["difference_per_100_degrees_participant_balanced"]
    - ita_weighting["difference_per_100_degrees_pair_weighted"]
)

missingness_rows = []
for available, group in accuracy.assign(
    emitter_ita_available=accuracy["emitter_site_ita"].notna()
).groupby("emitter_ita_available"):
    missingness_rows.append({
        "emitter_ita_available": bool(available),
        "pairs": len(group),
        "participants": group["patient_id"].nunique(),
        "encounters": group["encounter_id"].nunique(),
        "devices": group["device_probe_key"].nunique(),
        "median_gap_seconds": group["gap_seconds"].median(),
        "finger_site_pct": 100 * (group["emitter_site"] == "dorsal_finger").mean(),
        "forehead_site_pct": 100 * (group["emitter_site"] == "forehead").mean(),
    })
ita_missingness = pd.DataFrame(missingness_rows)

fitz = accuracy.dropna(subset=["fitzpatrick"]).copy()
fitz["fitzpatrick_group"] = pd.cut(
    fitz["fitzpatrick"], bins=[0, 2, 4, 6],
    labels=["Fitzpatrick I-II", "Fitzpatrick III-IV", "Fitzpatrick V-VI"]
)
fitz_summary = (
    fitz.groupby("fitzpatrick_group", observed=True)
    .agg(pairs=("error", "size"), participants=("patient_id", "nunique"),
         mean_error=("error", "mean"), arms=("error", lambda x: np.sqrt(np.mean(np.square(x)))))
    .reset_index()
)

display(weighting_sensitivity.round(3))
display(ita_weighting.round(3))
display(ita_missingness.round(2))
display(fitz_summary.round(3))"""
    )
)

cells.append(
    nbf.v4.new_markdown_cell(
        r"""## Restricted cubic-spline ITA sensitivity

For the five devices with complete co-primary support, a natural cubic regression spline checks whether the linear ITA specification masks pronounced nonlinearity. Curves are standardized over each device/interval's empirical SaO2 distribution and are descriptive sensitivities; the locked linear 100-degree contrast remains primary."""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        r"""spline_rows = []
for device in full_support_devices:
    for interval in INTERVALS:
        sub, margin = interval_subset(accuracy.loc[accuracy["device_probe_key"] == device], interval)
        sub = sub.dropna(subset=["emitter_site_ita", "error", "so2", "patient_id"]).copy()
        model = fit_cluster_formula(
            "error ~ cr(emitter_site_ita, df=4) + so2_c + I(so2_c ** 2)", sub
        )
        lo, hi = np.quantile(sub["emitter_site_ita"], [0.05, 0.95])
        grid = np.linspace(lo, hi, 41)
        params = np.asarray(model.params)
        cov = np.asarray(model.cov_params())
        for ita_value in grid:
            counterfactual = sub.copy()
            counterfactual["emitter_site_ita"] = ita_value
            L = design_average(model, counterfactual)
            estimate = float(L @ params)
            se = float(np.sqrt(max(L @ cov @ L, 0)))
            spline_rows.append({
                "device_probe_key": device, "interval": interval,
                "emitter_site_ita": ita_value, "adjusted_bias": estimate,
                "ci_low": estimate - 1.96 * se, "ci_high": estimate + 1.96 * se,
                "observed_ita_p05": lo, "observed_ita_p95": hi,
            })
spline_sensitivity = pd.DataFrame(spline_rows)
print(f"Spline sensitivity rows: {len(spline_sensitivity):,}")"""
    )
)

cells.append(
    nbf.v4.new_markdown_cell(
        r"""## Figures, exports, and QA"""
    )
)

cells.append(
    nbf.v4.new_code_cell(
        r"""sns.set_theme(style="whitegrid", context="notebook")
plot_parts = []
for measure, data_, est_col, lo_col, hi_col in [
    ("MST maximum absolute contrast", mst_primary, "max_abs_difference", "simultaneous_lower_abs", "simultaneous_upper_abs"),
    ("Emitter-site ITA absolute contrast", ita_primary.assign(abs_est=lambda x: x["difference_per_100_degrees"].abs()), "abs_est", "lower_abs", "upper_abs"),
]:
    part = data_[["device_probe_key", "interval", est_col, lo_col, hi_col, "margin", "status"]].copy()
    part.columns = ["device_probe_key", "interval", "estimate", "lower", "upper", "margin", "status"]
    part["measure"] = measure
    plot_parts.append(part)
benchmark_plot = pd.concat(plot_parts, ignore_index=True)

fig, axes = plt.subplots(2, 2, figsize=(13, 10), sharex=False)
status_colors = {
    "Meets benchmark": "#16836B",
    "Inconclusive": "#D39B26",
    "Difference exceeds benchmark": "#B84A4A",
}
for ax, ((measure, interval), group) in zip(
    axes.flat, benchmark_plot.groupby(["measure", "interval"], sort=False)
):
    group = group.sort_values("estimate").reset_index(drop=True)
    y = np.arange(len(group))
    for j, row in group.iterrows():
        ax.errorbar(
            row["estimate"], y[j],
            xerr=[[row["estimate"] - row["lower"]], [row["upper"] - row["estimate"]]],
            fmt="o", color=status_colors[row["status"]], capsize=3, lw=1.5
        )
    ax.axvline(group["margin"].iloc[0], color="#555555", ls="--", lw=1.2, label="Benchmark margin")
    ax.set_yticks(y, [x.replace("|", " / ") for x in group["device_probe_key"]])
    ax.set_title(f"{measure}\n{interval}")
    ax.set_xlabel("Absolute bias contrast (percentage points)")
    ax.legend(loc="lower right", frameon=True)
fig.suptitle("Pigmentation contrasts versus prespecified research benchmark margins", fontsize=15, weight="bold")
fig.tight_layout(rect=[0, 0, 1, 0.96])
figure_path = FIGURES / "pigmentation_non_disparate_benchmark_results.png"
fig.savefig(figure_path, dpi=200, bbox_inches="tight")
plt.show()

mst_group_estimates.to_csv(TABLES / "pigmentation_mst_adjusted_group_bias.csv", index=False)
mst_pairwise.to_csv(TABLES / "pigmentation_mst_pairwise_contrasts.csv", index=False)
mst_primary.to_csv(TABLES / "pigmentation_mst_primary_benchmarks.csv", index=False)
ita_primary.to_csv(TABLES / "pigmentation_ita_primary_benchmarks.csv", index=False)
components.to_csv(TABLES / "pigmentation_intersection_union_components.csv", index=False)
iut_summary.to_csv(TABLES / "pigmentation_intersection_union_summary.csv", index=False)
mst_balanced.to_csv(TABLES / "pigmentation_mst_participant_balanced_sensitivity.csv", index=False)
ita_balanced.to_csv(TABLES / "pigmentation_ita_participant_balanced_sensitivity.csv", index=False)
forehead_ita_sensitivity.to_csv(TABLES / "pigmentation_forehead_ita_sensitivity.csv", index=False)
weighting_sensitivity.to_csv(TABLES / "pigmentation_mst_weighting_sensitivity.csv", index=False)
ita_weighting.to_csv(TABLES / "pigmentation_ita_weighting_sensitivity.csv", index=False)
ita_missingness.to_csv(TABLES / "pigmentation_emitter_ita_missingness_context.csv", index=False)
fitz_summary.to_csv(TABLES / "pigmentation_fitzpatrick_descriptive_sensitivity.csv", index=False)
spline_sensitivity.to_csv(TABLES / "pigmentation_ita_spline_sensitivity.csv", index=False)

qa = pd.DataFrame({
    "check": [
        "Frozen merge preserved 28,693 rows",
        "Pair key remains unique",
        "Stored error identity reconciles",
        "All supported MST models produced finite bounds",
        "All supported ITA models produced finite bounds",
        "Every full-support device has four IUT components",
        "MST simultaneous critical values exceed 1.96",
        "Primary and sensitivity outputs written",
    ],
    "passed": [
        len(df) == 28_693,
        df["pulse_row_id"].is_unique,
        bool(np.allclose(df["error"], df["saturation"] - df["so2"], equal_nan=True)),
        np.isfinite(mst_primary[["max_abs_difference", "simultaneous_upper_abs"]]).all().all(),
        np.isfinite(ita_primary[["difference_per_100_degrees", "upper_abs"]]).all().all(),
        components.groupby("device_probe_key").size().eq(4).all(),
        (mst_primary["simultaneous_critical_value"] > 1.96).all(),
        figure_path.exists(),
    ],
})
qa.to_csv(TABLES / "pigmentation_non_disparate_qa.csv", index=False)
display(qa)
assert qa["passed"].all()
print("All QA checks passed.")
print("Figure:", figure_path)"""
    )
)

cells.append(
    nbf.v4.new_markdown_cell(
        r"""## Interpretation boundary

The benchmark classifications describe precision relative to prespecified research margins in this retrospective, repeated-measures repository. They do not constitute FDA pass/fail determinations, do not identify manufacturers, and do not estimate the probability that a clinical patient will experience harm. Component-specific evidence for a device lacking all four supported analyses cannot be promoted to a complete non-disparate-performance conclusion."""
    )
)

nb["cells"] = cells
nbf.write(nb, OUT)
print(OUT)
