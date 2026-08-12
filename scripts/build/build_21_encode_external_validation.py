from __future__ import annotations

import json
from pathlib import Path


ROOT = Path.cwd()
TARGET = ROOT / "notebooks" / "21_encode_external_validation.ipynb"


def markdown(text: str):
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text: str):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": text.splitlines(keepends=True),
    }


cells = [
    markdown(
        """# ENCoDE external validation and measured-pigmentation replication

## tl;dr

The hash-verified ENCoDE v1.0.0 OMOP release reconstructs 615 protocol-conforming SpO2-SaO2 pairs from 127 patients. The publication reported an earlier 521-pair/128-patient analytic extract; released saturation summaries closely reproduce the paper, but the exact REDCap extract is not identifiable in v1.0.0.

Only three released pairs occupy SaO2 70-85%, so the low-saturation pigmentation component is unsupported. At SaO2 >85-100%, the locked forehead-MST contrast is supported and directionally shows more positive SpO2 error in darker MST groups, but its simultaneous 95% upper bound narrowly exceeds the 1.5-point research margin. Exact emitter-site ITA coverage is below the prespecified 80% gate and its confidence interval crosses zero.

Within the frozen SpO2 92-96% risk denominator, ENCoDE supplies 157 pairs from 71 patients and zero SaO2 <88% events. The unchanged D028 model is therefore **not scored**. This is a partial mechanistic replication, not a quantitative external risk-model validation.
"""
    ),
    code(
        """from pathlib import Path
import json
import sys
import pandas as pd
try:
    from IPython.display import display, Image
except ImportError:
    display = print
    Image = None

PROJECT_ROOT = Path.cwd()
if not (PROJECT_ROOT / 'src').exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.analysis.encode_external_validation import run_validation

OUTPUT = PROJECT_ROOT / 'encode_external_validation'
summary = run_validation()
display(summary)
display(pd.read_csv(OUTPUT / 'external_validation_evidence_summary.csv'))
"""
    ),
    markdown("## Source integrity, crosswalk, and released-pair reconstruction\n"),
    code(
        """source_hashes = pd.read_csv(OUTPUT / 'encode_source_hash_qa.csv')
crosswalk_qa = pd.read_csv(OUTPUT / 'encode_crosswalk_qa.csv')
reconstruction = pd.read_csv(OUTPUT / 'encode_pair_reconstruction.csv')
display(source_hashes)
display(crosswalk_qa)
display(reconstruction.round(3))
assert source_hashes['passed'].all() and crosswalk_qa['passed'].all()
"""
    ),
    markdown(
        """## Measured-pigmentation replication

The primary OpenOx-compatible Monk specification uses median forehead MST grouped 1-4, 5-7, and 8-10. Models adjust for centered linear and quadratic SaO2 and use participant-cluster CR1 covariance. The exact objective specification maps left/right finger placements to ipsilateral dorsal-finger Delfin ITA and forehead placements to forehead ITA; unknown and toe locations are not imputed.
"""
    ),
    code(
        """pig_support = pd.read_csv(OUTPUT / 'encode_pigmentation_support.csv')
mst_groups = pd.read_csv(OUTPUT / 'encode_mst_adjusted_group_bias.csv')
mst_benchmark = pd.read_csv(OUTPUT / 'encode_mst_primary_benchmark.csv')
ita = pd.read_csv(OUTPUT / 'encode_ita_associations.csv')
display(pig_support)
display(mst_groups.round(3))
display(mst_benchmark.round(3))
display(ita.round(3))
if Image is not None:
    display(Image(filename=str(OUTPUT / 'encode_pigmentation_replication.png')))
else:
    print('Figure:', OUTPUT / 'encode_pigmentation_replication.png')
"""
    ),
    markdown("## Conditional risk-validation gate\n"),
    code(
        """risk_gate = pd.read_csv(OUTPUT / 'encode_risk_validation_gate.csv')
display(risk_gate)
assert risk_gate['events'].iloc[0] == 0
assert not bool(risk_gate['unchanged_model_scored'].iloc[0])
"""
    ),
    markdown("## Reproducibility and QA\n"),
    code(
        """qa = pd.read_csv(OUTPUT / 'encode_external_qa.csv')
independent_qa = pd.read_csv(OUTPUT / 'encode_external_independent_qa.csv')
manifest = pd.read_csv(OUTPUT / 'encode_external_artifact_manifest.csv')
display(qa)
display(independent_qa)
display(manifest)
assert qa['passed'].all() and independent_qa['passed'].all()
print('ENCoDE external-validation workflow completed with all QA checks passing.')
"""
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

TARGET.write_text(json.dumps(notebook, indent=1), encoding="utf-8")
print(TARGET)
