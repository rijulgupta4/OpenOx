# Public release audit through D035

## Assessment

**Ready for a code-only public repository after the automated release checks pass.** The unrestricted publication boundary is source code, cleared notebooks, configuration templates, and aggregate decision documentation. Restricted data and row-level derivatives are excluded.

## Controls applied

- Included only analysis materials through D035; waveform/V2 files are excluded.
- Removed every notebook output and execution count from the release copies.
- Excluded all source and processed data, row-level predictions, model objects, figures, PDFs, Word files, and rendered report directories.
- Replaced personal absolute paths with repository-relative locations.
- Added deny-by-default patterns for common clinical-data and model-artifact formats.
- Preserved dataset citations, version identifiers, integrity hashes, and model-updating claim boundaries.

## Residual caveats

- Public release does not confirm that every future contributor is credentialed; each user is responsible for obtaining their own PhysioNet access.
- Aggregate decision documentation remains a scientific communication and should continue to avoid sparse cells or details that could identify people or institutions.
- A legal or institutional determination may impose requirements beyond this technical audit.

## Release blockers

- GitHub CLI must be installed and authenticated before the reviewed tree can be committed and pushed under the repository publishing workflow.
- The complete staged diff must be checked again immediately before push.
