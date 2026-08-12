# Data access, confidentiality, and citation

## Code-only public release

This repository does not distribute PhysioNet source data or row-level derivatives. Do not open a pull request containing source files, processed cohorts, row-level predictions, participant/patient/encounter or institutional identifiers, copied timestamps, images, waveforms, fitted model objects derived from restricted rows, or notebook outputs produced from restricted data.

Repository code is MIT-licensed. PhysioNet data remain governed by their own license and data-use agreement; repository licensing does not transfer, sublicense, or weaken those terms.

## Dataset-specific access requirements

Requirements below were verified against the cited PhysioNet version pages on 2026-08-12. Users must confirm the current terms on PhysioNet before access because requirements can change.

| Resource | Version used | Access class and requirements | Version citation |
|---|---|---|---|
| [OpenOximetry Repository](https://physionet.org/content/openox-repo/1.1.1/) | 1.1.1 | Restricted access: registered user plus project DUA; Restricted Health Data License/DUA 1.5.0 | Fong et al. (2025), doi:10.13026/be2e-cn29 |
| [BOLD](https://physionet.org/content/blood-gas-oximetry/1.0/) | 1.0 | Credentialed access: credentialing, CITI Data or Specimens Only Research training, and project DUA; Credentialed Health Data License/DUA 1.5.0 | Matos et al. (2023), doi:10.13026/phvt-3277 |
| [ENCoDE](https://physionet.org/content/encode-skin-color/1.0.0/) | 1.0.0 | Credentialed access: credentialing, CITI Data or Specimens Only Research training, and project DUA; Credentialed Health Data License/DUA 1.5.0 | Hao et al. (2024), doi:10.13026/mcgk-1s42 |

The applicable agreements prohibit attempted re-identification, disclosure of individual or institutional identity, sharing data access, and insecure handling. They require lawful scientific use and contribution of publication-associated code to an open research repository. Obligations concerning PhysioNet data continue even if access or an agreement is later terminated.

If a file appears to contain information that could permit identification, do not commit or discuss it publicly. Follow PhysioNet's agreement instructions, including reporting the specific location to `PHI-report@physionet.org`, and see [SECURITY.md](SECURITY.md).

## Publication citations

Use the citation displayed on each version-specific PhysioNet page. OpenOximetry also requests citation of its original *Scientific Data* publication (Fong et al., 2025, doi:10.1038/s41597-025-04870-8). BOLD requests citation of its parent MIMIC-III, MIMIC-IV, and eICU-CRD projects when used.

PhysioNet currently requests this standard citation:

> Pollard T, Moody BE, Lehman L, Gow B, Fernandes C, Xie C, Johnson A, Mark RG, Heldt T. PhysioNet as a global platform for biomedical research. *Nature Health*. 2026. doi:10.1038/s44360-026-00096-z.

Confirm the citation on the dataset page at submission time rather than relying only on this snapshot.

## Safe contribution checklist

Before every public push:

- stage only reviewed code and documentation;
- confirm notebooks contain no outputs, execution counts, or embedded attachments;
- scan for secrets, personal paths, restricted filenames, and local metadata;
- reject row-level CSV/TSV/JSONL, Parquet, database, array, model, image, waveform, archive, PDF, and office-document artifacts;
- run `python scripts/release_check.py`;
- inspect the complete staged diff and file list.

Questions about agreement interpretation belong with PhysioNet or qualified institutional/legal counsel. The repository audit is a technical confidentiality control, not legal advice.
