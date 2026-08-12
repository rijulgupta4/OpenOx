# Contributing

OpenOx V1 is closed. Contributions should improve reproducibility, documentation, compatibility, or correct verified implementation defects. New retrospective predictors, interactions, model families, thresholds, BOLD tuning, ENCoDE selection, or waveform development are out of scope.

## Before opening a pull request

1. Read `DATA_USE.md` and `docs/FINAL_STATUS.md`.
2. Work only with data you are independently authorized to access.
3. Never stage source data, row-level derivatives, identifiers, timestamps, model objects, notebook outputs, images, or rendered reports from restricted data.
4. Keep notebooks free of outputs, execution counts, and attachments.
5. Run `python release_check.py`.
6. Review the full diff and staged file list.

If a proposed change could alter a scientific result, document the defect and all dependent artifacts before implementation. An unfavorable result is not a defect and is not a reason to reopen optimization.

Do not use a public issue or pull request to report suspected identifying information; follow `SECURITY.md`.
