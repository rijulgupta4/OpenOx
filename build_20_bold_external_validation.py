from pathlib import Path
import json


OUT = Path(__file__).with_name("20_bold_external_validation.ipynb")


def markdown(source):
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source):
    return {
        "cell_type": "code", "execution_count": None, "metadata": {},
        "outputs": [], "source": source.splitlines(keepends=True),
    }


cells = [
    markdown("""# OpenOx external validation in BOLD\n\n## tl;dr\n\nThe frozen D028 compact model does **not** transport as a calibrated probability model to BOLD. Among 11,880 eligible BOLD pairs from 11,441 participants, 671 readings (5.65%) had SaO2 below 88%, while the unchanged model predicted 21.10% mean risk. Calibration-in-the-large was -2.114 and calibration slope was 0.119. Ranking was weak (PR-AUC 0.074; ROC-AUC 0.568). At the locked 5% threshold, sensitivity was 71.4%, specificity 32.8%, PPV 6.0%, and NPV 95.0%.\n\nThis is a failed raw-transfer validation for probability calibration and only weak transportability for discrimination. It does not invalidate the OpenOx internal analysis, but it prevents an unchanged clinical probability claim in ICU BOLD data.\n"""),
    markdown("""## Context & Methods\n\n### Key assumptions and chronology\n\n- D028 froze the compact ridge model before BOLD outcomes were examined.\n- D030 freezes the BOLD feature, unit, coding, timing, and missingness crosswalk before loading SaO2.\n- Eligibility is SpO2 92-96% inclusive; the validation outcome is SaO2 below 88%.\n- The frozen inputs are SpO2, age, heart rate, respiratory rate, and assigned sex.\n- BOLD SpO2 is the distributed selected value 0-5 minutes before ABG. Available heart and respiratory rates are left-sided by up to 240 minutes.\n- Primary estimates are pair weighted. Participant-balanced estimates are sensitivity analyses.\n- Confidence intervals use 1,000 participant-cluster bootstrap samples.\n- Calibration/discrimination estimates are support-gated. Fixed thresholds remain 2%, 5%, and 10%.\n- Race/ethnicity is audit-only and is never interpreted as measured pigmentation.\n- Recalibration is intentionally not mixed into raw-transfer validation.\n\n### Key domain shifts\n\nBOLD is a retrospective ICU-EHR cohort, OpenOx development used controlled desaturation, BOLD permits a longer SpO2-ABG timing gap, time-varying vitals may be up to four hours old, and BOLD admission age is top-coded at 90.\n"""),
    markdown("## Data\n\n### 1. Re-run the sealed crosswalk and unchanged scoring pipeline"),
    code("""from pathlib import Path\nimport json\nimport pandas as pd\n\nfrom bold_external_validation import OUTPUT_DIR, run_validation\n\nsummary = run_validation()\nprint(json.dumps(summary, indent=2))\n"""),
    markdown("### 2. Verify cohort and source support"),
    code("""support = pd.read_csv(OUTPUT_DIR / 'bold_external_support.csv')\nprint(support.loc[support['dimension'].isin(['overall', 'source_db'])].to_string(index=False))\n"""),
    markdown("""## Results\n\n### 3. Overall raw-transfer performance\n\nCalibration-in-the-large is an intercept update with the frozen model logit as an offset. A value near zero is ideal. Calibration slope near one is ideal. PR-AUC is average precision, matching the internal OpenOx implementation.\n"""),
    code("""performance = pd.read_csv(OUTPUT_DIR / 'bold_external_performance.csv')\ncolumns = ['weighting', 'observed_rate', 'mean_predicted', 'calibration_gap',\n           'calibration_intercept', 'calibration_slope', 'brier', 'log_loss',\n           'pr_auc', 'roc_auc', 'sensitivity_5pct', 'specificity_5pct',\n           'ppv_5pct', 'npv_5pct']\noverall = performance.loc[performance['dimension'].eq('overall'), columns]\nprint(overall.to_string(index=False))\n"""),
    markdown("### 4. Participant-cluster uncertainty"),
    code("""bootstrap = pd.read_csv(OUTPUT_DIR / 'bold_external_bootstrap_intervals.csv')\nheadline = ['observed_rate', 'mean_predicted', 'calibration_gap', 'calibration_intercept',\n            'calibration_slope', 'brier', 'log_loss', 'pr_auc', 'roc_auc',\n            'sensitivity_5pct', 'specificity_5pct', 'ppv_5pct', 'npv_5pct']\nprint(bootstrap.loc[(bootstrap.dimension == 'overall') & bootstrap.metric.isin(headline),\n                    ['metric', 'lower_95', 'upper_95', 'valid_bootstrap_replicates']].to_string(index=False))\n"""),
    markdown("### 5. Source-database heterogeneity"),
    code("""source = performance.loc[(performance.dimension == 'source_db') & (performance.weighting == 'pair'),\n    ['group', 'observed_rate', 'mean_predicted', 'calibration_intercept',\n     'calibration_slope', 'brier', 'log_loss', 'pr_auc', 'roc_auc',\n     'sensitivity_5pct', 'specificity_5pct', 'ppv_5pct', 'npv_5pct']]\nprint(source.to_string(index=False))\n"""),
    markdown("""MIMIC-III has only six eligible events and fails the threshold-reporting gate. MIMIC-IV has ten events, so threshold estimates are descriptive but calibration slope and discrimination are withheld. Overall results are dominated by eICU, which contributes 655 of 671 events.\n"""),
    markdown("### 6. Decision-curve results at prespecified thresholds"),
    code("""decision = pd.read_csv(OUTPUT_DIR / 'bold_external_decision_curve.csv')\nprint(decision.loc[(decision.dimension == 'overall') & decision.threshold.isin([0.02, 0.05, 0.10])].to_string(index=False))\nprint('\\nBootstrap intervals for model net benefit and model-minus-flag-all:')\nprint(bootstrap.loc[(bootstrap.dimension == 'overall') & bootstrap.metric.isin([\n    'net_benefit_2pct', 'net_benefit_minus_all_2pct',\n    'net_benefit_5pct', 'net_benefit_minus_all_5pct',\n    'net_benefit_10pct', 'net_benefit_minus_all_10pct']),\n    ['metric', 'lower_95', 'upper_95']].to_string(index=False))\n"""),
    markdown("""At 2%, flag-all has greater net benefit. At 5%, the model is slightly positive but is not bootstrap-distinguishable from flag-all. At 10%, the model is worse than flag-none despite outperforming flag-all. The unchanged model therefore has no robust utility advantage across the full locked threshold range.\n"""),
    markdown("### 7. Race/ethnicity audit - not pigmentation"),
    code("""race = performance.loc[(performance.dimension == 'race_ethnicity') & (performance.weighting == 'pair'),\n    ['group', 'observed_rate', 'mean_predicted', 'calibration_gap',\n     'calibration_slope', 'pr_auc', 'roc_auc', 'sensitivity_5pct', 'specificity_5pct']]\nprint(race.to_string(index=False))\n"""),
    markdown("""The support-gated Black category shows higher observed risk and worse ranking than White, but these harmonized EHR social categories are not skin-pigmentation measurements. They cannot resolve the OpenOx MST 8-10 finding and should not be used to modify the frozen model from this validation.\n"""),
    markdown("### 8. Feature and workflow shift"),
    code("""shift = pd.read_csv(OUTPUT_DIR / 'bold_external_feature_shift.csv')\nprint(shift.to_string(index=False))\n"""),
    markdown("""Age is the largest transported feature shift: eligible BOLD participants average 65.1 years versus a 27.8-year OpenOx training center. Because age has a positive frozen coefficient, this shift is a major, prespecified explanation for average overprediction. This is an interpretation of the frozen coefficients and distributions, not authorization to revise the model.\n"""),
    markdown("## Takeaways\n\n1. **Raw probability transport fails.** Mean risk is overpredicted by 15.45 percentage points, calibration intercept is far below zero, and calibration slope is near zero.\n2. **Ranking transport is weak.** ROC-AUC is 0.568 (95% cluster-bootstrap interval 0.545-0.593); PR-AUC is only modestly above the 5.65% event prevalence.\n3. **The 5% flag is not selective.** Sensitivity is preserved at 71.4%, but specificity is 32.8% and PPV is 6.0%.\n4. **Source heterogeneity limits interpretation.** eICU supplies nearly all events; MIMIC-III and MIMIC-IV cannot support full source-specific validation.\n5. **No unchanged clinical probability claim is supported.** Any intercept or slope recalibration would be a separate model update and must not be relabeled external validation.\n6. **D029 remains binding.** BOLD cannot adjudicate the OpenOx device 60 or MST 8-10 calibration deficits.\n"""),
    markdown("## QA"),
    code("""qa = pd.read_csv(OUTPUT_DIR / 'bold_external_qa.csv')\nindependent_qa_path = OUTPUT_DIR / 'bold_external_independent_qa.csv'\nindependent = pd.read_csv(independent_qa_path) if independent_qa_path.exists() else pd.DataFrame()\nprint(qa.to_string(index=False))\nif not independent.empty:\n    print('\\nIndependent QA:')\n    print(independent.to_string(index=False))\nassert qa['pass'].all()\nif not independent.empty:\n    assert independent['pass'].all()\n"""),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}
OUT.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
print(OUT)
