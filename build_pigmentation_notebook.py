from pathlib import Path

import nbformat as nbf


OUTPUT = Path(r".\05_pigmentation_measure_lock.ipynb")

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python (openox)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}

nb["cells"] = [
    nbf.v4.new_markdown_cell(
        """# Pigmentation measurement and non-disparate-performance lock

## tl;dr

This notebook evaluates pigmentation predictors **without calculating pigmentation-stratified pulse-oximeter error or accuracy**. In the frozen 28,693-pair cohort, forehead Monk Skin Tone (MST) is available for 27,408 pairs (95.5%; 119 participants), and an emitter-site Individual Typology Angle (ITA) can be mapped for 24,462 pairs (85.3%; 116 participants). Forehead MST and forehead ITA show strong inverse encounter-level rank agreement (Spearman rho about -0.93).

The plan is locked to two complementary, co-primary pigmentation specifications aligned with FDA's January 2025 draft guidance: (1) forehead MST groups 1-4, 5-7, and 8-10; and (2) continuous emitter-site ITA. Fitzpatrick is secondary only. The FDA draft's non-disparate-performance margins—3.5 percentage points in SaO2 70-85% and 1.5 points in SaO2 >85-100%—will be used as research benchmarks with 95% confidence intervals, not as a regulatory claim.
"""
    ),
    nbf.v4.new_markdown_cell(
        """## Prespecified scope and evidence anchors

- **Scope in this notebook:** coverage, range, repeated colorimeter measurements, cross-measure agreement, site mapping, and support for later models.
- **Sealed outcomes:** no mean error, A_RMS, occult-hypoxemia rate, or pigmentation-stratified performance result is computed here.
- **FDA alignment:** forehead MST is grouped as 1-4, 5-7, and 8-10; objective ITA uses L* and b*; fingertip emitter-site ITA is mapped to the mid-dorsal distal phalanx. The draft guidance defines separate co-primary MST and emitter-site ITA bias analyses and recommends margins of 3.5 points at SaO2 70-85% and 1.5 points at >85-100%.
- **Interpretation boundary:** this retrospective multi-device analysis is not a pivotal manufacturer study. FDA criteria are methodological benchmarks, not pass/fail regulatory determinations.

Sources: [FDA January 2025 draft pulse-oximeter guidance](https://www.fda.gov/media/184896/download) and [OpenOximetry Repository v1.1.1](https://www.physionet.org/content/openox-repo/1.1.1/).
"""
    ),
    nbf.v4.new_code_cell(
        """from pathlib import Path
import sys

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import display

PROJECT_ROOT = Path.cwd()
if not (PROJECT_ROOT / "src").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_source_data_dir

SOURCE_DIR = get_source_data_dir()
COHORT_PATH = PROJECT_ROOT / "data" / "processed" / "analytic_cohort_180s.csv.gz"
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
FIGURE_DIR = PROJECT_ROOT / "outputs" / "figures"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
for path in (TABLE_DIR, FIGURE_DIR, PROCESSED_DIR):
    path.mkdir(parents=True, exist_ok=True)

# Load only columns needed for predictor mapping and support checks. Error and SpO2 are intentionally omitted.
cohort_cols = ["pulse_row_id", "patient_id", "encounter_id", "device_probe_key", "so2", "inferred_assignment_location"]
cohort = pd.read_csv(COHORT_PATH, usecols=cohort_cols, dtype={"patient_id": "string", "encounter_id": "string"})
encounter = pd.read_csv(SOURCE_DIR / "encounter.csv", low_memory=False, dtype={"patient_id": "string", "encounter_id": "string"})
spectro = pd.read_csv(SOURCE_DIR / "spectrophotometer.csv", low_memory=False, dtype={"patient_id": "string", "encounter_id": "string"})

assert len(cohort) == 28693
assert cohort["pulse_row_id"].is_unique
assert "error" not in cohort and "saturation" not in cohort
print(f"Frozen cohort: {len(cohort):,} pairs; {cohort.patient_id.nunique()} participants; {cohort.encounter_id.nunique()} encounters")
print("Outcome seal check passed: error and SpO2 were not loaded.")"""
    ),
    nbf.v4.new_markdown_cell(
        """## Build encounter-level pigmentation measures

Monk letters A-J are converted to numeric levels 1-10. Spectrophotometer replicates are converted to ITA and summarized by the encounter-site median. The repository contains two labels for the upper-arm site; they are retained transparently because neither is used for the primary emitter-site mapping.
"""
    ),
    nbf.v4.new_code_cell(
        """monk_columns = ["monk_fingernail", "monk_dorsal", "monk_palmar", "monk_upper_arm", "monk_forehead"]
monk_map = {chr(65 + i): i + 1 for i in range(10)}

encounter_features = encounter[["patient_id", "encounter_id", "fitzpatrick", *monk_columns]].copy()
encounter_features["fitzpatrick"] = pd.to_numeric(encounter_features["fitzpatrick"], errors="coerce")
for column in monk_columns:
    encounter_features[column] = encounter_features[column].astype("string").str.strip().str.upper().map(monk_map)
encounter_features["mst_group"] = pd.cut(
    encounter_features["monk_forehead"], bins=[0, 4, 7, 10], labels=["1-4", "5-7", "8-10"]
)

for column in ["lab_l", "lab_b", "melanin_index"]:
    spectro[column] = pd.to_numeric(spectro[column], errors="coerce")
spectro["ita"] = np.degrees(np.arctan((spectro["lab_l"] - 50.0) / spectro["lab_b"]))

spectro_by_site = spectro.groupby(["patient_id", "encounter_id", "group"], as_index=False).agg(
    colorimeter_replicates=("ita", "count"),
    ita=("ita", "median"),
    ita_within_sd=("ita", "std"),
    lab_l=("lab_l", "median"),
    lab_b=("lab_b", "median"),
    melanin_index=("melanin_index", "median"),
)

ita_wide = spectro_by_site.pivot(index=["patient_id", "encounter_id"], columns="group", values="ita")
ita_wide = ita_wide.rename(columns={
    "Dorsal (B)": "ita_dorsal", "Fingernail (A)": "ita_fingernail",
    "Forehead (E)": "ita_forehead", "Palmar (C)": "ita_palmar",
    "Inner Upper Arm (D)": "ita_inner_upper_arm", "Upper Inner Arm (D)": "ita_upper_inner_arm",
}).reset_index()

melanin_wide = spectro_by_site.pivot(index=["patient_id", "encounter_id"], columns="group", values="melanin_index")
melanin_wide = melanin_wide.rename(columns={
    "Dorsal (B)": "melanin_dorsal", "Forehead (E)": "melanin_forehead", "Palmar (C)": "melanin_palmar"
}).reset_index()

encounter_features = encounter_features.merge(ita_wide, on=["patient_id", "encounter_id"], how="left", validate="one_to_one")
encounter_features = encounter_features.merge(melanin_wide, on=["patient_id", "encounter_id"], how="left", validate="one_to_one")
analytic_encounters = cohort[["patient_id", "encounter_id"]].drop_duplicates()
analytic_encounter_features = analytic_encounters.merge(
    encounter_features, on=["patient_id", "encounter_id"], how="left", validate="one_to_one"
)

replicate_summary = spectro_by_site[spectro_by_site["encounter_id"].isin(analytic_encounters["encounter_id"])].groupby("group").agg(
    encounters=("encounter_id", "nunique"), participants=("patient_id", "nunique"),
    median_replicates=("colorimeter_replicates", "median"),
    median_within_sd_ita=("ita_within_sd", "median"), p90_within_sd_ita=("ita_within_sd", lambda x: x.quantile(.9)),
).reset_index()
replicate_summary.to_csv(TABLE_DIR / "pigmentation_colorimeter_repeats.csv", index=False)
display(replicate_summary.style.format({"median_replicates": "{:.1f}", "median_within_sd_ita": "{:.2f}", "p90_within_sd_ita": "{:.2f}"}))"""
    ),
    nbf.v4.new_markdown_cell(
        """## Map measures into every frozen-cohort row

For finger placements, the primary emitter-site ITA is the dorsal measurement, matching the FDA draft's recommended mid-dorsal distal-phalanx measurement. Forehead placements use forehead ITA. The analytic cohort contains no corresponding ear-site colorimetry, so ear rows are unavailable for the emitter-site ITA analysis but remain eligible for the forehead-MST analysis.
"""
    ),
    nbf.v4.new_code_cell(
        """mapped = cohort.merge(encounter_features, on=["patient_id", "encounter_id"], how="left", validate="many_to_one")
location = mapped["inferred_assignment_location"].astype("string")
mapped["emitter_site"] = pd.Series(pd.NA, index=mapped.index, dtype="string")
mapped.loc[location.str.startswith("finger", na=False), "emitter_site"] = "dorsal_finger"
mapped.loc[location.eq("forehead").fillna(False), "emitter_site"] = "forehead"
mapped["emitter_site_ita"] = np.nan
mapped.loc[mapped["emitter_site"].eq("dorsal_finger"), "emitter_site_ita"] = mapped.loc[mapped["emitter_site"].eq("dorsal_finger"), "ita_dorsal"]
mapped.loc[mapped["emitter_site"].eq("forehead"), "emitter_site_ita"] = mapped.loc[mapped["emitter_site"].eq("forehead"), "ita_forehead"]
mapped["emitter_site_mapping"] = np.select(
    [mapped["emitter_site_ita"].notna(), mapped["emitter_site"].isna()],
    ["mapped", "unsupported_or_unknown_site"], default="site_known_colorimetry_missing"
)

def coverage_row(label, column):
    present = mapped[column].notna()
    return {
        "measure": label, "paired_rows": int(present.sum()), "row_coverage_pct": 100 * present.mean(),
        "encounters": mapped.loc[present, "encounter_id"].nunique(),
        "participants": mapped.loc[present, "patient_id"].nunique(),
    }

coverage = pd.DataFrame([
    coverage_row("Fitzpatrick", "fitzpatrick"),
    coverage_row("Forehead MST", "monk_forehead"),
    coverage_row("Forehead ITA", "ita_forehead"),
    coverage_row("Dorsal ITA", "ita_dorsal"),
    coverage_row("Emitter-site ITA", "emitter_site_ita"),
])
site_mapping = mapped.groupby(["emitter_site", "emitter_site_mapping"], dropna=False).agg(
    paired_rows=("pulse_row_id", "size"), participants=("patient_id", "nunique"), encounters=("encounter_id", "nunique")
).reset_index()
coverage.to_csv(TABLE_DIR / "pigmentation_measure_coverage.csv", index=False)
site_mapping.to_csv(TABLE_DIR / "pigmentation_emitter_site_mapping.csv", index=False)
display(coverage.style.format({"row_coverage_pct": "{:.1f}%"}))
display(site_mapping)

fig, ax = plt.subplots(figsize=(8.5, 4.6))
bars = ax.barh(coverage["measure"], coverage["row_coverage_pct"], color=["#8c8c8c", "#15937c", "#3d8cbe", "#3d8cbe", "#6554c0"])
ax.set_xlim(0, 105); ax.set_xlabel("Coverage of frozen analytic pairs (%)"); ax.set_title("Pigmentation-measure coverage before outcome analysis")
ax.grid(axis="x", alpha=.2)
for bar, value in zip(bars, coverage["row_coverage_pct"]):
    ax.text(value + .8, bar.get_y() + bar.get_height()/2, f"{value:.1f}%", va="center")
fig.tight_layout(); fig.savefig(FIGURE_DIR / "pigmentation_measure_coverage.png", dpi=180); plt.show()

export_columns = [
    "pulse_row_id", "patient_id", "encounter_id", "fitzpatrick", "monk_forehead", "mst_group",
    "monk_dorsal", "monk_fingernail", "monk_palmar", "monk_upper_arm", "ita_forehead", "ita_dorsal",
    "ita_fingernail", "ita_palmar", "melanin_forehead", "melanin_dorsal", "emitter_site",
    "emitter_site_ita", "emitter_site_mapping"
]
mapped[export_columns].to_csv(PROCESSED_DIR / "pigmentation_covariates_by_pair.csv.gz", index=False, compression="gzip")
assert len(mapped) == len(cohort) and mapped["pulse_row_id"].is_unique"""
    ),
    nbf.v4.new_markdown_cell(
        """## Missingness, range, and cross-measure agreement

Agreement is estimated at the encounter level so encounters with many pulse-oximeter rows do not dominate. Spearman correlation is appropriate because Monk and Fitzpatrick are ordinal. Negative correlations with ITA are expected: lower ITA indicates darker pigmentation, while higher Monk/Fitzpatrick values indicate darker categories.
"""
    ),
    nbf.v4.new_code_cell(
        """agreement_pairs = [
    ("Fitzpatrick", "fitzpatrick", "Forehead MST", "monk_forehead"),
    ("Fitzpatrick", "fitzpatrick", "Forehead ITA", "ita_forehead"),
    ("Forehead MST", "monk_forehead", "Forehead ITA", "ita_forehead"),
    ("Dorsal MST", "monk_dorsal", "Dorsal ITA", "ita_dorsal"),
    ("Forehead MST", "monk_forehead", "Dorsal MST", "monk_dorsal"),
    ("Forehead ITA", "ita_forehead", "Dorsal ITA", "ita_dorsal"),
]
agreement_rows = []
for left_label, left, right_label, right in agreement_pairs:
    paired = analytic_encounter_features[[left, right]].dropna()
    agreement_rows.append({
        "measure_1": left_label, "measure_2": right_label, "complete_encounters": len(paired),
        "spearman_rho": paired[left].corr(paired[right], method="spearman")
    })
agreement = pd.DataFrame(agreement_rows)

range_rows = []
for label, column in [("Forehead ITA", "ita_forehead"), ("Dorsal ITA", "ita_dorsal"), ("Emitter-site ITA", "emitter_site_ita")]:
    frame = analytic_encounter_features if column != "emitter_site_ita" else mapped.drop_duplicates(["patient_id", "encounter_id", "emitter_site"])
    values = frame[column].dropna()
    range_rows.append({"measure": label, "n": len(values), "minimum": values.min(), "p25": values.quantile(.25), "median": values.median(), "p75": values.quantile(.75), "maximum": values.max()})
range_summary = pd.DataFrame(range_rows)

agreement.to_csv(TABLE_DIR / "pigmentation_measure_agreement.csv", index=False)
range_summary.to_csv(TABLE_DIR / "pigmentation_ita_range.csv", index=False)
display(agreement.style.format({"spearman_rho": "{:.3f}"}))
display(range_summary.style.format({c: "{:.1f}" for c in ["minimum", "p25", "median", "p75", "maximum"]}))

plot_data = analytic_encounter_features.dropna(subset=["mst_group", "ita_forehead"]).copy()
groups = ["1-4", "5-7", "8-10"]
fig, ax = plt.subplots(figsize=(7.5, 4.8))
ax.boxplot([plot_data.loc[plot_data.mst_group.astype("string").eq(g), "ita_forehead"] for g in groups], tick_labels=groups, showfliers=False)
ax.set_xlabel("Forehead Monk Skin Tone group"); ax.set_ylabel("Forehead ITA (degrees)")
ax.set_title("Objective forehead ITA separates prespecified MST groups")
ax.axhline(-50, color="#b14a4a", linestyle="--", linewidth=1, label="FDA darkest-group enrollment reference (-50 degrees)")
ax.legend(frameon=False, fontsize=8); ax.grid(axis="y", alpha=.2)
fig.tight_layout(); fig.savefig(FIGURE_DIR / "forehead_ita_by_mst_group.png", dpi=180); plt.show()"""
    ),
    nbf.v4.new_markdown_cell(
        """## Prespecify support rules before equity outcomes

The tables below count participants and observations but do not calculate device performance. A device/probe stratum may receive a standalone MST non-disparate-performance contrast only if each MST group has at least 10 participants and at least 50 pairs in each FDA saturation interval. A standalone continuous ITA contrast requires at least 30 participants, at least 80% emitter-site ITA coverage, a span of at least 100 ITA degrees, and at least 100 pairs in each saturation interval. Other strata can contribute to pooled or partially pooled models but will not receive pass/fail-style standalone interpretations.

These are study feasibility/reporting safeguards, not FDA sample-size equivalence. The FDA draft recommends substantially larger and deliberately balanced pivotal studies.
"""
    ),
    nbf.v4.new_code_cell(
        """mapped["sao2_interval"] = pd.Series(pd.NA, index=mapped.index, dtype="string")
mapped.loc[mapped["so2"].between(70, 85, inclusive="both"), "sao2_interval"] = "70-85"
mapped.loc[mapped["so2"].gt(85) & mapped["so2"].le(100), "sao2_interval"] = ">85-100"
accuracy = mapped[mapped["sao2_interval"].notna()].copy()

mst_support = accuracy.dropna(subset=["mst_group"]).groupby("mst_group", observed=True).agg(
    paired_rows=("pulse_row_id", "size"), participants=("patient_id", "nunique"), encounters=("encounter_id", "nunique")
).reset_index()
mst_support.to_csv(TABLE_DIR / "pigmentation_mst_group_support.csv", index=False)
display(mst_support)

# Recreate the already-locked D011 core stratum definition using support counts only.
core_support = accuracy.groupby("device_probe_key").agg(
    participants=("patient_id", "nunique"), pairs=("pulse_row_id", "size"),
    low_70_80=("so2", lambda x: x.ge(70).mul(x.lt(80)).sum()),
    mid_80_90=("so2", lambda x: x.ge(80).mul(x.lt(90)).sum()),
    high_90_100=("so2", lambda x: x.ge(90).mul(x.le(100)).sum()),
).reset_index()
core_keys = core_support.query("participants >= 30 and pairs >= 300 and low_70_80 >= 50 and mid_80_90 >= 50 and high_90_100 >= 50")["device_probe_key"]

device_rows = []
for key in core_keys:
    group = accuracy[accuracy["device_probe_key"].eq(key)]
    row = {
        "device_probe_key": key, "participants": group.patient_id.nunique(),
        "mst_coverage_pct": 100 * group.monk_forehead.notna().mean(),
        "ita_coverage_pct": 100 * group.emitter_site_ita.notna().mean(),
        "ita_min": group.emitter_site_ita.min(), "ita_max": group.emitter_site_ita.max(),
        "low_interval_pairs": group.sao2_interval.eq("70-85").sum(),
        "high_interval_pairs": group.sao2_interval.eq(">85-100").sum(),
    }
    mst_ok = True
    for mst in ["1-4", "5-7", "8-10"]:
        subgroup = group[group.mst_group.astype("string").eq(mst)]
        row[f"mst_{mst}_participants"] = subgroup.patient_id.nunique()
        row[f"mst_{mst}_low_pairs"] = subgroup.sao2_interval.eq("70-85").sum()
        row[f"mst_{mst}_high_pairs"] = subgroup.sao2_interval.eq(">85-100").sum()
        mst_ok &= row[f"mst_{mst}_participants"] >= 10 and row[f"mst_{mst}_low_pairs"] >= 50 and row[f"mst_{mst}_high_pairs"] >= 50
    ita_span = row["ita_max"] - row["ita_min"]
    row["standalone_mst_supported"] = bool(mst_ok)
    row["standalone_ita_supported"] = bool(
        row["participants"] >= 30 and row["ita_coverage_pct"] >= 80 and ita_span >= 100
        and row["low_interval_pairs"] >= 100 and row["high_interval_pairs"] >= 100
    )
    device_rows.append(row)

device_support = pd.DataFrame(device_rows)
device_support.to_csv(TABLE_DIR / "pigmentation_device_support.csv", index=False)
summary = pd.DataFrame({
    "criterion": ["D011 core device/probe strata", "Standalone MST contrasts supported", "Standalone emitter-site ITA contrasts supported"],
    "strata": [len(device_support), device_support.standalone_mst_supported.sum(), device_support.standalone_ita_supported.sum()]
})
display(summary)
display(device_support[["device_probe_key", "participants", "mst_coverage_pct", "ita_coverage_pct", "ita_min", "ita_max", "standalone_mst_supported", "standalone_ita_supported"]].style.format({"mst_coverage_pct": "{:.1f}%", "ita_coverage_pct": "{:.1f}%", "ita_min": "{:.1f}", "ita_max": "{:.1f}"}))"""
    ),
    nbf.v4.new_markdown_cell(
        """## Locked pigmentation and non-disparate-performance plan

1. **Co-primary specification A — forehead MST:** use encounter-specific forehead MST grouped 1-4, 5-7, and 8-10. Within each SaO2 interval (70-85% and >85-100%), estimate adjusted mean bias for each group and the largest absolute pairwise group difference.
2. **Co-primary specification B — emitter-site ITA:** use continuous encounter-specific ITA, taking the median of colorimeter replicates. Finger rows map to dorsal ITA and forehead rows to forehead ITA. Estimate the adjusted bias difference for a 100-degree ITA change within each SaO2 interval. The primary functional form is linear; a restricted cubic-spline curve is a sensitivity analysis.
3. **Margins and inference:** non-disparate performance requires the upper bound of the two-sided 95% confidence interval for the absolute contrast to be below 3.5 percentage points at SaO2 70-85% and below 1.5 points at >85-100%. Participant-cluster resampling/robust covariance follows D012.
4. **Fitzpatrick:** secondary sensitivity and descriptive variable only. It reflects sun-response phenotype and is not treated as interchangeable with direct skin-color measurement.
5. **Other quantitative measures:** standardized forehead ITA is a secondary continuous sensitivity analysis across all sensor sites; dorsal melanin index and alternative Monk body sites are concordance/robustness analyses. Race and ethnicity are descriptive social variables, not pigmentation proxies.
6. **Missing emitter-site ITA:** do not impute ear-site ITA from forehead or dorsal measurements in the primary analysis. Compare included versus excluded rows using pre-outcome characteristics and run a forehead-ITA sensitivity analysis. Multiple imputation, if later justified, is sensitivity-only.
7. **Device support:** report standalone benchmark contrasts only when the prespecified support rules above are met. Sparse strata remain eligible for pooled/partially pooled models with clear labeling.
8. **Outcome seal:** only after this lock is recorded may the equity models calculate error, bias contrasts, confidence intervals, or non-disparate-performance results.

### Decision outcome

**Accepted.** The plan follows the dual-measure structure in FDA's January 2025 draft while adapting transparently to the repository's repeated encounters and missing ear-site colorimetry. It does not claim that this retrospective dataset satisfies a pivotal regulatory study design.
"""
    ),
    nbf.v4.new_code_cell(
        """measure_lock = pd.DataFrame([
    ["Co-primary A", "Forehead MST groups 1-4 / 5-7 / 8-10", "Largest adjusted absolute pairwise bias difference", "3.5 pp at SaO2 70-85; 1.5 pp at >85-100"],
    ["Co-primary B", "Continuous emitter-site ITA", "Adjusted bias difference over a 100-degree ITA change", "3.5 pp at SaO2 70-85; 1.5 pp at >85-100"],
    ["Secondary", "Fitzpatrick", "Sensitivity/descriptive only", "No equivalence claim"],
    ["Secondary", "Forehead ITA / melanin index / alternate Monk sites", "Robustness and concordance", "No primary margin"],
], columns=["role", "measure", "estimand", "margin_or_interpretation"])
measure_lock.to_csv(TABLE_DIR / "pigmentation_measure_lock.csv", index=False)

qa = pd.DataFrame({
    "check": ["Frozen rows preserved", "Pair key unique", "MST valid range", "ITA finite when present", "No error outcome loaded", "Core strata reproduced"],
    "passed": [
        len(mapped) == 28693, mapped.pulse_row_id.is_unique,
        mapped.monk_forehead.dropna().between(1, 10).all(), np.isfinite(mapped.emitter_site_ita.dropna()).all(),
        "error" not in mapped.columns and "saturation" not in mapped.columns, len(device_support) == 11,
    ]
})
qa.to_csv(TABLE_DIR / "pigmentation_measure_lock_qa.csv", index=False)
display(measure_lock)
display(qa)
assert qa.passed.all()
print("Pigmentation measurement plan locked; equity outcomes remain sealed.")"""
    ),
]

nbf.write(nb, OUTPUT)
print(OUTPUT)
