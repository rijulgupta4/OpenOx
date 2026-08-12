# Reproducibility guide

## 1. Obtain authorized data

Complete the dataset-specific requirements in `DATA_USE.md`. Do not ask another user to share their files or credentials.

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

These directories are ignored. Some historical scripts use these repository-relative defaults directly, while `src/config.py` reads `OPENOX_DATA_DIR`. Run from the repository root.

## 4. Follow the frozen chronology

Use `docs/REPOSITORY_GUIDE.md` for stage order. The notebooks are output-cleared public records; builders reconstruct notebooks, while substantive execution creates restricted local outputs. Do not run later external scripts until their frozen local inputs have been generated and hash checks pass.

The repository intentionally does not promise a one-command public rerun: distributing the required source data, processed cohorts, row-level predictions, or fitted objects would violate the public-release boundary. Reproducibility means an independently authorized user can inspect the full code path and rebuild locally under the same frozen rules.

## 5. Validate the public tree

```powershell
python release_check.py
```

Before a release maintainer updates the public manifest:

```powershell
python release_check.py --write-manifest
python release_check.py
```

Never interpret a successful public-release scan as scientific validation or as proof that a data-use agreement has been satisfied in every environment.
