# Data access, confidentiality, and citation

## Code-only public release

This repository does not distribute source data or row-level derivatives. Do not open a pull request containing PhysioNet files, processed cohorts, row-level predictions, participant/patient/encounter identifiers, timestamps copied from source records, images, waveforms, fitted model objects derived from restricted rows, or notebook outputs produced from restricted data.

## PhysioNet requirements

The V1 analyses use three restricted PhysioNet resources:

1. OpenOximetry Repository v1.1.1: https://physionet.org/content/openox-repo/1.1.1/
2. BOLD v1.0: https://physionet.org/content/blood-gas-oximetry/1.0/
3. ENCoDE v1.0.0: https://physionet.org/content/encode-skin-color/1.0.0/

Users must obtain their own authorization from PhysioNet. Access may require credentialing, current human-subjects/HIPAA training, and acceptance of the project-specific license and data-use agreement.

The applicable restricted-data terms prohibit re-identification, disclosure of individual or institutional identity, sharing access with others, and insecure handling. They permit and expect associated research code to be contributed to an open repository. Publishing this code does not transfer or sublicense access to the underlying data.

## Required publication citations

Use the citation shown on each PhysioNet project page for the exact dataset version used. BOLD v1.0 should be cited as Matos et al. (2023), DOI `10.13026/phvt-3277`; ENCoDE v1.0.0 as Hao et al. (2024), DOI `10.13026/mcgk-1s42`. Also include the current standard PhysioNet citation requested on PhysioNet's About page.

## Safe contribution checklist

Before every public push:

- confirm only reviewed code, cleared notebooks, and documentation are staged;
- confirm no notebook contains cell outputs or execution counts;
- scan for secrets, personal local paths, and restricted filenames or records;
- reject row-level `.csv`, `.csv.gz`, Parquet, model, image, waveform, PDF, and document artifacts;
- inspect the complete staged diff rather than relying on `.gitignore` alone.

Questions about the interpretation of a PhysioNet agreement should be directed to PhysioNet or qualified institutional/legal counsel. This repository's release audit is a technical confidentiality control, not legal advice.
