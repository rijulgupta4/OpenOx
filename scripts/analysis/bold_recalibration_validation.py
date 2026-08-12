from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

os.environ["MKL_THREADING_LAYER"] = "SEQUENTIAL"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import SplineTransformer, StandardScaler

ROOT = Path.cwd()
INPUT = ROOT / "bold_spo2_baseline_validation" / "bold_baseline_predictions.csv.gz"
OUT = ROOT / "bold_recalibration_validation"
SEED = 20260805
REPEATS = 20
FOLDS = 5
EPS = 1e-6
METHODS = ["unchanged", "intercept_only", "logistic", "isotonic", "spline"]
BASE_SCORES = {
    "SpO2-only": "baseline_predicted_risk",
    "D028 compact": "compact_predicted_risk",
}
COMPLEXITY = {"intercept_only": 1, "logistic": 2, "isotonic": 3, "spline": 4}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clip(p):
    return np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)


def logit(p):
    p = clip(p)
    return np.log(p / (1 - p))


def fit_parametric(lp: np.ndarray, y: np.ndarray, slope: bool):
    x = np.column_stack([np.ones(len(lp)), lp]) if slope else np.ones((len(lp), 1))
    beta = np.array([0.0, 1.0]) if slope else np.array([0.0])
    offset = np.zeros(len(lp)) if slope else lp
    for _ in range(100):
        eta = offset + x @ beta
        q = 1 / (1 + np.exp(-np.clip(eta, -35, 35)))
        w = np.maximum(q * (1 - q), 1e-8)
        score = x.T @ (y - q)
        info = (x.T * w) @ x
        step = np.linalg.solve(info + np.eye(info.shape[0]) * 1e-10, score)
        beta += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return {"kind": "logistic" if slope else "intercept_only", "beta": beta}


def fit_calibrator(method: str, p: np.ndarray, y: np.ndarray):
    lp = logit(p)
    if method == "intercept_only":
        return fit_parametric(lp, y, False)
    if method == "logistic":
        return fit_parametric(lp, y, True)
    if method == "isotonic":
        return IsotonicRegression(out_of_bounds="clip", y_min=EPS, y_max=1-EPS).fit(p, y)
    if method == "spline":
        model = make_pipeline(
            SplineTransformer(n_knots=4, degree=3, include_bias=False),
            StandardScaler(),
            LogisticRegression(C=1e6, solver="lbfgs", max_iter=2000),
        )
        return model.fit(lp.reshape(-1, 1), y)
    raise ValueError(method)


def apply_calibrator(model, method: str, p: np.ndarray) -> np.ndarray:
    if method == "unchanged":
        return clip(p)
    if method == "intercept_only":
        eta = logit(p) + model["beta"][0]
        return clip(1 / (1 + np.exp(-np.clip(eta, -35, 35))))
    if method == "logistic":
        eta = model["beta"][0] + model["beta"][1] * logit(p)
        return clip(1 / (1 + np.exp(-np.clip(eta, -35, 35))))
    if method == "isotonic":
        return clip(model.predict(p))
    return clip(model.predict_proba(logit(p).reshape(-1, 1))[:, 1])


def metrics(y, p, weights=None):
    return {
        "observed_rate": float(np.average(y, weights=weights)),
        "mean_predicted": float(np.average(p, weights=weights)),
        "brier": float(np.average((y-p)**2, weights=weights)),
        "log_loss": float(log_loss(y, p, sample_weight=weights, labels=[0, 1])),
        "pr_auc": float(average_precision_score(y, p, sample_weight=weights)),
        "roc_auc": float(roc_auc_score(y, p, sample_weight=weights)),
    }


def make_folds(frame: pd.DataFrame, scope: str):
    patients = frame.groupby("patient_id", as_index=False).agg(
        outcome=("outcome", "max"), source_db=("source_db", "first")
    )
    labels = patients["outcome"].astype(str) if scope == "eICU" else (
        patients["source_db"].astype(str) + "|" + patients["outcome"].astype(str)
    )
    rows = []
    for repeat in range(REPEATS):
        skf = StratifiedKFold(n_splits=FOLDS, shuffle=True, random_state=SEED + repeat)
        for fold, (_, va) in enumerate(skf.split(patients, labels)):
            for patient_id in patients.iloc[va]["patient_id"]:
                rows.append({"scope": scope, "repeat": repeat, "fold": fold, "patient_id": patient_id})
    return pd.DataFrame(rows)


def run_scope(frame: pd.DataFrame, scope: str):
    folds = make_folds(frame, scope)
    index_by_patient = frame.groupby("patient_id").indices
    sums = {(base, method): np.zeros(len(frame)) for base in BASE_SCORES for method in METHODS}
    repeat_rows = []
    for repeat in range(REPEATS):
        assignment = folds.loc[folds.repeat.eq(repeat)].set_index("patient_id")["fold"]
        row_fold = frame["patient_id"].map(assignment).to_numpy()
        for base, column in BASE_SCORES.items():
            raw = frame[column].to_numpy(float)
            for method in METHODS:
                oof = np.empty(len(frame))
                for fold in range(FOLDS):
                    va = row_fold == fold
                    tr = ~va
                    model = None if method == "unchanged" else fit_calibrator(method, raw[tr], frame.loc[tr, "outcome"].to_numpy(int))
                    oof[va] = apply_calibrator(model, method, raw[va])
                sums[(base, method)] += oof
                for weighting, weights in [
                    ("pair", None),
                    ("participant_balanced", 1 / frame.groupby("patient_id")["patient_id"].transform("size").to_numpy(float)),
                ]:
                    row = {"scope": scope, "repeat": repeat, "base_model": base, "method": method, "weighting": weighting}
                    row.update(metrics(frame.outcome.to_numpy(int), oof, weights))
                    repeat_rows.append(row)
    prediction_rows = []
    for (base, method), total in sums.items():
        temp = frame[["pair_id", "patient_id", "source_db", "outcome"]].copy()
        temp.insert(0, "scope", scope)
        temp["base_model"] = base
        temp["method"] = method
        temp["predicted_risk"] = total / REPEATS
        prediction_rows.append(temp)
    return folds, pd.DataFrame(repeat_rows), pd.concat(prediction_rows, ignore_index=True)


def summarize(repeat_metrics: pd.DataFrame) -> pd.DataFrame:
    metrics_cols = ["observed_rate", "mean_predicted", "brier", "log_loss", "pr_auc", "roc_auc"]
    summary = repeat_metrics.groupby(["scope", "base_model", "method", "weighting"])[metrics_cols].agg(["median", "mean", "std"])
    summary.columns = [f"{a}_{b}" for a, b in summary.columns]
    return summary.reset_index()


def bootstrap_best(predictions: pd.DataFrame, best_base: str, best_method: str):
    wide = predictions.loc[predictions.scope.eq("overall_BOLD")].pivot_table(
        index=["pair_id", "patient_id", "outcome"], columns=["base_model", "method"], values="predicted_risk"
    ).reset_index()
    comparators = [("SpO2-only", "unchanged"), ("D028 compact", "unchanged")]
    best = wide[(best_base, best_method)].to_numpy(float)
    y = wide["outcome"].to_numpy(int)
    codes, subjects = pd.factorize(wide["patient_id"], sort=True)
    rng = np.random.default_rng(SEED + 1000)
    rows = []
    for comparator in comparators:
        comp = wide[comparator].to_numpy(float)
        vals = {"brier_difference_best_minus_comparator": [], "log_loss_difference_best_minus_comparator": []}
        for _ in range(1000):
            counts = rng.multinomial(len(subjects), np.repeat(1/len(subjects), len(subjects)))
            w = counts[codes].astype(float)
            vals["brier_difference_best_minus_comparator"].append(np.average((y-best)**2-(y-comp)**2, weights=w))
            vals["log_loss_difference_best_minus_comparator"].append(np.average(-(y*np.log(best)+(1-y)*np.log(1-best)) + (y*np.log(comp)+(1-y)*np.log(1-comp)), weights=w))
        for metric, values in vals.items():
            rows.append({"best_base_model": best_base, "best_method": best_method, "comparator_base_model": comparator[0], "comparator_method": comparator[1], "metric": metric, "estimate": float(np.mean(values)), "lower_95": float(np.quantile(values, .025)), "upper_95": float(np.quantile(values, .975)), "replicates": 1000})
    return pd.DataFrame(rows)


def run_validation():
    OUT.mkdir(exist_ok=True)
    frame = pd.read_csv(INPUT)
    if len(frame) != 11880 or frame.patient_id.nunique() != 11441 or int(frame.outcome.sum()) != 671:
        raise AssertionError("Frozen BOLD denominator changed")
    overall = frame.copy()
    eicu = frame.loc[frame.source_db.eq("eicu")].reset_index(drop=True)
    outputs = [run_scope(overall, "overall_BOLD"), run_scope(eicu, "eICU")]
    folds = pd.concat([x[0] for x in outputs], ignore_index=True)
    repeat_metrics = pd.concat([x[1] for x in outputs], ignore_index=True)
    predictions = pd.concat([x[2] for x in outputs], ignore_index=True)
    summary = summarize(repeat_metrics)
    eligible = summary.loc[
        summary.scope.eq("overall_BOLD") & summary.weighting.eq("pair") & ~summary.method.eq("unchanged")
    ].copy()
    eligible["complexity_rank"] = eligible.method.map(COMPLEXITY)
    eligible = eligible.sort_values(["log_loss_median", "brier_median", "complexity_rank", "base_model", "method"], kind="mergesort")
    eligible["selected"] = False
    eligible.loc[eligible.index[0], "selected"] = True
    best = eligible.iloc[0]
    uncertainty = bootstrap_best(predictions, best.base_model, best.method)
    raw_col = BASE_SCORES[best.base_model]
    final_model = fit_calibrator(best.method, overall[raw_col].to_numpy(float), overall.outcome.to_numpy(int))
    joblib.dump(final_model, OUT / "selected_bold_recalibrator.joblib", compress=3)
    spec = {
        "decision_id": "D035-recalibration",
        "status": "post-external-validation model updating; not new external validation",
        "input_score": best.base_model,
        "method": best.method,
        "selection_rule": "lowest median repeated-CV pair-weighted log loss; then Brier; then lower complexity",
        "resampling": {"repeats": REPEATS, "folds": FOLDS, "unit": "patient", "stratification": "source x outcome"},
        "candidate_methods": METHODS[1:],
        "claim_boundary": "Selected and fit using BOLD outcomes; requires evaluation on a third untouched dataset before transport claims.",
    }
    (OUT / "selected_bold_recalibrator_spec.json").write_text(json.dumps(spec, indent=2), encoding="utf-8")
    folds.to_csv(OUT / "patient_fold_assignments.csv.gz", index=False)
    repeat_metrics.to_csv(OUT / "repeated_cv_metrics.csv", index=False)
    predictions.to_csv(OUT / "consensus_oof_predictions.csv.gz", index=False)
    summary.to_csv(OUT / "recalibration_summary.csv", index=False)
    eligible.to_csv(OUT / "overall_selection_table.csv", index=False)
    uncertainty.to_csv(OUT / "selected_vs_unchanged_bootstrap.csv", index=False)
    result = {"best_base_model": best.base_model, "best_method": best.method, "median_log_loss": float(best.log_loss_median), "median_brier": float(best.brier_median), "median_pr_auc": float(best.pr_auc_median), "median_roc_auc": float(best.roc_auc_median)}
    (OUT / "recalibration_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    artifacts = [p for p in OUT.iterdir() if p.is_file() and p.name != "artifact_manifest.csv"]
    pd.DataFrame([{"path": str(p.resolve()), "sha256": sha256(p), "bytes": p.stat().st_size} for p in sorted(artifacts)]).to_csv(OUT / "artifact_manifest.csv", index=False)
    return result


if __name__ == "__main__":
    print(json.dumps(run_validation(), indent=2))
