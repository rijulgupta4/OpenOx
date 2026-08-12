# OpenOx V1 final status

**Decision:** D036, 2026-08-12
**Status:** Research-complete; not clinically validated; eligible for independent external evaluation; closed to further retrospective tuning.

## Locked conclusion

Internal performance did not translate cleanly across cohorts. External recalibration improved the simpler SpO2-only model in BOLD, while richer predictor enrichment did not demonstrate reliable transportable benefit. Further independent validation is required before clinical use.

## Evidence roles

| Evidence | What it supports | What it does not support |
|---|---|---|
| OpenOx | Model development and participant-grouped internal validation | Clinical prevalence, broad clinical generalizability, or deployment |
| BOLD raw transfer | Independent stress test showing failed unchanged D028 probability transport | A successful external-validation claim |
| BOLD SpO2-only comparison | Post-failure diagnostic showing the simpler frozen score transferred better | Confirmatory rescue-model validation |
| BOLD logistic recalibration | Outcome-informed model updating with improved probability performance | Independent external validation or transportability |
| ENCoDE | Partial high-saturation pigmentation replication and feasibility limits | Risk-model validation; the eligible denominator had zero events |

## Reopening criteria

V1 may be reopened only for a verified implementation defect, a materially corrected source release, or a prespecified evaluation in a genuinely untouched cohort. OpenOx or BOLD may not be reused for additional retrospective feature, model-family, coefficient, or threshold optimization.

## Clinical boundary

No score is approved for patient care. The project does not replace arterial blood-gas measurement, establish clinical utility, or authorize deployment.
