# OpenOx Project

OpenOx Project is a completed, code-only investigation of when pulse oximetry can mislead—and whether a risk model survives contact with a new clinical cohort. It covers device accuracy, occult hypoxemia, measured skin pigmentation, perfusion, and cross-cohort transportability. V1 was formally closed on 2026-08-12 at decision D036.

> **Final status:** Research-complete; not clinically validated; eligible for independent external evaluation; closed to further retrospective tuning.

## What the study found

The enriched D028 model showed useful participant-grouped internal performance, but it did not transport cleanly to BOLD. A simpler pre-existing SpO2-only score transferred better but remained imperfect. Logistic recalibration improved its probability performance in BOLD, but because BOLD outcomes were used to select and fit the recalibrator, this is **model-updating evidence, not independent external validation**. ENCoDE supported only partial mechanistic replication and contained no events in the eligible risk-model denominator.

No model in this repository is authorized for clinical use. A third untouched cohort is required before making a transportability claim about the BOLD-updated score.

Start with the [results at a glance](docs/RESULTS.md), then use the [final status](docs/FINAL_STATUS.md) for the evidence hierarchy and claim boundaries. The [workflow map](docs/WORKFLOW_MAP.md) connects questions to notebooks and scripts, the [glossary](docs/GLOSSARY.md) defines study terminology, and the [project hub](docs/PROJECT_HUB.md) preserves the full decision record.

## Study at a glance

| Question | Evidence | Final interpretation |
|---|---|---|
| Did the richer compact model work internally? | Participant-grouped OpenOx validation | It improved ranking and probability loss over SpO2 alone, with calibration caution. |
| Did it transfer unchanged? | Prespecified raw transfer to BOLD | No. It substantially overpredicted risk and discriminated poorly. |
| Was a simpler score more portable? | Frozen OpenOx SpO2-only score applied to BOLD | Yes, comparatively, but it remained imperfect and exploratory. |
| Did recalibration solve transportability? | BOLD outcome-informed recalibration | It improved BOLD probability performance, but it is model updating—not independent validation. |
| Did ENCoDE validate the risk model? | ENCoDE feasibility and pigmentation replication | No risk validation was possible because the eligible denominator had zero events; pigmentation evidence was partial and inconclusive. |

See [RESULTS.md](docs/RESULTS.md) for aggregate metrics and limitations. These summaries reproduce values already documented in the frozen decision record; no restricted rows or newly derived results are included.

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

1. Read the [final status](docs/FINAL_STATUS.md).
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
| `docs/` | Final status, project record, navigation, and reproduction guidance |
| `PUBLIC_RELEASE_MANIFEST.csv` | SHA-256 manifest of the reviewed public tree |

The root is intentionally limited to project entry points, governance, environment, license, and release metadata.

## License and clinical disclaimer

Original repository code and documentation are available under the [MIT License](LICENSE). MIT does **not** license or redistribute PhysioNet datasets, third-party records, or restricted derivatives; see the [license-scope notice](docs/LICENSE_SCOPE.md).

This repository is research software. It does not provide medical advice, replace arterial blood-gas testing, establish clinical utility, or authorize clinical deployment.

## Citation

Dataset citations and current PhysioNet requirements are listed in [DATA_USE.md](DATA_USE.md). Repository citation metadata is provided in [CITATION.cff](CITATION.cff); update it when a manuscript DOI or archival release DOI becomes available.
