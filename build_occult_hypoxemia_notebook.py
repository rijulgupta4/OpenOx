from pathlib import Path
import textwrap, nbformat as nbf
OUT=Path(r".\08_occult_hypoxemia.ipynb")
def md(s): return nbf.v4.new_markdown_cell(textwrap.dedent(s).strip())
def code(s): return nbf.v4.new_code_cell(textwrap.dedent(s).strip())
nb=nbf.v4.new_notebook()
nb["metadata"]={"kernelspec":{"display_name":"Python (openox)","language":"python","name":"openox"},"language_info":{"name":"python","version":"3.11"}}
nb["cells"]=[
md("""# 08 — Occult-hypoxemia analysis

## tl;dr

The locked endpoint is SaO2 <88% despite SpO2 92-96%. This notebook reports the
overall clustered analysis, support-gated standalone device rates, standardized
device risks, pairwise risk differences, and definition sensitivities. Pair-level
rates are measurement-event frequencies in controlled laboratory data, not patient
risks in clinical practice.
"""),
md("""## Context & Methods

- Primary denominator: paired SpO2 92-96% inclusive.
- Event: paired arterial SaO2 <88%.
- Overall model: binomial GEE with SpO2 centered at 94%, participant clusters,
  independence working correlation, and robust covariance.
- Device model: only D011-reportable strata (>=100 denominator pairs and >=10 events).
- Device presentation: standardized marginal risks over the pooled empirical SpO2
  distribution of reportable strata and risk differences.
- Sensitivities: SpO2 >=92%; SaO2 <=88%; participant-cluster bootstrap raw rates.
- Recorded-reading caveat: all estimates condition on a recorded, time-pairable SpO2.
"""),
code("""
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
import statsmodels.formula.api as smf
from patsy import build_design_matrices
from scipy.special import expit

PROJECT=Path(r".")
TABLES=PROJECT/"outputs"/"tables";FIGURES=PROJECT/"outputs"/"figures"
N_BOOT=2000;SEED=20260723
cohort=pd.read_csv(PROJECT/"data"/"processed"/"analytic_cohort_180s.csv.gz",
                   dtype={"patient_id":str,"encounter_id":str},low_memory=False)
support=pd.read_csv(TABLES/"device_probe_inference_support.csv")
reportable=support.loc[support.occult_rate_reportable.astype(str).str.lower().eq("true"),"device_probe_key"].tolist()
assert len(reportable)==3
"""),
md("## Results"),
md("### 1. Overall endpoint and GEE"),
code("""
cohort["occult_denominator"]=cohort.saturation.between(92,96,inclusive="both")
cohort["occult_event"]=cohort.occult_denominator & cohort.so2.lt(88)
occult=cohort.loc[cohort.occult_denominator].copy()
occult["event"]=occult.occult_event.astype(int);occult["spo2_centered"]=occult.saturation-94
overall=smf.gee("event ~ spo2_centered",groups="patient_id",data=occult,
                family=sm.families.Binomial(),cov_struct=sm.cov_struct.Independence()).fit()
overall_summary=pd.DataFrame({
 "metric":["denominator pairs","events","pair-level event frequency","participants","participants with event","encounters","GEE converged"],
 "value":[len(occult),occult.event.sum(),occult.event.mean(),occult.patient_id.nunique(),
          occult.loc[occult.event.eq(1),"patient_id"].nunique(),occult.encounter_id.nunique(),overall.converged]})
overall_coef=pd.DataFrame({"term":overall.params.index,"estimate":overall.params.values,
 "robust_se":overall.bse.values,"ci_low":overall.conf_int()[0].values,"ci_high":overall.conf_int()[1].values})
overall_summary.to_csv(TABLES/"occult_hypoxemia_overall_summary.csv",index=False)
overall_coef.to_csv(TABLES/"occult_hypoxemia_overall_gee.csv",index=False)
display(overall_summary);display(overall_coef)
"""),
md("### 2. Support-gated raw device rates with participant bootstrap"),
code("""
raw=[]
rng=np.random.default_rng(SEED)
for key in reportable:
 g=occult.loc[occult.device_probe_key.eq(key)]
 participants=g.patient_id.unique();p=len(participants)
 byp=g.groupby("patient_id").agg(n=("event","size"),events=("event","sum"))
 draws=rng.integers(0,p,size=(N_BOOT,p))
 ns=byp.n.to_numpy()[draws].sum(axis=1);es=byp.events.to_numpy()[draws].sum(axis=1)
 br=es/ns
 raw.append({"device_probe_key":key,"pairs":len(g),"events":int(g.event.sum()),
             "participants":p,"raw_risk":g.event.mean(),
             "raw_ci_low":np.quantile(br,.025),"raw_ci_high":np.quantile(br,.975),
             "valid_replicates":np.isfinite(br).sum()})
raw=pd.DataFrame(raw).sort_values("raw_risk")
raw.to_csv(TABLES/"occult_hypoxemia_reportable_raw_rates.csv",index=False)
display(raw)
"""),
md("### 3. Standardized device risks and risk differences"),
code("""
rep=occult.loc[occult.device_probe_key.isin(reportable)].copy()
rep["device_probe_key"]=pd.Categorical(rep.device_probe_key,categories=sorted(reportable))
device_model=smf.gee("event ~ spo2_centered + C(device_probe_key)",groups="patient_id",data=rep,
                     family=sm.families.Binomial(),cov_struct=sm.cov_struct.Independence()).fit()
design_info=device_model.model.data.design_info
beta=device_model.params.to_numpy();cov=device_model.cov_params().to_numpy()
standard_spo2=rep.saturation.to_numpy()
risks=[];gradients={}
for key in sorted(reportable):
 new=pd.DataFrame({"spo2_centered":standard_spo2-94,"device_probe_key":key})
 X=np.asarray(build_design_matrices([design_info],new)[0])
 pr=expit(X@beta);risk=pr.mean();grad=(pr*(1-pr))@X/len(pr)
 se=float(np.sqrt(grad@cov@grad));gradients[key]=grad
 risks.append({"device_probe_key":key,"standardized_risk":risk,"robust_se":se,
               "ci_low":max(0,risk-1.96*se),"ci_high":min(1,risk+1.96*se)})
risks=pd.DataFrame(risks).sort_values("standardized_risk")
risks.to_csv(TABLES/"occult_hypoxemia_standardized_device_risks.csv",index=False)

rd=[]
keys=risks.device_probe_key.tolist()
for i,a in enumerate(keys):
 for b in keys[i+1:]:
  ra=risks.set_index("device_probe_key").loc[a,"standardized_risk"];rb=risks.set_index("device_probe_key").loc[b,"standardized_risk"]
  gd=gradients[a]-gradients[b];se=float(np.sqrt(gd@cov@gd));d=ra-rb
  rd.append({"device_a":a,"device_b":b,"risk_difference_a_minus_b":d,"robust_se":se,
             "ci_low":d-1.96*se,"ci_high":d+1.96*se})
rd=pd.DataFrame(rd)
rd.to_csv(TABLES/"occult_hypoxemia_device_risk_differences.csv",index=False)
display(risks);display(rd)
"""),
code("""
fig,ax=plt.subplots(figsize=(7.5,4.5))
p=risks.sort_values("standardized_risk");y=np.arange(len(p))
ax.errorbar(100*p.standardized_risk,y,
 xerr=[100*(p.standardized_risk-p.ci_low),100*(p.ci_high-p.standardized_risk)],
 fmt="o",color="#2E749F",ecolor="#737B83",capsize=4)
ax.set(yticks=y,yticklabels=p.device_probe_key,xlabel="Standardized occult-hypoxemia frequency (%)",ylabel="",
       title="Support-gated standardized device risks")
fig.tight_layout();fig.savefig(FIGURES/"occult_hypoxemia_standardized_device_risks.png",dpi=180,bbox_inches="tight");plt.show()
"""),
md("### 4. Definition sensitivities"),
code("""
defs=[
("Primary: SpO2 92-96, SaO2 <88",cohort.saturation.between(92,96)&cohort.so2.lt(88),cohort.saturation.between(92,96)),
("Upper SpO2 >=92, SaO2 <88",cohort.saturation.ge(92)&cohort.so2.lt(88),cohort.saturation.ge(92)),
("SpO2 92-96, SaO2 <=88",cohort.saturation.between(92,96)&cohort.so2.le(88),cohort.saturation.between(92,96)),
]
sens=[]
for label,event,den in defs:
 sens.append({"definition":label,"denominator_pairs":int(den.sum()),"events":int(event.sum()),
              "pair_level_frequency":event.sum()/den.sum(),"participants":cohort.loc[den,"patient_id"].nunique(),
              "participants_with_event":cohort.loc[event,"patient_id"].nunique()})
sens=pd.DataFrame(sens);sens.to_csv(TABLES/"occult_hypoxemia_definition_sensitivity.csv",index=False);display(sens)
"""),
md("### 5. QA"),
code("""
qa=pd.DataFrame([
["primary denominator",len(occult)==6062,len(occult),6062],
["primary events",occult.event.sum()==261,int(occult.event.sum()),261],
["reportable strata",len(reportable)==3,len(reportable),3],
["all raw bootstraps valid",raw.valid_replicates.eq(N_BOOT).all(),raw.valid_replicates.min(),N_BOOT],
["overall GEE converged",overall.converged,overall.converged,True],
["device GEE converged",device_model.converged,device_model.converged,True],
["standardized risks bounded",risks.standardized_risk.between(0,1).all(),True,True],
["three pairwise differences",len(rd)==3,len(rd),3],
],columns=["check","passed","observed","expected"])
qa.to_csv(TABLES/"occult_hypoxemia_qa.csv",index=False);display(qa);assert qa.passed.all()
"""),
md("""## Takeaways

- Report overall and support-gated device estimates as pair-level measurement-event
  frequencies, not participant risks.
- Present standardized risks and risk differences rather than odds ratios.
- Do not publish standalone rates for sparse strata.
- Preserve the controlled-laboratory and recorded-reading caveats when later comparing
  with BOLD or other clinical cohorts.
""")
]
nbf.write(nb,OUT);print(OUT)
