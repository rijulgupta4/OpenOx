# Results at a glance

OpenOx V1 asked whether pulse-oximeter error varies across devices, pigmentation, and physiologic context, and whether a compact occult-hypoxemia risk model transfers to new cohorts. The study is complete and frozen. These are aggregate values already recorded in the final project documentation; no row-level or newly derived restricted-data results are published here.

## Bottom line

The richer compact model showed encouraging participant-grouped internal performance in OpenOx but failed unchanged probability transport to BOLD. A simpler, pre-existing SpO2-only score transferred better, although imperfectly. Logistic recalibration improved that score in BOLD, but the BOLD outcomes were used to fit the update, so the result is model-updating evidence rather than independent external validation. ENCoDE supported only partial high-saturation pigmentation replication and could not test the risk model because its eligible denominator had zero occult-hypoxemia events.

## Prediction evidence

| Evaluation | Population | Brier | Log loss | PR-AUC | ROC-AUC | Interpretation |
|---|---:|---:|---:|---:|---:|---|
| OpenOx compact model, median internal repeat | OpenOx, SpO2 92–96% | 0.03868 | 0.15171 | 0.17411 | 0.80104 | Better than the internal SpO2-only comparator, with calibration caution. |
| OpenOx SpO2-only comparator, median internal repeat | OpenOx, SpO2 92–96% | 0.03953 | 0.16112 | 0.10547 | 0.73302 | Required simple comparator. |
| Frozen compact model, unchanged BOLD transfer | 11,880 pairs from 11,441 patients | — | — | 0.0735 | 0.5680 | Failed unchanged transport; predicted 21.10% risk versus 5.65% observed. |
| Frozen SpO2-only score, unchanged BOLD diagnostic | Same BOLD denominator | 0.05226 | 0.21301 | 0.0998 | 0.6608 | Better than the compact model but still imperfect and exploratory. |
| BOLD-updated SpO2-only logistic recalibrator | 20 × 5-fold patient-level cross-validation | 0.05208 | 0.20762 | — | — | Selected bounded update; requires testing in a third untouched cohort. |

Blank metrics were not needed for the corresponding frozen decision and are not inferred here. Full calibration values and decision chronology are in [`ROADMAP.md`](ROADMAP.md) and decisions D028–D036 in [`PROJECT_HUB.md`](PROJECT_HUB.md).

## Pigmentation and feasibility evidence

- The OpenOx core used directly measured pigmentation rather than race as a substitute.
- ENCoDE reconstructed to 615 protocol-conforming pairs from 127 patients, while the publication reported 521 pairs from 128 patients; no post hoc 521-row subset was selected.
- Only three ENCoDE pairs were in the SaO2 70–85% interval, so lower-saturation pigmentation components were unsupported.
- In the higher-saturation interval, the maximum adjusted Monk Skin Tone contrast was 0.760 percentage points with a simultaneous 95% upper bound of 1.527 against a 1.5-point margin. This was directionally concordant but inconclusive.
- ENCoDE's locked SpO2 92–96% denominator contained 157 pairs from 71 patients and zero occult-hypoxemia events, so the risk model was not scored.

## What may be claimed

- The compact model improved on SpO2 alone in grouped internal validation.
- Its unchanged BOLD probability transport failed.
- The frozen SpO2-only score was comparatively more portable in BOLD, but remained exploratory.
- BOLD logistic recalibration was model updating, not independent external validation.
- ENCoDE offered partial mechanistic evidence and a failed risk-model feasibility gate.

## What may not be claimed

- Clinical validation, clinical utility, or deployment readiness.
- Successful external validation of the compact model or the BOLD-updated score.
- Equivalence of race/ethnicity and measured skin pigmentation.
- Clinical prevalence estimates from the controlled-desaturation OpenOx cohort.
- A completed independent external review merely because separate QA scripts reproduce selected calculations.

See [`FINAL_STATUS.md`](FINAL_STATUS.md) for the governing evidence hierarchy and [`DATA_USE.md`](../DATA_USE.md) for the public-release boundary.
