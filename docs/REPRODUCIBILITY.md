# Reproducibility guide

## 1. Obtain authorized data

Complete the dataset-specific requirements in [`DATA_USE.md`](../DATA_USE.md). Do not ask another user to share files or credentials.

## 2. Create the environment

```powershell
conda env create -f environment.yml
conda activate openox
Copy-Item .env.example .env
```

On macOS or Linux, replace the final command with:

```bash
cp .env.example .env
```

Keep the deterministic thread settings from `environment.yml`. Edit `.env` only with local authorized paths; never commit it.

[`environment.lock.yml`](../environment.lock.yml) preserves the exact package versions that were recorded for the final model artifact, closeout QA, and repeated-measures run. The project used stage-specific environments, and a complete historical solver export was not preserved. The lock file therefore distinguishes the recorded snapshots instead of pretending that one exact environment produced every artifact. `environment.yml` remains the practical environment specification for a new authorized rerun.

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

Selected late-stage workflows have separate scripted checks under `scripts/qa/`, also run as modules. These are second-code-path consistency checks, not external peer review. Substantive external-cohort runners are under `scripts/analysis/` and should likewise be invoked with `python -m scripts.analysis.<runner_name>`. Do not run a later stage until its frozen local inputs exist and any embedded hash checks pass.

The repository intentionally does not promise a one-command public rerun: distributing the required source data, processed cohorts, row-level predictions, or fitted objects would violate the public-release boundary. Reproducibility means an independently authorized user can inspect the full code path and rebuild locally under the same frozen rules.

No synthetic dataset or demo pipeline is included. That is a deliberate scope decision: a synthetic workflow could demonstrate software execution, but it could not reproduce the study evidence or replace authorized access to the source datasets.

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
