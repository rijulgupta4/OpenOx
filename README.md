# OpenOx

OpenOx is the code-only reproducibility repository for the pre-waveform V1 study of pulse-oximeter accuracy, occult hypoxemia, pigmentation, perfusion, and external transportability. The frozen V1 roadmap ends at decision D035.

## Release boundary

This public repository contains analysis code, cleared notebooks, environment specifications, and decision documentation through D035. It intentionally contains no PhysioNet records, row-level predictions, participant or encounter identifiers, processed cohorts, serialized fitted models, or notebook outputs.

The analyses require separately authorized local access to:

- OpenOximetry Repository v1.1.1
- BOLD v1.0
- ENCoDE v1.0.0

These resources are not redistributed here. Each user must obtain access directly through PhysioNet and comply with the applicable credentialing, training, license, and data-use-agreement requirements. See [DATA_USE.md](DATA_USE.md).

## Status at D035

- The frozen compact model failed unchanged probability transport in BOLD.
- A pre-existing SpO2-only diagnostic transported better but remained imperfect.
- A bounded post-validation calibration comparison selected logistic intercept-plus-slope recalibration of the SpO2-only score.
- D035 is model updating informed by BOLD outcomes, not a second external validation or a deployment-ready model.
- All waveform-enabled development belongs to V2 and is outside this release.

## Repository contents

- Numbered notebooks through `23_bold_recalibration_validation.ipynb`, with all outputs removed.
- Notebook-construction scripts and independent QA scripts.
- `src/config.py` for project-local configuration.
- `OpenOx_Project_Hub.md` and `ROADMAP_updated.md` for the frozen decision history.
- `PUBLIC_RELEASE_MANIFEST.csv` and `PUBLIC_RELEASE_AUDIT.md` documenting the release gate.

## Local setup

```powershell
conda env create -f environment.yml
conda activate openox
Copy-Item .env.example .env
```

Place authorized local data under the ignored directories below, or adapt the local configuration without committing paths or data:

```text
data/external/openoximetry/
data/external/bold/
data/external/encode/
```

Run notebooks from the repository root so project-relative paths resolve consistently. Generated `data/`, `outputs/`, model files, and row-level validation artifacts must remain local.

## Reproducibility and claims

The repository preserves the analysis chronology and frozen decision boundaries. Expected hashes in validation scripts are integrity checks for the exact restricted source releases used locally; they do not grant data access. Aggregate results should be interpreted with the limitations documented in the project hub.

This code is for research reproducibility and does not provide medical advice, replace arterial blood-gas testing, or authorize clinical deployment.

## Citations

Please cite the underlying PhysioNet resources and PhysioNet itself as described in [DATA_USE.md](DATA_USE.md). Publication-specific citation metadata for this repository can be added when the manuscript or archival release receives a stable identifier.
