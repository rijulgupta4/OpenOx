"""Compare locked OpenOx pairing windows using authorized local source data."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.config import get_source_data_dir

source = get_source_data_dir()
key = ["encounter_id", "sample_key"]

marker_frames = []
for path in sorted((source / "waveforms").rglob("*_2hz.csv")):
    frame = pd.read_csv(path, usecols=lambda c: c in {"Sample", "Timestamp", "encounter_id"}, low_memory=False)
    if {"Sample", "Timestamp", "encounter_id"}.issubset(frame.columns):
        frame = frame.dropna(subset=["Sample", "Timestamp", "encounter_id"])
        if len(frame):
            marker_frames.append(frame)
markers_raw = pd.concat(marker_frames, ignore_index=True)
markers_raw["sample_key"] = pd.to_numeric(markers_raw["Sample"], errors="coerce").astype("Int64")
markers_raw["marker_timestamp"] = pd.to_datetime(markers_raw["Timestamp"], errors="coerce")
markers_raw = markers_raw.dropna(subset=["sample_key", "marker_timestamp"])
markers = markers_raw.groupby(key, as_index=False).agg(
    marker_timestamp=("marker_timestamp", "median"),
    marker_min=("marker_timestamp", "min"),
    marker_max=("marker_timestamp", "max"),
)
markers["marker_span_seconds"] = (markers["marker_max"] - markers["marker_min"]).dt.total_seconds()
markers = markers.loc[markers["marker_span_seconds"].le(5)]

bloodgas = pd.read_csv(source / "bloodgas.csv", low_memory=False)
bloodgas["sample_key"] = pd.to_numeric(bloodgas["sample"], errors="coerce").astype("Int64")
bloodgas["bloodgas_row_id"] = np.arange(len(bloodgas))
bloodgas["bloodgas_timestamp"] = pd.to_datetime(
    bloodgas["date"].astype("string") + " " + bloodgas["time"].astype("string"), errors="coerce"
)
candidates = bloodgas.merge(markers[key + ["marker_timestamp"]], on=key, how="inner", validate="many_to_one")
candidates["gap_seconds"] = (candidates["bloodgas_timestamp"] - candidates["marker_timestamp"]).abs().dt.total_seconds()
candidates["min_gap"] = candidates.groupby(key)["gap_seconds"].transform("min")
nearest = candidates.loc[candidates["gap_seconds"].eq(candidates["min_gap"])].copy()
nearest_counts = nearest.groupby(key).size().rename("nearest_rows").reset_index()
selected = nearest.merge(nearest_counts.loc[nearest_counts["nearest_rows"].eq(1), key], on=key, how="inner")

pulse = pd.read_csv(source / "pulseoximeter.csv", low_memory=False)
pulse["pulse_row_id"] = np.arange(len(pulse))
pulse["sample_key"] = pd.to_numeric(pulse["sample_number"], errors="coerce").astype("Int64")
pulse["saturation"] = pd.to_numeric(pulse["saturation"], errors="coerce")
pulse_key = ["encounter_id", "sample_key", "device", "probe_location"]
pulse["ambiguous_pulse_key"] = pulse.duplicated(pulse_key, keep=False)
pairs = pulse.merge(selected[key + ["bloodgas_row_id", "so2", "gap_seconds"]], on=key, how="left", validate="many_to_one")
encounter = pd.read_csv(source / "encounter.csv", low_memory=False)
pairs = pairs.merge(
    encounter[["encounter_id", "patient_id", "fitzpatrick", "monk_dorsal"]],
    on="encounter_id", how="left", validate="many_to_one"
)
pairs["error"] = pairs["saturation"] - pairs["so2"]
eligible = pairs["saturation"].notna() & pairs["so2"].notna() & ~pairs["ambiguous_pulse_key"]

rows = []
cohorts = {}
for window in (60, 180, 300):
    cohort = pairs.loc[eligible & pairs["gap_seconds"].le(window)].copy()
    cohorts[window] = cohort
    rows.append({
        "window_seconds": window,
        "paired_rows": len(cohort),
        "participants": cohort["patient_id"].nunique(),
        "encounters": cohort["encounter_id"].nunique(),
        "device_labels": cohort["device"].nunique(dropna=True),
        "fitzpatrick_coverage": cohort["fitzpatrick"].notna().mean(),
        "monk_dorsal_coverage": cohort["monk_dorsal"].notna().mean(),
        "median_sao2": cohort["so2"].median(),
        "sao2_below_88_share": cohort["so2"].lt(88).mean(),
        "mean_error_bias": cohort["error"].mean(),
        "error_sd_precision": cohort["error"].std(ddof=1),
        "mean_absolute_error": cohort["error"].abs().mean(),
        "arms": np.sqrt(np.mean(np.square(cohort["error"]))),
        "median_gap_seconds": cohort["gap_seconds"].median(),
        "p90_gap_seconds": cohort["gap_seconds"].quantile(.9),
    })
summary = pd.DataFrame(rows)
print("SUMMARY")
print(summary.to_string(index=False))

bands = [(-np.inf, 60, "0-60"), (60, 180, "60-180"), (180, 300, "180-300")]
incremental = []
for low, high, label in bands:
    mask = eligible & pairs["gap_seconds"].le(high)
    if np.isfinite(low):
        mask &= pairs["gap_seconds"].gt(low)
    cohort = pairs.loc[mask]
    incremental.append({
        "gap_band_seconds": label,
        "paired_rows": len(cohort),
        "participants": cohort["patient_id"].nunique(),
        "encounters": cohort["encounter_id"].nunique(),
        "mean_error_bias": cohort["error"].mean(),
        "arms": np.sqrt(np.mean(np.square(cohort["error"]))),
        "median_sao2": cohort["so2"].median(),
        "sao2_below_88_share": cohort["so2"].lt(88).mean(),
    })
incremental = pd.DataFrame(incremental)
print("\nINCREMENTAL")
print(incremental.to_string(index=False))

print("\nNESTED", set(cohorts[60].pulse_row_id).issubset(set(cohorts[180].pulse_row_id)), set(cohorts[180].pulse_row_id).issubset(set(cohorts[300].pulse_row_id)))
print("\nFITZ MIX")
for window, cohort in cohorts.items():
    print(window, cohort["fitzpatrick"].value_counts(normalize=True, dropna=False).sort_index().round(4).to_dict())
print("\nMONK MIX")
for window, cohort in cohorts.items():
    print(window, cohort["monk_dorsal"].value_counts(normalize=True, dropna=False).sort_index().round(4).to_dict())
