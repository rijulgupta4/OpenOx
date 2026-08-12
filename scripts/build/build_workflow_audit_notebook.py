from pathlib import Path
import textwrap
import nbformat as nbf

OUT = Path(r".\notebooks\07b_workflow_audit.ipynb")
def md(s): return nbf.v4.new_markdown_cell(textwrap.dedent(s).strip())
def code(s): return nbf.v4.new_code_cell(textwrap.dedent(s).strip())

nb = nbf.v4.new_notebook()
nb["metadata"] = {"kernelspec":{"display_name":"Python (openox)","language":"python","name":"openox"},"language_info":{"name":"python","version":"3.11"}}
nb["cells"] = [
md("""
# 07b — Workflow, novelty, and estimand audit

## tl;dr

The project remains methodologically coherent and may proceed, but two safeguards are
added: participant-balanced device sensitivities and an explicit recorded-reading
selection caveat. The 2026 ISO edition and 2026 Hughes et al. 34-oximeter paper also
change the novelty framing: raw A_RMS and pigmentation comparisons are now replication
and extension targets, while our differentiators are full-repository reproducibility,
occult hypoxemia, physiologic/perfusion context, and transportability modeling.
"""),
md("""
## Context & Methods

This audit retraces the project objective, reproducible artifact chain, current
external landscape, and dependencies between remaining analyses.

### Current external anchors

- [OpenOximetry repository v1.1.1](https://physionet.org/content/openox-repo/1.1.1/)
- [FDA January 2025 draft guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/pulse-oximeters-medical-purposes-non-clinical-and-clinical-performance-testing-labeling-and)
- [ISO 80601-2-61:2026, Edition 3](https://www.iso.org/standard/84595.html)
- [Hughes et al., 34-oximeter comparison, Anesthesia & Analgesia 2026](https://pubmed.ncbi.nlm.nih.gov/42012940/)

The ISO text is not locally licensed; only its public metadata may be treated as
verified here. FDA's 2025 document remains labeled draft and non-binding.
"""),
code("""
from pathlib import Path
import json, re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

PROJECT = Path(r".")
REPO = Path(r"data\\external\\openoximetry")
TABLES = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
"""),
md("## Data"),
code("""
# Reproducible artifact chain.
artifact_rows = []
for path in sorted((PROJECT / "notebooks").glob("*.ipynb")):
    if path.name == "07b_workflow_audit.ipynb":
        continue
    node = json.load(open(path, encoding="utf-8"))
    cells = [c for c in node["cells"] if c.get("cell_type") == "code"]
    errors = [o for c in cells for o in c.get("outputs", []) if o.get("output_type") == "error"]
    artifact_rows.append({
        "artifact": path.name, "type": "notebook", "exists": True,
        "code_cells": len(cells), "executed_cells": sum(c.get("execution_count") is not None for c in cells),
        "errors": len(errors), "passed": len(errors) == 0 and all(c.get("execution_count") is not None for c in cells),
    })
for name in ["analytic_cohort_180s.csv.gz", "pigmentation_covariates_by_pair.csv.gz", "context_covariates_by_pair.csv.gz"]:
    path = PROJECT / "data" / "processed" / name
    frame = pd.read_csv(path, usecols=["pulse_row_id"])
    artifact_rows.append({
        "artifact": name, "type": "processed data", "exists": path.exists(),
        "code_cells": np.nan, "executed_cells": np.nan, "errors": 0,
        "passed": len(frame) == 28693 and frame.pulse_row_id.is_unique,
    })
artifact_audit = pd.DataFrame(artifact_rows)
artifact_audit.to_csv(TABLES / "project_artifact_audit.csv", index=False)
display(artifact_audit)
assert artifact_audit.passed.all()
"""),
md("## Results"),
md("### 1. Participant weighting sensitivity"),
code("""
cohort = pd.read_csv(
    PROJECT / "data" / "processed" / "analytic_cohort_180s.csv.gz",
    dtype={"patient_id": str, "encounter_id": str}, low_memory=False,
)
support = pd.read_csv(TABLES / "device_probe_inference_support.csv")
core = support.loc[support.core_inferential_accuracy.astype(str).str.lower().eq("true"), "device_probe_key"]
acc = cohort.loc[cohort.device_probe_key.isin(core) & cohort.so2.between(70,100)].copy()
acc["error_sq"] = acc.error ** 2

pair = acc.groupby("device_probe_key").agg(pairs=("error","size"), bias_pair=("error","mean"), mse_pair=("error_sq","mean"))
participant = (
    acc.groupby(["device_probe_key","patient_id"])
    .agg(rows=("error","size"), bias=("error","mean"), mse=("error_sq","mean")).reset_index()
)
balanced = participant.groupby("device_probe_key").agg(
    participants=("patient_id","nunique"), median_rows=("rows","median"), max_rows=("rows","max"),
    bias_participant_balanced=("bias","mean"), mse_participant_balanced=("mse","mean"),
)
weighting = pair.join(balanced)
weighting["arms_pair"] = np.sqrt(weighting.mse_pair)
weighting["arms_participant_balanced"] = np.sqrt(weighting.mse_participant_balanced)
weighting["bias_shift"] = weighting.bias_participant_balanced - weighting.bias_pair
weighting["arms_shift"] = weighting.arms_participant_balanced - weighting.arms_pair
for key, group in participant.groupby("device_probe_key"):
    weighting.loc[key, "largest_participant_row_share"] = group.rows.max()/group.rows.sum()
    weighting.loc[key, "kish_effective_participants"] = group.rows.sum()**2/(group.rows.pow(2).sum())
weighting = weighting.reset_index()
weighting.to_csv(TABLES / "device_weighting_sensitivity.csv", index=False)
display(weighting[["device_probe_key","pairs","participants","largest_participant_row_share","kish_effective_participants","bias_pair","bias_participant_balanced","bias_shift","arms_pair","arms_participant_balanced","arms_shift"]].round(3))
"""),
code("""
fig, axes = plt.subplots(1,2,figsize=(10.5,5.5))
order = weighting.sort_values("arms_pair").device_probe_key
w = weighting.set_index("device_probe_key").loc[order].reset_index()
y = np.arange(len(w))
axes[0].plot(w.bias_pair,y,"o",label="Pair-weighted",color="#2E749F")
axes[0].plot(w.bias_participant_balanced,y,"s",label="Participant-balanced",color="#A66A00")
axes[0].set(yticks=y,yticklabels=w.device_probe_key,xlabel="Mean error (percentage points)",title="Bias estimand sensitivity")
axes[1].plot(w.arms_pair,y,"o",label="Pair-weighted",color="#2E749F")
axes[1].plot(w.arms_participant_balanced,y,"s",label="Participant-balanced",color="#A66A00")
axes[1].set(yticks=y,yticklabels=[],xlabel="A_RMS (percentage points)",title="A_RMS estimand sensitivity")
for ax in axes: ax.legend(frameon=False)
fig.tight_layout()
fig.savefig(FIGURES/"device_weighting_sensitivity.png",dpi=180,bbox_inches="tight")
plt.show()
"""),
md("### 2. Recorded-reading availability proxy"),
code("""
def normalize_device(series):
    numeric = pd.to_numeric(series.astype("string").str.strip().str.replace(r"\\s+","",regex=True), errors="coerce")
    base = np.floor(numeric).astype("Int64")
    frac = numeric - np.floor(numeric)
    has_probe = numeric.notna() & ~np.isclose(frac.fillna(0),0)
    probe = pd.Series(pd.NA,index=series.index,dtype="Int64")
    probe.loc[has_probe] = np.rint(frac.loc[has_probe]*100).astype(int)
    key = base.astype("string")+"|probe_unknown"
    key.loc[has_probe] = base.loc[has_probe].astype("string")+"|probe_"+probe.loc[has_probe].astype("string").str.zfill(2)
    key.loc[numeric.isna()] = pd.NA
    return key

encounter = pd.read_csv(REPO/"encounter.csv",dtype={"encounter_id":str},low_memory=False)
device_cols = [c for c in encounter if c.endswith("_device")]
assigned = encounter[["encounter_id"]+device_cols].melt(id_vars="encounter_id",value_name="raw").dropna(subset=["raw"])
assigned["device_probe_key"] = normalize_device(assigned.raw)
assigned = assigned.drop_duplicates(["encounter_id","device_probe_key"])
selected_bg = cohort[["encounter_id","bloodgas_row_id"]].drop_duplicates()
expected = assigned.merge(selected_bg,on="encounter_id",how="inner")
observed = cohort[["encounter_id","bloodgas_row_id","device_probe_key"]].drop_duplicates()
availability = expected.merge(observed,on=["encounter_id","bloodgas_row_id","device_probe_key"],how="left",indicator=True)
availability = (
    availability.loc[availability.device_probe_key.isin(core)]
    .groupby("device_probe_key")
    .agg(expected_assigned_sample_pairs=("bloodgas_row_id","size"),
         observed_pairs=("_merge",lambda x:(x=="both").sum()),
         encounters=("encounter_id","nunique")).reset_index()
)
availability["pairing_coverage_proxy"] = availability.observed_pairs/availability.expected_assigned_sample_pairs
availability["core_assignment_proxy_available"] = True
missing = pd.DataFrame({"device_probe_key":sorted(set(core)-set(availability.device_probe_key)),
                        "expected_assigned_sample_pairs":np.nan,"observed_pairs":np.nan,"encounters":np.nan,
                        "pairing_coverage_proxy":np.nan,"core_assignment_proxy_available":False})
availability = pd.concat([availability,missing],ignore_index=True).sort_values("device_probe_key")
availability.to_csv(TABLES/"device_assignment_pairing_completeness_proxy.csv",index=False)
display(availability)
"""),
md("### 3. Formal workflow findings"),
code("""
findings = pd.DataFrame([
["Research question","Pass","The hierarchy still answers device accuracy, occult hypoxemia, pigmentation, perfusion/context, then secondary prediction.","Retain the roadmap."],
["Novelty positioning","Repair made","A 2026 study already reports A_RMS and pigment differential bias for 34 oximeters from this research program.","Frame device/pigment results as reproducible replication plus extension; emphasize occult hypoxemia, context, and transportability."],
["Standards currency","Repair made","ISO 80601-2-61:2026 Edition 3 is now published; FDA January 2025 guidance remains draft.","Add ISO 2026 to the evidence register; do not infer paywalled requirements or call FDA draft criteria final."],
["Participant weighting","Pass with sensitivity","Largest absolute participant-balanced shift is %.3f bias points and %.3f A_RMS points." % (weighting.bias_shift.abs().max(),weighting.arms_shift.abs().max()),"Keep pair-weighted primary estimand and publish participant-balanced sensitivity."],
["Recorded-reading selection","Caveat","Accuracy is conditional on a recorded, time-pairable SpO2. The assignment proxy is estimable for only %d of 11 core strata." % availability.core_assignment_proxy_available.sum(),"Do not call the proxy a no-read rate; disclose unavailable assignment metadata and consider waveform-based availability in V2."],
["Device identity","Caveat","Repository codes remain opaque and probe identity is frequently unknown.","Avoid manufacturer/model causal claims until an authoritative codebook is recovered."],
["Clinical transportability","Caveat","The frozen cohort is controlled laboratory data; pair-level occult events are not patient risk.","Reserve BOLD/clinical data for shared-feature transportability and keep setting-specific conclusions."],
["Multiplicity","Repair specified","Pigmentation has two co-primary specifications across two SaO2 intervals.","Use an intersection-union success rule: all prespecified benchmark components must pass; do not cherry-pick a favorable component."],
["Outcome leakage","Pass","Pigmentation and context locks were made before error outcomes were opened.","Preserve the frozen maps and do not revise predictor definitions after subgroup results."],
["Reproducibility","Pass","All notebooks execute without errors and all three 28,693-row maps preserve unique pulse_row_id.","Continue top-to-bottom execution and QA gates."],
],columns=["domain","assessment","evidence","action"])
findings.to_csv(TABLES/"workflow_audit_findings.csv",index=False)
display(findings)
"""),
md("""
## Takeaways

### Overall assessment: proceed with documented caveats

No blocker requires reopening the frozen cohort or analysis locks. The next analysis
may proceed after carrying forward:

1. participant-balanced sensitivity for device accuracy;
2. conditional-on-recorded-reading language;
3. ISO 2026 and Hughes et al. 2026 as current benchmarks;
4. replication/extension rather than raw-device-accuracy novelty;
5. an intersection-union rule for later non-disparate-performance claims.
""")
]
nbf.write(nb,OUT)
print(OUT)
