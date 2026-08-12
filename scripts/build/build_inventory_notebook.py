from pathlib import Path
import nbformat as nbf

output_path = Path("notebooks/01_data_inventory.ipynb")
output_path.parent.mkdir(parents=True, exist_ok=True)

nb = nbf.v4.new_notebook()
nb.metadata = {
    "kernelspec": {"display_name": "Python (openox)", "language": "python", "name": "openox"},
    "language_info": {"name": "python", "version": "3.12"},
}

nb.cells = [
    nbf.v4.new_markdown_cell("""# OpenOx Phase 1: Data Inventory and Pairing Feasibility

## tl;dr

This notebook profiles OpenOximetry v1.1.1 before an analytic cohort is built. It tests table grain, candidate-key uniqueness, referential integrity, SpO₂/SaO₂ pairing coverage, skin-variable coverage, and device/probe consistency. The executed results will determine the Phase 1.5 analysis plan."""),
    nbf.v4.new_markdown_cell("""## Context & Methods

The intended downstream grain is one paired SpO₂/SaO₂ observation for a specific device and probe configuration. This notebook does not calculate subgroup outcome differences.

### Key Assumptions

- patient_id identifies participants.
- encounter_id connects encounter and measurement tables.
- pulseoximeter sample_number is the candidate match to bloodgas sample.
- Blood-gas so2 is the candidate arterial reference saturation.
- Device suffixes may represent distinct configurations and are not collapsed.
- Missingness and pairing feasibility are assessed before endpoints and margins are locked."""),
    nbf.v4.new_code_cell("""from pathlib import Path
import sys
import numpy as np
import pandas as pd
from IPython.display import display

WORKING_DIR = Path.cwd().resolve()
PROJECT_ROOT = WORKING_DIR if (WORKING_DIR / "src").is_dir() else WORKING_DIR.parent
if not (PROJECT_ROOT / "src").is_dir():
    raise RuntimeError("Launch from the OpenOx Project directory or its notebooks directory.")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import TABLE_DIR, get_source_data_dir

SOURCE_DIR = get_source_data_dir()
TABLE_DIR.mkdir(parents=True, exist_ok=True)
pd.set_option("display.max_columns", 80)
pd.set_option("display.max_rows", 100)
print(f"Project root: {PROJECT_ROOT}")
print(f"Source data: {SOURCE_DIR}")"""),
    nbf.v4.new_markdown_cell("""## Data

### 1. Load the six relational source tables"""),
    nbf.v4.new_code_cell("""TABLE_FILES = {
    "patient": "patient.csv",
    "encounter": "encounter.csv",
    "bloodgas": "bloodgas.csv",
    "pulseoximeter": "pulseoximeter.csv",
    "spectrophotometer": "spectrophotometer.csv",
    "devices": "devices.csv",
}
tables = {
    name: pd.read_csv(SOURCE_DIR / filename, low_memory=False)
    for name, filename in TABLE_FILES.items()
}
for name, frame in tables.items():
    print(f"{name:20s} {len(frame):>8,} rows x {frame.shape[1]:>3} columns")"""),
    nbf.v4.new_markdown_cell("""## Results

### 2. Source-table inventory"""),
    nbf.v4.new_code_cell("""inventory_rows = []
for table_name, filename in TABLE_FILES.items():
    frame = tables[table_name]
    inventory_rows.append({
        "table_name": table_name,
        "file_name": filename,
        "n_rows": len(frame),
        "n_columns": frame.shape[1],
        "n_patients": frame["patient_id"].nunique(dropna=True) if "patient_id" in frame else np.nan,
        "n_encounters": frame["encounter_id"].nunique(dropna=True) if "encounter_id" in frame else np.nan,
        "has_spo2": "saturation" in frame,
        "has_sao2": "so2" in frame,
        "has_perfusion_index": "pi" in frame,
        "file_size_mb": round((SOURCE_DIR / filename).stat().st_size / 1_048_576, 3),
    })
data_inventory = pd.DataFrame(inventory_rows)
data_inventory.to_csv(TABLE_DIR / "data_inventory.csv", index=False)
display(data_inventory)"""),
    nbf.v4.new_markdown_cell("""### 3. Candidate keys and table grain

A failed candidate key may indicate a finer table grain rather than corrupt data. Any such key must be understood before joining."""),
    nbf.v4.new_code_cell("""CANDIDATE_KEYS = {
    "patient": ["patient_id"],
    "encounter": ["encounter_id"],
    "bloodgas": ["encounter_id", "sample"],
    "pulseoximeter": ["encounter_id", "sample_number", "device", "probe_location"],
    "spectrophotometer": ["encounter_id", "group", "date_calc"],
    "devices": ["device_number"],
}

def key_profile(table_name, frame, columns):
    complete = frame.loc[frame[columns].notna().all(axis=1), columns]
    duplicate_mask = complete.duplicated(columns, keep=False)
    return {
        "table_name": table_name,
        "candidate_key": " + ".join(columns),
        "n_rows": len(frame),
        "complete_key_rows": len(complete),
        "duplicate_key_rows": int(duplicate_mask.sum()),
        "duplicate_key_groups": int(complete.loc[duplicate_mask].drop_duplicates(columns).shape[0]),
        "is_unique_when_complete": bool(not duplicate_mask.any()),
    }

key_checks = pd.DataFrame([
    key_profile(name, tables[name], columns)
    for name, columns in CANDIDATE_KEYS.items()
])
key_checks.to_csv(TABLE_DIR / "table_key_checks.csv", index=False)
display(key_checks)"""),
    nbf.v4.new_markdown_cell("""### 4. Referential integrity"""),
    nbf.v4.new_code_cell("""patient_ids = set(tables["patient"]["patient_id"].dropna())
encounter_ids = set(tables["encounter"]["encounter_id"].dropna())

integrity_rows = [{
    "relationship": "encounter.patient_id to patient.patient_id",
    "child_rows": len(tables["encounter"]),
    "orphan_rows": int((~tables["encounter"]["patient_id"].isin(patient_ids)).sum()),
}]
for child_name in ["bloodgas", "pulseoximeter", "spectrophotometer"]:
    child = tables[child_name]
    orphan_mask = ~child["encounter_id"].isin(encounter_ids)
    integrity_rows.append({
        "relationship": f"{child_name}.encounter_id to encounter.encounter_id",
        "child_rows": len(child),
        "orphan_rows": int(orphan_mask.sum()),
    })
referential_integrity = pd.DataFrame(integrity_rows)
referential_integrity["orphan_rate"] = referential_integrity["orphan_rows"] / referential_integrity["child_rows"]
referential_integrity.to_csv(TABLE_DIR / "referential_integrity.csv", index=False)
display(referential_integrity)"""),
    nbf.v4.new_markdown_cell("""### 5. SpO₂/SaO₂ pairing feasibility

The initial candidate pairing key is encounter_id plus sample. This section measures match coverage and detects ambiguous blood-gas keys before cohort construction."""),
    nbf.v4.new_code_cell("""bloodgas = tables["bloodgas"].copy()
pulseox = tables["pulseoximeter"].copy()
bloodgas["sample_key"] = pd.to_numeric(bloodgas["sample"], errors="coerce").astype("Int64")
pulseox["sample_key"] = pd.to_numeric(pulseox["sample_number"], errors="coerce").astype("Int64")
pair_key = ["encounter_id", "sample_key"]

bg_key_counts = bloodgas.dropna(subset=pair_key).groupby(pair_key).size().rename("bloodgas_rows").reset_index()
px_key_counts = pulseox.dropna(subset=pair_key).groupby(pair_key).size().rename("pulseox_rows").reset_index()
key_comparison = px_key_counts.merge(bg_key_counts, on=pair_key, how="left")

pulseox_with_match = pulseox.merge(bg_key_counts, on=pair_key, how="left", validate="many_to_one")
valid_spo2 = pulseox_with_match["saturation"].notna()
matched_spo2 = valid_spo2 & pulseox_with_match["bloodgas_rows"].notna()
ambiguous_spo2 = valid_spo2 & pulseox_with_match["bloodgas_rows"].fillna(0).gt(1)

pairing_feasibility = pd.DataFrame([
    {"metric": "Blood-gas rows", "count": len(bloodgas), "denominator": len(bloodgas)},
    {"metric": "Unique blood-gas encounter/sample keys", "count": len(bg_key_counts), "denominator": len(bg_key_counts)},
    {"metric": "Blood-gas keys with more than one row", "count": int((bg_key_counts["bloodgas_rows"] > 1).sum()), "denominator": len(bg_key_counts)},
    {"metric": "Pulse-oximeter rows", "count": len(pulseox), "denominator": len(pulseox)},
    {"metric": "Pulse-oximeter rows with nonmissing SpO2", "count": int(valid_spo2.sum()), "denominator": len(pulseox)},
    {"metric": "Nonmissing SpO2 rows with blood-gas match", "count": int(matched_spo2.sum()), "denominator": int(valid_spo2.sum())},
    {"metric": "Nonmissing SpO2 rows with ambiguous blood-gas key", "count": int(ambiguous_spo2.sum()), "denominator": int(valid_spo2.sum())},
    {"metric": "Pulse-ox encounter/sample keys with match", "count": int(key_comparison["bloodgas_rows"].notna().sum()), "denominator": len(key_comparison)},
])
pairing_feasibility["rate"] = pairing_feasibility["count"] / pairing_feasibility["denominator"]
pairing_feasibility.to_csv(TABLE_DIR / "pairing_feasibility.csv", index=False)
display(pairing_feasibility)"""),
    nbf.v4.new_markdown_cell("""### 6. Skin-pigmentation measurement coverage

Visual ratings and spectrophotometer sites are reported separately. Anatomical sites are not assumed to be interchangeable."""),
    nbf.v4.new_code_cell("""encounter = tables["encounter"]
skin_columns = ["fitzpatrick", "monk_fingernail", "monk_dorsal", "monk_palmar", "monk_upper_arm", "monk_forehead"]
skin_rows = []
for column in skin_columns:
    nonmissing = int(encounter[column].notna().sum())
    skin_rows.append({
        "source_table": "encounter",
        "measurement": column,
        "n_rows": len(encounter),
        "n_nonmissing": nonmissing,
        "coverage_rate": nonmissing / len(encounter),
        "n_encounters": encounter.loc[encounter[column].notna(), "encounter_id"].nunique(),
    })

spectro = tables["spectrophotometer"]
for group_name, group_frame in spectro.groupby("group", dropna=False):
    complete_lab = group_frame[["lab_l", "lab_a", "lab_b"]].notna().all(axis=1)
    skin_rows.append({
        "source_table": "spectrophotometer",
        "measurement": f"CIELAB: {group_name if pd.notna(group_name) else 'missing group'}",
        "n_rows": len(group_frame),
        "n_nonmissing": int(complete_lab.sum()),
        "coverage_rate": float(complete_lab.mean()),
        "n_encounters": group_frame.loc[complete_lab, "encounter_id"].nunique(),
    })

skin_coverage = pd.DataFrame(skin_rows).sort_values(["source_table", "measurement"])
skin_coverage.to_csv(TABLE_DIR / "skin_variable_coverage.csv", index=False)
display(skin_coverage)"""),
    nbf.v4.new_markdown_cell("""### 7. Device and probe inventory

Formatting is normalized only for comparison. Original values and decimal suffixes remain distinguishable."""),
    nbf.v4.new_code_cell("""def normalize_device_label(value):
    if pd.isna(value):
        return pd.NA
    text = str(value).strip().replace(" ", "")
    try:
        number = float(text)
    except ValueError:
        return text
    if number.is_integer():
        return str(int(number))
    return f"{number:.10f}".rstrip("0").rstrip(".")

pulseox["device_normalized"] = pulseox["device"].map(normalize_device_label)
pulseox["probe_location_clean"] = pulseox["probe_location"].astype("string").str.strip().replace("", pd.NA)

device_probe_inventory = (
    pulseox.groupby(["device_normalized", "probe_location_clean"], dropna=False)
    .agg(
        n_rows=("saturation", "size"),
        n_spo2_nonmissing=("saturation", "count"),
        n_pi_nonmissing=("pi", "count"),
        n_encounters=("encounter_id", "nunique"),
        n_raw_device_labels=("device", lambda values: values.nunique(dropna=True)),
    )
    .reset_index()
    .sort_values(["n_rows", "device_normalized"], ascending=[False, True])
)
device_probe_inventory.to_csv(TABLE_DIR / "device_probe_inventory.csv", index=False)
display(device_probe_inventory.head(30))"""),
    nbf.v4.new_markdown_cell("""### 8. Feasibility summary"""),
    nbf.v4.new_code_cell("""summary = {
    "participants": int(tables["patient"]["patient_id"].nunique(dropna=True)),
    "encounters": int(tables["encounter"]["encounter_id"].nunique(dropna=True)),
    "bloodgas_rows": len(bloodgas),
    "pulseox_rows": len(pulseox),
    "valid_spo2_rows": int(valid_spo2.sum()),
    "matched_valid_spo2_rows": int(matched_spo2.sum()),
    "matched_valid_spo2_rate": float(matched_spo2.sum() / valid_spo2.sum()),
    "ambiguous_bg_keys": int((bg_key_counts["bloodgas_rows"] > 1).sum()),
    "normalized_devices": int(pulseox["device_normalized"].nunique(dropna=True)),
    "encounters_with_fitzpatrick": int(encounter["fitzpatrick"].notna().sum()),
    "encounters_with_monk_dorsal": int(encounter["monk_dorsal"].notna().sum()),
}
summary_table = pd.DataFrame([{"metric": key, "value": value} for key, value in summary.items()])
summary_table.to_csv(TABLE_DIR / "phase1_feasibility_summary.csv", index=False)
display(summary_table)
print(f"Candidate pairing coverage: {summary['matched_valid_spo2_rate']:.1%}")
if summary["ambiguous_bg_keys"]:
    print("CAUTION: Resolve nonunique blood-gas encounter/sample keys before cohort construction.")"""),
    nbf.v4.new_markdown_cell("""## Takeaways

1. Confirm the true grain of every candidate key that is not unique.
2. Resolve ambiguous blood-gas encounter/sample keys before joining.
3. Select eligible device–probe configurations based on coverage and interpretable identifiers.
4. Select the primary pigmentation measure and anatomical site based on coverage and probe relevance.
5. Lock endpoints, exclusions, correlation structure, and any equivalence margin only after these checks.

Generated tables are written to outputs/tables."""),
]

nbf.write(nb, output_path)
print(output_path)
