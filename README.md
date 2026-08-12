# OpenOx

OpenOx is the code-only reproducibility repository for a completed research study of pulse-oximeter accuracy, occult hypoxemia, pigmentation, perfusion, and cross-cohort transportability. V1 was formally closed on 2026-08-12 at decision D036.

> **Final status:** Research-complete; not clinically validated; eligible for independent external evaluation; closed to further retrospective tuning.

## What the study found

The enriched D028 model showed useful participant-grouped internal performance, but it did not transport cleanly to BOLD. A simpler pre-existing SpO2-only score transferred better but remained imperfect. Logistic recalibration of that score improved probability performance in BOLD, but BOLD outcomes were used to select and fit the recalibrator. It is therefore **model-updating evidence, not independent external validation**. ENCoDE supported only partial mechanistic replication and contained no events in the eligible risk-model denominator.

No model in this repository is authorized for clinical use. A third untouched cohort is required before making a transportability claim about the BOLD-updated score.

For the concise evidence hierarchy and claim boundaries, start with [Final status](docs/FINAL_STATUS.md). For the full chronological record, see [OpenOx_Project_Hub.md](OpenOx_Project_Hub.md).

## Public-release boundary

This repository contains reviewed source code, output-cleared notebooks, configuration templates, and aggregate decision documentation. It intentionally excludes:

- PhysioNet source records and extracts;
- participant, patient, encounter, or institutional identifiers;
- processed cohorts, row-level predictions, and copied timestamps;
- fitted model objects and model-derived row-level artifacts;
- notebook outputs, figures generated from restricted rows, and rendered reports.

The analyses require separately authorized access to OpenOximetry v1.1.1, BOLD v1.0, and ENCoDE v1.0.0. Access is not conveyed by this repository. Review [DATA_USE.md](DATA_USE.md) before downloading data or running code.

## Choose your path

### Understand the completed project without data

1. Read [Final status](docs/FINAL_STATUS.md).
2. Use [Repository guide](docs/REPOSITORY_GUIDE.md) to navigate the analysis chronology.
3. Consult [ROADMAP_updated.md](ROADMAP_updated.md) and [OpenOx_Project_Hub.md](OpenOx_Project_Hub.md) for prespecification, decisions, negative findings, and limitations.

### Reproduce analyses with your own authorized data access

1. Complete the applicable PhysioNet access requirements described in [DATA_USE.md](DATA_USE.md).
2. Follow [Reproducibility guide](docs/REPRODUCIBILITY.md).
3. Run notebooks from the repository root. Generated `data/`, `outputs/`, validation directories, and model files must remain local and uncommitted.

### Contribute safely

Read [CONTRIBUTING.md](CONTRIBUTING.md), run `python release_check.py`, and inspect the complete staged diff. Never rely on `.gitignore` as the only confidentiality control.

## Repository map

| Path | Purpose |
|---|---|
| `01b_...ipynb` through `23_...ipynb` | Output-cleared chronological V1 notebooks |
| `build_*.py` | Notebook construction and frozen workflow builders |
| `qa_*.py` | Independent checks for selected late-stage analyses |
| `src/` | Shared local configuration |
| `docs/` | Final status, navigation, and reproduction guidance |
| `OpenOx_Project_Hub.md` | Detailed decision and evidence history through D036 |
| `ROADMAP_updated.md` | Frozen project roadmap and scope boundaries |
| `DATA_USE.md` | Dataset-specific access, confidentiality, and citation rules |
| `PUBLIC_RELEASE_AUDIT.md` | Public-release safety assessment |
| `PUBLIC_RELEASE_MANIFEST.csv` | SHA-256 manifest of the reviewed public tree |

The root-level chronological layout is retained intentionally because builders and notebooks refer to those names. The repository guide provides a task-oriented view without breaking the frozen workflow.

## License and clinical disclaimer

Original repository code and documentation are available under the [MIT License](LICENSE). The MIT license does **not** license or redistribute PhysioNet datasets, third-party records, or restricted derivatives; see [LICENSE_SCOPE.md](LICENSE_SCOPE.md).

This repository is research software. It does not provide medical advice, replace arterial blood-gas testing, establish clinical utility, or authorize clinical deployment.

## Citation

Dataset citations and current PhysioNet requirements are listed in [DATA_USE.md](DATA_USE.md). Repository citation metadata is provided in [CITATION.cff](CITATION.cff); update it when a manuscript DOI or archival release DOI becomes available.
