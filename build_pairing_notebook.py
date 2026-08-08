from pathlib import Path
import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.metadata["kernelspec"] = {"display_name": "Python (openox)", "language": "python", "name": "python3"}
nb.metadata["language_info"] = {"name": "python", "version": "3"}

cells = []
cells.append(nbf.v4.new_markdown_cell("""# Phase 1b — Pairing diagnostics

## TL;DR

The nominal `encounter_id + sample` blood-gas key is not unique: **13,117 keys repeat**, and nearly all repeated keys contain conflicting measurements rather than harmless copies. The public-build notebook shows that blood-gas data were merged to waveform sample markers before release, which helps explain how repeats can arise but does not make arbitrary row selection defensible.

A conservative recovery path is feasible: use reliable 2 Hz waveform sample timestamps, select a blood-gas row only when the nearest timestamp is unique, require a provisional gap of no more than 180 seconds, and exclude ambiguous pulse-ox keys. This notebook measures the resulting cohort without yet writing a patient-level analytic dataset.

Sources: [PhysioNet OpenOximetry v1.1.1](https://www.physionet.org/content/openox-repo/1.1.1/), [Scientific Data descriptor](https://www.nature.com/articles/s41597-025-04870-8), and the [official public database build notebook](https://github.com/OpenOximetry/PublicDatabaseCode/blob/master/2_process_redcap.ipynb)."""))

cells.append(nbf.v4.new_code_cell("""from pathlib import Path
import sys

import numpy as np
import pandas as pd
from IPython.display import display

PROJECT_ROOT = Path.cwd()
if not (PROJECT_ROOT / "src").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_source_data_dir

SOURCE_DIR = get_source_data_dir()
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "tables"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print(f"Project: {PROJECT_ROOT}")
print(f"Source data: {SOURCE_DIR}")"""))

cells.append(nbf.v4.new_markdown_cell("""## 1. Diagnose the blood-gas key

We distinguish exact duplicate rows from repeated keys that contain conflicting analytes. A repeated clinical key with different `SO2`, `PO2`, `PCO2`, pH, or time cannot be safely resolved with `drop_duplicates()` or by choosing the most complete row."""))

cells.append(nbf.v4.new_code_cell("""bloodgas = pd.read_csv(SOURCE_DIR / "bloodgas.csv", low_memory=False)
key = ["encounter_id", "sample_key"]
bloodgas["sample_key"] = pd.to_numeric(bloodgas["sample"], errors="coerce").astype("Int64")

original_columns = [c for c in bloodgas.columns if c != "sample_key"]
exact_mask = bloodgas[original_columns].duplicated(keep=False)
exact_duplicate_rows = int(exact_mask.sum())
exact_duplicate_groups = int(bloodgas.loc[exact_mask, original_columns].drop_duplicates().shape[0])

complete = bloodgas.dropna(subset=key).copy()
key_sizes = complete.groupby(key).size().rename("rows_per_key")
duplicate_keys = key_sizes[key_sizes > 1]
duplicate_rows = complete.set_index(key).index.isin(duplicate_keys.index)

duplicate_frame = complete.loc[duplicate_rows]
core_columns = ["so2", "po2", "pco2", "ph", "time"]
conflict_by_column = pd.DataFrame({
    "column": core_columns,
    "duplicate_keys_with_conflict": [
        int((duplicate_frame.groupby(key)[column].nunique(dropna=True) > 1).sum())
        for column in core_columns
    ],
})
core_conflict = duplicate_frame.groupby(key)[core_columns].nunique(dropna=True).gt(1).any(axis=1)

duplicate_summary = pd.DataFrame({
    "metric": [
        "bloodgas_rows", "complete_key_rows", "unique_complete_keys",
        "duplicate_keys", "rows_in_duplicate_keys", "exact_duplicate_rows",
        "exact_duplicate_groups", "duplicate_keys_with_core_conflict",
        "duplicate_keys_without_core_conflict",
    ],
    "value": [
        len(bloodgas), len(complete), len(key_sizes), len(duplicate_keys),
        int(duplicate_rows.sum()), exact_duplicate_rows, exact_duplicate_groups,
        int(core_conflict.sum()), int((~core_conflict).sum()),
    ],
})

duplicate_summary.to_csv(OUTPUT_DIR / "bloodgas_duplicate_diagnostics.csv", index=False)
conflict_by_column.to_csv(OUTPUT_DIR / "bloodgas_conflict_by_column.csv", index=False)
display(duplicate_summary)
display(conflict_by_column)"""))

cells.append(nbf.v4.new_markdown_cell("""## 2. Recover sample timing from the 2 Hz waveforms

The waveform tables retain a `Sample` marker and exact `Timestamp`. Repeated marker rows usually span only adjacent 0.5-second observations. We conservatively exclude marker keys whose span exceeds 5 seconds, because those may represent more than one marker event."""))

cells.append(nbf.v4.new_code_cell("""waveform_files = sorted((SOURCE_DIR / "waveforms").rglob("*_2hz.csv"))
marker_frames, failed_files = [], []
for path in waveform_files:
    try:
        frame = pd.read_csv(
            path,
            usecols=lambda c: c in {"Sample", "Timestamp", "encounter_id"},
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

markers = (
    markers_raw.groupby(key, as_index=False)
    .agg(
        marker_timestamp=("marker_timestamp", "median"),
        marker_rows=("marker_timestamp", "size"),
        marker_time_min=("marker_timestamp", "min"),
        marker_time_max=("marker_timestamp", "max"),
    )
)
markers["marker_span_seconds"] = (markers["marker_time_max"] - markers["marker_time_min"]).dt.total_seconds()
reliable_markers = markers.loc[markers["marker_span_seconds"].le(5)].copy()

marker_summary = pd.DataFrame({
    "metric": ["waveform_files", "failed_files", "raw_marker_rows", "unique_marker_keys", "reliable_marker_keys", "excluded_marker_keys_span_over_5_seconds", "marker_encounters"],
    "value": [len(waveform_files), len(failed_files), len(markers_raw), len(markers), len(reliable_markers), int(markers["marker_span_seconds"].gt(5).sum()), markers["encounter_id"].nunique()],
})
display(marker_summary)
display(markers["marker_span_seconds"].quantile([0, .5, .9, .95, .99, 1]).rename("marker_span_seconds").to_frame())"""))

cells.append(nbf.v4.new_markdown_cell("""## 3. Select only a unique nearest blood-gas timestamp

For each reliable waveform marker, calculate the absolute gap to every blood-gas row sharing its encounter/sample key. Keep the reference only if exactly one row has the minimum gap. Ties remain unresolved and are excluded."""))

cells.append(nbf.v4.new_code_cell("""bloodgas["bloodgas_row_id"] = np.arange(len(bloodgas))
bloodgas["bloodgas_timestamp"] = pd.to_datetime(
    bloodgas["date"].astype("string") + " " + bloodgas["time"].astype("string"),
    errors="coerce",
)

candidates = bloodgas.merge(
    reliable_markers[key + ["marker_timestamp"]], on=key, how="inner", validate="many_to_one"
)
candidates["gap_seconds"] = (candidates["bloodgas_timestamp"] - candidates["marker_timestamp"]).abs().dt.total_seconds()
candidates["minimum_gap"] = candidates.groupby(key)["gap_seconds"].transform("min")
candidates["is_nearest"] = candidates["gap_seconds"].eq(candidates["minimum_gap"])
nearest = candidates.loc[candidates["is_nearest"]].copy()
nearest_counts = nearest.groupby(key).size().rename("nearest_rows").reset_index()
selected_unique = nearest.merge(
    nearest_counts.loc[nearest_counts["nearest_rows"].eq(1), key], on=key, how="inner"
)

duplicate_key_frame = duplicate_keys.rename("bloodgas_rows").reset_index()
duplicate_with_marker = duplicate_key_frame.merge(reliable_markers[key], on=key, how="inner")
duplicate_resolution = duplicate_with_marker.merge(nearest_counts, on=key, how="left")

gap_quantiles = selected_unique["gap_seconds"].quantile([0, .25, .5, .75, .9, .95, .99, 1]).rename_axis("quantile").reset_index(name="gap_seconds")
gap_quantiles.to_csv(OUTPUT_DIR / "time_pairing_gap_quantiles.csv", index=False)

time_summary = pd.DataFrame({
    "metric": [
        "all_bloodgas_keys", "duplicate_bloodgas_keys", "all_keys_with_reliable_marker",
        "duplicate_keys_with_reliable_marker", "duplicate_keys_uniquely_resolved",
        "duplicate_keys_tied_at_nearest", "duplicate_keys_without_reliable_marker",
        "selected_unique_within_60_seconds", "selected_unique_within_180_seconds",
        "selected_unique_within_300_seconds",
    ],
    "value": [
        len(key_sizes), len(duplicate_keys),
        len(key_sizes.reset_index().merge(reliable_markers[key], on=key, how="inner")),
        len(duplicate_with_marker), int(duplicate_resolution["nearest_rows"].eq(1).sum()),
        int(duplicate_resolution["nearest_rows"].gt(1).sum()), len(duplicate_keys) - len(duplicate_with_marker),
        int(selected_unique["gap_seconds"].le(60).sum()),
        int(selected_unique["gap_seconds"].le(180).sum()),
        int(selected_unique["gap_seconds"].le(300).sum()),
    ],
})
time_summary.to_csv(OUTPUT_DIR / "time_pairing_feasibility.csv", index=False)
display(time_summary)
display(gap_quantiles)"""))

cells.append(nbf.v4.new_markdown_cell("""## 4. Provisional high-confidence paired cohort

For feasibility only, apply a 180-second maximum gap and require nonmissing SpO2/SaO2. This threshold is **provisional** and should be locked in the analysis plan before inferential work. Pulse-ox keys repeated within encounter/sample/device/probe are flagged; none survive into this provisional cohort, but the exclusion remains explicit."""))

cells.append(nbf.v4.new_code_cell("""pulseox = pd.read_csv(SOURCE_DIR / "pulseoximeter.csv", low_memory=False)
pulseox["sample_key"] = pd.to_numeric(pulseox["sample_number"], errors="coerce").astype("Int64")
pulse_key = ["encounter_id", "sample_key", "device", "probe_location"]
pulseox["ambiguous_pulse_key"] = pulseox.duplicated(pulse_key, keep=False)

selected_reference = selected_unique[key + ["bloodgas_row_id", "so2", "gap_seconds"]]
pairs = pulseox.merge(selected_reference, on=key, how="left", validate="many_to_one")
valid_pair = pairs["saturation"].notna() & pairs["so2"].notna()
within_180 = valid_pair & pairs["gap_seconds"].le(180)
primary_mask = within_180 & ~pairs["ambiguous_pulse_key"]
primary_pairs = pairs.loc[primary_mask].copy()

encounter = pd.read_csv(SOURCE_DIR / "encounter.csv", low_memory=False)
primary_pairs = primary_pairs.merge(
    encounter[["encounter_id", "patient_id", "fitzpatrick", "monk_dorsal"]],
    on="encounter_id", how="left", validate="many_to_one"
)

cohort_summary = pd.DataFrame({
    "metric": [
        "valid_spo2_rows", "valid_spo2_sao2_pairs_after_unique_time_selection",
        "pairs_with_gap_over_180_seconds", "ambiguous_pulseox_rows_overall",
        "ambiguous_pulseox_rows_within_180_second_cohort", "primary_pairs",
        "primary_participants", "primary_encounters", "primary_device_labels",
        "fitzpatrick_pair_row_coverage", "monk_dorsal_pair_row_coverage",
    ],
    "value": [
        int(pairs["saturation"].notna().sum()), int(valid_pair.sum()),
        int((valid_pair & pairs["gap_seconds"].gt(180)).sum()),
        int(pulseox["ambiguous_pulse_key"].sum()),
        int((within_180 & pairs["ambiguous_pulse_key"]).sum()), len(primary_pairs),
        primary_pairs["patient_id"].nunique(), primary_pairs["encounter_id"].nunique(),
        primary_pairs["device"].nunique(dropna=True),
        primary_pairs["fitzpatrick"].notna().mean(), primary_pairs["monk_dorsal"].notna().mean(),
    ],
})
cohort_summary.to_csv(OUTPUT_DIR / "time_resolved_cohort_coverage.csv", index=False)
display(cohort_summary)
display(primary_pairs["device"].value_counts(dropna=False).head(15).rename("paired_rows").to_frame())"""))

cells.append(nbf.v4.new_markdown_cell("""## 5. QA and decision

The primary-analysis candidate is the timestamp-resolved subset, not the naive encounter/sample merge. Rows without a reliable marker, tied nearest reference, missing saturation, or exceeding the locked time window should remain outside the primary cohort. Sensitivity analyses can later compare 60-, 180-, and 300-second windows after the analysis plan is frozen."""))

cells.append(nbf.v4.new_code_cell("""assert len(failed_files) == 0, "Some 2 Hz files could not be scanned"
assert reliable_markers.duplicated(key).sum() == 0
assert selected_unique.duplicated(key).sum() == 0
assert primary_pairs["gap_seconds"].le(180).all()
assert primary_pairs[["saturation", "so2"]].notna().all().all()
assert not primary_pairs["ambiguous_pulse_key"].any()
assert len(primary_pairs) > 0
print("All QA checks passed.")
print("Recommendation: carry the timestamp-resolved cohort into analysis-plan lock; do not use the naive key join.")"""))

nb["cells"] = cells
nb["metadata"]["openox"] = {"phase": "1", "purpose": "pairing diagnostics", "patient_level_output_written": False}

out = Path("phase0_staging") / "01b_pairing_diagnostics.ipynb"
out.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, out)
print(out.resolve())
