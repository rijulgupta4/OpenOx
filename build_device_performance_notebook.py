from pathlib import Path
import textwrap
import nbformat as nbf

OUT = Path(r".\07_device_performance.ipynb")

def md(s): return nbf.v4.new_markdown_cell(textwrap.dedent(s).strip())
def code(s): return nbf.v4.new_code_cell(textwrap.dedent(s).strip())

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python (openox)", "language": "python", "name": "openox"},
    "language_info": {"name": "python", "version": "3.11"},
}
nb["cells"] = [
md("""
# 07 — Primary device-performance analysis

## tl;dr

This notebook estimates the prespecified accuracy metrics for the 11 D011 core
device/probe strata. Conclusions are descriptive academic estimates, not FDA
regulatory pass/fail determinations. The executed results and takeaways appear below.
"""),
md("""
## Context & Methods

### Locked specification

- Cohort: frozen 180-second pairing cohort.
- Accuracy range: arterial SaO2 70-100% inclusive.
- Error: SpO2 − SaO2, retaining direction.
- Primary metrics: mean bias, precision (sample SD of error), and
  `A_RMS = sqrt(mean(error²))`.
- Uncertainty: 2,000 participant-cluster bootstrap replicates with percentile 95% CIs.
- Reporting: only the 11 D011 core device/probe strata receive primary inferential estimates.
- Agreement display: error versus SaO2 with SaO2-band means and pair-level
  bias ± 1.96 SD reference lines. These limits describe pair dispersion; clustered
  bootstrap intervals remain the inferential foundation.

### Key assumptions

The normalized device/probe key is the reporting entity. Repeated rows from the same
participant are not treated as independent for confidence intervals. No manufacturer
identity is inferred from opaque repository codes.
"""),
code("""
from pathlib import Path
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

PROJECT = Path(r".")
COHORT_PATH = PROJECT / "data" / "processed" / "analytic_cohort_180s.csv.gz"
SUPPORT_PATH = PROJECT / "outputs" / "tables" / "device_probe_inference_support.csv"
TABLES = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
N_BOOT = 2000
SEED = 20260723

print("MKL_THREADING_LAYER =", os.environ.get("MKL_THREADING_LAYER"))
print("MKL_NUM_THREADS =", os.environ.get("MKL_NUM_THREADS"))
print("OMP_NUM_THREADS =", os.environ.get("OMP_NUM_THREADS"))
"""),
md("## Data"),
code("""
usecols = ["patient_id", "encounter_id", "pulse_row_id", "device_probe_key", "saturation", "so2", "error"]
cohort = pd.read_csv(
    COHORT_PATH, usecols=usecols,
    dtype={"patient_id": str, "encounter_id": str},
    low_memory=False,
)
support = pd.read_csv(SUPPORT_PATH)
core_keys = support.loc[support["core_inferential_accuracy"].astype(str).str.lower().eq("true"), "device_probe_key"].tolist()

analysis = cohort.loc[
    cohort["device_probe_key"].isin(core_keys)
    & cohort["so2"].between(70, 100, inclusive="both")
].copy()

assert cohort["pulse_row_id"].is_unique
assert len(core_keys) == 11
assert np.allclose(analysis["error"], analysis["saturation"] - analysis["so2"], equal_nan=True)
assert analysis[["saturation", "so2", "error"]].notna().all().all()
print(f"Core strata: {len(core_keys)}; accuracy pairs: {len(analysis):,}; participants: {analysis.patient_id.nunique()}")
"""),
md("## Results"),
md("### 1. Point estimates and saturation-band profiles"),
code("""
def metric_row(g):
    e = g["error"].to_numpy(float)
    return pd.Series({
        "pairs": len(g),
        "participants": g["patient_id"].nunique(),
        "encounters": g["encounter_id"].nunique(),
        "bias": e.mean(),
        "precision_sd": e.std(ddof=1),
        "arms": np.sqrt(np.mean(e**2)),
        "loa_lower": e.mean() - 1.96 * e.std(ddof=1),
        "loa_upper": e.mean() + 1.96 * e.std(ddof=1),
    })

point = analysis.groupby("device_probe_key", sort=False).apply(metric_row, include_groups=False).reset_index()
point = point.sort_values("arms")

analysis["sao2_band"] = pd.cut(
    analysis["so2"], bins=[70, 80, 90, 100.000001],
    labels=["70-<80%", "80-<90%", "90-100%"], right=False,
)
band = (
    analysis.groupby(["device_probe_key", "sao2_band"], observed=True)
    .apply(metric_row, include_groups=False).reset_index()
)
band.to_csv(TABLES / "device_performance_by_sao2_band.csv", index=False)
display(point.round(3))
display(band[["device_probe_key", "sao2_band", "pairs", "participants", "bias", "precision_sd", "arms"]].round(3))
"""),
md("### 2. Participant-cluster bootstrap"),
code("""
# Aggregate sufficient statistics by stratum and participant.
cluster = (
    analysis.assign(error_sq=analysis["error"] ** 2)
    .groupby(["device_probe_key", "patient_id"])
    .agg(n=("error", "size"), sum_e=("error", "sum"), sum_e2=("error_sq", "sum"))
    .reset_index()
)
rng = np.random.default_rng(SEED)
boot_rows = []

for key in core_keys:
    c = cluster.loc[cluster.device_probe_key.eq(key)].reset_index(drop=True)
    p = len(c)
    draws = rng.integers(0, p, size=(N_BOOT, p))
    n = c["n"].to_numpy()[draws].sum(axis=1)
    se = c["sum_e"].to_numpy()[draws].sum(axis=1)
    se2 = c["sum_e2"].to_numpy()[draws].sum(axis=1)
    b = se / n
    a = np.sqrt(se2 / n)
    sd = np.sqrt(np.maximum(0, (se2 - n * b**2) / (n - 1)))
    observed = point.loc[point.device_probe_key.eq(key)].iloc[0]
    boot_rows.append({
        "device_probe_key": key,
        "participants": int(observed.participants),
        "pairs": int(observed.pairs),
        "bias": observed.bias,
        "bias_ci_low": np.quantile(b, .025),
        "bias_ci_high": np.quantile(b, .975),
        "precision_sd": observed.precision_sd,
        "precision_ci_low": np.quantile(sd, .025),
        "precision_ci_high": np.quantile(sd, .975),
        "arms": observed.arms,
        "arms_ci_low": np.quantile(a, .025),
        "arms_ci_high": np.quantile(a, .975),
        "loa_lower": observed.loa_lower,
        "loa_upper": observed.loa_upper,
        "bootstrap_replicates": N_BOOT,
        "valid_replicates": int(np.isfinite(a).sum()),
    })

results = pd.DataFrame(boot_rows).sort_values("arms")
results.to_csv(TABLES / "device_performance_core_results.csv", index=False)
display(results.round(3))
"""),
md("### 3. Independent reconciliation against D012 feasibility output"),
code("""
prior = pd.read_csv(TABLES / "core_device_participant_bootstrap.csv")
recon = results.merge(
    prior[["device_probe_key", "bias", "arms"]],
    on="device_probe_key", suffixes=("_final", "_d012"), validate="one_to_one",
)
recon["bias_abs_difference"] = (recon.bias_final - recon.bias_d012).abs()
recon["arms_abs_difference"] = (recon.arms_final - recon.arms_d012).abs()
reconciliation = pd.DataFrame([
    {"check": "max point-estimate bias difference vs D012", "value": recon.bias_abs_difference.max(), "tolerance": 1e-12},
    {"check": "max point-estimate A_RMS difference vs D012", "value": recon.arms_abs_difference.max(), "tolerance": 1e-12},
])
reconciliation["passed"] = reconciliation["value"] <= reconciliation["tolerance"]
reconciliation.to_csv(TABLES / "device_performance_reconciliation.csv", index=False)
display(reconciliation)
assert reconciliation["passed"].all()
"""),
md("### 4. Core-stratum uncertainty"),
code("""
sns.set_theme(style="whitegrid")
order = results.sort_values("arms")["device_probe_key"].tolist()
plot = results.set_index("device_probe_key").loc[order].reset_index()
y = np.arange(len(plot))
fig, axes = plt.subplots(1, 2, figsize=(11.5, 6.2), sharey=True)

axes[0].errorbar(
    plot.bias, y,
    xerr=[plot.bias - plot.bias_ci_low, plot.bias_ci_high - plot.bias],
    fmt="o", color="#2E749F", ecolor="#737B83", capsize=3,
)
axes[0].axvline(0, color="#30363B", linewidth=1)
axes[0].set(title="Mean error by core device/probe stratum",
            xlabel="Bias: SpO2 − SaO2 (percentage points)", yticks=y, yticklabels=order)

axes[1].errorbar(
    plot.arms, y,
    xerr=[plot.arms - plot.arms_ci_low, plot.arms_ci_high - plot.arms],
    fmt="o", color="#A66A00", ecolor="#737B83", capsize=3,
)
axes[1].axvline(3.0, color="#30363B", linestyle="--", linewidth=1, label="3.0 reference")
axes[1].set(title="A_RMS by core device/probe stratum",
            xlabel="A_RMS (percentage points)")
axes[1].legend(frameon=False, loc="lower right")
fig.suptitle("Participant-cluster bootstrap 95% confidence intervals", y=1.01)
fig.tight_layout()
fig.savefig(FIGURES / "device_performance_core_intervals.png", dpi=180, bbox_inches="tight")
plt.show()
"""),
md("### 5. Modified Bland–Altman displays"),
code("""
panel_order = results.sort_values("arms")["device_probe_key"].tolist()
fig, axes = plt.subplots(4, 3, figsize=(13, 13), sharex=True, sharey=True)
axes = axes.ravel()
for ax, key in zip(axes, panel_order):
    g = analysis.loc[analysis.device_probe_key.eq(key)]
    r = results.loc[results.device_probe_key.eq(key)].iloc[0]
    ax.scatter(g["so2"], g["error"], s=5, alpha=.13, color="#2E749F", linewidths=0)
    bm = g.groupby("sao2_band", observed=True).agg(x=("so2", "mean"), y=("error", "mean"))
    ax.plot(bm.x, bm.y, color="#A66A00", marker="o", linewidth=1.5)
    ax.axhline(0, color="#30363B", linewidth=.8)
    ax.axhline(r.bias, color="#2E749F", linewidth=1.2)
    ax.axhline(r.loa_lower, color="#737B83", linestyle="--", linewidth=.8)
    ax.axhline(r.loa_upper, color="#737B83", linestyle="--", linewidth=.8)
    ax.set_title(f"{key}\\nn={int(r.pairs):,}, participants={int(r.participants)}", fontsize=9)
for ax in axes[len(panel_order):]:
    ax.axis("off")
for ax in axes[-3:]:
    ax.set_xlabel("SaO2 (%)")
for ax in axes[::3]:
    ax.set_ylabel("SpO2 − SaO2")
fig.suptitle("Modified Bland–Altman profiles for D011 core strata", y=.995, fontsize=14)
fig.text(.5, .975, "Orange: SaO2-band mean; blue: overall bias; dashed: pair-level bias ± 1.96 SD", ha="center", fontsize=9)
fig.tight_layout(rect=[0, 0, 1, .96])
fig.savefig(FIGURES / "device_performance_modified_bland_altman.png", dpi=180, bbox_inches="tight")
plt.show()
"""),
md("### 6. QA and headline range"),
code("""
qa = pd.DataFrame([
    ["frozen cohort row count", len(cohort) == 28693, len(cohort), 28693],
    ["unique pulse rows", cohort.pulse_row_id.is_unique, cohort.pulse_row_id.nunique(), len(cohort)],
    ["core strata count", len(results) == 11, len(results), 11],
    ["all bootstrap replicates valid", results.valid_replicates.eq(N_BOOT).all(), results.valid_replicates.min(), N_BOOT],
    ["minimum participants", results.participants.min() >= 30, results.participants.min(), 30],
    ["minimum accuracy pairs", results.pairs.min() >= 300, results.pairs.min(), 300],
    ["error identity", np.allclose(analysis.error, analysis.saturation-analysis.so2), 0, 0],
    ["D012 point reconciliation", reconciliation.passed.all(), reconciliation.passed.sum(), len(reconciliation)],
], columns=["check", "passed", "observed", "expected"])
qa.to_csv(TABLES / "device_performance_core_qa.csv", index=False)
display(qa)
assert qa.passed.all()

best = results.loc[results.arms.idxmin()]
worst = results.loc[results.arms.idxmax()]
print(f"A_RMS range: {best.arms:.3f} ({best.device_probe_key}) to {worst.arms:.3f} ({worst.device_probe_key}).")
print(f"Bias range: {results.bias.min():+.3f} to {results.bias.max():+.3f} percentage points.")
"""),
md("""
## Takeaways

- All 11 core strata passed the locked support and execution checks.
- The interval plot is the primary compact comparison; exact estimates are saved in
  `device_performance_core_results.csv`.
- Saturation-band estimates and modified Bland–Altman panels show whether an overall
  metric masks saturation-dependent behavior.
- Differences between opaque device codes are measurement-performance findings only;
  they are not causal manufacturer comparisons and are not regulatory determinations.
""")
]
nbf.write(nb, OUT)
print(OUT)
