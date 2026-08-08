from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import math

import numpy as np
import pandas as pd


WORKSPACE = Path(r".")
BOLD_ROOT = Path(r"data\external\bold")
OPENOX_ROOT = Path(r".")
BOLD_CSV = BOLD_ROOT / "bold_dataset.csv"
BOLD_DICTIONARY = BOLD_ROOT / "bold_dictionary.pdf"
SPEC_PATH = (
    OPENOX_ROOT / "outputs" / "models"
    / "openox_compact_occult_ridge_v1_scoring_spec.json"
)
OUTPUT_DIR = WORKSPACE / "bold_external_validation"

EXPECTED_BOLD_SHA256 = "342891ad85e118e7e57bb2ddeadeafce57e99e01d48175c08576bb3855bede44"
EXPECTED_DICTIONARY_SHA256 = "15c1d4642decf1a9f2cc1b558404fcd9c646ccd6286441cce1c529821e279802"
BOOTSTRAP_REPLICATES = 1000
BOOTSTRAP_SEED = 20260803
THRESHOLDS = np.array([0.02, 0.05, 0.10], dtype=float)
DECISION_THRESHOLDS = np.arange(0.02, 0.101, 0.01)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def sigmoid(values):
    values = np.clip(np.asarray(values, dtype=float), -40, 40)
    return 1.0 / (1.0 + np.exp(-values))


def weighted_mean(values, weights=None):
    values = np.asarray(values, dtype=float)
    if weights is None:
        return float(values.mean())
    weights = np.asarray(weights, dtype=float)
    return float(np.sum(values * weights) / np.sum(weights))


def weighted_average_precision(y, score, weights=None):
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    weights = np.ones(len(y), dtype=float) if weights is None else np.asarray(weights, dtype=float)
    positive_weight = float(np.sum(weights * y))
    if positive_weight <= 0:
        return np.nan
    order = np.argsort(-score, kind="mergesort")
    y, score, weights = y[order], score[order], weights[order]
    boundaries = np.r_[np.flatnonzero(np.diff(score) != 0), len(score) - 1]
    cumulative_tp = np.cumsum(weights * y)[boundaries]
    cumulative_total = np.cumsum(weights)[boundaries]
    keep = cumulative_total > 0
    cumulative_tp = cumulative_tp[keep]
    cumulative_total = cumulative_total[keep]
    recall = cumulative_tp / positive_weight
    precision = cumulative_tp / cumulative_total
    return float(np.sum(np.diff(np.r_[0.0, recall]) * precision))


def weighted_roc_auc(y, score, weights=None):
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    weights = np.ones(len(y), dtype=float) if weights is None else np.asarray(weights, dtype=float)
    positive_weight = float(np.sum(weights * y))
    negative_weight = float(np.sum(weights * (1 - y)))
    if positive_weight <= 0 or negative_weight <= 0:
        return np.nan
    order = np.argsort(-score, kind="mergesort")
    y, score, weights = y[order], score[order], weights[order]
    boundaries = np.r_[np.flatnonzero(np.diff(score) != 0), len(score) - 1]
    tpr = np.r_[0.0, np.cumsum(weights * y)[boundaries] / positive_weight]
    fpr = np.r_[0.0, np.cumsum(weights * (1 - y))[boundaries] / negative_weight]
    return float(np.trapezoid(tpr, fpr))


def calibration_intercept(y, p, weights=None):
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-8, 1 - 1e-8)
    weights = np.ones(len(y), dtype=float) if weights is None else np.asarray(weights, dtype=float)
    logit_p = np.log(p / (1 - p))
    alpha = 0.0
    for _ in range(100):
        fitted = sigmoid(logit_p + alpha)
        score = np.sum(weights * (y - fitted))
        information = np.sum(weights * fitted * (1 - fitted))
        if information <= 1e-12:
            return np.nan
        step = score / information
        alpha += step
        if abs(step) < 1e-10:
            break
    return float(alpha)


def calibration_slope(y, p, weights=None):
    y = np.asarray(y, dtype=float)
    p = np.clip(np.asarray(p, dtype=float), 1e-8, 1 - 1e-8)
    weights = np.ones(len(y), dtype=float) if weights is None else np.asarray(weights, dtype=float)
    logit_p = np.log(p / (1 - p))
    design = np.column_stack([np.ones(len(y)), logit_p])
    beta = np.array([0.0, 1.0])
    for _ in range(100):
        fitted = sigmoid(design @ beta)
        variance_weight = weights * fitted * (1 - fitted)
        score = design.T @ (weights * (y - fitted))
        information = design.T @ (variance_weight[:, None] * design)
        try:
            step = np.linalg.solve(information, score)
        except np.linalg.LinAlgError:
            return np.nan
        current_ll = np.sum(weights * (y * np.log(fitted) + (1 - y) * np.log(1 - fitted)))
        accepted = False
        for reduction in range(20):
            candidate = beta + step / (2 ** reduction)
            candidate_p = np.clip(sigmoid(design @ candidate), 1e-12, 1 - 1e-12)
            candidate_ll = np.sum(
                weights * (y * np.log(candidate_p) + (1 - y) * np.log(1 - candidate_p))
            )
            if np.isfinite(candidate_ll) and candidate_ll >= current_ll - 1e-10:
                beta = candidate
                accepted = True
                break
        if not accepted:
            return np.nan
        if np.max(np.abs(step / (2 ** reduction))) < 1e-9:
            return float(beta[1]) if np.max(np.abs(beta)) < 50 else np.nan
    return np.nan


def threshold_metrics(y, p, threshold, weights=None):
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    weights = np.ones(len(y), dtype=float) if weights is None else np.asarray(weights, dtype=float)
    flagged = p >= threshold
    tp = np.sum(weights * y * flagged)
    fn = np.sum(weights * y * (~flagged))
    tn = np.sum(weights * (1 - y) * (~flagged))
    fp = np.sum(weights * (1 - y) * flagged)
    total = np.sum(weights)
    return {
        "sensitivity": tp / (tp + fn) if tp + fn else np.nan,
        "specificity": tn / (tn + fp) if tn + fp else np.nan,
        "ppv": tp / (tp + fp) if tp + fp else np.nan,
        "npv": tn / (tn + fn) if tn + fn else np.nan,
        "flagged_rate": (tp + fp) / total,
        "net_benefit": (tp / total) - (fp / total) * threshold / (1 - threshold),
    }


def metric_bundle(y, p, weights=None, calibration_support=True):
    y = np.asarray(y, dtype=int)
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    weights = np.ones(len(y), dtype=float) if weights is None else np.asarray(weights, dtype=float)
    output = {
        "observed_rate": weighted_mean(y, weights),
        "mean_predicted": weighted_mean(p, weights),
        "calibration_gap": weighted_mean(p - y, weights),
        "calibration_intercept": calibration_intercept(y, p, weights),
        "calibration_slope": calibration_slope(y, p, weights) if calibration_support else np.nan,
        "brier": weighted_mean((y - p) ** 2, weights),
        "log_loss": weighted_mean(-(y * np.log(p) + (1 - y) * np.log(1 - p)), weights),
        "pr_auc": weighted_average_precision(y, p, weights) if calibration_support else np.nan,
        "roc_auc": weighted_roc_auc(y, p, weights) if calibration_support else np.nan,
    }
    for threshold in THRESHOLDS:
        suffix = f"{int(threshold * 100)}pct"
        threshold_output = threshold_metrics(y, p, threshold, weights)
        for name, value in threshold_output.items():
            output[f"{name}_{suffix}"] = value
        observed = output["observed_rate"]
        flag_all = observed - (1 - observed) * threshold / (1 - threshold)
        output[f"net_benefit_minus_all_{suffix}"] = threshold_output["net_benefit"] - flag_all
    return output


def support_row(frame, dimension, group):
    events = int(frame["outcome"].sum())
    positive_participants = frame.loc[frame["outcome"].eq(1), "patient_id"].nunique()
    nonevents = int(len(frame) - events)
    return {
        "dimension": dimension,
        "group": str(group),
        "rows": len(frame),
        "participants": frame["patient_id"].nunique(),
        "events": events,
        "event_positive_participants": positive_participants,
        "nonevents": nonevents,
        "threshold_support": bool(len(frame) >= 100 and events >= 10 and positive_participants >= 5),
        "calibration_discrimination_support": bool(
            events >= 30 and positive_participants >= 10 and nonevents >= 100
        ),
    }


def freeze_crosswalk():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    dataset_hash = sha256(BOLD_CSV)
    dictionary_hash = sha256(BOLD_DICTIONARY)
    if dataset_hash != EXPECTED_BOLD_SHA256 or dictionary_hash != EXPECTED_DICTIONARY_SHA256:
        raise AssertionError("BOLD source hashes do not match the distributed manifest")

    preoutcome_columns = [
        "unique_subject_id", "unique_hospital_admission_id", "unique_icustay_id",
        "source_db", "admission_age", "sex_female", "race_ethnicity",
        "SaO2_timestamp", "SpO2", "SpO2_timestamp", "delta_SpO2",
        "vitals_heart_rate", "delta_vitals_heart_rate",
        "vitals_resp_rate", "delta_vitals_resp_rate",
    ]
    frame = pd.read_csv(BOLD_CSV, usecols=preoutcome_columns)
    required = set(preoutcome_columns)
    if set(frame.columns) != required:
        raise AssertionError("Unexpected BOLD pre-outcome schema")

    checks = {
        "distributed dataset hash matches": dataset_hash == EXPECTED_BOLD_SHA256,
        "distributed dictionary hash matches": dictionary_hash == EXPECTED_DICTIONARY_SHA256,
        "hospital-admission pair key is unique": frame["unique_hospital_admission_id"].is_unique,
        "SpO2 is complete": frame["SpO2"].notna().all(),
        "SpO2 is 0 to 5 minutes before ABG": frame["delta_SpO2"].between(-5, 0).all(),
        "heart-rate values have left-sided deltas": (
            frame.loc[frame["vitals_heart_rate"].notna(), "delta_vitals_heart_rate"]
            .between(-240, 0).all()
        ),
        "respiratory-rate values have left-sided deltas": (
            frame.loc[frame["vitals_resp_rate"].notna(), "delta_vitals_resp_rate"]
            .between(-240, 0).all()
        ),
        "sex coding is binary 0/1": set(frame["sex_female"].dropna().unique()) <= {0, 1},
        "source coding is recognized": set(frame["source_db"].unique()) == {"eicu", "mimic_iii", "mimic_iv"},
        "age is in years and plausible": frame["admission_age"].dropna().between(14, 90).all(),
    }
    if not all(checks.values()):
        raise AssertionError({key: value for key, value in checks.items() if not value})

    eligible = frame["SpO2"].between(92, 96, inclusive="both")
    audit_rows = [
        {"item": "source_rows", "value": len(frame), "scope": "all BOLD"},
        {"item": "source_participants", "value": frame["unique_subject_id"].nunique(), "scope": "all BOLD"},
        {"item": "eligible_rows", "value": int(eligible.sum()), "scope": "SpO2 92-96"},
        {"item": "eligible_participants", "value": frame.loc[eligible, "unique_subject_id"].nunique(), "scope": "SpO2 92-96"},
        {"item": "age_missing_rate", "value": frame.loc[eligible, "admission_age"].isna().mean(), "scope": "SpO2 92-96"},
        {"item": "heart_rate_missing_rate", "value": frame.loc[eligible, "vitals_heart_rate"].isna().mean(), "scope": "SpO2 92-96"},
        {"item": "respiratory_rate_missing_rate", "value": frame.loc[eligible, "vitals_resp_rate"].isna().mean(), "scope": "SpO2 92-96"},
        {"item": "minimum_SpO2_delta_minutes", "value": frame["delta_SpO2"].min(), "scope": "all BOLD"},
        {"item": "maximum_SpO2_delta_minutes", "value": frame["delta_SpO2"].max(), "scope": "all BOLD"},
        {"item": "minimum_heart_rate_delta_minutes", "value": frame["delta_vitals_heart_rate"].min(), "scope": "available values"},
        {"item": "minimum_resp_rate_delta_minutes", "value": frame["delta_vitals_resp_rate"].min(), "scope": "available values"},
    ]
    pd.DataFrame(audit_rows).to_csv(OUTPUT_DIR / "bold_preoutcome_audit.csv", index=False)
    pd.DataFrame({"check": checks.keys(), "pass": checks.values()}).to_csv(
        OUTPUT_DIR / "bold_crosswalk_qa.csv", index=False
    )

    crosswalk = {
        "decision_id": "D030",
        "status": "frozen before external outcome analysis",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset": "BOLD 1.0",
        "dataset_path": str(BOLD_CSV),
        "dataset_sha256": dataset_hash,
        "dictionary_path": str(BOLD_DICTIONARY),
        "dictionary_sha256": dictionary_hash,
        "row_grain": "one selected SpO2-SaO2 pair per unique hospital admission in this release",
        "participant_cluster": "unique_subject_id",
        "eligibility": "SpO2 between 92 and 96 percentage points inclusive",
        "outcome": "SaO2 below 88 percentage points; loaded only after this crosswalk is written",
        "mapping": {
            "saturation": {"BOLD": "SpO2", "unit": "percentage points", "timing": "0-5 minutes pre-ABG using the distributed selected pair"},
            "age_at_encounter": {"BOLD": "admission_age", "unit": "years", "missing": "OpenOx training median plus indicator"},
            "heart_rate_consensus": {"BOLD": "vitals_heart_rate", "unit": "beats/minute", "timing": "left-sided, up to 240 minutes pre-ABG", "missing": "OpenOx training median plus indicator"},
            "RR": {"BOLD": "vitals_resp_rate", "unit": "breaths/minute", "timing": "left-sided, up to 240 minutes pre-ABG", "missing": "OpenOx training median plus indicator"},
            "assigned_sex_normalized": {"BOLD": "sex_female", "mapping": {"1": "female", "0": "male", "missing": "OpenOx training mode"}},
        },
        "forbidden_predictors": ["SaO2", "pO2", "pH", "pCO2", "same-draw ABG fields", "future SOFA fields", "race_ethnicity"],
        "audit_only_fields": ["race_ethnicity", "source_db"],
        "known_domain_shift": [
            "BOLD is a retrospective ICU-EHR cohort rather than controlled desaturation.",
            "BOLD SpO2 timing permits five minutes rather than the OpenOx 180-second primary pairing window.",
            "BOLD heart and respiratory rates may be up to four hours old.",
            "Admission age is top-coded at 90 in this release.",
        ],
    }
    write_json(OUTPUT_DIR / "bold_crosswalk_lock.json", crosswalk)
    crosswalk["crosswalk_sha256"] = sha256(OUTPUT_DIR / "bold_crosswalk_lock.json")
    return frame, crosswalk


def score_from_spec(frame, spec):
    numeric_columns = ["saturation", "age_at_encounter", "heart_rate_consensus", "RR"]
    numeric = frame[numeric_columns].to_numpy(dtype=float)
    medians = np.asarray(spec["preprocessing"]["numeric_imputer"]["statistics"], dtype=float)
    missing = np.isnan(numeric)
    imputed = np.where(missing, medians, numeric)
    indicator_indices = spec["preprocessing"]["numeric_imputer"]["indicator_feature_indices"]
    indicators = missing[:, indicator_indices].astype(float)
    augmented = np.column_stack([imputed, indicators])
    scaler = spec["preprocessing"]["numeric_scaler"]
    scaled = (
        augmented - np.asarray(scaler["mean"], dtype=float)
    ) / np.asarray(scaler["scale"], dtype=float)

    sex = frame["assigned_sex_normalized"].astype("object")
    sex = sex.where(sex.notna(), spec["preprocessing"]["categorical_imputer"]["statistics"][0])
    categories = spec["preprocessing"]["onehot"]["categories"][0]
    if categories != ["female", "male", "unknown"]:
        raise AssertionError("Unexpected frozen category order")
    encoded = np.column_stack([
        sex.eq("male").astype(float).to_numpy(),
        sex.eq("unknown").astype(float).to_numpy(),
    ])
    design = np.column_stack([scaled, encoded])
    coefficients = np.asarray(spec["coefficients"], dtype=float)
    if design.shape[1] != len(coefficients):
        raise AssertionError("Frozen design and coefficient widths differ")
    return sigmoid(float(spec["intercept"]) + design @ coefficients)


def bootstrap_intervals(frame, dimension, group, support, replicates=BOOTSTRAP_REPLICATES):
    y = frame["outcome"].to_numpy(dtype=int)
    p = frame["predicted_risk"].to_numpy(dtype=float)
    subject_codes, subjects = pd.factorize(frame["patient_id"], sort=True)
    cluster_sizes = np.bincount(subject_codes)
    rng = np.random.default_rng(BOOTSTRAP_SEED + int(hashlib.sha256(f"{dimension}|{group}".encode()).hexdigest()[:8], 16))
    metric_names = [
        "observed_rate", "mean_predicted", "calibration_gap", "calibration_intercept",
        "calibration_slope", "brier", "log_loss", "pr_auc", "roc_auc",
    ]
    for threshold in THRESHOLDS:
        suffix = f"{int(threshold * 100)}pct"
        metric_names.extend([
            f"sensitivity_{suffix}", f"specificity_{suffix}", f"ppv_{suffix}",
            f"npv_{suffix}", f"flagged_rate_{suffix}", f"net_benefit_{suffix}",
            f"net_benefit_minus_all_{suffix}",
        ])
    values = {name: [] for name in metric_names}

    for _ in range(replicates):
        sampled_counts = rng.multinomial(len(subjects), np.repeat(1 / len(subjects), len(subjects)))
        weights = sampled_counts[subject_codes].astype(float)
        bundle = metric_bundle(y, p, weights, support["calibration_discrimination_support"])
        for name in metric_names:
            values[name].append(bundle[name])

    rows = []
    for name, samples in values.items():
        samples = np.asarray(samples, dtype=float)
        finite = samples[np.isfinite(samples)]
        rows.append({
            "dimension": dimension,
            "group": str(group),
            "metric": name,
            "lower_95": np.quantile(finite, 0.025) if len(finite) else np.nan,
            "upper_95": np.quantile(finite, 0.975) if len(finite) else np.nan,
            "valid_bootstrap_replicates": len(finite),
            "requested_bootstrap_replicates": replicates,
        })
    return rows


def run_validation():
    preoutcome, crosswalk = freeze_crosswalk()
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec["decision_id"] != "D028":
        raise AssertionError("The scoring specification is not the frozen D028 model")

    outcome = pd.read_csv(BOLD_CSV, usecols=["unique_hospital_admission_id", "SaO2"])
    if not outcome["unique_hospital_admission_id"].is_unique:
        raise AssertionError("Outcome key is not unique")
    frame = preoutcome.merge(outcome, on="unique_hospital_admission_id", how="left", validate="one_to_one")
    frame = frame.loc[frame["SpO2"].between(92, 96, inclusive="both")].copy()
    if frame["SaO2"].isna().any():
        raise AssertionError("Eligible BOLD rows have missing SaO2")

    frame = frame.rename(columns={
        "unique_subject_id": "patient_id",
        "unique_hospital_admission_id": "pair_id",
        "SpO2": "saturation",
        "admission_age": "age_at_encounter",
        "vitals_heart_rate": "heart_rate_consensus",
        "vitals_resp_rate": "RR",
    })
    frame["assigned_sex_normalized"] = frame["sex_female"].map({1: "female", 0: "male"})
    frame["outcome"] = (frame["SaO2"] < 88).astype(int)
    frame["predicted_risk"] = score_from_spec(frame, spec)

    support_rows = [support_row(frame, "overall", "BOLD")]
    support_rows.extend(
        support_row(group, "source_db", name)
        for name, group in frame.groupby("source_db", sort=True)
    )
    support_rows.extend(
        support_row(group, "race_ethnicity", name)
        for name, group in frame.groupby("race_ethnicity", dropna=False, sort=True)
    )
    support = pd.DataFrame(support_rows)
    support.to_csv(OUTPUT_DIR / "bold_external_support.csv", index=False)

    metric_rows = []
    group_frames = [("overall", "BOLD", frame)]
    group_frames.extend(("source_db", name, group) for name, group in frame.groupby("source_db", sort=True))
    group_frames.extend(("race_ethnicity", name, group) for name, group in frame.groupby("race_ethnicity", dropna=False, sort=True))
    support_lookup = support.set_index(["dimension", "group"]).to_dict("index")

    for dimension, group, subset in group_frames:
        key = (dimension, str(group))
        gate = support_lookup[key]
        for weighting in ["pair", "participant_balanced"]:
            if weighting == "participant_balanced":
                counts = subset.groupby("patient_id")["patient_id"].transform("size").to_numpy()
                weights = 1 / counts
            else:
                weights = None
            bundle = metric_bundle(
                subset["outcome"].to_numpy(), subset["predicted_risk"].to_numpy(),
                weights, gate["calibration_discrimination_support"],
            )
            if not gate["threshold_support"]:
                for name in list(bundle):
                    if any(token in name for token in ["sensitivity_", "specificity_", "ppv_", "npv_", "flagged_rate_", "net_benefit_"]):
                        bundle[name] = np.nan
                bundle["calibration_intercept"] = np.nan
            metric_rows.append({"dimension": dimension, "group": str(group), "weighting": weighting, **bundle})

    metrics = pd.DataFrame(metric_rows)
    metrics.to_csv(OUTPUT_DIR / "bold_external_performance.csv", index=False)

    bootstrap_rows = []
    for dimension, group, subset in group_frames:
        gate = support_lookup[(dimension, str(group))]
        if gate["threshold_support"]:
            bootstrap_rows.extend(bootstrap_intervals(subset, dimension, group, gate))
    bootstrap = pd.DataFrame(bootstrap_rows)
    bootstrap.to_csv(OUTPUT_DIR / "bold_external_bootstrap_intervals.csv", index=False)

    decision_rows = []
    for dimension, group, subset in group_frames[:4]:
        gate = support_lookup[(dimension, str(group))]
        if not gate["threshold_support"]:
            continue
        y = subset["outcome"].to_numpy()
        p = subset["predicted_risk"].to_numpy()
        prevalence = y.mean()
        for threshold in DECISION_THRESHOLDS:
            model_nb = threshold_metrics(y, p, threshold)["net_benefit"]
            all_nb = prevalence - (1 - prevalence) * threshold / (1 - threshold)
            decision_rows.append({
                "dimension": dimension, "group": str(group), "threshold": threshold,
                "model_net_benefit": model_nb, "flag_all_net_benefit": all_nb,
                "flag_none_net_benefit": 0.0, "model_minus_flag_all": model_nb - all_nb,
            })
    pd.DataFrame(decision_rows).to_csv(OUTPUT_DIR / "bold_external_decision_curve.csv", index=False)

    calibration_rows = []
    for dimension, group, subset in group_frames[:4]:
        ranked = subset["predicted_risk"].rank(method="first")
        bins = pd.qcut(ranked, q=min(10, len(subset)), labels=False, duplicates="drop")
        temp = subset.assign(calibration_bin=bins)
        table = temp.groupby("calibration_bin").agg(
            rows=("outcome", "size"), observed_rate=("outcome", "mean"),
            mean_predicted=("predicted_risk", "mean"),
            min_predicted=("predicted_risk", "min"), max_predicted=("predicted_risk", "max"),
        ).reset_index()
        table.insert(0, "group", str(group))
        table.insert(0, "dimension", dimension)
        calibration_rows.append(table)
    pd.concat(calibration_rows, ignore_index=True).to_csv(
        OUTPUT_DIR / "bold_external_calibration_bins.csv", index=False
    )

    feature_shift = pd.DataFrame([
        {"feature": "saturation", "eligible_missing_rate": frame["saturation"].isna().mean(), "eligible_mean": frame["saturation"].mean(), "eligible_median": frame["saturation"].median(), "eligible_p01": frame["saturation"].quantile(.01), "eligible_p99": frame["saturation"].quantile(.99), "openox_training_center": spec["preprocessing"]["numeric_scaler"]["mean"][0]},
        {"feature": "age_at_encounter", "eligible_missing_rate": frame["age_at_encounter"].isna().mean(), "eligible_mean": frame["age_at_encounter"].mean(), "eligible_median": frame["age_at_encounter"].median(), "eligible_p01": frame["age_at_encounter"].quantile(.01), "eligible_p99": frame["age_at_encounter"].quantile(.99), "openox_training_center": spec["preprocessing"]["numeric_scaler"]["mean"][1]},
        {"feature": "heart_rate_consensus", "eligible_missing_rate": frame["heart_rate_consensus"].isna().mean(), "eligible_mean": frame["heart_rate_consensus"].mean(), "eligible_median": frame["heart_rate_consensus"].median(), "eligible_p01": frame["heart_rate_consensus"].quantile(.01), "eligible_p99": frame["heart_rate_consensus"].quantile(.99), "openox_training_center": spec["preprocessing"]["numeric_scaler"]["mean"][2]},
        {"feature": "RR", "eligible_missing_rate": frame["RR"].isna().mean(), "eligible_mean": frame["RR"].mean(), "eligible_median": frame["RR"].median(), "eligible_p01": frame["RR"].quantile(.01), "eligible_p99": frame["RR"].quantile(.99), "openox_training_center": spec["preprocessing"]["numeric_scaler"]["mean"][3]},
    ])
    feature_shift.to_csv(OUTPUT_DIR / "bold_external_feature_shift.csv", index=False)

    prediction_columns = [
        "pair_id", "patient_id", "source_db", "race_ethnicity", "saturation",
        "age_at_encounter", "heart_rate_consensus", "RR", "assigned_sex_normalized",
        "delta_SpO2", "delta_vitals_heart_rate", "delta_vitals_resp_rate",
        "outcome", "predicted_risk",
    ]
    frame[prediction_columns].to_csv(
        OUTPUT_DIR / "bold_external_predictions.csv.gz", index=False, compression="gzip"
    )

    qa_checks = {
        "crosswalk was frozen before outcome load": crosswalk["status"] == "frozen before external outcome analysis",
        "frozen D028 scoring specification used": spec["decision_id"] == "D028",
        "all eligible rows have outcome": frame["outcome"].notna().all(),
        "predicted risks are finite and bounded": np.isfinite(frame["predicted_risk"]).all() and frame["predicted_risk"].between(0, 1).all(),
        "all rows satisfy SpO2 eligibility": frame["saturation"].between(92, 96, inclusive="both").all(),
        "participant IDs are complete": frame["patient_id"].notna().all(),
        "three source databases are retained": set(frame["source_db"].unique()) == {"eicu", "mimic_iii", "mimic_iv"},
        "1000 cluster bootstrap replicates requested": BOOTSTRAP_REPLICATES == 1000,
        "race/ethnicity is not a predictor": "race_ethnicity" not in spec["raw_feature_order"],
        "no forbidden ABG field is a predictor": not ({"SaO2", "pO2", "pH", "pCO2"} & set(spec["raw_feature_order"])),
    }
    if not all(qa_checks.values()):
        raise AssertionError({key: value for key, value in qa_checks.items() if not value})
    pd.DataFrame({"check": qa_checks.keys(), "pass": qa_checks.values()}).to_csv(
        OUTPUT_DIR / "bold_external_qa.csv", index=False
    )

    artifact_paths = sorted(OUTPUT_DIR.glob("bold_*"))
    manifest = []
    for path in artifact_paths:
        if path.name == "bold_external_artifact_manifest.csv":
            continue
        manifest.append({"artifact": path.name, "path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size})
    pd.DataFrame(manifest).to_csv(OUTPUT_DIR / "bold_external_artifact_manifest.csv", index=False)

    overall = metrics.loc[
        metrics["dimension"].eq("overall") & metrics["weighting"].eq("pair")
    ].iloc[0]
    summary = {
        "eligible_rows": len(frame),
        "participants": frame["patient_id"].nunique(),
        "events": int(frame["outcome"].sum()),
        "event_positive_participants": frame.loc[frame["outcome"].eq(1), "patient_id"].nunique(),
        "observed_rate": overall["observed_rate"],
        "mean_predicted": overall["mean_predicted"],
        "calibration_intercept": overall["calibration_intercept"],
        "calibration_slope": overall["calibration_slope"],
        "brier": overall["brier"],
        "log_loss": overall["log_loss"],
        "pr_auc": overall["pr_auc"],
        "roc_auc": overall["roc_auc"],
        "sensitivity_5pct": overall["sensitivity_5pct"],
        "specificity_5pct": overall["specificity_5pct"],
        "ppv_5pct": overall["ppv_5pct"],
        "npv_5pct": overall["npv_5pct"],
    }
    write_json(OUTPUT_DIR / "bold_external_summary.json", summary)

    # Rebuild the manifest after the compact summary has been written.
    artifact_paths = sorted(OUTPUT_DIR.glob("bold_*"))
    manifest = []
    for path in artifact_paths:
        if path.name == "bold_external_artifact_manifest.csv":
            continue
        manifest.append({
            "artifact": path.name, "path": str(path),
            "sha256": sha256(path), "bytes": path.stat().st_size,
        })
    pd.DataFrame(manifest).to_csv(
        OUTPUT_DIR / "bold_external_artifact_manifest.csv", index=False
    )
    return summary


if __name__ == "__main__":
    result = run_validation()
    print(json.dumps(result, indent=2))
