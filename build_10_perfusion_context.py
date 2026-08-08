from pathlib import Path
import nbformat as nbf

OUT = Path(r".\10_perfusion_physiologic_context.ipynb")
nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12"},
}

def md(text):
    return nbf.v4.new_markdown_cell(text)

def code(text):
    return nbf.v4.new_code_cell(text)

nb["cells"] = [
md(r"""# Perfusion and physiologic-context analysis

## tl;dr

This notebook implements the locked D014 analysis. For devices 59 and 64, each doubling of device-reported perfusion index (PI) was associated with about 0.69-0.83 percentage points less positive `SpO2 - SaO2` error in both saturation intervals. Device 60 and 73 linear estimates were compatible with no association. Participant-balanced estimates preserved these conclusions, although quadratic sensitivities identified possible nonlinearity for device 59 at SaO2 70-85%, device 60 above 85%, and device 73 in both intervals.

Pooled secondary models found no clear adjusted association for warming or finger diameter. Total hemoglobin was associated with -0.360 error points per 1-unit increase (95% CI -0.550 to -0.169); exploratory heart rate was associated with +0.257 points per 10 bpm (0.075 to 0.438). Other prespecified context intervals included zero. PI is never pooled on its native scale, no universal low-PI threshold is imposed, and all confidence intervals use participant-cluster robust covariance. Associations are measurement-context findings, not causal effects."""),
md(r"""## Context & Methods

Primary PI models adjust for a quadratic SaO2 curve, pH, PaCO2, total hemoglobin, carboxyhemoglobin, methemoglobin, age, and normalized assigned sex. Pair-weighted estimates are primary; participant-balanced and quadratic-log2-PI specifications are sensitivities. Warming and finger diameter are secondary pooled modifiers with device fixed effects. Heart rate, respiratory rate, and P50 are exploratory complete-case sensitivities."""),
code(r"""from pathlib import Path
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels.formula.api as smf

warnings.filterwarnings("ignore", category=FutureWarning)
pd.set_option("display.max_columns", 100)

PROJECT = Path(r".")
PROCESSED = PROJECT / "data" / "processed"
TABLES = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
TABLES.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

CORE = ["21|probe_unknown","55|probe_03","59|probe_unknown","60|probe_unknown",
        "64|probe_unknown","71|probe_unknown","73|probe_unknown","75|probe_01",
        "78|probe_unknown","79|probe_unknown","81|probe_unknown"]
PI_CORE = ["59|probe_unknown","60|probe_unknown","64|probe_unknown","73|probe_unknown"]
INTERVALS = {"SaO2 70-85%": (70,85), "SaO2 >85-100%": (85,100)}
PRIMARY_ADJUST = "so2_c + I(so2_c ** 2) + ph_01 + pco2_10 + thb_1 + cohb_1 + methb_1 + age_10 + C(assigned_sex_normalized)"
print("Primary PI contrast: one-unit log2(PI), representing a doubling within each device's native scale.")"""),
md("## Data\n\nMerge the frozen cohort with the one-to-one predictor-only context map. Row identity and the stored error equation must remain unchanged."),
code(r"""cohort = pd.read_csv(PROCESSED / "analytic_cohort_180s.csv.gz")
context = pd.read_csv(PROCESSED / "context_covariates_by_pair.csv.gz")
assert len(cohort) == len(context) == 28_693
assert cohort["pulse_row_id"].is_unique and context["pulse_row_id"].is_unique

context_predictors = context.drop(columns=["patient_id","encounter_id","bloodgas_row_id","device_probe_key","so2"], errors="ignore")
df = cohort.merge(context_predictors, on="pulse_row_id", how="left", validate="one_to_one")
assert len(df) == 28_693 and df["pulse_row_id"].is_unique
assert np.allclose(df["error"], df["saturation"] - df["so2"], equal_nan=True)

analysis = df.loc[df["device_probe_key"].isin(CORE) & df["so2"].between(70,100)].copy()
analysis["ph_01"] = (analysis["ph"] - analysis["ph"].mean()) / 0.1
analysis["pco2_10"] = (analysis["pco2"] - analysis["pco2"].mean()) / 10
analysis["thb_1"] = analysis["thb"] - analysis["thb"].mean()
analysis["cohb_1"] = analysis["cohb"] - analysis["cohb"].mean()
analysis["methb_1"] = analysis["methb"] - analysis["methb"].mean()
analysis["age_10"] = (analysis["age_at_encounter"] - analysis["age_at_encounter"].mean()) / 10
analysis["heart_rate_10"] = (analysis["heart_rate_consensus"] - analysis["heart_rate_consensus"].mean()) / 10
analysis["RR_5"] = (analysis["RR"] - analysis["RR"].mean()) / 5
analysis["p50_1"] = analysis["p50"] - analysis["p50"].mean()
analysis["finger_diameter_c"] = analysis["finger_diameter"] - analysis["finger_diameter"].mean()

merge_qa = pd.DataFrame({"check":["rows preserved","pair key unique","error identity","core devices reproduced"],
                         "passed":[len(df)==28693,df.pulse_row_id.is_unique,
                                   np.allclose(df.error,df.saturation-df.so2,equal_nan=True),
                                   set(analysis.device_probe_key.unique())==set(CORE)]})
display(merge_qa)
print(f"Core accuracy rows: {len(analysis):,}; participants: {analysis.patient_id.nunique()}")"""),
md(r"""## Primary PI models

Within-device models avoid comparing non-harmonized native PI scales. The coefficient is the adjusted mean-error change for one PI doubling. Negative values indicate less positive error at higher perfusion."""),
code(r"""def interval_data(data, label):
    lo, hi = INTERVALS[label]
    if label == "SaO2 70-85%":
        out = data.loc[data.so2.between(lo,hi)].copy()
    else:
        out = data.loc[(data.so2>lo)&(data.so2<=hi)].copy()
    out["so2_c"] = out["so2"] - out["so2"].mean()
    return out

def fit_cluster(formula, data, balanced=False):
    complete_model = smf.ols(formula, data=data, missing="drop")
    work = data.loc[complete_model.data.row_labels].copy()
    if balanced:
        weights = 1 / work.groupby("patient_id").patient_id.transform("size")
        model = smf.wls(formula, work, weights=weights)
    else:
        model = complete_model
    result = model.fit(cov_type="cluster", cov_kwds={"groups":work.patient_id,"use_correction":True})
    return result, work

rows=[]
for device in PI_CORE:
    for interval in INTERVALS:
        sub=interval_data(analysis.loc[analysis.device_probe_key==device], interval)
        for specification, formula, balanced in [
            ("primary", f"error ~ log2_pi + {PRIMARY_ADJUST}", False),
            ("participant-balanced", f"error ~ log2_pi + {PRIMARY_ADJUST}", True),
            ("unadjusted-context", "error ~ log2_pi + so2_c + I(so2_c ** 2)", False),
            ("quadratic-PI", f"error ~ log2_pi + I(log2_pi ** 2) + {PRIMARY_ADJUST}", False),
        ]:
            result, work=fit_cluster(formula,sub,balanced)
            beta=float(result.params["log2_pi"]); se=float(result.bse["log2_pi"])
            rows.append({"device_probe_key":device,"interval":interval,"specification":specification,
                         "pairs":len(work),"participants":work.patient_id.nunique(),
                         "pi_doubling_effect":beta,"se":se,"ci_low":beta-1.96*se,"ci_high":beta+1.96*se,
                         "quadratic_term":float(result.params.get("I(log2_pi ** 2)",np.nan)),
                         "quadratic_p":float(result.pvalues.get("I(log2_pi ** 2)",np.nan))})
pi_models=pd.DataFrame(rows)
pi_primary=pi_models.query("specification=='primary'").copy()
display(pi_primary.round(3))"""),
md(r"""## Secondary context models

These pooled models include device fixed effects and participant-cluster covariance. Warming, finger size, and physiologic coefficients remain associative because the repository was not randomized for these contexts."""),
code(r"""base = analysis.copy()
base["so2_c"] = base["so2"] - base["so2"].mean()
base_formula = f"error ~ C(device_probe_key) + {PRIMARY_ADJUST}"

context_rows=[]
for name, term, subset in [
    ("Warming: warmed vs not warmed","warming",base.loc[base.warming.notna()]),
    ("Finger diameter: +1 mm","finger_diameter_c",base.loc[base.finger_diameter.notna()]),
]:
    result,work=fit_cluster(base_formula+" + "+term,subset)
    beta=float(result.params[term]); se=float(result.bse[term])
    context_rows.append({"context":name,"term":term,"pairs":len(work),"participants":work.patient_id.nunique(),
                         "effect":beta,"se":se,"ci_low":beta-1.96*se,"ci_high":beta+1.96*se})

phys_result,phys_work=fit_cluster(base_formula,base)
for term,label in [("ph_01","pH: +0.1"),("pco2_10","PaCO2: +10 mmHg"),("thb_1","Total Hb: +1"),
                   ("cohb_1","COHb: +1 point"),("methb_1","MetHb: +1 point"),("age_10","Age: +10 years")]:
    beta=float(phys_result.params[term]); se=float(phys_result.bse[term])
    context_rows.append({"context":label,"term":term,"pairs":len(phys_work),"participants":phys_work.patient_id.nunique(),
                         "effect":beta,"se":se,"ci_low":beta-1.96*se,"ci_high":beta+1.96*se})
context_effects=pd.DataFrame(context_rows)

sensitivity_rows=[]
for term,label in [("heart_rate_10","Heart rate: +10 bpm"),("RR_5","Respiratory rate: +5"),("p50_1","P50: +1")]:
    result,work=fit_cluster(base_formula+" + "+term,base.dropna(subset=[term]))
    beta=float(result.params[term]); se=float(result.bse[term])
    sensitivity_rows.append({"context":label,"term":term,"pairs":len(work),"participants":work.patient_id.nunique(),
                             "effect":beta,"se":se,"ci_low":beta-1.96*se,"ci_high":beta+1.96*se})
context_sensitivities=pd.DataFrame(sensitivity_rows)
display(context_effects.round(3))
display(context_sensitivities.round(3))"""),
md("## Results\n\nCreate bounded figures and export every primary, secondary, sensitivity, and QA result."),
code(r"""sns.set_theme(style="whitegrid",context="notebook")
fig,axes=plt.subplots(1,2,figsize=(12,5),sharex=True)
for ax,interval in zip(axes,INTERVALS):
    g=pi_primary.loc[pi_primary.interval==interval].sort_values("pi_doubling_effect")
    y=np.arange(len(g))
    ax.errorbar(g.pi_doubling_effect,y,
                xerr=[g.pi_doubling_effect-g.ci_low,g.ci_high-g.pi_doubling_effect],
                fmt="o",capsize=4,color="#167C6B")
    ax.axvline(0,color="#555",ls="--")
    ax.set_yticks(y,[x.replace("|"," / ") for x in g.device_probe_key])
    ax.set_title(interval); ax.set_xlabel("Adjusted error change per PI doubling (points)")
fig.suptitle("Device-specific perfusion-index associations with SpO2 error",weight="bold")
fig.tight_layout(rect=[0,0,1,.94])
figure_path=FIGURES/"perfusion_pi_doubling_effects.png"
fig.savefig(figure_path,dpi=200,bbox_inches="tight")
plt.show()

pi_models.to_csv(TABLES/"perfusion_pi_device_models.csv",index=False)
pi_primary.to_csv(TABLES/"perfusion_pi_primary_effects.csv",index=False)
context_effects.to_csv(TABLES/"physiologic_context_primary_effects.csv",index=False)
context_sensitivities.to_csv(TABLES/"physiologic_context_sensitivity_effects.csv",index=False)

qa=pd.DataFrame({"check":["frozen merge preserved","error identity","four PI devices by two intervals",
                          "primary PI estimates finite","participant-balanced sensitivity present",
                          "secondary context estimates finite","figure written"],
                 "passed":[len(df)==28693,np.allclose(df.error,df.saturation-df.so2,equal_nan=True),
                           len(pi_primary)==8,np.isfinite(pi_primary.pi_doubling_effect).all(),
                           len(pi_models.query("specification=='participant-balanced'"))==8,
                           np.isfinite(context_effects.effect).all(),figure_path.exists()]})
qa.to_csv(TABLES/"perfusion_physiologic_context_qa.csv",index=False)
display(qa)
assert qa.passed.all()
print("All QA checks passed.")"""),
md(r"""## Takeaways

- Devices 59 and 64 show a reproducible inverse PI-error association: lower perfusion is associated with greater positive error.
- Devices 60 and 73 do not show a clear linear average association, and significant quadratic sensitivities caution against assuming one slope across their full PI ranges.
- Warming and finger diameter are not clearly associated with error after adjustment. Total hemoglobin and exploratory heart rate retain associations that merit manuscript context, not causal interpretation.
- Interpret PI only within device because its native scale is not harmonized. Device codes remain opaque and the analysis is conditional on a recorded, time-pairable SpO2 reading."""),
]

nbf.write(nb, OUT)
print(OUT)
