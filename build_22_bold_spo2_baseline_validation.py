from pathlib import Path
import json

import nbformat as nbf


ROOT = Path(__file__).parent
OUT = ROOT / "22_bold_spo2_baseline_validation.ipynb"
RESULTS = ROOT / "bold_spo2_baseline_validation"
summary = json.loads((RESULTS / "bold_baseline_summary.json").read_text(encoding="utf-8"))


def pct(value):
    return f"{100 * value:.2f}%"


nb = nbf.v4.new_notebook()
cells = []

cells.append(nbf.v4.new_markdown_cell(f"""# BOLD SpO2-only occult-hypoxemia baseline diagnostic

## tl;dr

The locked SpO2-only OpenOx baseline transported substantially better to BOLD than the D028 compact model. On the same 11,880-pair denominator, the baseline predicted {pct(summary['baseline_mean_predicted'])} risk versus {pct(summary['observed_rate'])} observed; D028 predicted {pct(summary['compact_mean_predicted'])}. Baseline Brier score was {summary['baseline_brier']:.5f} versus {summary['compact_brier']:.5f}, log loss {summary['baseline_log_loss']:.5f} versus {summary['compact_log_loss']:.5f}, PR-AUC {summary['baseline_pr_auc']:.4f} versus {summary['compact_pr_auc']:.4f}, and ROC-AUC {summary['baseline_roc_auc']:.4f} versus {summary['compact_roc_auc']:.4f}.

This is a post-validation diagnostic comparator specified after the D028 BOLD result was known. It indicates that the added compact predictors materially contributed to poor BOLD transport, but it is not a second confirmatory validation or a rescue-model selection exercise.
"""))

cells.append(nbf.v4.new_markdown_cell("""## Context & Methods

### Key assumptions

- The development cohort remains the frozen 180-second OpenOx cohort restricted to SpO2 92-96%, with SaO2 below 88% as the target.
- The candidate is the already-authorized SpO2-only ridge baseline from Notebook 13; no new predictors or model classes are searched.
- The final penalty is selected solely from the 250 pre-existing frozen OpenOx baseline tuning contexts using minimum mean inner log loss, mean Brier score, then smaller `C`.
- The model, coefficients, scoring specification, and diagnostic lock are written before this run loads BOLD SaO2 or prior D028 BOLD predictions.
- BOLD uses the same 11,880-pair denominator and 11,441 participants as D030-D031.
- Comparisons use paired 1,000-replicate participant-cluster bootstrap resampling.
- Because BOLD outcomes were already known when this diagnostic was authorized, all findings are exploratory mechanism evidence rather than confirmatory external validation.
"""))

cells.append(nbf.v4.new_code_cell("""import os
os.environ["MKL_THREADING_LAYER"] = "SEQUENTIAL"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

from pathlib import Path
import json
import pandas as pd

from bold_spo2_baseline_validation import run_validation
from qa_bold_spo2_baseline_validation import run_qa

ROOT = Path.cwd()
RESULTS = ROOT / "bold_spo2_baseline_validation"
"""))

cells.append(nbf.v4.new_markdown_cell("""## Data

### 1. Recreate the OpenOx-only lock and score BOLD unchanged

Running this cell recreates all model, prediction, metric, bootstrap, chronology, and hash artifacts. The OpenOx-only lock is persisted before external outcome access within the run.
"""))
cells.append(nbf.v4.new_code_cell("""summary = run_validation()
pd.Series(summary, name="value").to_frame()
"""))

cells.append(nbf.v4.new_markdown_cell("""### 2. Verify the frozen penalty selection and model contract"""))
cells.append(nbf.v4.new_code_cell("""penalty = pd.read_csv(RESULTS / "baseline_penalty_selection.csv")
coefficients = pd.read_csv(RESULTS / "baseline_coefficients.csv")
lock = json.loads((RESULTS / "baseline_model_lock.json").read_text())
penalty, coefficients, pd.Series(lock, name="value").to_frame()
"""))

cells.append(nbf.v4.new_markdown_cell("""## Results

### 3. Compare unchanged BOLD performance on the identical denominator"""))
cells.append(nbf.v4.new_code_cell("""comparison = pd.read_csv(RESULTS / "bold_baseline_vs_compact.csv")
headline = [
    "mean_predicted", "calibration_intercept", "calibration_slope",
    "brier", "log_loss", "pr_auc", "roc_auc",
    "sensitivity_5pct", "specificity_5pct", "ppv_5pct", "npv_5pct",
    "flagged_rate_5pct", "net_benefit_5pct",
]
comparison.loc[comparison["metric"].isin(headline)].reset_index(drop=True)
"""))

cells.append(nbf.v4.new_markdown_cell("""### 4. Inspect participant-bootstrap uncertainty and SpO2-specific calibration"""))
cells.append(nbf.v4.new_code_cell("""intervals = pd.read_csv(RESULTS / "bold_baseline_bootstrap_intervals.csv")
differences = pd.read_csv(
    RESULTS / "bold_baseline_vs_compact_bootstrap_differences.csv"
)
calibration = pd.read_csv(RESULTS / "bold_baseline_calibration_by_spo2.csv")
metrics = [
    "mean_predicted", "calibration_intercept", "calibration_slope",
    "brier", "log_loss", "pr_auc", "roc_auc",
]
(
    intervals.loc[intervals["metric"].isin(metrics)].reset_index(drop=True),
    differences.loc[differences["metric"].isin(metrics)].reset_index(drop=True),
    calibration,
)
"""))

cells.append(nbf.v4.new_markdown_cell("""### 5. Run independent metric and artifact QA"""))
cells.append(nbf.v4.new_code_cell("""qa_result = run_qa()
qa = pd.read_csv(RESULTS / "bold_baseline_independent_qa.csv")
qa_result, qa
"""))

cells.append(nbf.v4.new_markdown_cell(f"""## Takeaways

- The SpO2-only baseline is much closer to BOLD's observed event rate: {pct(summary['baseline_mean_predicted'])} predicted versus {pct(summary['observed_rate'])} observed. Its calibration intercept is {summary['baseline_calibration_intercept']:.3f} and slope is {summary['baseline_calibration_slope']:.3f}. Calibration is not perfect—the model underpredicts on average and remains overfit—but it is far better than D028's {pct(summary['compact_mean_predicted'])} prediction, -2.114 intercept, and 0.119 slope.
- Probability loss and ranking both improve materially: baseline-minus-D028 Brier is {summary['baseline_brier'] - summary['compact_brier']:+.5f}, log loss {summary['baseline_log_loss'] - summary['compact_log_loss']:+.5f}, PR-AUC {summary['baseline_pr_auc'] - summary['compact_pr_auc']:+.4f}, and ROC-AUC {summary['baseline_roc_auc'] - summary['compact_roc_auc']:+.4f}. The paired participant-bootstrap intervals exclude zero for all four differences.
- The result supports a specific interpretation: the added age, sex, heart-rate, and respiratory-rate terms—under major ICU case-mix and measurement-timing shift—substantially degraded transport relative to the simpler SpO2 signal.
- The baseline is still not clinically validated or deployment-ready. Its slope is below one, its overall prediction is low, and its 5% threshold exchanges lower sensitivity for much higher specificity. The exercise diagnoses D028's failure; it does not authorize choosing a new clinical model after seeing BOLD.
- ENCoDE remains unscorable for occult-risk models because its eligible denominator contains zero events.
"""))

nb["cells"] = cells
nb["metadata"] = {
    "kernelspec": {
        "display_name": "Python (openox)", "language": "python", "name": "openox"
    },
    "language_info": {"name": "python", "version": "3.12"},
    "openox_analysis": {
        "decision_id": "D034-diagnostic",
        "role": "post-validation diagnostic comparator",
        "confirmatory": False,
    },
}
nbf.write(nb, OUT)
print(OUT)
