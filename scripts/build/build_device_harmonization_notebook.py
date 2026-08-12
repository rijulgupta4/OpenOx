from pathlib import Path

import nbformat as nbf


OUTPUT = Path(r".\notebooks\03_device_harmonization.ipynb")

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python (openox)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}

nb["cells"] = [
    nbf.v4.new_markdown_cell(
        """# Device and probe harmonization

## tl;dr

The 81 raw text labels previously counted in the 180-second cohort collapse to 65 normalized device/probe strata without removing any of the 28,693 paired readings or exposing new duplicate keys. Eleven strata meet the conservative core inference rule (>=30 participants, >=300 accuracy-range pairs, and >=50 pairs in every SaO2 band); 11 more meet an extended descriptive rule. Only three strata have enough occult-hypoxemia denominator and event support for standalone device/probe rates. Known probe IDs and probe-unknown records remain separate.
"""
    ),
    nbf.v4.new_markdown_cell(
        """## Context & Methods

The OpenOximetry v1.1.1 release notes state that the integer portion of a device value represents the device ID and the decimal portion represents a probe ID; further probe metadata are deferred to a future release. The repository describes `devices.csv` as one row per pulse-oximeter model with a unique ID and light-transmission mode. The current local `devices.csv` exposes only `device_number` and an opaque numeric `device_type` code.

### Key assumptions

- Whitespace and numeric-format variants such as `10`, `10.0`, and `56 .01` are formatting aliases, not separate devices.
- A missing decimal suffix means **probe unknown**, not probe zero.
- Known probe-specific records are not pooled with unknown-probe records for primary device/probe inference.
- Device-type codes remain opaque unless an authoritative codebook is recovered.
- The 180-second timestamp rule and unique-nearest-reference logic from D008 remain unchanged.

Source: https://www.physionet.org/content/openox-repo/1.1.1/
"""
    ),
    nbf.v4.new_code_cell(
        """from pathlib import Path
import sys
import gc

import numpy as np
import pandas as pd
from IPython.display import display

PROJECT_ROOT = Path.cwd()
if not (PROJECT_ROOT / "src").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_source_data_dir

SOURCE_DIR = get_source_data_dir()
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
TABLE_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
WINDOW_SECONDS = 180

print(f"Project: {PROJECT_ROOT}")
print(f"Source: {SOURCE_DIR}")"""
    ),
    nbf.v4.new_markdown_cell("## Data\n\n### Normalize raw device identifiers before checking uniqueness"),
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
    return pd.DataFrame({
        "device_clean": cleaned,
        "device_value": numeric,
        "device_base_id": base,
        "probe_id": probe,
        "device_probe_key": key,
    })

pulseox = pd.read_csv(SOURCE_DIR / "pulseoximeter.csv", low_memory=False, dtype={"device": "string"})
pulseox["pulse_row_id"] = np.arange(len(pulseox))
pulseox["device_raw"] = pulseox["device"]
pulseox = pd.concat([pulseox, normalize_device(pulseox["device_raw"])], axis=1)
pulseox["sample_key"] = pd.to_numeric(pulseox["sample_number"], errors="coerce").astype("Int64")
pulseox["saturation"] = pd.to_numeric(pulseox["saturation"], errors="coerce")
pulseox["probe_location_code"] = pd.to_numeric(pulseox["probe_location"], errors="coerce").astype("Int64")

raw_key = ["encounter_id", "sample_key", "device_raw", "probe_location_code"]
normalized_key = ["encounter_id", "sample_key", "device_probe_key", "probe_location_code"]
pulseox["ambiguous_raw_key"] = pulseox.duplicated(raw_key, keep=False)
pulseox["ambiguous_normalized_key"] = pulseox.duplicated(normalized_key, keep=False)

label_audit = (
    pulseox.groupby(["device_probe_key", "device_base_id", "probe_id"], dropna=False)
    .agg(
        raw_rows=("pulse_row_id", "size"),
        raw_text_variants=("device_raw", "nunique"),
        encounters=("encounter_id", "nunique"),
        raw_key_ambiguous_rows=("ambiguous_raw_key", "sum"),
        normalized_key_ambiguous_rows=("ambiguous_normalized_key", "sum"),
    )
    .reset_index()
    .sort_values("raw_rows", ascending=False)
)

normalization_summary = pd.DataFrame({
    "metric": [
        "Pulse-oximeter rows", "Distinct raw text labels", "Distinct normalized device/probe keys",
        "Rows with missing/unparseable device", "Rows ambiguous under raw key",
        "Rows ambiguous after normalization", "Additional ambiguous rows exposed by normalization",
    ],
    "value": [
        len(pulseox), pulseox["device_raw"].nunique(dropna=True), pulseox["device_probe_key"].nunique(dropna=True),
        pulseox["device_value"].isna().sum(), pulseox["ambiguous_raw_key"].sum(),
        pulseox["ambiguous_normalized_key"].sum(),
        (pulseox["ambiguous_normalized_key"] & ~pulseox["ambiguous_raw_key"]).sum(),
    ],
})
normalization_summary.to_csv(TABLE_DIR / "device_label_normalization_summary.csv", index=False)
label_audit.to_csv(TABLE_DIR / "device_label_normalization_audit.csv", index=False)
display(normalization_summary)
display(label_audit.head(15))"""
    ),
    nbf.v4.new_markdown_cell("### Audit device lookup and encounter assignment fields"),
    nbf.v4.new_code_cell(
        """devices = pd.read_csv(SOURCE_DIR / "devices.csv", low_memory=False)
devices["device_number"] = pd.to_numeric(devices["device_number"], errors="coerce").astype("Int64")
devices = devices.rename(columns={"device_number": "device_base_id", "device_type": "device_type_code"})

encounter = pd.read_csv(SOURCE_DIR / "encounter.csv", low_memory=False)
device_columns = [column for column in encounter.columns if column.endswith("_device")]
assignment = encounter[["encounter_id"] + device_columns].melt(
    id_vars="encounter_id", var_name="assignment_field", value_name="assignment_raw"
).dropna(subset=["assignment_raw"])
assignment["assignment_location"] = assignment["assignment_field"].str.replace("_device", "", regex=False)
assignment = pd.concat([assignment.reset_index(drop=True), normalize_device(assignment["assignment_raw"].reset_index(drop=True))], axis=1)

exact_map = (
    assignment.groupby(["encounter_id", "device_value"], dropna=False)
    .agg(exact_location_count=("assignment_location", "nunique"), exact_location=("assignment_location", "first"))
    .reset_index()
)
base_map = (
    assignment.groupby(["encounter_id", "device_base_id"], dropna=False)
    .agg(base_location_count=("assignment_location", "nunique"), base_location=("assignment_location", "first"))
    .reset_index()
)

pulseox = pulseox.merge(exact_map, on=["encounter_id", "device_value"], how="left", validate="many_to_one")
pulseox = pulseox.merge(base_map, on=["encounter_id", "device_base_id"], how="left", validate="many_to_one")
pulseox["assignment_status"] = np.select(
    [
        pulseox["exact_location_count"].eq(1),
        pulseox["exact_location_count"].gt(1),
        pulseox["base_location_count"].eq(1),
        pulseox["base_location_count"].gt(1),
    ],
    ["exact_unique", "exact_ambiguous", "base_unique", "base_ambiguous"],
    default="no_assignment",
)
pulseox["inferred_assignment_location"] = np.where(
    pulseox["assignment_status"].eq("exact_unique"), pulseox["exact_location"],
    np.where(pulseox["assignment_status"].eq("base_unique"), pulseox["base_location"], pd.NA),
)

lookup_coverage = (
    pulseox[["device_base_id"]].drop_duplicates()
    .merge(devices, on="device_base_id", how="left", validate="one_to_one")
)
assignment_coverage = (
    pulseox["assignment_status"].value_counts(dropna=False).rename_axis("assignment_status").reset_index(name="pulse_rows")
)
assignment_coverage["share"] = assignment_coverage["pulse_rows"] / len(pulseox)
assignment_coverage.to_csv(TABLE_DIR / "device_assignment_coverage.csv", index=False)

location_crosswalk = (
    pulseox.dropna(subset=["probe_location_code", "inferred_assignment_location"])
    .groupby(["probe_location_code", "inferred_assignment_location"])
    .size().rename("pulse_rows").reset_index()
)
location_crosswalk["share_within_code"] = location_crosswalk["pulse_rows"] / location_crosswalk.groupby("probe_location_code")["pulse_rows"].transform("sum")
location_crosswalk.to_csv(TABLE_DIR / "probe_location_crosswalk_audit.csv", index=False)

print(f"Encounter device-assignment fields: {len(device_columns)}")
print(f"Normalized base device IDs in pulseox: {pulseox['device_base_id'].nunique(dropna=True)}")
unmatched_parseable_bases = lookup_coverage["device_base_id"].notna() & lookup_coverage["device_type_code"].isna()
print(f"Parseable base IDs absent from devices.csv: {unmatched_parseable_bases.sum()}")
display(devices["device_type_code"].value_counts(dropna=False).rename_axis("device_type_code").reset_index(name="models"))
display(assignment_coverage.style.format({"share": "{:.1%}"}))
display(location_crosswalk.sort_values(["probe_location_code", "pulse_rows"], ascending=[True, False]).head(20).style.format({"share_within_code": "{:.1%}"}))"""
    ),
    nbf.v4.new_markdown_cell("## Results\n\n### Rebuild the 180-second cohort using normalized-key ambiguity checks"),
    nbf.v4.new_code_cell(
        """key = ["encounter_id", "sample_key"]
waveform_files = sorted((SOURCE_DIR / "waveforms").rglob("*_2hz.csv"))
marker_frames, failed_files = [], []
for path in waveform_files:
    try:
        frame = pd.read_csv(
            path,
            usecols=lambda column: column in {"Sample", "Timestamp", "encounter_id"},
            low_memory=False,
        )
        required = {"Sample", "Timestamp", "encounter_id"}
        if not required.issubset(frame.columns):
            failed_files.append(str(path))
            continue
        frame = frame.dropna(subset=["Sample", "Timestamp", "encounter_id"])
        if len(frame):
            marker_frames.append(frame)
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

pairs = pulseox.merge(
    selected_reference[key + ["bloodgas_row_id", "so2", "gap_seconds"]], on=key, how="left", validate="many_to_one"
)
pairs = pairs.merge(encounter[["encounter_id", "patient_id"]], on="encounter_id", how="left", validate="many_to_one")
pairs["error"] = pairs["saturation"] - pairs["so2"]

raw_eligible = (
    pairs["saturation"].notna() & pairs["so2"].notna()
    & ~pairs["ambiguous_raw_key"] & pairs["gap_seconds"].le(WINDOW_SECONDS)
)
normalized_eligible = (
    pairs["saturation"].notna() & pairs["so2"].notna()
    & pairs["device_probe_key"].notna()
    & ~pairs["ambiguous_normalized_key"] & pairs["gap_seconds"].le(WINDOW_SECONDS)
)
cohort = pairs.loc[normalized_eligible].copy()

analytic_columns = [
    "patient_id", "encounter_id", "sample_key", "pulse_row_id", "bloodgas_row_id",
    "device_base_id", "probe_id", "device_probe_key", "probe_location_code",
    "assignment_status", "inferred_assignment_location", "saturation", "so2", "error", "gap_seconds",
]
analytic_cohort_path = PROCESSED_DIR / "analytic_cohort_180s.csv.gz"
cohort[analytic_columns].to_csv(analytic_cohort_path, index=False, compression="gzip")
print(f"Frozen analytic cohort: {analytic_cohort_path} ({len(cohort):,} rows)")

cohort_impact = pd.DataFrame({
    "cohort_rule": ["Prior raw-label ambiguity rule", "Normalized device/probe ambiguity rule"],
    "paired_rows": [raw_eligible.sum(), normalized_eligible.sum()],
    "participants": [pairs.loc[raw_eligible, "patient_id"].nunique(), cohort["patient_id"].nunique()],
    "encounters": [pairs.loc[raw_eligible, "encounter_id"].nunique(), cohort["encounter_id"].nunique()],
    "device_probe_strata": [pairs.loc[raw_eligible, "device_probe_key"].nunique(), cohort["device_probe_key"].nunique()],
})
cohort_impact.to_csv(TABLE_DIR / "device_normalization_cohort_impact.csv", index=False)
display(cohort_impact)

del marker_frames, markers_raw, bloodgas, candidates, nearest, pairs
gc.collect()"""
    ),
    nbf.v4.new_markdown_cell("### Quantify support for device/probe-specific inference"),
    nbf.v4.new_code_cell(
        """cohort["in_accuracy_range"] = cohort["so2"].between(70, 100, inclusive="both")
cohort["sao2_70_80"] = cohort["so2"].ge(70) & cohort["so2"].lt(80)
cohort["sao2_80_90"] = cohort["so2"].ge(80) & cohort["so2"].lt(90)
cohort["sao2_90_100"] = cohort["so2"].ge(90) & cohort["so2"].le(100)
cohort["occult_denominator"] = cohort["saturation"].between(92, 96)
cohort["occult_event"] = cohort["occult_denominator"] & cohort["so2"].lt(88)

support = (
    cohort.groupby(["device_probe_key", "device_base_id", "probe_id"], dropna=False)
    .agg(
        paired_rows=("pulse_row_id", "size"), participants=("patient_id", "nunique"), encounters=("encounter_id", "nunique"),
        accuracy_pairs=("in_accuracy_range", "sum"), pairs_70_80=("sao2_70_80", "sum"),
        pairs_80_90=("sao2_80_90", "sum"), pairs_90_100=("sao2_90_100", "sum"),
        occult_denominator_pairs=("occult_denominator", "sum"), occult_events=("occult_event", "sum"),
        mean_error=("error", "mean"),
    )
    .reset_index()
    .merge(devices, on="device_base_id", how="left", validate="many_to_one")
)

support["core_inferential_accuracy"] = (
    support["participants"].ge(30)
    & support["accuracy_pairs"].ge(300)
    & support[["pairs_70_80", "pairs_80_90", "pairs_90_100"]].min(axis=1).ge(50)
)
support["extended_descriptive_accuracy"] = (
    ~support["core_inferential_accuracy"]
    & support["participants"].ge(20)
    & support["accuracy_pairs"].ge(200)
    & support[["pairs_70_80", "pairs_80_90", "pairs_90_100"]].min(axis=1).ge(30)
)
support["exploratory_accuracy"] = (
    ~support["core_inferential_accuracy"]
    & ~support["extended_descriptive_accuracy"]
    & support["participants"].ge(10)
    & support["accuracy_pairs"].ge(100)
)
support["occult_rate_reportable"] = support["occult_denominator_pairs"].ge(100) & support["occult_events"].ge(10)
support = support.sort_values(["core_inferential_accuracy", "extended_descriptive_accuracy", "participants", "accuracy_pairs"], ascending=False)
support.to_csv(TABLE_DIR / "device_probe_inference_support.csv", index=False)

support_summary = pd.DataFrame({
    "tier": [
        "Core inference: >=30 participants, >=300 accuracy pairs, >=50 pairs in each SaO2 band",
        "Extended descriptive: >=20 participants, >=200 accuracy pairs, >=30 pairs in each SaO2 band",
        "Exploratory descriptive: >=10 participants and >=100 accuracy pairs",
        "Pooled analysis only",
        "Reportable device/probe occult rate: >=100 denominator pairs and >=10 events",
    ],
    "device_probe_strata": [
        support["core_inferential_accuracy"].sum(), support["extended_descriptive_accuracy"].sum(),
        support["exploratory_accuracy"].sum(),
        (~support["core_inferential_accuracy"] & ~support["extended_descriptive_accuracy"] & ~support["exploratory_accuracy"]).sum(),
        support["occult_rate_reportable"].sum(),
    ],
})
support_summary.to_csv(TABLE_DIR / "device_probe_support_summary.csv", index=False)
display(support_summary)
display(support.head(20).style.format({"mean_error": "{:.3f}"}))"""
    ),
    nbf.v4.new_markdown_cell(
        """## Takeaways

- The analysis entity should be the normalized **device/probe stratum**, while the integer base ID remains available for model-level summaries.
- Unknown-probe rows must remain distinct from explicit probe IDs; no probe metadata should be invented.
- Device type is retained as an opaque repository code until the missing data dictionary or another authoritative codebook is recovered.
- Eleven device/probe strata meet the conservative core inference rule; 11 additional strata meet the extended descriptive rule, nine are exploratory, and 34 remain pooled-analysis only.
- The support tiers are pragmatic academic-analysis rules, not FDA sample-size claims. Even the core tier remains below FDA pivotal-study recommendations, so results will emphasize estimates and clustered uncertainty rather than regulatory conclusions.
- Sparse device-specific occult events should not be forced into unstable standalone rates; strata failing the event rule remain usable in pooled repeated-measures models.
"""
    ),
    nbf.v4.new_code_cell(
        """# QA checks
assert len(failed_files) == 0
assert pulseox["device_value"].notna().sum() + pulseox["device_value"].isna().sum() == len(pulseox)
assert reliable_markers.duplicated(key).sum() == 0
assert selected_reference.duplicated(key).sum() == 0
assert cohort["gap_seconds"].le(WINDOW_SECONDS).all()
assert not cohort["ambiguous_normalized_key"].any()
assert cohort[["saturation", "so2", "patient_id", "device_probe_key"]].notna().all().all()
assert analytic_cohort_path.exists()
assert support["paired_rows"].sum() == len(cohort)
assert support.loc[support["core_inferential_accuracy"], ["pairs_70_80", "pairs_80_90", "pairs_90_100"]].min(axis=1).ge(50).all()
print("All device-harmonization QA checks passed.")"""
    ),
]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, OUTPUT)
print(OUTPUT)
