# OpenOx Project

OpenOx Project is a completed, code-only investigation of when pulse oximetry can mislead—and whether a risk model survives contact with a new clinical cohort. It covers device accuracy, occult hypoxemia, measured skin pigmentation, perfusion, and cross-cohort transportability. V1 was formally closed on 2026-08-12 at decision D036.

> **Final status:** Research-complete; not clinically validated; eligible for independent external evaluation; closed to further retrospective tuning.

## What the study found

Device error varied and was larger at lower arterial oxygen levels. Hidden low oxygen occurred despite apparently reassuring readings, and some device-specific results associated greater overestimation with darker measured skin pigmentation or lower perfusion. The richer risk model performed better internally but failed unchanged transport to BOLD; a simpler SpO2-only score transferred better, although imperfectly.

No model in this repository is authorized for clinical use. A third untouched cohort is required before making a transportability claim about the BOLD-updated score.

Read the [results at a glance](docs/RESULTS.md) for the full plain-language summary. Use the [final status](docs/FINAL_STATUS.md) for the governing claim boundaries and the [project hub](docs/PROJECT_HUB.md) only when the detailed decision history is needed.

## A waveform study that stopped at the timing stage

A separate [waveform timing study](docs/WAVEFORM_STUDY.md) asked whether raw pulse signals from an investigational recorder could be matched reliably to the correct oxygen measurements. Only one of 18 targeted records passed the frozen timing rules and masked visual review, so the study stopped before linking outcomes or building a model. This was a stopped study, not a negative model result.

## Public-release boundary

This repository contains reviewed source code, output-cleared notebooks, configuration templates, and aggregate decision documentation. It intentionally excludes:

- PhysioNet source records and extracts;
- participant, patient, encounter, or institutional identifiers;
- processed cohorts, row-level predictions, and copied timestamps;
- fitted model objects and model-derived row-level artifacts;
- notebook outputs, figures generated from restricted rows, and rendered reports.

The analyses require separately authorized access to OpenOximetry v1.1.1, BOLD v1.0, and ENCoDE v1.0.0. Access is not conveyed by this repository. Read [DATA_USE.md](DATA_USE.md) before downloading data or running code.

## Choose your path

### Understand the completed project without data

1. Read the [results at a glance](docs/RESULTS.md), then the [final status](docs/FINAL_STATUS.md).
2. Follow the stage table in the [repository guide](docs/REPOSITORY_GUIDE.md).
3. Consult the frozen [roadmap](docs/ROADMAP.md) and [project hub](docs/PROJECT_HUB.md) for prespecification, decisions, negative findings, and limitations.

### Reproduce analyses with authorized data access

1. Complete the applicable PhysioNet requirements in [DATA_USE.md](DATA_USE.md).
2. Create the environment and local configuration described in the [reproducibility guide](docs/REPRODUCIBILITY.md).
3. Launch Jupyter from the repository root and run notebooks in chronological order from `notebooks/`.
4. Use `python -m scripts.build.<builder_name>` to reconstruct a notebook or `python -m scripts.qa.<check_name>` for an available separate scripted check.

Generated `data/`, `outputs/`, validation directories, and model files must remain local and uncommitted.

### Contribute safely

OpenOx V1 is closed to retrospective scientific expansion. Read [CONTRIBUTING.md](CONTRIBUTING.md), run `python scripts/release_check.py`, and inspect the complete staged diff. Never rely on `.gitignore` as the only confidentiality control.

## Repository map

| Path | Purpose |
|---|---|
| `notebooks/` | Output-cleared chronological V1 notebooks (`01b` through `23`) |
| `scripts/analysis/` | Substantive analysis runners against authorized local inputs |
| `scripts/build/` | Deterministic notebook construction scripts |
| `scripts/qa/` | Independent checks for selected late-stage analyses |
| `scripts/release_check.py` | Fail-closed public-tree scanner and manifest generator |
| `src/` | Shared configuration and canonical repository paths |
| `docs/` | Results, final status, project record, navigation, and reproduction guidance |
| `environment.lock.yml` | Exact recorded package snapshots for the frozen study stages |
| `PUBLIC_RELEASE_MANIFEST.csv` | SHA-256 manifest of the reviewed public tree |

The root is intentionally limited to project entry points, governance, environment, license, and release metadata.

## License and clinical disclaimer

Original repository code and documentation are available under the [MIT License](LICENSE). MIT does **not** license or redistribute PhysioNet datasets, third-party records, or restricted derivatives; see the [license-scope notice](docs/LICENSE_SCOPE.md).

This repository is research software. It does not provide medical advice, replace arterial blood-gas testing, establish clinical utility, or authorize clinical deployment.

## Citation

Dataset citations and current PhysioNet requirements are listed in [DATA_USE.md](DATA_USE.md). Repository citation metadata is provided in [CITATION.cff](CITATION.cff); update it when a manuscript DOI or archival release DOI becomes available.
