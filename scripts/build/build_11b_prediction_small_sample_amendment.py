from pathlib import Path
import nbformat as nbf


OUT = Path(r".\notebooks\11b_prediction_small_sample_amendment.ipynb")
nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12"},
}


def md(text):
    return nbf.v4.new_markdown_cell(text)


def code(text):
    return nbf.v4.new_code_cell(text)


nb["cells"] = [
    md(
        r"""# Prediction lock amendment: sparse clustered outcomes

## tl;dr

The 261 occult-hypoxemia readings arise from only 38 event-positive participants. The primary prediction claim is therefore a **pilot, internally validated risk-flagging model**, even though the outcome remains the clinically motivated headline target.

This amendment makes six safeguards explicit before fitting:

1. Restrict development and evaluation to readings with `SpO2 92-96%`; rows outside that band are excluded, not labeled negative.
2. Keep the model low-dimensional and fixed; do not perform unrestricted feature selection or interaction searches.
3. Use 50 repeats of five-fold participant-grouped cross-validation, stratifying on participant event status and pooling fold predictions within each repeat.
4. Retain ridge logistic regression as the primary predictive algorithm; add intercept-corrected Firth logistic regression (FLIC, or FLAC if implemented) as a separation/finite-sample sensitivity—not as a cure for clustering.
5. Use `abs(SpO2-SaO2) >=3` in the same SpO2 band as a richer-event pipeline robustness target.
6. Add decision-curve analysis as a secondary clinical-utility analysis, with participant-cluster uncertainty and explicit threshold assumptions.

No outcome model is fit in this amendment notebook."""
    ),
    md(
        r"""## Why the amendment is needed

Repeated readings add information about reading-level prediction, but they do not create independent participants. Grouped resampling, cluster bootstrap uncertainty, and participant-balanced sensitivity analyses therefore remain essential.

Firth penalization addresses separation and small-sample maximum-likelihood coefficient bias; it does not address within-participant dependence. Moreover, ordinary Firth predictions can be biased toward 0.5, so prediction work should use an intercept-corrected variant and evaluate calibration directly.

References: [Puhr et al., 2017](https://pubmed.ncbi.nlm.nih.gov/28295456/), [Heinze and Schemper, 2002](https://onlinelibrary.wiley.com/doi/10.1002/sim.1047), [Riley et al., 2019](https://pmc.ncbi.nlm.nih.gov/articles/PMC6710621/), [Efron and Tibshirani, 1997](https://www.tandfonline.com/doi/abs/10.1080/01621459.1997.10474007), and [Vickers et al., decision-curve guidance](https://pubmed.ncbi.nlm.nih.gov/27247223/)."""
    ),
    code(
        r"""from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROJECT = Path(r".")
PROCESSED = PROJECT / "data" / "processed"
TABLES = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
TABLES.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

cohort = pd.read_csv(PROCESSED / "analytic_cohort_180s.csv.gz")
assert len(cohort) == 28_693
assert cohort.pulse_row_id.is_unique
assert np.allclose(cohort.error, cohort.saturation - cohort.so2, equal_nan=True)

band = cohort.loc[cohort.saturation.between(92, 96)].copy()
band["occult_hypoxemia"] = band.so2 < 88
band["abs_error_ge_3"] = band.error.abs() >= 3
band["abs_error_ge_4"] = band.error.abs() >= 4

def support(label, frame, outcome):
    positive = frame[outcome].astype(bool)
    return {
        "target": label,
        "eligible_pairs": len(frame),
        "positive_pairs": int(positive.sum()),
        "positive_pair_rate_pct": 100 * positive.mean(),
        "participants": frame.patient_id.nunique(),
        "positive_participants": frame.loc[positive, "patient_id"].nunique(),
    }

target_support = pd.DataFrame([
    support("Occult hypoxemia: SaO2 <88 within SpO2 92-96", band, "occult_hypoxemia"),
    support("Robustness: absolute error >=3 within SpO2 92-96", band, "abs_error_ge_3"),
    support("Optional sensitivity: absolute error >=4 within SpO2 92-96", band, "abs_error_ge_4"),
])
display(target_support.round(3))"""
    ),
    md(
        r"""## Locked target interpretation

The deployment question is conditional: among readings that look reassuring (`SpO2 92-96%`), which readings merit an additional warning? Therefore the SpO2 band defines the entire development/evaluation population. The binary outcome is `SaO2 <88%` only within that population.

SpO2 remains a required baseline predictor even though its range is narrow. A weak coefficient is informative: it would show that the displayed value has little remaining ranking information once the reading is already inside the reassuring band. The primary model uses SpO2 linearly; no spline or data-driven cut point is justified by 38 positive participants."""
    ),
    code(
        r"""method_amendments = pd.DataFrame([
    {
        "domain": "Development population",
        "locked decision": "Restrict all fitting and evaluation to SpO2 92-96%; exclude outside-band rows.",
        "role": "Primary",
        "reason": "Matches the clinical meaning of occult hypoxemia and avoids automatic negatives outside the alert context.",
    },
    {
        "domain": "Primary target",
        "locked decision": "SaO2 <88% within the restricted population; describe prediction evidence as pilot/exploratory because only 38 participants are positive.",
        "role": "Headline",
        "reason": "Clinically motivated but sparse at the participant level.",
    },
    {
        "domain": "Richer-event target",
        "locked decision": "Absolute SpO2-SaO2 error >=3 percentage points within the same SpO2 92-96% population.",
        "role": "Secondary robustness",
        "reason": "778 positive pairs from 76 positive participants test pipeline stability without changing the decision context.",
    },
    {
        "domain": "Primary algorithm",
        "locked decision": "Fixed low-dimensional ridge logistic regression; no unrestricted feature selection, interactions, or nonlinear search.",
        "role": "Primary",
        "reason": "Prediction-oriented shrinkage with limited degrees of freedom.",
    },
    {
        "domain": "Firth sensitivity",
        "locked decision": "Fit FLIC (or FLAC) using the same features inside each training resample; compare convergence, coefficients, calibration, and predictions with ridge.",
        "role": "Sensitivity",
        "reason": "Addresses separation/finite-sample bias; intercept correction avoids ordinary Firth probability distortion.",
    },
    {
        "domain": "Outer validation",
        "locked decision": "50 repeats of five-fold participant-grouped CV, stratified by participant event status; target 7-8 positive participants per validation fold.",
        "role": "Primary",
        "reason": "Prevents leakage and zero-positive folds while quantifying split instability.",
    },
    {
        "domain": "Metric aggregation",
        "locked decision": "Pool out-of-fold predictions across the five folds within each repeat; summarize distributions across 50 repeats, not unstable single-fold metrics.",
        "role": "Primary",
        "reason": "Each fold contains few positive participants.",
    },
    {
        "domain": "Tuning",
        "locked decision": "Use a small prespecified ridge penalty grid in grouped inner folds; record selection frequencies and include a fixed-penalty sensitivity.",
        "role": "Primary",
        "reason": "Sparse data can make data-driven penalty selection unstable.",
    },
    {
        "domain": "Bootstrap cross-check",
        "locked decision": "Use at least 500 participant-cluster bootstrap resamples and refit the entire pipeline; report ordinary optimism correction, plus .632+ for compatible loss metrics when out-of-bag event support is adequate.",
        "role": "Secondary",
        "reason": ".632+ is useful but must resample participants and is not equally natural for every calibration/discrimination estimand.",
    },
    {
        "domain": "Clustering",
        "locked decision": "Keep pair-weighted fitting primary; add inverse-participant-frequency weighting as sensitivity. Never claim Firth itself handles repeated-measures dependence.",
        "role": "Required sensitivity",
        "reason": "Heavy contributors otherwise exert more influence; grouped evaluation alone does not change model-fitting weights.",
    },
    {
        "domain": "Decision curve",
        "locked decision": "Estimate out-of-fold net benefit from 2%-10% risk thresholds against flag-all and flag-none; use participant-bootstrap intervals.",
        "role": "Secondary",
        "reason": "Links a risk flag to assumed clinical tradeoffs without replacing calibration and discrimination metrics.",
    },
    {
        "domain": "Enriched features",
        "locked decision": "Evaluate device, pigmentation, and perfusion blocks one at a time against the fixed primary model; do not build an unrestricted cumulative full model.",
        "role": "Exploratory",
        "reason": "Limits degrees of freedom and isolates incremental feature value.",
    },
    {
        "domain": "Pigmentation interpretation",
        "locked decision": "Keep disparate-performance estimands separate from incremental predictive-value estimands.",
        "role": "Reporting safeguard",
        "reason": "No incremental prediction gain does not imply absence of device disparity, and disparity does not automatically justify using pigmentation as a predictor.",
    },
])
display(method_amendments)"""
    ),
    md(
        r"""## Pigmentation: two questions, two result sections

1. **Disparate-performance analysis (already completed):** Does signed error or occult-hypoxemia risk differ by measured pigmentation?
2. **Feature-value analysis (future prediction extension):** Does adding measured pigmentation to a frozen model improve out-of-fold calibration, Brier score, PR-AUC, or decision-curve net benefit?

The two findings cannot negate one another. Pigmentation feature value is exploratory, OpenOx-specific, and assessed as an incremental block—not as evidence that a protected or biologically complex characteristic should be required for safe oximetry."""
    ),
    code(
        r"""fig, ax = plt.subplots(figsize=(8.4, 4.6))
plot = target_support.iloc[::-1]
bars = ax.barh(plot["target"], plot["positive_participants"], color=["#8f8ccf", "#56a38d", "#a56b79"])
ax.set_xlabel("Participants with at least one positive reading")
ax.set_title("Participant-level event support in the SpO2 92-96% population")
ax.set_xlim(0, 85)
ax.grid(axis="x", alpha=.2)
for bar, value in zip(bars, plot["positive_participants"]):
    ax.text(value + 1.2, bar.get_y() + bar.get_height()/2, str(value), va="center", fontweight="bold")
fig.tight_layout()
figure_path = FIGURES / "prediction_target_participant_support.png"
fig.savefig(figure_path, dpi=180, bbox_inches="tight")
plt.show()

target_support.to_csv(TABLES / "prediction_small_sample_target_support.csv", index=False)
method_amendments.to_csv(TABLES / "prediction_small_sample_method_amendments.csv", index=False)

qa = pd.DataFrame([
    {"check": "Frozen cohort row count", "pass": len(cohort) == 28_693},
    {"check": "Restricted denominator row count", "pass": len(band) == 6_062},
    {"check": "Occult positive readings", "pass": int(band.occult_hypoxemia.sum()) == 261},
    {"check": "Occult positive participants", "pass": band.loc[band.occult_hypoxemia, "patient_id"].nunique() == 38},
    {"check": "Absolute-error >=3 positive readings", "pass": int(band.abs_error_ge_3.sum()) == 778},
    {"check": "Absolute-error >=3 positive participants", "pass": band.loc[band.abs_error_ge_3, "patient_id"].nunique() == 76},
    {"check": "All amendment domains unique", "pass": method_amendments.domain.is_unique},
])
qa.to_csv(TABLES / "prediction_small_sample_lock_qa.csv", index=False)
display(qa)
assert qa["pass"].all()
print("Small-sample amendment QA passed; no model was fit.")"""
    ),
    md(
        r"""## Interpretation

This amendment does not change the project’s overall architecture. It narrows the claims and strengthens the validation:

- Occult hypoxemia remains the headline outcome but the model is explicitly pilot evidence.
- The richer absolute-error target tests whether the modeling pipeline behaves coherently with more participant-level events; it cannot validate the occult-hypoxemia model by proxy.
- Ridge remains primary because the goal is calibrated prediction. FLIC/FLAC is a valuable rare-event sensitivity, not an automatic replacement and not a clustering correction.
- Repeated grouped cross-validation is primary; clustered bootstrap optimism correction is an independent cross-check.
- Decision curves are secondary because net benefit depends on an assumed clinical threshold tradeoff.

The next authorized step is to implement the frozen resampling object first, audit its fold-by-fold participant/event allocation, and only then fit the baseline and primary models."""
    ),
]

OUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, OUT)
print(OUT)
