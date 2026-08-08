from pathlib import Path
import nbformat as nbf


OUT = Path(r".\12_prediction_resampling_qa.ipynb")
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
    md(
        r"""# Prediction resampling allocation and QA

## tl;dr

This notebook creates the frozen nested resampling object before model fitting:

- **Outer validation:** 50 repeats of five participant-level folds (250 validation sets).
- **Inner tuning:** four participant-level folds inside each outer training set (1,000 tuning-validation sets).
- **Stratification:** three mutually exclusive participant categories: occult-positive; absolute-error-≥3 positive without occult hypoxemia; and neither.
- **Leakage rule:** a participant can never appear in outer training and outer validation simultaneously, and every inner participant must belong to the corresponding outer training set.

The split assignment—not merely a random seed—is saved as a permanent artifact. No preprocessing, feature selection, tuning, or model fitting occurs here."""
    ),
    md(
        r"""## Context & Methods

### Key assumptions

The prediction population is restricted to paired readings with `SpO2 92-96%`. Participant-level stratification may use the outcome because it controls resampling balance; it does not expose validation outcomes to model fitting. Since every occult-positive participant also has an absolute-error-≥3 reading, the composite participant categories balance both locked targets more directly than stratifying on occult status alone.

Outer metrics will later be computed from pooled out-of-fold predictions within each repeat. Individual-fold performance estimates are not intended for headline reporting. Inner folds are used only within the associated outer training set."""
    ),
    code(
        r"""from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.model_selection import StratifiedKFold

PROJECT = Path(r".")
PROCESSED = PROJECT / "data" / "processed"
TABLES = PROJECT / "outputs" / "tables"
FIGURES = PROJECT / "outputs" / "figures"
TABLES.mkdir(parents=True, exist_ok=True)
FIGURES.mkdir(parents=True, exist_ok=True)

BASE_SEED = 20_260_726
N_OUTER_REPEATS = 50
N_OUTER_FOLDS = 5
N_INNER_FOLDS = 4

cohort = pd.read_csv(PROCESSED / "analytic_cohort_180s.csv.gz")
assert len(cohort) == 28_693 and cohort.pulse_row_id.is_unique
band = cohort.loc[cohort.saturation.between(92, 96)].copy()
band["occult_hypoxemia"] = band.so2 < 88
band["abs_error_ge_3"] = band.error.abs() >= 3
band["abs_error_ge_4"] = band.error.abs() >= 4

participant_profile = (
    band.groupby("patient_id", as_index=False)
    .agg(
        eligible_pairs=("pulse_row_id", "size"),
        occult_events=("occult_hypoxemia", "sum"),
        abs3_events=("abs_error_ge_3", "sum"),
        abs4_events=("abs_error_ge_4", "sum"),
    )
)
for target in ("occult", "abs3", "abs4"):
    participant_profile[f"{target}_positive"] = participant_profile[f"{target}_events"] > 0

participant_profile["split_stratum"] = np.select(
    [
        participant_profile.occult_positive,
        participant_profile.abs3_positive,
    ],
    ["occult_positive", "abs3_only"],
    default="neither",
)
participant_profile = participant_profile.sort_values("patient_id").reset_index(drop=True)

display(
    participant_profile.groupby("split_stratum", as_index=False)
    .agg(participants=("patient_id", "size"), eligible_pairs=("eligible_pairs", "sum"))
)
assert participant_profile.patient_id.nunique() == 123
assert participant_profile.occult_positive.sum() == 38
assert participant_profile.abs3_positive.sum() == 76
assert participant_profile.split_stratum.value_counts().to_dict() == {
    "neither": 47, "occult_positive": 38, "abs3_only": 38
}"""
    ),
    md("## Data\n\nGenerate and persist the complete outer and inner participant assignments."),
    code(
        r"""def assign_stratified_folds(profile, n_splits, random_state):
    profile = profile.sort_values("patient_id").reset_index(drop=True)
    fold = np.full(len(profile), -1, dtype=int)
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    placeholder = np.zeros(len(profile))
    for fold_id, (_, validation_index) in enumerate(
        splitter.split(placeholder, profile["split_stratum"])
    ):
        fold[validation_index] = fold_id
    assert np.all(fold >= 0)
    return pd.DataFrame({"patient_id": profile.patient_id, "fold": fold})


outer_rows = []
inner_rows = []

for repeat in range(N_OUTER_REPEATS):
    outer_seed = BASE_SEED + repeat
    outer = assign_stratified_folds(participant_profile, N_OUTER_FOLDS, outer_seed)
    outer["repeat"] = repeat
    outer["outer_seed"] = outer_seed
    outer_rows.append(outer)

    for outer_fold in range(N_OUTER_FOLDS):
        outer_training_ids = outer.loc[outer.fold != outer_fold, "patient_id"]
        outer_training_profile = participant_profile[
            participant_profile.patient_id.isin(outer_training_ids)
        ].copy()
        inner_seed = BASE_SEED + 10_000 + repeat * N_OUTER_FOLDS + outer_fold
        inner = assign_stratified_folds(outer_training_profile, N_INNER_FOLDS, inner_seed)
        inner["repeat"] = repeat
        inner["outer_fold"] = outer_fold
        inner["inner_seed"] = inner_seed
        inner_rows.append(inner)

outer_assignments = pd.concat(outer_rows, ignore_index=True)[
    ["repeat", "fold", "patient_id", "outer_seed"]
].sort_values(["repeat", "fold", "patient_id"]).reset_index(drop=True)
inner_assignments = pd.concat(inner_rows, ignore_index=True)[
    ["repeat", "outer_fold", "fold", "patient_id", "inner_seed"]
].rename(columns={"fold": "inner_fold"}).sort_values(
    ["repeat", "outer_fold", "inner_fold", "patient_id"]
).reset_index(drop=True)

display(outer_assignments.head())
display(inner_assignments.head())"""
    ),
    md("## Results\n\nAudit target support, assignment completeness, fold diversity, and nested-split containment."),
    code(
        r"""profile_columns = [
    "patient_id", "eligible_pairs", "occult_events", "abs3_events", "abs4_events",
    "occult_positive", "abs3_positive", "abs4_positive", "split_stratum"
]

outer_support = (
    outer_assignments.merge(participant_profile[profile_columns], on="patient_id", validate="many_to_one")
    .groupby(["repeat", "fold"], as_index=False)
    .agg(
        validation_participants=("patient_id", "size"),
        validation_pairs=("eligible_pairs", "sum"),
        occult_positive_participants=("occult_positive", "sum"),
        occult_events=("occult_events", "sum"),
        abs3_positive_participants=("abs3_positive", "sum"),
        abs3_events=("abs3_events", "sum"),
        abs4_positive_participants=("abs4_positive", "sum"),
        abs4_events=("abs4_events", "sum"),
    )
)

inner_support = (
    inner_assignments.merge(participant_profile[profile_columns], on="patient_id", validate="many_to_one")
    .groupby(["repeat", "outer_fold", "inner_fold"], as_index=False)
    .agg(
        validation_participants=("patient_id", "size"),
        validation_pairs=("eligible_pairs", "sum"),
        occult_positive_participants=("occult_positive", "sum"),
        occult_events=("occult_events", "sum"),
        abs3_positive_participants=("abs3_positive", "sum"),
        abs3_events=("abs3_events", "sum"),
    )
)

outer_validation_sets = (
    outer_assignments.groupby(["repeat", "fold"]).patient_id
    .apply(lambda x: hashlib.sha256(",".join(map(str, sorted(x))).encode()).hexdigest())
)

outer_repeat_counts = outer_assignments.groupby(["repeat", "patient_id"]).size()
inner_assignment_counts = inner_assignments.groupby(["repeat", "outer_fold", "patient_id"]).size()

outer_validation_lookup = (
    outer_assignments.rename(columns={"fold": "outer_fold"})
    .assign(in_outer_validation=True)
)
inner_outer_overlap = inner_assignments.merge(
    outer_validation_lookup[["repeat", "outer_fold", "patient_id", "in_outer_validation"]],
    on=["repeat", "outer_fold", "patient_id"],
    how="inner",
)

summary = pd.DataFrame([
    {
        "domain": "Outer folds",
        "sets": len(outer_support),
        "minimum_occult_positive_participants": outer_support.occult_positive_participants.min(),
        "maximum_occult_positive_participants": outer_support.occult_positive_participants.max(),
        "minimum_abs3_positive_participants": outer_support.abs3_positive_participants.min(),
        "maximum_abs3_positive_participants": outer_support.abs3_positive_participants.max(),
    },
    {
        "domain": "Inner folds",
        "sets": len(inner_support),
        "minimum_occult_positive_participants": inner_support.occult_positive_participants.min(),
        "maximum_occult_positive_participants": inner_support.occult_positive_participants.max(),
        "minimum_abs3_positive_participants": inner_support.abs3_positive_participants.min(),
        "maximum_abs3_positive_participants": inner_support.abs3_positive_participants.max(),
    },
])
display(summary)

qa = pd.DataFrame([
    {"check": "Outer assignment has 50 x 123 rows", "pass": len(outer_assignments) == 50 * 123},
    {"check": "Every participant assigned once per outer repeat", "pass": outer_repeat_counts.eq(1).all()},
    {"check": "Exactly 250 outer validation sets", "pass": len(outer_support) == 250},
    {"check": "All outer validation sets are unique", "pass": outer_validation_sets.nunique() == 250},
    {"check": "Outer folds contain 7-8 occult-positive participants", "pass": outer_support.occult_positive_participants.between(7, 8).all()},
    {"check": "Outer folds contain at least 14 abs3-positive participants", "pass": outer_support.abs3_positive_participants.ge(14).all()},
    {"check": "Outer folds contain at least one abs4-positive participant", "pass": outer_support.abs4_positive_participants.ge(1).all()},
    {"check": "Every outer fold contains positive readings for all targets", "pass": (outer_support[["occult_events", "abs3_events", "abs4_events"]] > 0).all().all()},
    {"check": "Exactly 1,000 inner validation sets", "pass": len(inner_support) == 1_000},
    {"check": "Every outer-training participant assigned once to an inner fold", "pass": inner_assignment_counts.eq(1).all()},
    {"check": "No outer-validation participant appears in corresponding inner allocation", "pass": inner_outer_overlap.empty},
    {"check": "Every inner fold has occult-positive participants", "pass": inner_support.occult_positive_participants.ge(1).all()},
    {"check": "Every inner fold has abs3-positive participants", "pass": inner_support.abs3_positive_participants.ge(1).all()},
])
display(qa)
assert qa["pass"].all()"""
    ),
    code(
        r"""fig, axes = plt.subplots(2, 2, figsize=(10, 7))
panels = [
    ("occult_positive_participants", "Outer: occult-positive participants", outer_support, "discrete"),
    ("abs3_positive_participants", "Outer: abs-error≥3 positive participants", outer_support, "discrete"),
    ("occult_events", "Outer: occult-positive readings", outer_support, 16),
    ("validation_pairs", "Outer: eligible validation readings", outer_support, 16),
]
for ax, (column, title, frame, bin_rule) in zip(axes.flat, panels):
    values = frame[column]
    bins = (
        np.arange(values.min() - 0.5, values.max() + 1.5)
        if bin_rule == "discrete"
        else bin_rule
    )
    ax.hist(values, bins=bins, color="#3c82b5", edgecolor="white")
    ax.axvline(values.median(), color="#b87900", linestyle="--", linewidth=1.5)
    ax.set_title(title)
    ax.set_xlabel(column.replace("_", " "))
    ax.set_ylabel("Outer validation folds")
    ax.grid(axis="y", alpha=.2)
fig.suptitle("Frozen resampling support across 250 outer validation folds", fontweight="bold")
fig.tight_layout()
figure_path = FIGURES / "prediction_resampling_fold_support.png"
fig.savefig(figure_path, dpi=180, bbox_inches="tight")
plt.show()

def allocation_digest(frame, columns):
    payload = frame[columns].to_csv(index=False, lineterminator="\n").encode()
    return hashlib.sha256(payload).hexdigest()

outer_digest = allocation_digest(outer_assignments, ["repeat", "fold", "patient_id", "outer_seed"])
inner_digest = allocation_digest(inner_assignments, ["repeat", "outer_fold", "inner_fold", "patient_id", "inner_seed"])

# Independent deterministic regeneration spot-check.
repeat_zero_check = assign_stratified_folds(participant_profile, N_OUTER_FOLDS, BASE_SEED)
stored_repeat_zero = (
    outer_assignments.loc[outer_assignments.repeat == 0, ["patient_id", "fold"]]
    .sort_values("patient_id").reset_index(drop=True)
)
repeat_zero_check = repeat_zero_check[["patient_id", "fold"]].sort_values("patient_id").reset_index(drop=True)
assert repeat_zero_check.equals(stored_repeat_zero)

manifest = pd.DataFrame([{
    "base_seed": BASE_SEED,
    "outer_repeats": N_OUTER_REPEATS,
    "outer_folds": N_OUTER_FOLDS,
    "inner_folds": N_INNER_FOLDS,
    "participant_strata": "occult_positive | abs3_only | neither",
    "outer_assignment_sha256": outer_digest,
    "inner_assignment_sha256": inner_digest,
}])

participant_profile.to_csv(TABLES / "prediction_participant_event_profile.csv", index=False)
outer_assignments.to_csv(TABLES / "prediction_outer_fold_assignments.csv.gz", index=False, compression="gzip")
inner_assignments.to_csv(TABLES / "prediction_inner_fold_assignments.csv.gz", index=False, compression="gzip")
outer_support.to_csv(TABLES / "prediction_outer_fold_support.csv", index=False)
inner_support.to_csv(TABLES / "prediction_inner_fold_support.csv", index=False)
manifest.to_csv(TABLES / "prediction_resampling_manifest.csv", index=False)
qa.to_csv(TABLES / "prediction_resampling_qa.csv", index=False)

display(manifest)
print("Resampling allocation frozen and QA passed. No model was fit.")"""
    ),
    md(
        r"""## Takeaways

The resampling object is acceptable only if the executed QA table passes every row. Balanced participant counts do not imply balanced positive-reading counts because participants contribute different numbers of repeated readings; that variation is preserved and documented rather than hidden.

The saved assignments are now the authoritative split specification. Future notebooks must load these files instead of regenerating convenient splits. The next modeling step may fit only the SpO2-only baseline and the frozen compact ridge model, using the saved inner folds for tuning and saved outer folds for evaluation."""
    ),
]

OUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(nb, OUT)
print(OUT)
