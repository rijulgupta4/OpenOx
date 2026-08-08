from pathlib import Path
import textwrap, nbformat as nbf
OUT=Path(r".\07c_device_descriptive_tiers.ipynb")
def md(s): return nbf.v4.new_markdown_cell(textwrap.dedent(s).strip())
def code(s): return nbf.v4.new_code_cell(textwrap.dedent(s).strip())
nb=nbf.v4.new_notebook()
nb["metadata"]={"kernelspec":{"display_name":"Python (openox)","language":"python","name":"openox"},"language_info":{"name":"python","version":"3.11"}}
nb["cells"]=[
md("""# 07c — Extended and exploratory device reporting

## tl;dr

This notebook completes D011 descriptive-tier reporting without promoting sparse
strata to inferential conclusions. Core results are included only as context.
"""),
md("""## Context & Methods

- Accuracy range: SaO2 70-100%.
- Metrics: pair-weighted bias, precision SD, and A_RMS.
- Extended and exploratory tiers receive descriptive estimates only: no standalone
  confidence intervals, pass/fail claims, or rankings presented as stable truths.
- Participant-balanced estimates are included as a weighting sensitivity.
- The analysis is conditional on a recorded, time-pairable reading.
"""),
code("""
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
PROJECT=Path(r".")
TABLES=PROJECT/"outputs"/"tables"; FIGURES=PROJECT/"outputs"/"figures"
cohort=pd.read_csv(PROJECT/"data"/"processed"/"analytic_cohort_180s.csv.gz",dtype={"patient_id":str},low_memory=False)
support=pd.read_csv(TABLES/"device_probe_inference_support.csv")
def tier(r):
    if str(r.core_inferential_accuracy).lower()=="true": return "Core"
    if str(r.extended_descriptive_accuracy).lower()=="true": return "Extended descriptive"
    if str(r.exploratory_accuracy).lower()=="true": return "Exploratory"
    return "Pooled only"
support["reporting_tier"]=support.apply(tier,axis=1)
"""),
md("## Results"),
code("""
acc=cohort.loc[cohort.so2.between(70,100)].copy(); acc["error_sq"]=acc.error**2
point=acc.groupby("device_probe_key").agg(
    pairs=("error","size"),participants=("patient_id","nunique"),encounters=("encounter_id","nunique"),
    bias=("error","mean"),precision_sd=("error","std"),mse=("error_sq","mean"),
).reset_index()
point["arms"]=np.sqrt(point.mse)
pp=acc.groupby(["device_probe_key","patient_id"]).agg(bias=("error","mean"),mse=("error_sq","mean")).reset_index()
pb=pp.groupby("device_probe_key").agg(bias_participant_balanced=("bias","mean"),mse_pb=("mse","mean")).reset_index()
pb["arms_participant_balanced"]=np.sqrt(pb.mse_pb)
results=point.merge(pb,on="device_probe_key",validate="one_to_one").merge(
    support[["device_probe_key","reporting_tier","pairs_70_80","pairs_80_90","pairs_90_100"]],
    on="device_probe_key",validate="one_to_one")
results["bias_weighting_shift"]=results.bias_participant_balanced-results.bias
results["arms_weighting_shift"]=results.arms_participant_balanced-results.arms
results=results.loc[results.reporting_tier.ne("Pooled only")].sort_values(["reporting_tier","arms"])
results.to_csv(TABLES/"device_performance_all_reporting_tiers.csv",index=False)
display(results.loc[results.reporting_tier.ne("Core"),[
    "device_probe_key","reporting_tier","participants","pairs","bias","precision_sd","arms",
    "bias_participant_balanced","arms_participant_balanced"]].round(3))
"""),
code("""
band=acc.assign(sao2_band=pd.cut(acc.so2,[70,80,90,100.00001],right=False,labels=["70-<80%","80-<90%","90-100%"]))
band=(band.groupby(["device_probe_key","sao2_band"],observed=True)
      .agg(pairs=("error","size"),participants=("patient_id","nunique"),bias=("error","mean"),mse=("error_sq","mean")).reset_index())
band["arms"]=np.sqrt(band.mse)
band=band.merge(support[["device_probe_key","reporting_tier"]],on="device_probe_key",validate="many_to_one")
band=band.loc[band.reporting_tier.isin(["Extended descriptive","Exploratory"])]
band.to_csv(TABLES/"device_performance_descriptive_tiers_by_sao2_band.csv",index=False)
display(band.round(3))
"""),
code("""
palette={"Core":"#2E749F","Extended descriptive":"#A66A00","Exploratory":"#777777"}
p=results.sort_values("arms")
fig,ax=plt.subplots(figsize=(9,8))
y=np.arange(len(p))
ax.barh(y,p.arms,color=[palette[x] for x in p.reporting_tier],edgecolor="#30363B",linewidth=.4)
ax.set(yticks=y,yticklabels=p.device_probe_key,xlabel="A_RMS (percentage points)",ylabel="",
       title="Device/probe accuracy estimates by prespecified reporting tier")
for i,(v,t) in enumerate(zip(p.arms,p.reporting_tier)): ax.text(v+.08,i,f"{v:.2f}",va="center",fontsize=8)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(facecolor=v,label=k) for k,v in palette.items()],frameon=False,loc="lower right")
fig.tight_layout();fig.savefig(FIGURES/"device_performance_reporting_tiers.png",dpi=180,bbox_inches="tight");plt.show()
"""),
code("""
qa=pd.DataFrame([
["core count",(results.reporting_tier=="Core").sum()==11,(results.reporting_tier=="Core").sum(),11],
["extended count",(results.reporting_tier=="Extended descriptive").sum()==11,(results.reporting_tier=="Extended descriptive").sum(),11],
["exploratory count",(results.reporting_tier=="Exploratory").sum()==9,(results.reporting_tier=="Exploratory").sum(),9],
["D011 band support",((results.pairs_70_80>0)&(results.pairs_80_90>0)&(results.pairs_90_100>0)).all(),True,True],
["error identity",np.allclose(acc.error,acc.saturation-acc.so2),True,True],
],columns=["check","passed","observed","expected"])
qa.to_csv(TABLES/"device_descriptive_tiers_qa.csv",index=False);display(qa);assert qa.passed.all()
"""),
md("""## Takeaways

- Descriptive-tier estimates are now complete under the prespecified support hierarchy.
- Several sparse strata have extreme estimates, especially `20|probe_unknown`
  (large negative bias) and `42|probe_02` (high A_RMS). These are signals for
  investigation, not stable inferential comparisons.
- The primary manuscript should lead with the 11 core strata and move extended and
  exploratory tables to secondary or supplement reporting.
""")
]
nbf.write(nb,OUT);print(OUT)
