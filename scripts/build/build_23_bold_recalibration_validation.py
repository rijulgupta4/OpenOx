from pathlib import Path
import json
import nbformat as nbf

ROOT = Path.cwd()
OUT = ROOT / "notebooks" / "23_bold_recalibration_validation.ipynb"
nb = nbf.v4.new_notebook()
nb.cells = [
    nbf.v4.new_markdown_cell("# BOLD post-validation recalibration comparison\n\n## tl;dr\n\nThis notebook compares four bounded score-recalibration methods for both frozen BOLD scores using identical repeated patient-level folds. The winner is descriptive model updating, not independent external validation."),
    nbf.v4.new_markdown_cell("## Context & Methods\n\n- Candidates: intercept-only, logistic intercept-plus-slope, isotonic, and a fixed 4-knot cubic spline.\n- Reference: each unchanged score.\n- Resampling: 20 repeats of five-fold patient-level cross-validation, stratified by source and outcome.\n- Selection: lowest median pair-weighted log loss, then Brier score, then lower complexity.\n- eICU-specific calibration is reported separately and cannot win the overall BOLD comparison.\n- Coefficient refitting and threshold optimization are outside scope."),
    nbf.v4.new_code_cell("import os\nos.environ['MKL_THREADING_LAYER']='SEQUENTIAL'\nos.environ['MKL_NUM_THREADS']='1'\nos.environ['OMP_NUM_THREADS']='1'\nfrom pathlib import Path\nimport sys\nPROJECT_ROOT=Path.cwd()\nif not (PROJECT_ROOT/'src').exists(): PROJECT_ROOT=PROJECT_ROOT.parent\nif str(PROJECT_ROOT) not in sys.path: sys.path.insert(0,str(PROJECT_ROOT))\nimport pandas as pd\nimport matplotlib.pyplot as plt\nfrom scripts.analysis.bold_recalibration_validation import run_validation\nfrom scripts.qa.qa_bold_recalibration_validation import run_qa\nROOT=PROJECT_ROOT; RESULTS=ROOT/'bold_recalibration_validation'"),
    nbf.v4.new_markdown_cell("## Data\n\nRecreate all repeated-CV predictions and fixed-candidate comparisons from the frozen BOLD score file."),
    nbf.v4.new_code_cell("result=run_validation(); pd.Series(result, name='value').to_frame()"),
    nbf.v4.new_markdown_cell("## Results\n\n### Overall BOLD selection table"),
    nbf.v4.new_code_cell("selection=pd.read_csv(RESULTS/'overall_selection_table.csv'); selection[['base_model','method','log_loss_median','brier_median','pr_auc_median','roc_auc_median','complexity_rank','selected']]"),
    nbf.v4.new_markdown_cell("### Compare probability loss across all candidates"),
    nbf.v4.new_code_cell("summary=pd.read_csv(RESULTS/'recalibration_summary.csv'); plot=summary.query(\"scope=='overall_BOLD' and weighting=='pair'\").copy(); plot['candidate']=plot['base_model']+' | '+plot['method']; plot=plot.sort_values('log_loss_median'); ax=plot.plot.barh(x='candidate',y='log_loss_median',legend=False,figsize=(8,5),color=['#2b6cb0' if m else '#a0aec0' for m in plot.method.ne('unchanged')]); ax.set_xlabel('Median cross-fitted log loss (lower is better)'); ax.set_ylabel(''); plt.tight_layout(); plt.show()"),
    nbf.v4.new_markdown_cell("### eICU-specific secondary results and paired bootstrap uncertainty"),
    nbf.v4.new_code_cell("eicu=summary.query(\"scope=='eICU' and weighting=='pair'\").sort_values('log_loss_median'); uncertainty=pd.read_csv(RESULTS/'selected_vs_unchanged_bootstrap.csv'); eicu[['base_model','method','log_loss_median','brier_median','pr_auc_median','roc_auc_median']], uncertainty"),
    nbf.v4.new_markdown_cell("### Independent QA"),
    nbf.v4.new_code_cell("qa_result=run_qa(); qa=pd.read_csv(RESULTS/'independent_qa.csv'); qa_result, qa"),
    nbf.v4.new_markdown_cell("## Takeaways\n\nThe selected candidate is the best *within this locked recalibration comparison*. Because BOLD outcomes were used to fit and select it, its cross-fitted performance estimates model-updating potential; it does not constitute a new external validation. A final recalibrator fit on all BOLD is saved for research use and must be evaluated on a third untouched cohort before any transport or deployment claim."),
]
nb.metadata = {"kernelspec":{"display_name":"Python (openox)","language":"python","name":"openox"},"language_info":{"name":"python","version":"3.12"},"openox_analysis":{"decision_id":"D035-recalibration","confirmatory":False}}
nbf.write(nb, OUT)
print(OUT)
