# Reproducibility guide

## 1. Obtain authorized data

Complete the dataset-specific requirements in [`DATA_USE.md`](../DATA_USE.md). Do not ask another user to share files or credentials.

## 2. Create the environment

```powershell
conda env create -f environment.yml
conda activate openox
Copy-Item .env.example .env
```

Keep the deterministic thread settings from `environment.yml`. Edit `.env` only with local authorized paths; never commit it.

## 3. Place data locally

The default templates expect:

```text
data/external/openoximetry/
data/external/bold/
data/external/encode/
```

These directories are ignored. Some historical workflows use these repository-relative defaults directly, while `src/config.py` reads `OPENOX_DATA_DIR`. Run all commands from the repository root.

## 4. Follow the frozen chronology

Use the [repository guide](REPOSITORY_GUIDE.md) for stage order. Launch Jupyter from the repository root so notebook-relative imports and paths resolve consistently:

```powershell
jupyter lab
```

The notebooks are output-cleared public records. To reconstruct a notebook source, run its builder as a module; for example:

```powershell
python -m scripts.build.build_20_bold_external_validation
```

Selected late-stage workflows have independent checks under `scripts/qa/`, also run as modules. Substantive external-cohort runners are under `scripts/analysis/` and should likewise be invoked with `python -m scripts.analysis.<runner_name>`. Do not run a later stage until its frozen local inputs exist and any embedded hash checks pass.

The repository intentionally does not promise a one-command public rerun: distributing the required source data, processed cohorts, row-level predictions, or fitted objects would violate the public-release boundary. Reproducibility means an independently authorized user can inspect the full code path and rebuild locally under the same frozen rules.

## 5. Validate the public tree

```powershell
python scripts/release_check.py
```

Before a release maintainer updates the public manifest:

```powershell
python scripts/release_check.py --write-manifest
python scripts/release_check.py
```

A successful public-release scan is a technical confidentiality and packaging check. It is not scientific validation or proof that every environment satisfies a data-use agreement.
