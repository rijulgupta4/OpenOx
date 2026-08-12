# Public release audit through D036

## Assessment

**Approved as a code-only, aggregate-documentation repository after the automated release check passes.** V1 is closed. The public boundary includes reviewed code, output-cleared notebooks, configuration templates, aggregate decision documentation, and repository governance files. It excludes source data, row-level derivatives, model objects, and rendered artifacts.

## Controls applied

- Updated entry-point language from the D035 interim state to the D036 final closeout perspective.
- Preserved the unfavorable BOLD raw-transfer result and labeled BOLD-fitted recalibration as model updating, not independent external validation.
- Recorded V2 as closed and excluded; no waveform analysis is included or resumed.
- Removed notebook outputs/execution counts from release copies and reject embedded notebook attachments.
- Excluded source/processed data, row-level predictions, copied timestamps, model objects, figures, PDFs, office documents, archives, and validation output directories.
- Replaced personal paths with repository-relative paths.
- Added deny-by-default patterns for common clinical-data, array, database, archive, media, and model formats.
- Added dataset-specific PhysioNet access classes, version citations, confidentiality instructions, and license separation.
- Added an outside-user repository guide, reproducibility guide, contribution policy, security policy, citation metadata, and license-scope notice.

## License assessment

The standard MIT license remains appropriate for the author's original code and documentation and includes broad permission plus warranty/liability disclaimers. `LICENSE_SCOPE.md` now makes clear that MIT does not license PhysioNet data, third-party records, or restricted derivatives and does not represent clinical authorization. This is a scope clarification, not a replacement for legal counsel.

## Prospective outside-user assessment

The root chronology is intentionally retained because file names and builders encode the frozen workflow. Moving dozens of files would add reproducibility risk without improving the evidence. Navigation is instead reorganized through the README and `docs/REPOSITORY_GUIDE.md`, which provide separate paths for readers, authorized reproducers, and contributors.

Known friction remains: a complete rerun requires separately authorized data and locally generated restricted intermediates that cannot be distributed. The repository states this early and does not imply one-command reproduction from a public clone.

## Required pre-push gate

Run `python release_check.py`, regenerate the reviewed manifest with `python release_check.py --write-manifest`, rerun the check, then inspect `git diff --cached --stat` and `git diff --cached` before publishing.
