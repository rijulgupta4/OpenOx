from pathlib import Path
import nbformat as nbf

nb = nbf.v4.new_notebook()
nb.metadata["kernelspec"] = {"display_name": "Python (openox)", "language": "python", "name": "python3"}
nb.metadata["language_info"] = {"name": "python", "version": "3"}
nb.metadata["openox"] = {"phase": "1", "purpose": "pairing-window sensitivity", "patient_level_output_written": False}

cells = []
cells.append(nbf.v4.new_markdown_cell("""# Phase 1c — Pairing-window sensitivity

## TL;DR

The 60-, 180-, and 300-second cohorts are strictly nested and contain the same **123 participants, 325 encounters, and 81 device labels**. The 180-second rule retains **28,693 paired readings**, adding **8,106 (+39.4%)** versus 60 seconds without expanding the participant, encounter, or device universe. Its descriptive bias and A_RMS remain close to the 60-second estimates.

Extending from 180 to 300 seconds adds only **1,058 readings (+3.7%)**. Those added readings are selectively more hypoxemic (median SaO2 82.2%; 68.2% below 88%) and show higher mean error (+1.88 percentage points) than either shorter-gap band. That pattern could reflect genuine low-saturation device behavior, timestamp uncertainty, or both.

**Recommendation:** retain **180 seconds as the provisional primary rule**, use **60 seconds as the stricter sensitivity analysis**, and use **300 seconds only as an outer stress test**. This is a cohort-selection recommendation, not an inferential result; repeated-measure models and outcome definitions remain to be locked."""))

cells.append(nbf.v4.new_markdown_cell("""## Context & Methods

The purpose is to test whether the provisional 180-second timestamp criterion materially changes cohort composition or descriptive SpO2 error relative to stricter and looser alternatives.

### Key assumptions

- The time window resolves duplicated blood-gas rows against the waveform sample marker; it does not replace OpenOximetry's sample-number link.
- Waveform marker keys spanning more than 5 seconds remain excluded.
- A blood-gas reference is retained only when the nearest timestamp is unique.
- Pulse-oximeter keys duplicated within encounter/sample/device/probe are excluded rather than arbitrarily selected.
- Error is `SpO2 - SaO2`; positive values indicate overestimation.
- Error metrics here are descriptive. They do not account for repeated measurements within encounters or participants and are not final device-performance estimates.
- No patient-level analytic cohort is written by this notebook; only aggregate tables and figures are saved."""))

cells.append(nbf.v4.new_code_cell("""from pathlib import Path
import sys
import subprocess

import numpy as np
import pandas as pd
import gc
from IPython.display import Image, display

PROJECT_ROOT = Path.cwd()
if not (PROJECT_ROOT / "src").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import get_source_data_dir

SOURCE_DIR = get_source_data_dir()
TABLE_DIR = PROJECT_ROOT / "outputs" / "tables"
FIGURE_DIR = PROJECT_ROOT / "outputs" / "figures"
TABLE_DIR.mkdir(parents=True, exist_ok=True)
FIGURE_DIR.mkdir(parents=True, exist_ok=True)

WINDOWS = [60, 180, 300]

print(f"Project: {PROJECT_ROOT}")
print(f"Source: {SOURCE_DIR}")"""))

cells.append(nbf.v4.new_markdown_cell("""## Data

### 1. Recover reliable waveform sample markers"""))

cells.append(nbf.v4.new_code_cell("""key = ["encounter_id", "sample_key"]
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
    marker_timestamp=("marker_timestamp", "median"),
    marker_min=("marker_timestamp", "min"),
    marker_max=("marker_timestamp", "max"),
)
markers["marker_span_seconds"] = (markers["marker_max"] - markers["marker_min"]).dt.total_seconds()
reliable_markers = markers.loc[markers["marker_span_seconds"].le(5)].copy()

print(f"2 Hz files scanned: {len(waveform_files):,}")
print(f"Failed files: {len(failed_files):,}")
print(f"Reliable marker keys: {len(reliable_markers):,} of {len(markers):,}")
del marker_frames, markers_raw
gc.collect()"""))

cells.append(nbf.v4.new_markdown_cell("""### 2. Select unique nearest blood-gas references and construct eligible pairs"""))

cells.append(nbf.v4.new_code_cell("""bloodgas = pd.read_csv(SOURCE_DIR / "bloodgas.csv", low_memory=False)
bloodgas["sample_key"] = pd.to_numeric(bloodgas["sample"], errors="coerce").astype("Int64")
bloodgas["bloodgas_row_id"] = np.arange(len(bloodgas))
bloodgas["bloodgas_timestamp"] = pd.to_datetime(
    bloodgas["date"].astype("string") + " " + bloodgas["time"].astype("string"),
    errors="coerce",
)

candidates = bloodgas.merge(
    reliable_markers[key + ["marker_timestamp"]], on=key, how="inner", validate="many_to_one"
)
candidates["gap_seconds"] = (
    candidates["bloodgas_timestamp"] - candidates["marker_timestamp"]
).abs().dt.total_seconds()
candidates["minimum_gap"] = candidates.groupby(key)["gap_seconds"].transform("min")
nearest = candidates.loc[candidates["gap_seconds"].eq(candidates["minimum_gap"])].copy()
nearest_counts = nearest.groupby(key).size().rename("nearest_rows").reset_index()
selected_reference = nearest.merge(
    nearest_counts.loc[nearest_counts["nearest_rows"].eq(1), key], on=key, how="inner"
)

pulseox = pd.read_csv(SOURCE_DIR / "pulseoximeter.csv", low_memory=False)
pulseox["pulse_row_id"] = np.arange(len(pulseox))
pulseox["sample_key"] = pd.to_numeric(pulseox["sample_number"], errors="coerce").astype("Int64")
pulseox["saturation"] = pd.to_numeric(pulseox["saturation"], errors="coerce")
pulse_key = ["encounter_id", "sample_key", "device", "probe_location"]
pulseox["ambiguous_pulse_key"] = pulseox.duplicated(pulse_key, keep=False)

pairs = pulseox.merge(
    selected_reference[key + ["bloodgas_row_id", "so2", "gap_seconds"]],
    on=key, how="left", validate="many_to_one",
)
encounter = pd.read_csv(SOURCE_DIR / "encounter.csv", low_memory=False)
pairs = pairs.merge(
    encounter[["encounter_id", "patient_id", "fitzpatrick", "monk_dorsal"]],
    on="encounter_id", how="left", validate="many_to_one",
)
pairs["error"] = pairs["saturation"] - pairs["so2"]
eligible = (
    pairs["saturation"].notna()
    & pairs["so2"].notna()
    & ~pairs["ambiguous_pulse_key"]
)

print(f"Unique timestamp-resolved reference keys: {len(selected_reference):,}")
print(f"Eligible pulse-ox rows before a maximum-gap rule: {eligible.sum():,}")
del bloodgas, candidates, nearest, pulseox, encounter
gc.collect()"""))

cells.append(nbf.v4.new_markdown_cell("""## Results

### 3. Compare nested cohort size, coverage, and descriptive error"""))

cells.append(nbf.v4.new_code_cell("""cohorts = {}
summary_rows = []
for window in WINDOWS:
    cohort = pairs.loc[eligible & pairs["gap_seconds"].le(window)].copy()
    cohorts[window] = cohort
    summary_rows.append({
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

summary = pd.DataFrame(summary_rows)
summary["retained_vs_180"] = summary["paired_rows"] / summary.loc[summary["window_seconds"].eq(180), "paired_rows"].iloc[0]
summary.to_csv(TABLE_DIR / "pairing_window_sensitivity_summary.csv", index=False)

display(summary.style.format({
    "fitzpatrick_coverage": "{:.1%}", "monk_dorsal_coverage": "{:.1%}",
    "sao2_below_88_share": "{:.1%}", "retained_vs_180": "{:.1%}",
    "mean_error_bias": "{:.3f}", "error_sd_precision": "{:.3f}",
    "mean_absolute_error": "{:.3f}", "arms": "{:.3f}",
    "median_gap_seconds": "{:.1f}", "p90_gap_seconds": "{:.1f}",
}))"""))

cells.append(nbf.v4.new_markdown_cell("""The retained-row and incremental-band figures are generated after both aggregate tables are available."""))

cells.append(nbf.v4.new_markdown_cell("""### 4. Characterize what each wider window adds"""))

cells.append(nbf.v4.new_code_cell("""bands = [(-np.inf, 60, "0-60"), (60, 180, "60-180"), (180, 300, "180-300")]
incremental_rows = []
for low, high, label in bands:
    mask = eligible & pairs["gap_seconds"].le(high)
    if np.isfinite(low):
        mask &= pairs["gap_seconds"].gt(low)
    cohort = pairs.loc[mask].copy()
    incremental_rows.append({
        "gap_band_seconds": label,
        "paired_rows": len(cohort),
        "participants": cohort["patient_id"].nunique(),
        "encounters": cohort["encounter_id"].nunique(),
        "median_sao2": cohort["so2"].median(),
        "sao2_below_88_share": cohort["so2"].lt(88).mean(),
        "mean_error_bias": cohort["error"].mean(),
        "arms": np.sqrt(np.mean(np.square(cohort["error"]))),
    })

incremental = pd.DataFrame(incremental_rows)
incremental.to_csv(TABLE_DIR / "pairing_window_incremental_summary.csv", index=False)
display(incremental.style.format({
    "sao2_below_88_share": "{:.1%}", "mean_error_bias": "{:.3f}", "arms": "{:.3f}",
}))

plot_script = PROJECT_ROOT / "src" / "plot_pairing_window_sensitivity.py"
completed = subprocess.run(
    [sys.executable, str(plot_script), str(PROJECT_ROOT)],
    check=True, capture_output=True, text=True,
)
print(completed.stdout.strip())
display(Image(filename=str(FIGURE_DIR / "pairing_window_retention.png")))
display(Image(filename=str(FIGURE_DIR / "pairing_window_incremental_bands.png")))"""))

cells.append(nbf.v4.new_markdown_cell("""### 5. Check skin-tone and device composition stability"""))

cells.append(nbf.v4.new_code_cell("""skin_rows = []
device_rows = []
for window, cohort in cohorts.items():
    for variable in ["fitzpatrick", "monk_dorsal"]:
        values = cohort[variable].astype("string").fillna("Missing")
        counts = values.value_counts(dropna=False)
        for category, count in counts.items():
            skin_rows.append({
                "window_seconds": window, "variable": variable,
                "category": category, "paired_rows": int(count), "share": count / len(cohort),
            })
    device_counts = cohort["device"].astype("string").fillna("Missing").value_counts()
    for device, count in device_counts.items():
        device_rows.append({
            "window_seconds": window, "device": device,
            "paired_rows": int(count), "share": count / len(cohort),
        })

skin_distribution = pd.DataFrame(skin_rows)
device_distribution = pd.DataFrame(device_rows)
skin_distribution.to_csv(TABLE_DIR / "pairing_window_skin_distribution.csv", index=False)
device_distribution.to_csv(TABLE_DIR / "pairing_window_device_distribution.csv", index=False)

coverage = summary[["window_seconds", "fitzpatrick_coverage", "monk_dorsal_coverage"]].copy()
display(coverage.style.format({"fitzpatrick_coverage": "{:.1%}", "monk_dorsal_coverage": "{:.1%}"}))

top_devices = (
    device_distribution.loc[device_distribution["window_seconds"].eq(180)]
    .nlargest(10, "paired_rows")["device"].tolist()
)
device_pivot = (
    device_distribution.loc[device_distribution["device"].isin(top_devices)]
    .pivot(index="device", columns="window_seconds", values="share")
    .fillna(0)
    .sort_values(180, ascending=False)
)
display(device_pivot.style.format("{:.1%}"))"""))

cells.append(nbf.v4.new_markdown_cell("""## Takeaways

1. **Sixty seconds is usefully strict but costly at the reading level.** It retains the full participant, encounter, and device universe but removes 8,106 readings relative to 180 seconds.
2. **The 60- to 180-second increment is informative rather than merely duplicative.** It adds substantial low-SaO2 coverage while leaving aggregate descriptive error metrics close to the 60-second cohort.
3. **The 180- to 300-second increment is small and selective.** It adds 1,058 readings, disproportionately at lower SaO2, with higher positive error. Because low saturation itself can increase device error, this does not prove mispairing—but it makes 300 seconds a poor default primary rule.
4. **Skin-variable completeness changes only modestly.** Fitzpatrick coverage remains about 99%; Monk dorsal completeness declines as the window expands and should be handled explicitly in later subgroup analyses.
5. **Recommended hierarchy:** 180 seconds primary, 60 seconds strict sensitivity, 300 seconds outer stress test. Final inferential claims must use the repeated-measure model and endpoints locked in the next phase."""))

cells.append(nbf.v4.new_code_cell("""# QA checks
assert len(failed_files) == 0
assert reliable_markers.duplicated(key).sum() == 0
assert selected_reference.duplicated(key).sum() == 0
assert set(cohorts[60]["pulse_row_id"]).issubset(set(cohorts[180]["pulse_row_id"]))
assert set(cohorts[180]["pulse_row_id"]).issubset(set(cohorts[300]["pulse_row_id"]))
assert summary["participants"].nunique() == 1
assert summary["encounters"].nunique() == 1
assert summary["device_labels"].nunique() == 1
assert cohorts[60]["gap_seconds"].le(60).all()
assert cohorts[180]["gap_seconds"].le(180).all()
assert cohorts[300]["gap_seconds"].le(300).all()
assert all(not cohort["ambiguous_pulse_key"].any() for cohort in cohorts.values())
assert all(cohort[["saturation", "so2"]].notna().all().all() for cohort in cohorts.values())
print("All pairing-window sensitivity QA checks passed.")"""))

nb["cells"] = cells
out = Path("phase0_staging") / "01c_pairing_window_sensitivity.ipynb"
nbf.write(nb, out)
print(out.resolve())
