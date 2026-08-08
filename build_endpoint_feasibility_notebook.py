from pathlib import Path

import nbformat as nbf


OUTPUT = Path(r".\02_endpoint_feasibility.ipynb")

nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python (openox)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}

nb["cells"] = [
    nbf.v4.new_markdown_cell(
        """# Endpoint feasibility for the OpenOx analysis plan

## tl;dr

The locked 180-second cohort supports both proposed endpoints. Of 28,693 pairs, 27,891 (97.2%) fall in the primary SaO2 70-100% accuracy range; their pooled bias is +1.130 percentage points and pooled A_RMS is 3.237. The canonical occult-hypoxemia definition (SpO2 92-96% with SaO2 <88%) has 6,062 eligible pairs and 261 events (4.3%) spanning 38 participants. Device-specific occult-event inference will need support rules because only 17 raw device labels contribute an event.
"""
    ),
    nbf.v4.new_markdown_cell(
        """## Context & Methods

### Locked endpoint definitions

- **Device accuracy:** error = SpO2 - SaO2; primary metric = device-specific A_RMS over SaO2 70-100%, with mean bias, error SD, and repeated-measures Bland-Altman limits as complementary measures.
- **Occult hypoxemia:** primary definition = SaO2 <88% while SpO2 is 92-96%; sensitivity definitions use SpO2 >=92% and/or SaO2 <=88%.
- **Inference:** participant-clustered uncertainty will be required because controlled-desaturation studies contribute repeated observations per participant. This notebook is descriptive only.

### Key assumptions

The deterministic pairing rules and 180-second maximum timestamp gap accepted in D008 are reused without modification. Device labels are not yet harmonized into final device/probe families.

### External methodological anchors

- FDA, *Pulse Oximeters for Medical Purposes: Non-Clinical and Clinical Performance Testing, Labeling, and Premarket Submission Recommendations* (January 2025 draft; nonbinding and not for implementation): https://www.fda.gov/media/184896/download
- FDA, *Pulse Oximeters - Premarket Notification Submissions [510(k)s]* (2013 guidance): https://www.fda.gov/regulatory-information/search-fda-guidance-documents/pulse-oximeters-premarket-notification-submissions-510ks-guidance-industry-and-food-drug
- Sjoding et al., *Racial Bias in Pulse Oximetry Measurement* (NEJM 2020): https://doi.org/10.1056/NEJMc2029240
- OpenOximetry Repository v1.1.1: https://www.physionet.org/content/openox-repo/1.1.1/
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
WINDOW_SECONDS = 180

print(f"Project: {PROJECT_ROOT}")
print(f"Source: {SOURCE_DIR}")
print(f"Primary pairing window: {WINDOW_SECONDS} seconds")"""
    ),
    nbf.v4.new_markdown_cell("## Data\n\n### Rebuild the accepted 180-second pairing cohort"),
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
    marker_timestamp=("marker_timestamp", "median"),
    marker_min=("marker_timestamp", "min"),
    marker_max=("marker_timestamp", "max"),
)
markers["marker_span_seconds"] = (markers["marker_max"] - markers["marker_min"]).dt.total_seconds()
reliable_markers = markers.loc[markers["marker_span_seconds"].le(5)].copy()

bloodgas = pd.read_csv(SOURCE_DIR / "bloodgas.csv", low_memory=False)
bloodgas["sample_key"] = pd.to_numeric(bloodgas["sample"], errors="coerce").astype("Int64")
bloodgas["bloodgas_row_id"] = np.arange(len(bloodgas))
bloodgas["bloodgas_timestamp"] = pd.to_datetime(
    bloodgas["date"].astype("string") + " " + bloodgas["time"].astype("string"), errors="coerce"
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
    & pairs["gap_seconds"].le(WINDOW_SECONDS)
)
cohort = pairs.loc[eligible].copy()

print(f"Accepted 180-second pairs: {len(cohort):,}")
print(f"Participants: {cohort['patient_id'].nunique():,}")
print(f"Encounters: {cohort['encounter_id'].nunique():,}")
print(f"Raw device labels: {cohort['device'].nunique(dropna=True):,}")

del marker_frames, markers_raw, bloodgas, candidates, nearest, pulseox, encounter, pairs
gc.collect()"""
    ),
    nbf.v4.new_markdown_cell("## Results\n\n### Accuracy-range and saturation-bin support"),
    nbf.v4.new_code_cell(
        """range_masks = {
    "SaO2 70-100% (accuracy analysis range)": cohort["so2"].between(70, 100, inclusive="both"),
    "SaO2 <70% (outside primary accuracy range)": cohort["so2"].lt(70),
    "SaO2 >100% or missing": cohort["so2"].gt(100) | cohort["so2"].isna(),
    "SaO2 70-<80%": cohort["so2"].ge(70) & cohort["so2"].lt(80),
    "SaO2 80-<90%": cohort["so2"].ge(80) & cohort["so2"].lt(90),
    "SaO2 90-100%": cohort["so2"].ge(90) & cohort["so2"].le(100),
}

range_rows = []
for label, mask in range_masks.items():
    subset = cohort.loc[mask]
    range_rows.append({
        "range": label,
        "paired_rows": len(subset),
        "share_of_180s_cohort": len(subset) / len(cohort),
        "participants": subset["patient_id"].nunique(),
        "encounters": subset["encounter_id"].nunique(),
        "device_labels": subset["device"].nunique(dropna=True),
        "mean_error_bias": subset["error"].mean(),
        "arms": np.sqrt(np.mean(np.square(subset["error"]))) if len(subset) else np.nan,
    })

range_summary = pd.DataFrame(range_rows)
range_summary.to_csv(TABLE_DIR / "endpoint_sao2_range_coverage.csv", index=False)
display(range_summary.style.format({
    "share_of_180s_cohort": "{:.1%}", "mean_error_bias": "{:.3f}", "arms": "{:.3f}"
}))"""
    ),
    nbf.v4.new_markdown_cell("### Occult-hypoxemia definition support"),
    nbf.v4.new_code_cell(
        """definitions = [
    ("Primary candidate", "SpO2 92-96%; SaO2 <88%", cohort["saturation"].between(92, 96), cohort["so2"].lt(88)),
    ("SpO2-bound sensitivity", "SpO2 >=92%; SaO2 <88%", cohort["saturation"].ge(92), cohort["so2"].lt(88)),
    ("SaO2-rounding sensitivity", "SpO2 92-96%; SaO2 <=88%", cohort["saturation"].between(92, 96), cohort["so2"].le(88)),
    ("Combined sensitivity", "SpO2 >=92%; SaO2 <=88%", cohort["saturation"].ge(92), cohort["so2"].le(88)),
]

occult_rows = []
for role, definition, denominator_mask, event_mask in definitions:
    denominator = cohort.loc[denominator_mask]
    events = cohort.loc[denominator_mask & event_mask]
    occult_rows.append({
        "role": role,
        "definition": definition,
        "eligible_pairs": len(denominator),
        "event_pairs": len(events),
        "pair_level_rate": len(events) / len(denominator) if len(denominator) else np.nan,
        "eligible_participants": denominator["patient_id"].nunique(),
        "participants_with_event": events["patient_id"].nunique(),
        "eligible_encounters": denominator["encounter_id"].nunique(),
        "device_labels_in_denominator": denominator["device"].nunique(dropna=True),
        "device_labels_with_event": events["device"].nunique(dropna=True),
    })

occult_summary = pd.DataFrame(occult_rows)
occult_summary.to_csv(TABLE_DIR / "endpoint_occult_hypoxemia_feasibility.csv", index=False)
display(occult_summary.style.format({"pair_level_rate": "{:.1%}"}))"""
    ),
    nbf.v4.new_markdown_cell("### Device-level support for the candidate endpoints"),
    nbf.v4.new_code_cell(
        """accuracy_mask = cohort["so2"].between(70, 100, inclusive="both")
occult_denominator_mask = cohort["saturation"].between(92, 96)
occult_event_mask = occult_denominator_mask & cohort["so2"].lt(88)

device_support = (
    cohort.assign(
        in_accuracy_range=accuracy_mask,
        in_occult_denominator=occult_denominator_mask,
        occult_event=occult_event_mask,
    )
    .groupby("device", dropna=False)
    .agg(
        total_pairs=("pulse_row_id", "size"),
        participants=("patient_id", "nunique"),
        encounters=("encounter_id", "nunique"),
        accuracy_range_pairs=("in_accuracy_range", "sum"),
        occult_denominator_pairs=("in_occult_denominator", "sum"),
        occult_event_pairs=("occult_event", "sum"),
    )
    .reset_index()
    .sort_values(["participants", "accuracy_range_pairs"], ascending=False)
)
device_support.to_csv(TABLE_DIR / "endpoint_device_support.csv", index=False)

support_summary = pd.DataFrame({
    "criterion": [
        ">=10 participants", ">=20 participants", ">=30 participants",
        ">=200 accuracy-range pairs", ">=20 occult-denominator pairs", ">=5 occult events",
    ],
    "device_labels_meeting": [
        device_support["participants"].ge(10).sum(),
        device_support["participants"].ge(20).sum(),
        device_support["participants"].ge(30).sum(),
        device_support["accuracy_range_pairs"].ge(200).sum(),
        device_support["occult_denominator_pairs"].ge(20).sum(),
        device_support["occult_event_pairs"].ge(5).sum(),
    ],
})
display(support_summary)
display(device_support.head(15))"""
    ),
    nbf.v4.new_markdown_cell(
        """## Takeaways

- The observed support is sufficient to lock the primary endpoint definitions without choosing thresholds solely because they produce favorable results.
- The accuracy analysis retains 97.2% of the 180-second cohort. Values below 70% remain clinically informative but are outside the primary standards-aligned accuracy range and will be reported separately.
- The primary occult-hypoxemia definition produces 261 events among 6,062 eligible readings (4.3%); definition sensitivities change the rate only modestly.
- Treat FDA performance criteria as methodological anchors, not as a claim of regulatory validation: this repository analysis is retrospective, multi-device, and not a manufacturer-sponsored pivotal study.
- The next lock should specify device/probe harmonization and minimum support, then select a participant-level repeated-measures uncertainty method before any device ranking or subgroup inference.
"""
    ),
    nbf.v4.new_code_cell(
        """# QA checks
assert len(failed_files) == 0
assert reliable_markers.duplicated(key).sum() == 0
assert selected_reference.duplicated(key).sum() == 0
assert len(cohort) == 28_693
assert cohort[["saturation", "so2", "patient_id"]].notna().all().all()
assert cohort["gap_seconds"].le(WINDOW_SECONDS).all()
assert not cohort["ambiguous_pulse_key"].any()
assert range_summary.loc[range_summary["range"].eq("SaO2 70-100% (accuracy analysis range)"), "paired_rows"].iloc[0] > 0
assert occult_summary["eligible_pairs"].gt(0).all()
assert (occult_summary["event_pairs"] <= occult_summary["eligible_pairs"]).all()
assert device_support["total_pairs"].sum() == len(cohort)
print("All endpoint-feasibility QA checks passed.")"""
    ),
]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, OUTPUT)
print(OUTPUT)
