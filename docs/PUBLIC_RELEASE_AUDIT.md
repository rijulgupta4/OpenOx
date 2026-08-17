# Public release audit through D036 and V1.0.0 preparation

## Assessment

**Approved as a code-only, aggregate-documentation repository after the automated release check passes.** V1 is closed. The public boundary includes reviewed code, output-cleared notebooks, configuration templates, aggregate decision documentation, and repository governance files. It excludes source data, row-level derivatives, model objects, and rendered artifacts.

## Controls applied

- Updated entry-point language from the D035 interim state to the D036 final closeout perspective.
- Preserved the unfavorable BOLD raw-transfer result and labeled BOLD-fitted recalibration as model updating, not independent external validation.
- Recorded the waveform study as closed; no waveform analysis is included or resumed.
- Added a public explanation containing narrative context, aggregate timing-review findings, and the frozen matching thresholds only. It includes no waveform files, headers, filenames, timestamps, participant-level matches, restricted-data figures or tables, or derived patient-level material.
- Removed notebook outputs/execution counts from release copies and reject embedded notebook attachments.
- Excluded source/processed data, row-level predictions, copied timestamps, model objects, restricted-data figures, PDFs, office documents, archives, and validation output directories.
- Allowlisted two hand-authored SVGs containing aggregate public values only. The release check rejects any other SVG and rejects embedded or externally linked SVG content.
- Replaced personal paths with repository-relative paths.
- Added deny-by-default patterns for common clinical-data, array, database, archive, media, and model formats.
- Added dataset-specific PhysioNet access classes, version citations, confidentiality instructions, and license separation.
- Added an outside-user repository guide, reproducibility guide, contribution policy, security policy, citation metadata, and license-scope notice.
- Preserved exact stage-specific software versions where the frozen execution record contained them; unrecorded versions were not guessed.

## License assessment

The standard MIT license remains appropriate for the author's original code and documentation and includes broad permission plus warranty/liability disclaimers. [`LICENSE_SCOPE.md`](LICENSE_SCOPE.md) clarifies that MIT does not license PhysioNet data, third-party records, or restricted derivatives and does not represent clinical authorization. This is a scope clarification, not a replacement for legal counsel.

## Prospective outside-user assessment

The earlier root-level chronology made the project difficult to scan: notebooks, builders, analysis runners, QA checks, and governance documents appeared as one undifferentiated file list. The final structure now separates these roles while preserving the notebook sequence and Git rename history:

- `notebooks/` is a flat chronological reading and execution path;
- `scripts/build/`, `scripts/analysis/`, and `scripts/qa/` expose distinct code responsibilities;
- `docs/` contains the final record and task-oriented guidance;
- the root contains only entry points, governance, environment, licensing, and release metadata.

The README now gives separate routes for readers, authorized reproducers, and contributors. The repository guide explains chronology, naming gaps, code-to-notebook mapping, and module invocation. Canonical path definitions and package-qualified imports reduce dependence on the former root layout. The release checker rejects future root-level Python files or notebooks, preventing a return to the previous navigation problem.

Known friction remains by design: a complete rerun requires separately authorized data and locally generated restricted intermediates that cannot be distributed. This limitation is stated before execution instructions, and the repository does not imply one-command reproduction from a public clone.

## Required pre-push gate

Run `python scripts/release_check.py`, regenerate the reviewed manifest with `python scripts/release_check.py --write-manifest`, rerun the check, then inspect the complete staged diff before publishing.
