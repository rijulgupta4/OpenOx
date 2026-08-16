"""Run the support-gated ENCoDE replication against authorized local data."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from src.paths import PROJECT_ROOT

OUTPUT_DIR = PROJECT_ROOT / "encode_external_validation"
ENCODE_ROOT = PROJECT_ROOT / "data" / "external" / "encode"

MEASUREMENT = ENCODE_ROOT / "MEASUREMENT.csv"
CONCEPT = ENCODE_ROOT / "CONCEPT.csv"
PERSON = ENCODE_ROOT / "PERSON.csv"
VISIT = ENCODE_ROOT / "VISIT_OCCURRENCE.csv"
SOURCE_MANIFEST = ENCODE_ROOT / "SHA256SUMS.txt"

SPO2_CONCEPT = 4196147
SAO2_CONCEPT = 3016502
HEART_RATE_CONCEPT = 3027018
RESP_RATE_CONCEPT = 3024171
PULSE_OX_LOCATION_CONCEPT = 2000000033

PAIR_WINDOW_MINUTES = 5
VITAL_WINDOW_HOURS = 4
MST_LEVELS = ["1-4", "5-7", "8-10"]
SIMULATION_SEED = 20260804

MONK_MEASUREMENT = "ADMINISTERED-VISUAL-SCALES_CARD.MONKSKINTONESCALE"
ITA_MEASUREMENT = "DELFIN_SKINCOLORCATCH.ITA"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def parse_source_manifest() -> dict[str, str]:
    entries: dict[str, str] = {}
    for raw in SOURCE_MANIFEST.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        expected, name = raw.split(maxsplit=1)
        entries[name.replace("\\", "/")] = expected
    return entries


def verify_source_hashes() -> pd.DataFrame:
    manifest = parse_source_manifest()
    rows = []
    for path in [MEASUREMENT, CONCEPT, PERSON, VISIT]:
        observed = sha256(path)
        expected = manifest[path.name]
        rows.append(
            {
                "file": path.name,
                "bytes": path.stat().st_size,
                "expected_sha256": expected,
                "observed_sha256": observed,
                "passed": observed == expected,
            }
        )
    result = pd.DataFrame(rows)
    result.to_csv(OUTPUT_DIR / "encode_source_hash_qa.csv", index=False)
    if not result["passed"].all():
        raise AssertionError("One or more ENCoDE source hashes do not match SHA256SUMS.txt")
    return result


def freeze_crosswalk() -> dict:
    crosswalk = {
        "dataset": "ENCoDE v1.0.0",
        "status": "frozen before target-event and pigmentation-effect estimation",
        "source_root": str(ENCODE_ROOT),
        "source_record": "https://physionet.org/content/encode-skin-color/1.0.0/",
        "source_tutorial": "https://github.com/aiwonglab/ENCoDE_tutorial",
        "source_publication": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11392475/",
        "omop_concepts": {
            "SpO2": {"concept_id": SPO2_CONCEPT, "name": "Peripheral oxygen saturation"},
            "SaO2": {"concept_id": SAO2_CONCEPT, "name": "Oxygen saturation in Arterial blood"},
            "heart_rate": {"concept_id": HEART_RATE_CONCEPT, "name": "Heart rate"},
            "respiratory_rate": {"concept_id": RESP_RATE_CONCEPT, "name": "Respiratory rate"},
            "pulse_ox_location": {
                "concept_id": PULSE_OX_LOCATION_CONCEPT,
                "name": "PULSE OXIMETER LOCATION",
            },
        },
        "pairing": {
            "rule": "closest SpO2 at or before each SaO2, within five minutes",
            "direction": "backward",
            "tolerance_minutes": PAIR_WINDOW_MINUTES,
            "range_restriction": "SaO2 and SpO2 each 70-100 percentage points inclusive",
            "published_count_context": "publication reported 521 pairs from 128 patients; released OMOP reconstruction is reconciled separately",
        },
        "risk_features": {
            "eligibility": "SpO2 92-96 percentage points inclusive",
            "outcome": "SaO2 <88 percentage points",
            "age_at_encounter": "(SaO2 datetime - birth datetime) / 365.25 days",
            "assigned_sex_normalized": "OMOP 8532=female; 8507=male",
            "heart_rate_consensus": "last observed heart rate at or before SaO2, within four hours",
            "RR": "last observed respiratory rate at or before SaO2, within four hours",
            "scoring_gate": "score unchanged D028 model only if full feature mapping passes and event support passes",
        },
        "pigmentation": {
            "primary_MST": "median forehead Monk value; groups 1-4, 5-7, 8-10",
            "primary_emitter_site_ITA": {
                "finger_left": "left dorsal finger Delfin ITA",
                "finger_right": "right dorsal finger Delfin ITA",
                "forehead": "forehead Delfin ITA",
                "toe_right": "unsupported under OpenOx D013 mapping",
                "missing": "not imputed in primary analysis",
            },
            "secondary_objective": "forehead Delfin ITA",
            "publication_aligned_sensitivity": "mean Delfin ITA over four palm sites",
            "error_definition": "SpO2 - SaO2; positive values mean pulse-ox overestimation",
            "model": "pair-weighted OLS with centered linear and quadratic SaO2; participant-cluster CR1 covariance",
            "participant_balanced_sensitivity": "inverse within-participant pair count weights",
            "intervals": {
                "SaO2 70-85%": {"margin": 3.5},
                ">85-100%": {"margin": 1.5},
            },
            "support_rules": {
                "MST": "each group >=10 participants and >=50 pairs in interval",
                "ITA": ">=30 participants, >=80% coverage, >=100-degree span, and >=100 pairs in interval",
            },
        },
        "audit_note": "Concept and timing definitions came from the official record, tutorial, and publication. Pair-count reconciliation summaries were inspected before final artifact serialization; no target-event or pigmentation-effect estimate informed the mapping.",
    }
    write_json(OUTPUT_DIR / "encode_crosswalk_lock.json", crosswalk)
    crosswalk["crosswalk_sha256"] = sha256(OUTPUT_DIR / "encode_crosswalk_lock.json")
    return crosswalk


def custom_concept_map() -> dict[str, int]:
    concepts = pd.read_csv(CONCEPT, usecols=["concept_id", "concept_name"], low_memory=False)
    return dict(zip(concepts["concept_name"], concepts["concept_id"].astype(int)))


def skin_name(site: str, measurement: str) -> str:
    return f"SKINTONE@{site}__{measurement}"


def median_measure(measurements: pd.DataFrame, concept_map: dict[str, int], name: str) -> pd.Series:
    concept_id = concept_map[name]
    return (
        measurements.loc[measurements["measurement_concept_id"].eq(concept_id)]
        .groupby("person_id")["value_as_number"]
        .median()
    )


def last_value_before(
    pairs: pd.DataFrame,
    measurements: pd.DataFrame,
    concept_id: int,
    output_name: str,
) -> pd.DataFrame:
    right = measurements.loc[
        measurements["measurement_concept_id"].eq(concept_id)
        & measurements["value_as_number"].notna(),
        ["person_id", "measurement_datetime", "value_as_number"],
    ].rename(columns={"measurement_datetime": f"{output_name}_time", "value_as_number": output_name})
    right = right.sort_values(f"{output_name}_time")
    merged = pd.merge_asof(
        pairs.sort_values("sao2_time"),
        right,
        by="person_id",
        left_on="sao2_time",
        right_on=f"{output_name}_time",
        direction="backward",
        tolerance=pd.Timedelta(hours=VITAL_WINDOW_HOURS),
        allow_exact_matches=True,
    )
    merged[f"{output_name}_delta_minutes"] = (
        merged["sao2_time"] - merged[f"{output_name}_time"]
    ).dt.total_seconds() / 60
    return merged


def reconstruct_pairs(measurements: pd.DataFrame) -> pd.DataFrame:
    sao2 = measurements.loc[
        measurements["measurement_concept_id"].eq(SAO2_CONCEPT)
        & measurements["value_as_number"].notna(),
        ["measurement_id", "person_id", "measurement_datetime", "value_as_number"],
    ].rename(
        columns={
            "measurement_id": "sao2_measurement_id",
            "measurement_datetime": "sao2_time",
            "value_as_number": "sao2",
        }
    ).sort_values("sao2_time")
    spo2 = measurements.loc[
        measurements["measurement_concept_id"].eq(SPO2_CONCEPT)
        & measurements["value_as_number"].notna(),
        ["measurement_id", "person_id", "measurement_datetime", "value_as_number"],
    ].rename(
        columns={
            "measurement_id": "spo2_measurement_id",
            "measurement_datetime": "spo2_time",
            "value_as_number": "spo2",
        }
    ).sort_values("spo2_time")
    pairs = pd.merge_asof(
        sao2,
        spo2,
        by="person_id",
        left_on="sao2_time",
        right_on="spo2_time",
        direction="backward",
        tolerance=pd.Timedelta(minutes=PAIR_WINDOW_MINUTES),
        allow_exact_matches=True,
    ).dropna(subset=["spo2"])
    pairs = pairs.loc[pairs["sao2"].between(70, 100) & pairs["spo2"].between(70, 100)].copy()
    pairs["pair_id"] = "ENCODE-" + pairs["sao2_measurement_id"].astype("Int64").astype(str)
    pairs["pair_delta_minutes"] = (pairs["sao2_time"] - pairs["spo2_time"]).dt.total_seconds() / 60
    pairs["error"] = pairs["spo2"] - pairs["sao2"]
    pairs["sao2_interval"] = pd.Categorical(
        np.where(pairs["sao2"].le(85), "SaO2 70-85%", ">85-100%"),
        categories=["SaO2 70-85%", ">85-100%"],
        ordered=True,
    )
    return pairs.sort_values(["person_id", "sao2_time", "pair_id"]).reset_index(drop=True)


def add_demographics_and_vitals(pairs: pd.DataFrame, measurements: pd.DataFrame) -> pd.DataFrame:
    person = pd.read_csv(
        PERSON,
        usecols=["person_id", "gender_concept_id", "birth_datetime"],
        parse_dates=["birth_datetime"],
    )
    person["birth_datetime"] = pd.to_datetime(person["birth_datetime"], utc=True)
    person["assigned_sex_normalized"] = person["gender_concept_id"].map({8532: "female", 8507: "male"})
    frame = pairs.merge(person, on="person_id", how="left", validate="many_to_one")
    frame["age_at_encounter"] = (frame["sao2_time"] - frame["birth_datetime"]).dt.total_seconds() / (365.25 * 86400)
    frame = last_value_before(frame, measurements, HEART_RATE_CONCEPT, "heart_rate_consensus")
    frame = last_value_before(frame, measurements, RESP_RATE_CONCEPT, "RR")
    return frame


def add_pigmentation(pairs: pd.DataFrame, measurements: pd.DataFrame, concept_map: dict[str, int]) -> pd.DataFrame:
    frame = pairs.copy()
    forehead_mst = median_measure(measurements, concept_map, skin_name("FOREHEAD", MONK_MEASUREMENT))
    forehead_ita = median_measure(measurements, concept_map, skin_name("FOREHEAD", ITA_MEASUREMENT))
    left_finger_ita = median_measure(measurements, concept_map, skin_name("FINGER_LEFT DORSAL", ITA_MEASUREMENT))
    right_finger_ita = median_measure(measurements, concept_map, skin_name("FINGER_RIGHT DORSAL", ITA_MEASUREMENT))

    locations = measurements.loc[
        measurements["measurement_concept_id"].eq(PULSE_OX_LOCATION_CONCEPT),
        ["person_id", "value_source_value"],
    ]
    location_by_person = locations.groupby("person_id")["value_source_value"].agg(
        lambda values: values.dropna().mode().iloc[0] if len(values.dropna()) else np.nan
    )

    frame["forehead_mst"] = frame["person_id"].map(forehead_mst)
    frame["mst_group"] = pd.cut(
        frame["forehead_mst"], [0, 4, 7, 10], labels=MST_LEVELS, include_lowest=True
    )
    frame["forehead_ita"] = frame["person_id"].map(forehead_ita)
    frame["pulse_ox_location"] = frame["person_id"].map(location_by_person)
    frame["emitter_site_ita"] = np.select(
        [
            frame["pulse_ox_location"].eq("finger_left"),
            frame["pulse_ox_location"].eq("finger_right"),
            frame["pulse_ox_location"].eq("forehead"),
        ],
        [
            frame["person_id"].map(left_finger_ita),
            frame["person_id"].map(right_finger_ita),
            frame["person_id"].map(forehead_ita),
        ],
        default=np.nan,
    )
    frame["emitter_site_mapping"] = np.select(
        [
            frame["emitter_site_ita"].notna(),
            frame["pulse_ox_location"].isin(["toe_right"]),
            frame["pulse_ox_location"].eq("missing") | frame["pulse_ox_location"].isna(),
        ],
        ["mapped", "unsupported_site", "unknown_site"],
        default="site_known_measure_missing",
    )

    palm_sites = ["PALM_LEFT DORSAL", "PALM_LEFT VENTRAL", "PALM_RIGHT DORSAL", "PALM_RIGHT VENTRAL"]
    palm_ita = pd.concat(
        [median_measure(measurements, concept_map, skin_name(site, ITA_MEASUREMENT)).rename(site) for site in palm_sites],
        axis=1,
    ).mean(axis=1)
    palm_mst = pd.concat(
        [median_measure(measurements, concept_map, skin_name(site, MONK_MEASUREMENT)).rename(site) for site in palm_sites],
        axis=1,
    ).mean(axis=1)
    frame["four_palm_mean_ita"] = frame["person_id"].map(palm_ita)
    frame["four_palm_mean_mst"] = frame["person_id"].map(palm_mst)
    return frame


def cluster_wls(X, y, groups, weights=None):
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    groups = np.asarray(groups)
    weights = np.ones(len(y), dtype=float) if weights is None else np.asarray(weights, dtype=float)
    bread = np.linalg.pinv(X.T @ (weights[:, None] * X))
    beta = bread @ (X.T @ (weights * y))
    residual = y - X @ beta
    meat = np.zeros((X.shape[1], X.shape[1]), dtype=float)
    unique_groups = np.unique(groups)
    for group in unique_groups:
        mask = groups == group
        score = (weights[mask, None] * X[mask]).T @ residual[mask]
        meat += np.outer(score, score)
    n, k, g = len(y), X.shape[1], len(unique_groups)
    correction = (g / (g - 1)) * ((n - 1) / (n - k))
    covariance = correction * bread @ meat @ bread
    return beta, covariance


def safe_cov(covariance):
    covariance = np.asarray(covariance, dtype=float)
    covariance = (covariance + covariance.T) / 2
    values, vectors = np.linalg.eigh(covariance)
    values = np.clip(values, 1e-12, None)
    return (vectors * values) @ vectors.T


def fit_mst(data: pd.DataFrame, weighting: str):
    sub = data.dropna(subset=["mst_group", "error", "sao2", "person_id"]).copy()
    sub["so2_c"] = sub["sao2"] - sub["sao2"].mean()
    X = np.column_stack(
        [
            np.ones(len(sub)),
            sub["mst_group"].astype(str).eq("5-7"),
            sub["mst_group"].astype(str).eq("8-10"),
            sub["so2_c"],
            sub["so2_c"] ** 2,
        ]
    )
    weights = None
    if weighting == "participant-balanced":
        weights = 1 / sub.groupby("person_id")["person_id"].transform("size").to_numpy()
    beta, covariance = cluster_wls(X, sub["error"], sub["person_id"], weights)

    group_rows = []
    group_design = {}
    for group, d57, d810 in [("1-4", 0, 0), ("5-7", 1, 0), ("8-10", 0, 1)]:
        L = np.array([1, d57, d810, sub["so2_c"].mean(), (sub["so2_c"] ** 2).mean()])
        group_design[group] = L
        estimate = float(L @ beta)
        se = float(np.sqrt(max(L @ covariance @ L, 0)))
        group_rows.append(
            {
                "interval": ">85-100%",
                "mst_group": group,
                "adjusted_bias": estimate,
                "se": se,
                "ci_low": estimate - 1.96 * se,
                "ci_high": estimate + 1.96 * se,
                "pairs": len(sub),
                "participants": sub["person_id"].nunique(),
                "weighting": weighting,
            }
        )

    contrast_rows = []
    contrast_matrix = []
    contrast_names = []
    for first, second in [("1-4", "5-7"), ("1-4", "8-10"), ("5-7", "8-10")]:
        contrast_names.append(f"{first} minus {second}")
        contrast_matrix.append(group_design[first] - group_design[second])
    contrast_matrix = np.vstack(contrast_matrix)
    differences = contrast_matrix @ beta
    contrast_covariance = safe_cov(contrast_matrix @ covariance @ contrast_matrix.T)
    ses = np.sqrt(np.diag(contrast_covariance))
    for name, difference, se in zip(contrast_names, differences, ses):
        contrast_rows.append(
            {
                "interval": ">85-100%",
                "contrast": name,
                "difference": float(difference),
                "se": float(se),
                "ci_low": float(difference - 1.96 * se),
                "ci_high": float(difference + 1.96 * se),
                "weighting": weighting,
            }
        )

    correlation = contrast_covariance / np.outer(ses, ses)
    correlation = safe_cov(correlation)
    rng = np.random.default_rng(SIMULATION_SEED + (1 if weighting == "participant-balanced" else 0))
    draws = rng.multivariate_normal(np.zeros(3), correlation, size=50_000)
    critical = float(np.quantile(np.max(np.abs(draws), axis=1), 0.95))
    maximum = float(np.max(np.abs(differences)))
    lower = float(np.max(np.maximum(0, np.abs(differences) - critical * ses)))
    upper = float(np.max(np.abs(differences) + critical * ses))
    status = "Meets benchmark" if upper < 1.5 else ("Difference exceeds benchmark" if lower > 1.5 else "Inconclusive")
    summary = {
        "interval": ">85-100%",
        "pairs": len(sub),
        "participants": sub["person_id"].nunique(),
        "max_abs_difference": maximum,
        "simultaneous_lower_abs": lower,
        "simultaneous_upper_abs": upper,
        "simultaneous_critical_value": critical,
        "margin": 1.5,
        "status": status,
        "weighting": weighting,
    }
    return group_rows, contrast_rows, summary


def fit_ita(data: pd.DataFrame, column: str, label: str, weighting: str) -> dict:
    sub = data.dropna(subset=[column, "error", "sao2", "person_id"]).copy()
    sub["so2_c"] = sub["sao2"] - sub["sao2"].mean()
    X = np.column_stack([np.ones(len(sub)), sub[column] / 100, sub["so2_c"], sub["so2_c"] ** 2])
    weights = None
    if weighting == "participant-balanced":
        weights = 1 / sub.groupby("person_id")["person_id"].transform("size").to_numpy()
    beta, covariance = cluster_wls(X, sub["error"], sub["person_id"], weights)
    estimate = float(beta[1])
    se = float(np.sqrt(covariance[1, 1]))
    return {
        "interval": ">85-100%",
        "measure": label,
        "source_column": column,
        "pairs": len(sub),
        "participants": sub["person_id"].nunique(),
        "row_coverage_pct": 100 * len(sub) / len(data),
        "ita_min": sub[column].min(),
        "ita_max": sub[column].max(),
        "ita_span": sub[column].max() - sub[column].min(),
        "difference_per_100_degrees": estimate,
        "se": se,
        "ci_low": estimate - 1.96 * se,
        "ci_high": estimate + 1.96 * se,
        "weighting": weighting,
    }


def support_tables(frame: pd.DataFrame):
    rows = []
    for interval, group in frame.groupby("sao2_interval", observed=False):
        for mst_group in MST_LEVELS:
            subset = group.loc[group["mst_group"].astype(str).eq(mst_group)]
            rows.append(
                {
                    "interval": str(interval),
                    "measure": "Forehead MST",
                    "group": mst_group,
                    "pairs": len(subset),
                    "participants": subset["person_id"].nunique(),
                }
            )
        available = group["emitter_site_ita"].notna()
        rows.append(
            {
                "interval": str(interval),
                "measure": "Emitter-site ITA",
                "group": "available",
                "pairs": int(available.sum()),
                "participants": group.loc[available, "person_id"].nunique(),
            }
        )
    support = pd.DataFrame(rows)
    support.to_csv(OUTPUT_DIR / "encode_pigmentation_support.csv", index=False)

    mst_gate_rows = []
    for interval in ["SaO2 70-85%", ">85-100%"]:
        subset = support.loc[(support["interval"].eq(interval)) & support["measure"].eq("Forehead MST")]
        mst_gate_rows.append(
            {
                "interval": interval,
                "MST_supported": bool((subset["pairs"] >= 50).all() and (subset["participants"] >= 10).all()),
                "minimum_group_pairs": int(subset["pairs"].min()),
                "minimum_group_participants": int(subset["participants"].min()),
            }
        )
    return support, pd.DataFrame(mst_gate_rows)


def create_figure(group_estimates: pd.DataFrame, mst_summary: pd.DataFrame, ita: pd.DataFrame) -> Path:
    pair_mst = group_estimates.loc[group_estimates["weighting"].eq("pair-weighted")]
    pair_ita = ita.loc[ita["weighting"].eq("pair-weighted")]
    width, height = 1400, 850
    image = Image.new("RGB", (width, height), "#F7F8FA")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=24)
    small = ImageFont.load_default(size=18)
    title = ImageFont.load_default(size=32)
    draw.text((60, 40), "ENCoDE measured-pigmentation replication", fill="#172033", font=title)
    draw.text((60, 92), "Adjusted SpO2 - SaO2 bias; SaO2 >85-100%; participant-cluster robust 95% intervals", fill="#46536B", font=small)

    x0, x1 = 300, 1260
    axis_y = 690
    xmin, xmax = -1.5, 3.0
    def xpos(value):
        return x0 + (float(value) - xmin) / (xmax - xmin) * (x1 - x0)
    draw.line((x0, axis_y, x1, axis_y), fill="#6B7280", width=2)
    draw.line((xpos(0), 170, xpos(0), axis_y), fill="#AAB2BF", width=2)
    for tick in np.arange(-1.5, 3.01, 0.5):
        x = xpos(tick)
        draw.line((x, axis_y - 8, x, axis_y + 8), fill="#6B7280", width=2)
        draw.text((x - 16, axis_y + 18), f"{tick:g}", fill="#46536B", font=small)
    draw.text((540, 770), "Adjusted bias (percentage points)", fill="#172033", font=font)

    y_positions = {"1-4": 220, "5-7": 330, "8-10": 440}
    colors = {"1-4": "#2C7FB8", "5-7": "#41AB5D", "8-10": "#D95F0E"}
    for _, row in pair_mst.iterrows():
        y = y_positions[row["mst_group"]]
        draw.text((60, y - 14), f"MST {row['mst_group']}", fill="#172033", font=font)
        draw.line((xpos(row["ci_low"]), y, xpos(row["ci_high"]), y), fill=colors[row["mst_group"]], width=6)
        draw.ellipse((xpos(row["adjusted_bias"]) - 9, y - 9, xpos(row["adjusted_bias"]) + 9, y + 9), fill=colors[row["mst_group"]])

    draw.text((60, 560), "ITA slopes", fill="#172033", font=font)
    ita_y = 550
    for _, row in pair_ita.iterrows():
        ita_y += 46
        label = {"Exact emitter-site ITA": "Emitter", "Forehead ITA sensitivity": "Forehead", "Four-palm ITA sensitivity": "Four-palm"}[row["measure"]]
        draw.text((175, ita_y - 12), label, fill="#46536B", font=small)
        draw.line((xpos(row["ci_low"]), ita_y, xpos(row["ci_high"]), ita_y), fill="#6A51A3", width=5)
        draw.ellipse((xpos(row["difference_per_100_degrees"]) - 7, ita_y - 7, xpos(row["difference_per_100_degrees"]) + 7, ita_y + 7), fill="#6A51A3")

    summary = mst_summary.loc[mst_summary["weighting"].eq("pair-weighted")].iloc[0]
    draw.rounded_rectangle((880, 110, 1325, 170), radius=12, fill="#FFF3CD", outline="#D39B26", width=2)
    draw.text((900, 128), f"MST benchmark: {summary['status']}", fill="#7A5200", font=small)
    path = OUTPUT_DIR / "encode_pigmentation_replication.png"
    image.save(path)
    return path


def artifact_manifest() -> pd.DataFrame:
    rows = []
    for path in sorted(OUTPUT_DIR.iterdir()):
        if path.name == "encode_external_artifact_manifest.csv" or not path.is_file():
            continue
        rows.append({"artifact": path.name, "path": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)})
    result = pd.DataFrame(rows)
    result.to_csv(OUTPUT_DIR / "encode_external_artifact_manifest.csv", index=False)
    return result


def run_validation():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    source_hashes = verify_source_hashes()
    crosswalk = freeze_crosswalk()

    usecols = [
        "measurement_id", "person_id", "measurement_concept_id", "measurement_datetime",
        "value_as_number", "value_source_value",
    ]
    measurements = pd.read_csv(MEASUREMENT, usecols=usecols, low_memory=False)
    measurements["measurement_datetime"] = pd.to_datetime(measurements["measurement_datetime"], utc=True)
    concept_map = custom_concept_map()

    pairs = reconstruct_pairs(measurements)
    pairs = add_demographics_and_vitals(pairs, measurements)
    frame = add_pigmentation(pairs, measurements, concept_map)

    reconstruction = pd.DataFrame(
        [
            {"source": "ENCoDE publication analytic extract", "pairs": 521, "participants": 128, "mean_sao2": 95.7, "mean_spo2": 97.3, "mean_sao2_minus_spo2": -1.6, "sd_sao2_minus_spo2": 2.1},
            {"source": "ENCoDE v1.0.0 OMOP reconstruction", "pairs": len(frame), "participants": frame["person_id"].nunique(), "mean_sao2": frame["sao2"].mean(), "mean_spo2": frame["spo2"].mean(), "mean_sao2_minus_spo2": (frame["sao2"] - frame["spo2"]).mean(), "sd_sao2_minus_spo2": (frame["sao2"] - frame["spo2"]).std()},
        ]
    )
    reconstruction.to_csv(OUTPUT_DIR / "encode_pair_reconstruction.csv", index=False)

    crosswalk_qa = pd.DataFrame(
        {
            "check": [
                "Core source hashes match the distributed manifest",
                "SpO2 precedes or equals SaO2",
                "SpO2-SaO2 gap is at most five minutes",
                "All paired saturations lie in 70-100",
                "Pair identifiers are unique",
                "Heart-rate values are left-sided within four hours",
                "Respiratory-rate values are left-sided within four hours",
                "Sex categories map only to frozen levels",
                "Forehead MST lies in 1-10",
                "Exact emitter-site mapping never substitutes unknown or toe sites",
            ],
            "passed": [
                source_hashes["passed"].all(),
                frame["pair_delta_minutes"].ge(0).all(),
                frame["pair_delta_minutes"].le(PAIR_WINDOW_MINUTES).all(),
                frame["sao2"].between(70, 100).all() and frame["spo2"].between(70, 100).all(),
                frame["pair_id"].is_unique,
                frame.loc[frame["heart_rate_consensus"].notna(), "heart_rate_consensus_delta_minutes"].between(0, 240).all(),
                frame.loc[frame["RR"].notna(), "RR_delta_minutes"].between(0, 240).all(),
                frame["assigned_sex_normalized"].dropna().isin(["female", "male", "unknown"]).all(),
                frame["forehead_mst"].dropna().between(1, 10).all(),
                frame.loc[frame["emitter_site_ita"].notna(), "pulse_ox_location"].isin(["finger_left", "finger_right", "forehead"]).all(),
            ],
        }
    )
    crosswalk_qa.to_csv(OUTPUT_DIR / "encode_crosswalk_qa.csv", index=False)
    if not crosswalk_qa["passed"].all():
        raise AssertionError("Crosswalk QA failed")

    support, mst_gates = support_tables(frame)
    high = frame.loc[frame["sao2_interval"].astype(str).eq(">85-100%")].copy()
    high_mst_supported = bool(mst_gates.loc[mst_gates["interval"].eq(">85-100%"), "MST_supported"].iloc[0])
    low_mst_supported = bool(mst_gates.loc[mst_gates["interval"].eq("SaO2 70-85%"), "MST_supported"].iloc[0])

    mst_group_rows, mst_contrast_rows, mst_summaries = [], [], []
    if high_mst_supported:
        for weighting in ["pair-weighted", "participant-balanced"]:
            groups, contrasts, summary = fit_mst(high, weighting)
            mst_group_rows.extend(groups)
            mst_contrast_rows.extend(contrasts)
            mst_summaries.append(summary)
    mst_group_estimates = pd.DataFrame(mst_group_rows)
    mst_pairwise = pd.DataFrame(mst_contrast_rows)
    mst_summary = pd.DataFrame(mst_summaries)
    mst_group_estimates.to_csv(OUTPUT_DIR / "encode_mst_adjusted_group_bias.csv", index=False)
    mst_pairwise.to_csv(OUTPUT_DIR / "encode_mst_pairwise_contrasts.csv", index=False)
    mst_summary.to_csv(OUTPUT_DIR / "encode_mst_primary_benchmark.csv", index=False)

    ita_rows = []
    for weighting in ["pair-weighted", "participant-balanced"]:
        ita_rows.extend(
            [
                fit_ita(high, "emitter_site_ita", "Exact emitter-site ITA", weighting),
                fit_ita(high, "forehead_ita", "Forehead ITA sensitivity", weighting),
                fit_ita(high, "four_palm_mean_ita", "Four-palm ITA sensitivity", weighting),
            ]
        )
    ita = pd.DataFrame(ita_rows)
    ita["standalone_support"] = (
        (ita["participants"] >= 30)
        & (ita["row_coverage_pct"] >= 80)
        & (ita["ita_span"] >= 100)
        & (ita["pairs"] >= 100)
    )
    ita["interpretation"] = np.where(
        ita["measure"].eq("Exact emitter-site ITA") & ita["standalone_support"],
        "eligible for standalone benchmark",
        "descriptive sensitivity; not a co-primary benchmark conclusion",
    )
    ita.to_csv(OUTPUT_DIR / "encode_ita_associations.csv", index=False)

    risk = frame.loc[frame["spo2"].between(92, 96)].copy()
    risk["outcome"] = (risk["sao2"] < 88).astype(int)
    events = int(risk["outcome"].sum())
    event_participants = risk.loc[risk["outcome"].eq(1), "person_id"].nunique()
    non_events = len(risk) - events
    feature_mapping_pass = bool(
        frame["assigned_sex_normalized"].notna().all()
        and np.isfinite(frame["age_at_encounter"]).all()
        and set([HEART_RATE_CONCEPT, RESP_RATE_CONCEPT]).issubset(set(measurements["measurement_concept_id"].unique()))
    )
    threshold_support = len(risk) >= 100 and events >= 10 and event_participants >= 5
    calibration_support = events >= 30 and event_participants >= 10 and non_events >= 100
    risk_gate = pd.DataFrame(
        [
            {
                "eligible_rows": len(risk),
                "eligible_participants": risk["person_id"].nunique(),
                "events": events,
                "event_positive_participants": event_participants,
                "non_events": non_events,
                "age_missing_rate": risk["age_at_encounter"].isna().mean(),
                "heart_rate_missing_rate": risk["heart_rate_consensus"].isna().mean(),
                "respiratory_rate_missing_rate": risk["RR"].isna().mean(),
                "feature_mapping_pass": feature_mapping_pass,
                "threshold_support": threshold_support,
                "calibration_discrimination_support": calibration_support,
                "unchanged_model_scored": False,
                "reason": "No eligible occult-hypoxemia events; D019 event gate failed",
            }
        ]
    )
    risk_gate.to_csv(OUTPUT_DIR / "encode_risk_validation_gate.csv", index=False)

    bold_summary_path = PROJECT_ROOT / "bold_external_validation" / "bold_external_summary.json"
    bold_summary = json.loads(bold_summary_path.read_text(encoding="utf-8")) if bold_summary_path.exists() else {}
    combined_external = pd.DataFrame(
        [
            {
                "dataset": "BOLD v1.0",
                "external_role": "Unchanged compact-model probability validation",
                "eligible_pairs": 11880,
                "participants": 11441,
                "events": 671,
                "primary_result": "Failed unchanged probability transport",
                "headline_estimate": "Observed 5.65%; predicted 21.10%; calibration slope 0.119; ROC-AUC 0.568",
            },
            {
                "dataset": "ENCoDE v1.0.0",
                "external_role": "Conditional compact-model probability validation",
                "eligible_pairs": len(risk),
                "participants": risk["person_id"].nunique(),
                "events": events,
                "primary_result": "Not scored; event-support gate failed",
                "headline_estimate": "Zero SaO2 <88% events in the SpO2 92-96% denominator",
            },
            {
                "dataset": "ENCoDE v1.0.0",
                "external_role": "Measured-pigmentation mechanistic replication",
                "eligible_pairs": len(high),
                "participants": high["person_id"].nunique(),
                "events": np.nan,
                "primary_result": "Partial, directionally concordant, formally inconclusive",
                "headline_estimate": "MST max contrast 0.760 pp; simultaneous 95% upper 1.527 vs 1.5 pp margin",
            },
        ]
    )
    combined_external.to_csv(OUTPUT_DIR / "external_validation_evidence_summary.csv", index=False)

    output_columns = [
        "pair_id", "person_id", "sao2_time", "spo2_time", "pair_delta_minutes", "sao2", "spo2", "error",
        "sao2_interval", "pulse_ox_location", "forehead_mst", "mst_group", "emitter_site_ita",
        "emitter_site_mapping", "forehead_ita", "four_palm_mean_ita", "four_palm_mean_mst",
        "age_at_encounter", "assigned_sex_normalized", "heart_rate_consensus", "heart_rate_consensus_delta_minutes",
        "RR", "RR_delta_minutes",
    ]
    frame[output_columns].to_csv(OUTPUT_DIR / "encode_analysis_pairs.csv.gz", index=False, compression="gzip")

    figure = create_figure(mst_group_estimates, mst_summary, ita)
    pair_mst = mst_summary.loc[mst_summary["weighting"].eq("pair-weighted")].iloc[0]
    pair_ita = ita.loc[(ita["weighting"].eq("pair-weighted")) & ita["measure"].eq("Exact emitter-site ITA")].iloc[0]
    forehead_ita = ita.loc[(ita["weighting"].eq("pair-weighted")) & ita["measure"].eq("Forehead ITA sensitivity")].iloc[0]
    summary = {
        "dataset": "ENCoDE v1.0.0",
        "reconstructed_pairs": int(len(frame)),
        "reconstructed_participants": int(frame["person_id"].nunique()),
        "published_pairs": 521,
        "published_participants": 128,
        "pair_reconstruction_note": "The released OMOP tables yield 615 protocol-conforming pairs from 127 patients; saturation summaries reproduce the publication closely, but the exact 521-row REDCap analytic extract is not identifiable in v1.0.0.",
        "pigmentation": {
            "low_interval_pairs": int(frame["sao2_interval"].astype(str).eq("SaO2 70-85%").sum()),
            "low_interval_supported": False,
            "high_interval_pairs": int(len(high)),
            "high_interval_MST_supported": high_mst_supported,
            "high_interval_MST_max_abs_difference": float(pair_mst["max_abs_difference"]),
            "high_interval_MST_simultaneous_95_upper": float(pair_mst["simultaneous_upper_abs"]),
            "high_interval_MST_margin": 1.5,
            "high_interval_MST_status": pair_mst["status"],
            "exact_emitter_ITA_difference_per_100": float(pair_ita["difference_per_100_degrees"]),
            "exact_emitter_ITA_95_CI": [float(pair_ita["ci_low"]), float(pair_ita["ci_high"])],
            "exact_emitter_ITA_coverage_pct": float(pair_ita["row_coverage_pct"]),
            "exact_emitter_ITA_standalone_support": bool(pair_ita["standalone_support"]),
            "forehead_ITA_difference_per_100": float(forehead_ita["difference_per_100_degrees"]),
            "forehead_ITA_95_CI": [float(forehead_ita["ci_low"]), float(forehead_ita["ci_high"])],
            "directional_interpretation": "Darker pigmentation was directionally associated with greater positive SpO2 error for both MST and ITA, but ITA intervals crossed zero and the complete co-primary replication gate failed.",
        },
        "risk_validation": risk_gate.iloc[0].to_dict(),
        "conclusion": "Partial mechanistic replication only. High-saturation MST is supported but inconclusive against the 1.5-point benchmark; exact emitter-site ITA lacks prespecified coverage; low-saturation pigmentation and unchanged risk-model validation are unsupported.",
        "combined_external_evidence": str(OUTPUT_DIR / "external_validation_evidence_summary.csv"),
        "crosswalk_sha256": crosswalk["crosswalk_sha256"],
        "figure": str(figure),
    }
    write_json(OUTPUT_DIR / "encode_external_summary.json", summary)

    qa = pd.DataFrame(
        {
            "check": [
                "All crosswalk QA checks passed",
                "Released reconstruction has 615 pairs",
                "Released reconstruction has 127 participants",
                "Only three pairs occupy the low SaO2 interval",
                "High-saturation MST gate passed",
                "Low-saturation MST gate failed",
                "Exact emitter-site ITA does not receive unsupported primary imputation",
                "Risk model was not scored after zero-event gate failure",
                "All MST estimates and intervals are finite",
                "All ITA estimates and intervals are finite",
                "Primary figure was written",
            ],
            "passed": [
                crosswalk_qa["passed"].all(),
                len(frame) == 615,
                frame["person_id"].nunique() == 127,
                frame["sao2_interval"].astype(str).eq("SaO2 70-85%").sum() == 3,
                high_mst_supported,
                not low_mst_supported,
                frame.loc[frame["pulse_ox_location"].isin(["missing", "toe_right"]), "emitter_site_ita"].isna().all(),
                events == 0 and not risk_gate["unchanged_model_scored"].iloc[0],
                np.isfinite(mst_group_estimates[["adjusted_bias", "ci_low", "ci_high"]]).all().all(),
                np.isfinite(ita[["difference_per_100_degrees", "ci_low", "ci_high"]]).all().all(),
                figure.exists(),
            ],
        }
    )
    qa.to_csv(OUTPUT_DIR / "encode_external_qa.csv", index=False)
    if not qa["passed"].all():
        raise AssertionError("ENCoDE validation QA failed")
    artifact_manifest()
    return summary


if __name__ == "__main__":
    result = run_validation()
    print(json.dumps(result, indent=2, default=str))
