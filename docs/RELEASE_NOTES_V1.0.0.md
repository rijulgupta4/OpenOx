# OpenOx V1.0.0 release notes

OpenOx V1.0.0 is the final public, code-only record of the completed pulse-oximetry reliability and transportability study.

## Included

- output-cleared notebooks covering cohort construction, device accuracy, hidden low oxygen, measured skin pigmentation, perfusion/context, prediction, and external evaluation;
- substantive analysis code, notebook builders, and selected second-code-path QA checks;
- a plain-language aggregate results summary and two public-safe aggregate visuals;
- the final evidence hierarchy, decision history, workflow map, glossary, and reproduction guidance;
- a documented stopped waveform timing study, including its prespecified aggregate timing criteria and stopping decision;
- recorded stage-specific software snapshots and a fail-closed public-release scanner.

## Final scientific status

The richer compact model improved on SpO2 alone during participant-grouped internal validation but failed when applied unchanged to BOLD. A simpler SpO2-only score transferred better, though imperfectly. Its BOLD-informed recalibration is model updating and still requires testing in a third untouched cohort.

The separate waveform study stopped before outcome linkage or modeling because only one of 18 targeted records passed both frozen automated timing rules and masked visual review.

## Boundaries

This release contains no PhysioNet source data, processed cohorts, row-level results, timestamps, fitted model objects, restricted figures, or restricted tables. It is research software and documentation, not a clinically validated device or model.

See [`DATA_USE.md`](../DATA_USE.md), [`FINAL_STATUS.md`](FINAL_STATUS.md), and [`LICENSE_SCOPE.md`](LICENSE_SCOPE.md) before reuse.
