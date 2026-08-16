# OpenOx Project Roadmap

## Pulse-oximeter reliability across device, pigmentation, and physiologic context

**Updated:** 2026-08-16
**Current phase:** V1 formally closed at D036; research-complete and frozen

## Project purpose

OpenOx evaluates when pulse oximetry overestimates or underestimates arterial oxygen saturation in the OpenOximetry controlled-desaturation laboratory repository. Device performance, occult hypoxemia, directly measured skin pigmentation, and perfusion/physiologic context form the analytic core. Prediction remains a secondary risk-flagging extension and is not a replacement for arterial blood-gas measurement.

## Scope and interpretation

- Primary development data: OpenOximetry v1.1.1 controlled-desaturation studies.
- Primary error: `SpO2 - SaO2`, retaining direction as well as magnitude.
- Primary prediction target: `SaO2 < 88%` among readings with `SpO2 92-96%`.
- Controlled-desaturation event frequencies are laboratory phenotypes, not clinical prevalence estimates.
- Device codes remain opaque unless an authoritative crosswalk is obtained.
- Regulatory comparisons are methodological benchmarks, not regulatory validation.
- A separate waveform study was closed on 2026-08-11 after the timing review. The available information was not sufficient to match enough raw waveform sections reliably to individual SpO2 and reference SaO2 measurements. No waveform-based error model was developed. See [`WAVEFORM_STUDY.md`](WAVEFORM_STUDY.md).

## Progress overview

| Stage | Status | Main output |
|---|---|---|
| 0. Project setup | Complete | Reproducible folders, environment, configuration, and hub |
| 1. Data inputs and feasibility | Complete | Relational inventory, duplicate diagnosis, pairing feasibility |
| 2. Analysis-plan lock | Complete | Frozen endpoints, pairing, inference, pigmentation, and context rules |
| 3. Analytic cohort construction | Complete | QA-passed 28,693-pair cohort using the 180-second primary window |
| 4. Analytic core | Complete | Device, occult-hypoxemia, pigmentation, and perfusion/context analyses |
| 5. Secondary predictive modeling | Complete | D028 compact ridge frozen; OpenOx-only enrichment models rejected |
| 6. External transportability and validation | Complete | BOLD failed unchanged D028 probability transport; a post-validation SpO2-only diagnostic transported materially better but remained imperfect; ENCoDE provided partial high-saturation pigmentation replication and a zero-event risk gate |
| 7. Outputs and manuscript | Complete (authorized workspace) | D036 closeout and local reporting package; restricted-data-derived figures, tables, model artifacts, and rendered reports are excluded from this public repository |
| Waveform timing study | Closed | Some records appeared to line up, but the timing could not be matched reliably for enough records to support an analysis. The study stopped before waveform characteristics were tested against oxygen-measurement errors. |

## Frozen analytic foundation

The primary cohort contains 28,693 paired readings from 123 participants and 325 encounters. The 180-second pairing window is primary; 60 seconds is the strict sensitivity window and 300 seconds is the outer stress test. The four analytic pillars are complete:

1. Device-specific bias, precision, A_RMS, saturation-band behavior, and repeated-measures agreement.
2. Occult hypoxemia under the locked `SpO2 92-96% / SaO2 <88%` definition.
3. Forehead Monk Skin Tone and emitter-site ITA analyses with prespecified non-disparate-performance benchmarks.
4. Within-device perfusion-index and physiologic-context analyses.

## Phase 5 - Secondary predictive modeling

### Objective

Estimate the risk of occult hypoxemia among apparently reassuring SpO2 readings and test whether a compact bedside model improves on SpO2 alone.

### Locked model tiers

| Tier | Predictors | Role |
|---|---|---|
| Baseline | SpO2 | Required comparator |
| Primary transportable | SpO2, age, assigned sex, heart rate, respiratory rate | Primary internal model and external-validation candidate |
| Enriched A | Primary set plus device/probe identity | Exploratory OpenOx-only device-block incremental value |
| Enriched B | Primary set plus measured MST and emitter-site ITA | Exploratory OpenOx-only pigmentation feature-value analysis |
| Enriched C | Primary set plus within-device log2 perfusion index, warming, and finger diameter | Exploratory OpenOx-only context-block incremental value |

The primary model remains the compact transportable model. Enriched blocks are evaluated one at a time rather than accumulated into an unrestricted full model, and will not be promoted merely because they use more variables.

### Internal validation

- The development/evaluation population is restricted to SpO2 92-96%; outside-band rows are excluded rather than labeled negative.
- Fixed low-dimensional ridge logistic regression is primary; FLIC (or FLAC) is a prespecified rare-event/separation sensitivity. Firth penalization does not correct clustering.
- Fifty repeats of five-fold participant-grouped cross-validation stratify on participant event status, targeting 7-8 positive participants per validation fold.
- Fold predictions are pooled within each repeat; performance distributions are summarized across repeats rather than averaging unstable individual-fold metrics.
- Tuning, imputation, scaling, and encoding occur only within training folds.
- Calibration-in-the-large, calibration slope, Brier score, log loss, and PR-AUC are primary performance measures; ROC-AUC is secondary.
- Fixed 2%, 5%, and 10% thresholds prevent post hoc threshold selection.
- At least 500 participant-cluster bootstrap refits provide an optimism-correction cross-check; .632+ is secondary and used only for compatible losses with adequate out-of-bag event support.
- Pair-weighted fitting is primary, with inverse-participant-frequency weighting as sensitivity.
- Decision-curve net benefit from 2%-10% thresholds is secondary and compared with flag-all and flag-none using participant-bootstrap uncertainty.
- Performance must be reported overall and across prespecified device and pigmentation groups where support permits.

### Sparse-outcome claim boundary and robustness target

The occult-hypoxemia outcome remains the clinically motivated headline target, but its prediction evidence is explicitly pilot/exploratory because 261 positive readings arise from only 38 participants. A secondary robustness model uses `abs(SpO2-SaO2) >=3` within the same SpO2 92-96% population; it provides 778 positive readings from 76 participants. This richer target tests pipeline stability and does not validate the occult model by proxy.

The completed pigmentation/non-disparate-performance analysis and the future pigmentation feature-value analysis answer different questions. A null incremental prediction gain does not imply absence of device disparity, and a disparity finding does not automatically justify using pigmentation as a predictor.

### Frozen internal-validation allocation

The authoritative resampling object contains 50 repeated five-fold outer partitions and four inner folds inside every outer training set. Participants are stratified into occult-positive, absolute-error-≥3-positive without occult hypoxemia, and neither. All 250 outer validation sets are unique. Each contains 7-8 occult-positive participants and 14-16 absolute-error-≥3-positive participants. No outer-validation participant appears in the corresponding inner allocation.

The saved participant assignments—not merely the random seed—must be loaded by every modeling notebook. Positive-reading counts vary across folds because participants contribute unequal numbers of observations; performance will therefore be pooled across all outer folds within each repeat rather than interpreted fold by fold.

### Completed internal-validation checkpoint

The SpO2-only baseline and compact transportable ridge model were fitted under the frozen nested allocation with fold-contained imputation, encoding, scaling, and penalty selection. Across 50 pooled repeat-level evaluations, the compact model had median Brier score 0.03868, log loss 0.15171, PR-AUC 0.17411, and ROC-AUC 0.80104, compared with 0.03953, 0.16112, 0.10547, and 0.73302 for the baseline.

Compact-minus-baseline differences favored the compact model in 84% of repeats for Brier score, 94% for log loss, 100% for PR-AUC, and 98% for ROC-AUC. Calibration remains a caution: median predicted risk was 4.71% versus an observed 4.31%, and median calibration slope was 0.864. Subsequent small-sample, robustness, subgroup, enrichment, ablation, and utility checks were completed. D028 froze one full-development compact pipeline at `C=0.1`; all OpenOx-only enrichment blocks were rejected for final external use.

### Leakage exclusions

SaO2, PaO2, same-draw ABG results, SpO2 error, the derived outcome, future observations, and post-ABG treatments are prohibited predictors. Race and ethnicity are audit variables only and are never substitutes for measured pigmentation.

## Phase 6 - External transportability and validation

This phase began only after the OpenOx model specification and coefficients were frozen. External datasets were not pooled with OpenOx for model development.

### Common external-validation rules

1. Complete a dataset-specific feature, unit, coding, timing, missingness, and outcome audit before scoring.
2. Apply the frozen model unchanged for the primary raw-transfer evaluation.
3. Report discrimination and calibration separately.
4. Treat recalibration as model updating and report it separately from raw external performance.
5. Preserve each dataset's source population, pairing process, and case-mix limitations.
6. Do not interpret race/ethnicity as measured skin pigmentation.

### BOLD role

BOLD is the workhorse quantitative external-validation cohort. The hash-verified v1.0 release contains 49,093 pairs from 44,902 ICU patients across MIMIC-III, MIMIC-IV, and eICU-CRD; 11,880 pairs from 11,441 participants meet the locked SpO2 92-96% denominator. The unchanged D028 model overpredicted risk (21.10% predicted versus 5.65% observed), had calibration intercept -2.114, slope 0.119, PR-AUC 0.0735, and ROC-AUC 0.5680. It failed unchanged probability transport. Race/ethnicity remains an audit variable, not a pigmentation predictor.

After that failure was known, one post-validation diagnostic applied the pre-existing OpenOx SpO2-only baseline to the identical BOLD denominator. Its full-development `C=1.0` specification was selected solely from the frozen OpenOx tuning record and locked before BOLD outcome access within the run. It predicted 4.38% versus 5.65% observed, with calibration intercept +0.281, slope 0.611, Brier 0.05226, log loss 0.21301, PR-AUC 0.0998, and ROC-AUC 0.6608. Paired participant-bootstrap differences versus D028 favored the baseline for probability loss and ranking. This supports degradation from the combined added compact predictor block, but the baseline remains imperfect, exploratory, and not eligible for outcome-informed promotion.

A bounded post-validation recalibration study then compared intercept-only, logistic intercept-plus-slope, isotonic, and fixed spline calibration for both frozen scores using 20 repeats of five-fold patient-level cross-validation. Logistic recalibration of SpO2-only was selected (median log loss 0.20762; Brier 0.05208). Flexible SpO2-only methods were essentially tied, and the best recalibrated D028 candidate remained worse (spline log loss 0.21474; Brier 0.05304). This is BOLD-informed model updating, not new external validation. It closes the V1 recalibration bridge; a third untouched cohort is required before promotion. A future waveform study would require synchronized data collected or documented specifically for that purpose.

### ENCoDE role

The ENCoDE publication reports 521 SpO2-SaO2 pairs from 128 Duke acute-care patients and directly measured skin tone using Monk, Fitzpatrick, Von Luschan, colorimetry, and spectrophotometry across multiple body locations. The hash-verified v1.0.0 OMOP release reconstructs to 615 protocol-conforming pairs from 127 patients; saturation summaries closely reproduce the paper, but the exact 521-row REDCap analytic extract is not identifiable.

ENCoDE has two distinct, prespecified uses:

- **Measured-pigmentation replication:** test whether the direction and magnitude of the OpenOx pigmentation-error association are reproduced in acute care using harmonized Monk and objective colorimetric/spectrophotometric measures. This is a mechanistic transportability analysis, not validation of the full enriched prediction model.
- **Conditional risk-model validation:** evaluate the frozen primary transportable occult-hypoxemia model only if the accessible data can reconstruct the target and all required predictors and contain enough eligible events for interpretable estimates. If not, report the feasibility failure transparently and do not claim external model validation.

ENCoDE yielded only three pairs at SaO2 70-85%, so the lower-interval pigmentation components are unsupported. At >85-100%, adjusted SpO2-SaO2 bias rose from 1.231 points in MST 1-4 to 1.991 in MST 8-10; the maximum contrast was 0.760 with a simultaneous 95% upper bound of 1.527 against the 1.5-point margin, an inconclusive but directionally concordant result. Exact emitter-site ITA coverage was 69.4% and its interval crossed zero. The locked SpO2 92-96% denominator contained 157 pairs from 71 patients and zero occult events, so D028 was not scored.

### Dataset-role matrix

| Claim | OpenOx | BOLD | ENCoDE |
|---|---|---|---|
| Model development | Yes | No | No |
| Internal validation | Yes | No | No |
| Quantitative raw-transfer validation | Primary transportable model | Primary external cohort | Conditional on feature and event support |
| Calibration assessment | Cross-validated | Required | Conditional; likely imprecise |
| Recalibration | Not applicable | Separate secondary update | Normally not planned because of size |
| Measured-pigmentation replication | Primary mechanistic analysis | No measured skin tone | Primary external role |
| Race/ethnicity fairness audit | Descriptive only | Yes | Descriptive comparison only |
| Device/perfusion enriched-model validation | Internal only | Not supported | Not supported unless exact fields are documented |

## Phase 7 - Outputs and manuscript

This phase was completed within the authorized research workspace. The public repository preserves source code, output-cleared notebooks, aggregate decision documentation, and audit metadata. It does not publish the restricted-data-derived reporting package, figures, tables, fitted artifacts, or rendered reports. References below describe the reporting standard used for closeout, not a claim that every completed artifact is present publicly.

- Report model development and evaluation using TRIPOD+AI.
- Use PROBAST+AI as a structured risk-of-bias and applicability self-audit.
- Separate OpenOx internal performance, BOLD raw transfer, any BOLD recalibration, and ENCoDE mechanistic replication.
- Report case-mix shift and miscalibration as scientific findings rather than concealing them.
- Preserve the statement that the model flags risk and does not replace ABG testing.

## Post-closeout next steps

1. Do not refit, retune, reselect, or optimize thresholds on OpenOx or BOLD.
2. Evaluate the BOLD-fit SpO2-only logistic recalibrator only in a third untouched cohort under a new prespecified protocol.
3. Preserve the 615-versus-521 ENCoDE reconstruction discrepancy for author/data-curator clarification; do not select a post hoc 521-row subset.
4. Keep the waveform study closed under the current project. Revisiting the question would require synchronized waveform, pulse-oximeter, and reference oxygen measurements collected under a new study plan.

## Key limitations

- OpenOx development data come from controlled desaturation in a limited participant sample.
- Only 38 OpenOx participants experience the primary prediction event.
- BOLD and ENCoDE differ substantially in case mix, pairing, measurement workflow, and feature availability.
- ENCoDE is single-center, contains 128 patients, and has limited representation of the darkest skin tones.
- Measured pigmentation is not interchangeable across instruments or anatomical sites without a prespecified mapping.
- External miscalibration is expected under distribution shift and does not, by itself, negate preserved ranking performance.
