# Repository guide

OpenOx is a frozen chronological research record organized so an outside reader can distinguish study evidence, notebook generation, substantive analysis, and QA without searching the repository root.

## Reading order

1. [`README.md`](../README.md) - final conclusion and public-release boundary.
2. [`RESULTS.md`](RESULTS.md) - concise aggregate findings and limitations.
3. [`GLOSSARY.md`](GLOSSARY.md) - clinical and modeling terminology.
4. [`WORKFLOW_MAP.md`](WORKFLOW_MAP.md) - questions, evidence stages, notebooks, and code paths.
5. [`FINAL_STATUS.md`](FINAL_STATUS.md) - evidence hierarchy and prohibited interpretations.
6. [`DATA_USE.md`](../DATA_USE.md) - access and confidentiality requirements before touching data.
7. [`ROADMAP.md`](ROADMAP.md) - frozen prespecification and project phases.
8. [`PROJECT_HUB.md`](PROJECT_HUB.md) - detailed decisions D001-D036.
9. [`WAVEFORM_STUDY.md`](WAVEFORM_STUDY.md) - a separate stopped study explaining why the raw pulse recordings could not be matched reliably to enough oxygen measurements.
10. [`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) - environment, execution, and release checks.

## Analysis chronology

All reviewed notebooks are flat within `notebooks/`; their numeric prefixes are the execution and reading order.

| Stage | Notebooks | Purpose |
|---|---|---|
| Pairing and feasibility | `01b`-`04` | Pair construction, timing sensitivity, endpoints, device harmonization, repeated measures |
| Prespecification | `05`-`06`, `07b` | Pigmentation/context locks and workflow audit |
| Core analyses | `07`, `07c`, `08`-`10` | Device, occult-hypoxemia, pigmentation, and perfusion/context analyses |
| Prediction lock and internal validation | `11`, `11b`, `12`-`19` | Target, grouped resampling, compact model, safeguards, subgroup/enrichment tests, final lock |
| External evidence | `20`-`23` | BOLD raw transfer, ENCoDE partial replication, SpO2-only diagnostic, bounded BOLD updating |

Notebook 17 was generated during development but is not part of the reviewed public notebook set. Its aggregate decision record remains in the project hub; restricted outputs remain private.

The public notebook sequence covers the completed V1 study. The later waveform timing work is summarized separately and is not presented as another stage of the V1 modeling pipeline.

## How code maps to notebooks

- `scripts/build/` contains notebook constructors. From the repository root, run one as a module, for example: `python -m scripts.build.build_20_bold_external_validation`.
- `scripts/analysis/` contains calculations called by selected notebooks, including the BOLD and ENCoDE workflows.
- `scripts/qa/` contains separate scripted checks for selected late-stage analyses. They reproduce calculations through a second code path, but are not independent review by an external team. Run them as modules so package imports resolve consistently.
- `src/config.py` validates local OpenOximetry paths and defines output directories.
- `src/paths.py` is the canonical map of public repository directories.
- `scripts/release_check.py` scans the public tree, enforces the folder boundary, clears confidentiality gates, and validates the release manifest.

Builders write public notebook sources into `notebooks/`. Scientific execution writes restricted intermediates to ignored local directories; those artifacts are not part of the public repository.

## What cannot be public

The public tree is not a data bundle or a precomputed-results archive. Full execution requires separately authorized PhysioNet files and locally generated restricted intermediates. Expected hashes in scripts identify the analyzed releases; they do not grant access or permission to redistribute them.
