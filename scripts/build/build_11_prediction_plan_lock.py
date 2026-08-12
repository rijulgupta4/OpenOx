from pathlib import Path
import nbformat as nbf

OUT = Path(r".\notebooks\11_prediction_plan_lock.ipynb")
nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3.12"},
}

def md(x): return nbf.v4.new_markdown_cell(x)
def code(x): return nbf.v4.new_code_cell(x)

nb["cells"] = [
md(r"""# Secondary prediction-plan lock

## tl;dr

The primary prediction target is the already-locked occult-hypoxemia event: `SaO2 <88%` among readings with `SpO2 92-96%`. The frozen cohort provides 6,062 eligible pairs, 261 events, and 38 event-positive participants. This supports a deliberately low-complexity, penalized logistic model—not deep learning or an unrestricted feature search.

The primary transportable model will use only information plausibly available when the SpO2 reading is acted upon and represented in both OpenOx and BOLD: SpO2, age, assigned sex, heart rate, and respiratory rate. SaO2, error, blood-gas results, future information, race/ethnicity, device identity, measured pigmentation, PI, warming, and finger diameter are excluded from the primary feature set. OpenOx-only enriched models are exploratory incremental-value analyses.

Validation is nested and participant-separated. Primary performance emphasizes calibration, Brier score, and precision-recall AUC; ROC AUC is secondary. All preprocessing occurs inside training folds, thresholds are prespecified, and uncertainty is participant-bootstrapped. No prediction model is fit in this lock notebook."""),
md(r"""## Context & Methods

The model is intended to flag when an apparently reassuring pulse-oximeter reading may conceal arterial hypoxemia before the reference SaO2 is known. Feature eligibility therefore depends on temporal availability, not merely correlation.

BOLD contains 49,099 paired measurements representing 44,907 ICU patients. SpO2 precedes SaO2 by up to five minutes; time-varying covariates are left-sided relative to the ABG. Its different setting and pairing process make it an external transportability stress test, not interchangeable validation data.

Sources: [BOLD PhysioNet](https://physionet.org/content/blood-gas-oximetry/1.0/), [BOLD Scientific Data paper](https://www.nature.com/articles/s41597-024-03225-z), and [OpenOximetry publications](https://openoximetry.org/publications/)."""),
code(r"""from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

PROJECT = Path(r".")
PROCESSED = PROJECT / "data" / "processed"
TABLES = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
TABLES.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

cohort = pd.read_csv(PROCESSED / "analytic_cohort_180s.csv.gz")
context = pd.read_csv(PROCESSED / "context_covariates_by_pair.csv.gz")
pigment = pd.read_csv(PROCESSED / "pigmentation_covariates_by_pair.csv.gz")

assert len(cohort) == len(context) == len(pigment) == 28_693
assert cohort.pulse_row_id.is_unique and context.pulse_row_id.is_unique and pigment.pulse_row_id.is_unique

context_x = context.drop(columns=["patient_id","encounter_id","bloodgas_row_id","device_probe_key","so2"], errors="ignore")
pigment_x = pigment.drop(columns=["patient_id","encounter_id"], errors="ignore")
df = cohort.merge(context_x,on="pulse_row_id",how="left",validate="one_to_one")
df = df.merge(pigment_x,on="pulse_row_id",how="left",validate="one_to_one")
assert len(df)==28_693 and df.pulse_row_id.is_unique
assert np.allclose(df.error,df.saturation-df.so2,equal_nan=True)

prediction = df.loc[df.saturation.between(92,96)].copy()
prediction["occult_hypoxemia"] = prediction.so2 < 88
print(f"Prediction cohort: {len(prediction):,} pairs; {prediction.occult_hypoxemia.sum():,} events; "
      f"{prediction.patient_id.nunique()} participants; "
      f"{prediction.loc[prediction.occult_hypoxemia,'patient_id'].nunique()} event-positive participants")"""),
md("## Data\n\nQuantify target support and candidate-feature availability without fitting or selecting a model from predictive performance."),
code(r"""target_summary=pd.DataFrame([{
    "target":"SaO2 <88% when SpO2 92-96%",
    "eligible_pairs":len(prediction),
    "events":int(prediction.occult_hypoxemia.sum()),
    "event_rate_pct":100*prediction.occult_hypoxemia.mean(),
    "participants":prediction.patient_id.nunique(),
    "event_positive_participants":prediction.loc[prediction.occult_hypoxemia,"patient_id"].nunique(),
    "encounters":prediction.encounter_id.nunique(),
}])

feature_specs=[
    ("SpO2","saturation","Primary baseline","Yes","Available at decision time"),
    ("Age","age_at_encounter","Primary transportable","Yes","Baseline demographic"),
    ("Assigned sex","assigned_sex_normalized","Primary transportable","Yes","Baseline demographic"),
    ("Heart rate","heart_rate_consensus","Primary transportable","Yes","Bedside vital; source harmonization required"),
    ("Respiratory rate","RR","Primary transportable","Yes","Bedside vital; range QA and timing alignment required"),
    ("Device/probe","device_probe_key","OpenOx-enriched exploratory","No","Unavailable in BOLD; opaque codes"),
    ("Forehead MST","mst_group","OpenOx-enriched exploratory","No","Measured pigmentation unavailable in BOLD"),
    ("Emitter-site ITA","emitter_site_ita","OpenOx-enriched exploratory","No","Measured pigmentation unavailable in BOLD"),
    ("Device-specific log2 PI","log2_pi","OpenOx-enriched exploratory","No","Unavailable/non-harmonized in BOLD"),
    ("Warming","warming","OpenOx-enriched exploratory","No","Study procedure, not a general bedside feature"),
    ("Finger diameter","finger_diameter","OpenOx-enriched exploratory","No","Unavailable in BOLD"),
]
rows=[]
for label,col,role,bold,note in feature_specs:
    rows.append({"feature":label,"column":col,"role":role,"BOLD_candidate":bold,
                 "coverage_pct":100*prediction[col].notna().mean(),
                 "participants_with_data":prediction.loc[prediction[col].notna(),"patient_id"].nunique(),
                 "note":note})
feature_coverage=pd.DataFrame(rows)

display(target_summary.round(3))
display(feature_coverage.round(2))"""),
md(r"""## Locked feature and leakage rules

The transportable model is intentionally compact because only 38 participants contribute events. It will be compared with an SpO2-only baseline. OpenOx-enriched models test incremental value but cannot replace the primary model or be externally validated in BOLD."""),
code(r"""feature_lock=pd.DataFrame([
    {"model":"Baseline","features":"SpO2 only","role":"Required comparator"},
    {"model":"Primary transportable","features":"SpO2, age, assigned sex, heart rate, respiratory rate",
     "role":"Primary internally validated model; candidate for BOLD transportability"},
    {"model":"OpenOx-enriched A","features":"Primary set plus device/probe identity",
     "role":"Exploratory incremental value; OpenOx only"},
    {"model":"OpenOx-enriched B","features":"Enriched A plus measured MST and emitter-site ITA",
     "role":"Exploratory fairness/context model; missingness-aware; OpenOx only"},
    {"model":"OpenOx-enriched C","features":"Enriched B plus within-device log2 PI, warming, and finger diameter",
     "role":"Exploratory complete-case/incremental model; no universal PI scale"},
])

leakage_lock=pd.DataFrame([
    {"item":"SaO2, PaO2, error, occult outcome","decision":"Forbidden predictors","reason":"Direct target/reference leakage"},
    {"item":"pH, PaCO2, total Hb, COHb, MetHb and other ABG results","decision":"Forbidden in bedside primary model","reason":"Typically learned from the same blood draw used to establish the outcome"},
    {"item":"Future SOFA, outcomes, post-ABG treatment","decision":"Forbidden","reason":"Post-decision information"},
    {"item":"Race and ethnicity","decision":"Audit variable only","reason":"Social categories are not measured pigmentation and should not drive a correction"},
    {"item":"MST, ITA, device, PI","decision":"OpenOx-enriched only","reason":"Unavailable or non-harmonized in BOLD"},
])
display(feature_lock)
display(leakage_lock)"""),
md(r"""## Locked validation and reporting plan

All splits occur at participant level. Repeated rows from one participant may never appear in both training and validation data. Model comparison uses the same outer folds and out-of-fold predictions."""),
code(r"""validation_lock=pd.DataFrame([
    {"domain":"Algorithm","locked rule":"Penalized logistic regression is primary; hyperparameters tuned only in inner grouped folds. Gradient boosting may be exploratory only."},
    {"domain":"Outer validation","locked rule":"Repeated 5-fold stratified group cross-validation by participant; preserve event-positive participants across folds."},
    {"domain":"Inner tuning","locked rule":"Grouped inner cross-validation; optimize log loss/Brier-oriented criterion, not test-fold AUROC."},
    {"domain":"Preprocessing","locked rule":"Fit scaling, median imputation, missing indicators, and categorical encoding inside each training fold."},
    {"domain":"Primary metrics","locked rule":"Calibration-in-the-large, calibration slope, Brier score, log loss, and precision-recall AUC."},
    {"domain":"Secondary metrics","locked rule":"ROC AUC plus sensitivity, specificity, PPV, and NPV at prespecified 2%, 5%, and 10% risk thresholds."},
    {"domain":"Uncertainty","locked rule":"Participant bootstrap over out-of-fold predictions; also report participant-balanced metric sensitivity."},
    {"domain":"Model comparison","locked rule":"Primary model must improve calibration/Brier versus SpO2-only without materially degrading subgroup performance."},
    {"domain":"Fairness audit","locked rule":"Evaluate calibration, sensitivity, and false-negative rates by MST/ITA in OpenOx; BOLD race/ethnicity is audit-only, never a pigmentation proxy or predictor."},
    {"domain":"External validation","locked rule":"Freeze the OpenOx transportable model first; apply unchanged to BOLD, then report discrimination and calibration by source database. Any recalibration is separate and explicit."},
])

bold_crosswalk=pd.DataFrame([
    {"concept":"Target SaO2 <88% with SpO2 92-96%","OpenOx":"Available","BOLD":"Available","decision":"Transportable"},
    {"concept":"SpO2","OpenOx":"Available at paired reading","BOLD":"Pre-ABG within 5 minutes","decision":"Transportable with timing caveat"},
    {"concept":"Age and sex","OpenOx":"Available","BOLD":"Available","decision":"Transportable after coding audit"},
    {"concept":"Heart and respiratory rate","OpenOx":"Available with source/range caveats","BOLD":"Left-sided vitals available","decision":"Candidate; require units/window audit"},
    {"concept":"Device/probe identity","OpenOx":"Opaque code available","BOLD":"Unavailable","decision":"Not transportable"},
    {"concept":"MST/ITA pigmentation","OpenOx":"Available","BOLD":"Unavailable","decision":"Not transportable"},
    {"concept":"Race/ethnicity","OpenOx":"Social descriptor","BOLD":"Available","decision":"Audit only; not a substitute for pigmentation"},
    {"concept":"Perfusion index","OpenOx":"Device-specific subset","BOLD":"Unavailable","decision":"Not transportable"},
])
display(validation_lock)
display(bold_crosswalk)"""),
md("## Results\n\nExport the locked specifications and a compact availability figure. No predictive performance is calculated in this notebook."),
code(r"""sns.set_theme(style="whitegrid",context="notebook")
plot=feature_coverage.sort_values("coverage_pct")
fig,ax=plt.subplots(figsize=(9,5.5))
colors=plot.role.map(lambda x:"#2F78B7" if "Primary" in x else ("#8A62C1" if "enriched" in x else "#777777"))
ax.barh(plot.feature,plot.coverage_pct,color=colors)
ax.axvline(80,color="#555",ls="--",lw=1)
ax.set_xlim(0,103); ax.set_xlabel("Coverage in occult-hypoxemia denominator (%)")
ax.set_title("Prediction feature availability before model fitting",weight="bold")
for y,v in enumerate(plot.coverage_pct): ax.text(v+1,y,f"{v:.1f}%",va="center",fontsize=9)
fig.tight_layout()
figure_path=FIGURES/"prediction_feature_availability.png"
fig.savefig(figure_path,dpi=200,bbox_inches="tight")
plt.show()

target_summary.to_csv(TABLES/"prediction_target_lock.csv",index=False)
feature_coverage.to_csv(TABLES/"prediction_feature_coverage.csv",index=False)
feature_lock.to_csv(TABLES/"prediction_feature_set_lock.csv",index=False)
leakage_lock.to_csv(TABLES/"prediction_leakage_lock.csv",index=False)
validation_lock.to_csv(TABLES/"prediction_validation_lock.csv",index=False)
bold_crosswalk.to_csv(TABLES/"prediction_bold_crosswalk.csv",index=False)

qa=pd.DataFrame({"check":["frozen rows preserved","pair key unique","error identity",
                          "locked target reproduced","event-positive participants reproduced",
                          "no model fitted","all lock tables written","figure written"],
                 "passed":[len(df)==28693,df.pulse_row_id.is_unique,
                           np.allclose(df.error,df.saturation-df.so2,equal_nan=True),
                           len(prediction)==6062 and prediction.occult_hypoxemia.sum()==261,
                           prediction.loc[prediction.occult_hypoxemia,"patient_id"].nunique()==38,
                           True,True,figure_path.exists()]})
qa.to_csv(TABLES/"prediction_plan_lock_qa.csv",index=False)
display(qa)
assert qa.passed.all()
print("Prediction plan locked; no predictive model fit.")"""),
md(r"""## Takeaways

- The target is clinically interpretable and externally reproducible, but the effective event information is limited to 38 participants.
- A compact penalized model and participant-separated validation are mandatory.
- Blood-gas results are forbidden predictors because they would not be available when the model is supposed to trigger concern.
- OpenOx-enriched models answer incremental scientific questions; only the primary bedside model is eligible for BOLD transportability testing.
- BOLD validation remains conditional on credentialed access and a units, timing, missingness, and coding audit."""),
]

nbf.write(nb,OUT)
print(OUT)
