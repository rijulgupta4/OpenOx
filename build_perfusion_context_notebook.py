from pathlib import Path
import textwrap

import nbformat as nbf


OUT = Path(r".\06_perfusion_context_lock.ipynb")


def code(source: str):
    return nbf.v4.new_code_cell(textwrap.dedent(source).strip())


def md(source: str):
    return nbf.v4.new_markdown_cell(textwrap.dedent(source).strip())


nb = nbf.v4.new_notebook()
nb["metadata"] = {
    "kernelspec": {"display_name": "Python (openox)", "language": "python", "name": "openox"},
    "language_info": {"name": "python", "version": "3.11"},
}

nb["cells"] = [
    md(
        """
        # 06 — Perfusion and physiologic-context lock

        **Purpose.** Map candidate perfusion and physiologic predictors into the frozen
        180-second cohort, quantify coverage and usable support, and freeze their roles
        before any outcome association is examined.

        **Outcome seal.** This notebook never loads pulse-oximeter saturation or the
        derived SpO2 − SaO2 error. SaO2 is loaded only to describe support across the
        already locked oxygenation intervals.
        """
    ),
    code(
        """
        from pathlib import Path
        import json
        import os
        import re

        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        import seaborn as sns

        REPO = Path(r"data\\external\\openoximetry")
        PROJECT = Path(r".")
        COHORT_PATH = PROJECT / "data" / "processed" / "analytic_cohort_180s.csv.gz"
        CONTEXT_PATH = PROJECT / "data" / "processed" / "context_covariates_by_pair.csv.gz"
        TABLES = PROJECT / "outputs" / "tables"
        FIGURES = PROJECT / "outputs" / "figures"
        TABLES.mkdir(parents=True, exist_ok=True)
        FIGURES.mkdir(parents=True, exist_ok=True)

        print("MKL_THREADING_LAYER =", os.environ.get("MKL_THREADING_LAYER"))
        print("MKL_NUM_THREADS     =", os.environ.get("MKL_NUM_THREADS"))
        print("OMP_NUM_THREADS     =", os.environ.get("OMP_NUM_THREADS"))
        """
    ),
    md(
        """
        ## 1. Load only predictor-side fields

        The cohort is deliberately read with an explicit `usecols` list that excludes
        `saturation` and `error`. Source-row IDs are reconstructed from file order, as in
        the accepted cohort-building notebooks.
        """
    ),
    code(
        """
        cohort_cols = [
            "patient_id", "encounter_id", "pulse_row_id", "bloodgas_row_id",
            "device_probe_key", "device_base_id", "probe_id",
            "inferred_assignment_location", "so2",
        ]
        cohort = pd.read_csv(
            COHORT_PATH,
            usecols=cohort_cols,
            dtype={"patient_id": str, "encounter_id": str},
            low_memory=False,
        )
        pulse = pd.read_csv(
            REPO / "pulseoximeter.csv",
            usecols=["encounter_id", "pi"],
            dtype={"encounter_id": str},
            low_memory=False,
        ).reset_index(names="pulse_row_id")
        blood = pd.read_csv(
            REPO / "bloodgas.csv",
            dtype={"patient_id": str, "encounter_id": str},
            low_memory=False,
        ).reset_index(names="bloodgas_row_id")
        encounter = pd.read_csv(
            REPO / "encounter.csv",
            dtype={"patient_id": str, "encounter_id": str},
            low_memory=False,
        )
        patient = pd.read_csv(
            REPO / "patient.csv",
            dtype={"patient_id": str},
            low_memory=False,
        )

        assert cohort["pulse_row_id"].is_unique
        assert len(cohort) == 28_693
        assert {"saturation", "error"}.isdisjoint(cohort.columns)
        print(f"Frozen rows: {len(cohort):,}; participants: {cohort.patient_id.nunique():,}; encounters: {cohort.encounter_id.nunique():,}")
        print("Outcome-seal columns absent:", {"saturation", "error"}.isdisjoint(cohort.columns))
        """
    ),
    md("## 2. Validated source joins and covariate derivation"),
    code(
        """
        # Validate right-hand keys before joining.
        assert pulse["pulse_row_id"].is_unique
        assert blood["bloodgas_row_id"].is_unique
        assert not encounter.duplicated(["patient_id", "encounter_id"]).any()
        assert not patient.duplicated(["patient_id"]).any()

        ctx = cohort.merge(
            pulse[["pulse_row_id", "pi"]],
            on="pulse_row_id", how="left", validate="one_to_one",
        )
        ctx = ctx.merge(
            encounter,
            on=["patient_id", "encounter_id"], how="left", validate="many_to_one",
            suffixes=("", "_encounter"),
        )
        ctx = ctx.merge(
            patient[["patient_id", "assigned_sex", "race", "ethnicity"]],
            on="patient_id", how="left", validate="many_to_one",
        )

        blood_fields = [
            "bloodgas_row_id", "ph", "pco2", "po2", "so2", "cohb", "methb",
            "thb", "lactate", "p50", "ETCO2", "ETO2", "ScalcO2", "RR",
        ]
        hr_cols = [c for c in blood.columns if re.search(r"_HR(?:\\.\\d+)?$", c)]
        bp_cols = [c for c in blood.columns if re.search(r"_(?:NBP|ABP|ART)", c)]
        blood_map = blood[blood_fields + hr_cols + bp_cols].copy()
        ctx = ctx.merge(
            blood_map,
            on="bloodgas_row_id", how="left", validate="many_to_one",
            suffixes=("", "_blood"),
        )

        # Normalize a visibly inconsistent source label without inventing categories.
        sex_clean = (
            ctx["assigned_sex"].astype("string").str.strip().str.lower()
            .replace({"m": "male", "f": "female"})
        )
        ctx["assigned_sex_normalized"] = sex_clean.where(
            sex_clean.isin(["male", "female"]), "unknown"
        )

        # Map a finger-specific diameter only when the inferred sensor assignment is a finger.
        diameter_cols = [f"finger_{side}{digit}_diameter" for side in ("l", "r") for digit in range(1, 6)]
        for c in diameter_cols:
            ctx[c] = pd.to_numeric(ctx[c], errors="coerce")
        ctx["finger_diameter"] = np.nan
        for c in diameter_cols:
            location = c.removesuffix("_diameter")
            mask = ctx["inferred_assignment_location"].eq(location)
            ctx.loc[mask, "finger_diameter"] = ctx.loc[mask, c]

        # Device-reported PI: retain native scale, log2 transform, and robustly standardize only within device/probe.
        ctx["pi"] = pd.to_numeric(ctx["pi"], errors="coerce")
        ctx["log2_pi"] = np.log2(ctx["pi"].where(ctx["pi"] > 0))
        pi_group = ctx.groupby("device_probe_key")["log2_pi"]
        ctx["log2_pi_device_median"] = pi_group.transform("median")
        q25 = pi_group.transform(lambda s: s.quantile(0.25))
        q75 = pi_group.transform(lambda s: s.quantile(0.75))
        iqr = q75 - q25
        ctx["log2_pi_device_robust_z"] = (
            (ctx["log2_pi"] - ctx["log2_pi_device_median"]) / iqr.where(iqr > 0)
        )

        # A transparent heart-rate consensus, accompanied by disagreement diagnostics.
        hr_numeric = ctx[hr_cols].apply(pd.to_numeric, errors="coerce")
        ctx["heart_rate_consensus"] = hr_numeric.median(axis=1, skipna=True)
        ctx["heart_rate_source_count"] = hr_numeric.notna().sum(axis=1)
        ctx["heart_rate_source_spread"] = hr_numeric.max(axis=1) - hr_numeric.min(axis=1)
        print("Joined rows:", len(ctx), "| unique pulse rows:", ctx.pulse_row_id.nunique())
        """
    ),
    md("## 3. Candidate coverage"),
    code(
        """
        candidates = {
            "Device-reported PI": "pi",
            "Warming status": "warming",
            "Mapped finger diameter (all rows)": "finger_diameter",
            "Age": "age_at_encounter",
            "Normalized assigned sex": "assigned_sex_normalized",
            "pH": "ph",
            "PaCO2": "pco2",
            "Total hemoglobin": "thb",
            "Carboxyhemoglobin": "cohb",
            "Methemoglobin": "methb",
            "Lactate": "lactate",
            "P50": "p50",
            "End-tidal CO2": "ETCO2",
            "Respiratory rate": "RR",
            "Heart-rate consensus": "heart_rate_consensus",
        }

        coverage_rows = []
        for label, col in candidates.items():
            if col == "assigned_sex_normalized":
                available = ctx[col].ne("unknown")
            else:
                available = ctx[col].notna()
            coverage_rows.append({
                "measure": label,
                "field": col,
                "rows_available": int(available.sum()),
                "row_coverage": float(available.mean()),
                "participants_with_data": int(ctx.loc[available, "patient_id"].nunique()),
                "encounters_with_data": int(ctx.loc[available, "encounter_id"].nunique()),
            })
        coverage = pd.DataFrame(coverage_rows).sort_values("row_coverage", ascending=False)

        finger_rows = ctx["inferred_assignment_location"].str.startswith("finger_", na=False)
        finger_specific = pd.DataFrame([{
            "measure": "Mapped finger diameter among finger-assigned rows",
            "field": "finger_diameter",
            "rows_available": int(ctx.loc[finger_rows, "finger_diameter"].notna().sum()),
            "eligible_rows": int(finger_rows.sum()),
            "row_coverage": float(ctx.loc[finger_rows, "finger_diameter"].notna().mean()),
            "participants_with_data": int(ctx.loc[finger_rows & ctx.finger_diameter.notna(), "patient_id"].nunique()),
            "encounters_with_data": int(ctx.loc[finger_rows & ctx.finger_diameter.notna(), "encounter_id"].nunique()),
        }])
        coverage.to_csv(TABLES / "context_covariate_coverage.csv", index=False)
        finger_specific.to_csv(TABLES / "finger_diameter_coverage.csv", index=False)
        display(coverage)
        display(finger_specific)
        """
    ),
    code(
        """
        sns.set_theme(style="whitegrid")
        fig, ax = plt.subplots(figsize=(8.4, 5.5))
        plot_cov = coverage.sort_values("row_coverage")
        ax.barh(plot_cov["measure"], 100 * plot_cov["row_coverage"], color="#2E749F")
        ax.axvline(80, color="#8A5A00", linestyle="--", linewidth=1)
        ax.set(xlabel="Frozen-cohort row coverage (%)", ylabel="", xlim=(0, 101))
        ax.set_title("Coverage of candidate perfusion and physiologic-context fields")
        for y, v in enumerate(plot_cov["row_coverage"]):
            ax.text(min(99, 100 * v + 1), y, f"{100*v:.1f}%", va="center", fontsize=8)
        fig.tight_layout()
        fig.savefig(FIGURES / "context_covariate_coverage.png", dpi=180, bbox_inches="tight")
        plt.show()
        """
    ),
    md(
        """
        ## 4. Perfusion-index scale and support

        Native PI is checked separately by device/probe. The analysis does not assume
        that equal numeric values from different devices represent equal percent
        modulation.
        """
    ),
    code(
        """
        def q(s, p):
            return s.quantile(p) if s.notna().any() else np.nan

        pi_support = (
            ctx.groupby("device_probe_key", dropna=False)
            .agg(
                rows=("pulse_row_id", "size"),
                pi_rows=("pi", "count"),
                participants=("patient_id", "nunique"),
                encounters=("encounter_id", "nunique"),
                pi_min=("pi", "min"),
                pi_p25=("pi", lambda s: q(s, .25)),
                pi_median=("pi", "median"),
                pi_p75=("pi", lambda s: q(s, .75)),
                pi_max=("pi", "max"),
            )
            .reset_index()
        )
        pi_support["pi_coverage"] = pi_support["pi_rows"] / pi_support["rows"]
        pi_support = pi_support.sort_values(["pi_rows", "rows"], ascending=False)
        pi_support.to_csv(TABLES / "perfusion_index_device_support.csv", index=False)
        display(pi_support.loc[pi_support.pi_rows > 0])

        assert (ctx.loc[ctx.pi.notna(), "pi"] > 0).all()
        pi_devices = pi_support.loc[pi_support.pi_rows > 0, "device_probe_key"].tolist()
        print("PI-reporting device/probe strata:", pi_devices)
        print("Overall PI coverage:", f"{ctx.pi.notna().mean():.1%}")
        """
    ),
    code(
        """
        pi_plot = ctx.loc[ctx.pi.notna(), ["device_probe_key", "pi", "log2_pi"]].copy()
        order = (
            pi_plot.groupby("device_probe_key")["pi"].median()
            .sort_values().index.tolist()
        )
        fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
        sns.boxplot(data=pi_plot, x="device_probe_key", y="pi", order=order, ax=axes[0], color="#9FD8C2", showfliers=False)
        axes[0].set(title="Native PI scale (outliers hidden)", xlabel="Device/probe stratum", ylabel="Device-reported PI")
        sns.boxplot(data=pi_plot, x="device_probe_key", y="log2_pi", order=order, ax=axes[1], color="#B9B6E8", showfliers=False)
        axes[1].set(title="Log2 PI within each device", xlabel="Device/probe stratum", ylabel="log2(PI)")
        for ax in axes:
            ax.tick_params(axis="x", rotation=30)
        fig.suptitle("PI scales are device-specific and must not be pooled raw", y=1.02, fontsize=13)
        fig.tight_layout()
        fig.savefig(FIGURES / "perfusion_index_by_device.png", dpi=180, bbox_inches="tight")
        plt.show()
        """
    ),
    md("## 5. Procedural and sensor-fit context"),
    code(
        """
        warming_support = (
            ctx.assign(warming_label=ctx["warming"].map({0.0: "not warmed", 1.0: "warmed"}).fillna("missing"))
            .groupby(["device_probe_key", "warming_label"], dropna=False)
            .agg(rows=("pulse_row_id", "size"), participants=("patient_id", "nunique"))
            .reset_index()
        )
        warming_support.to_csv(TABLES / "warming_device_support.csv", index=False)

        finger_support = (
            ctx.loc[finger_rows]
            .groupby("device_probe_key")
            .agg(
                finger_rows=("pulse_row_id", "size"),
                diameter_rows=("finger_diameter", "count"),
                participants=("patient_id", "nunique"),
                diameter_min=("finger_diameter", "min"),
                diameter_median=("finger_diameter", "median"),
                diameter_max=("finger_diameter", "max"),
            )
            .reset_index()
        )
        finger_support["diameter_coverage"] = finger_support["diameter_rows"] / finger_support["finger_rows"]
        finger_support.to_csv(TABLES / "finger_diameter_device_support.csv", index=False)
        display(warming_support.groupby("warming_label").agg(rows=("rows", "sum"), participants=("participants", "max")))
        display(finger_support.sort_values("finger_rows", ascending=False).head(15))
        """
    ),
    md("## 6. Heart-rate agreement and physiologic QA"),
    code(
        """
        hr_qa = pd.DataFrame([{
            "rows_with_consensus": int(ctx.heart_rate_consensus.notna().sum()),
            "coverage": float(ctx.heart_rate_consensus.notna().mean()),
            "rows_with_2plus_sources": int((ctx.heart_rate_source_count >= 2).sum()),
            "median_spread_when_2plus": float(ctx.loc[ctx.heart_rate_source_count >= 2, "heart_rate_source_spread"].median()),
            "p95_spread_when_2plus": float(ctx.loc[ctx.heart_rate_source_count >= 2, "heart_rate_source_spread"].quantile(.95)),
            "max_spread_when_2plus": float(ctx.loc[ctx.heart_rate_source_count >= 2, "heart_rate_source_spread"].max()),
        }])
        hr_qa.to_csv(TABLES / "heart_rate_consensus_qa.csv", index=False)

        numeric_fields = ["ph", "pco2", "po2", "so2_blood", "cohb", "methb", "thb", "lactate", "p50", "ETCO2", "ETO2", "ScalcO2", "RR", "heart_rate_consensus"]
        range_rows = []
        for field in numeric_fields:
            if field not in ctx:
                continue
            x = pd.to_numeric(ctx[field], errors="coerce")
            range_rows.append({
                "field": field, "n": int(x.notna().sum()), "coverage": float(x.notna().mean()),
                "min": x.min(), "p01": x.quantile(.01), "median": x.median(),
                "p99": x.quantile(.99), "max": x.max(),
            })
        physiology_ranges = pd.DataFrame(range_rows)
        physiology_ranges.to_csv(TABLES / "physiology_range_qa.csv", index=False)
        display(hr_qa)
        display(physiology_ranges)
        """
    ),
    md("## 7. Lock candidate roles"),
    code(
        """
        roles = pd.DataFrame([
            ["Device-reported PI", "Perfusion effect modifier", "Primary within PI-reporting device/probe strata", "Use log2(PI); keep device/probe-specific scale; never pool raw PI; no universal PI<1 cutoff without a scale codebook."],
            ["Warming status", "Procedural perfusion context", "Secondary modifier / sensitivity", "No primary imputation; report missingness and device support."],
            ["Mapped finger diameter", "Sensor-fit/anatomic context", "Secondary modifier on finger-assigned rows", "Use only the diameter of the inferred instrumented finger; not defined for ear/forehead rows."],
            ["pH, PaCO2, total Hb, COHb, MetHb", "Mechanistic physiologic context", "Prespecified adjustment set", "Enter with SaO2 interval and device/probe; inspect collinearity and nonlinear form before final fits."],
            ["Age and normalized assigned sex", "Baseline context", "Prespecified adjustment / description", "Normalize source labels; do not overinterpret sex effects."],
            ["Heart-rate consensus and RR", "Dynamic physiologic context", "Exploratory / sensitivity", "HR source identity is ambiguous; RR has extreme values requiring range sensitivity."],
            ["P50", "Oxygen-affinity context", "Sensitivity only", "Incomplete and derived; complete-case sensitivity only."],
            ["ETCO2, ETO2, ScalcO2, PaO2", "Oxygenation/ventilation context", "Not in primary adjustment", "Redundant or downstream of SaO2/PaCO2 and risks overconditioning."],
            ["Blood pressure fields", "Hemodynamic context", "Exclude from tabular primary analysis", "Sparse, mixed-source fields with implausible extremes; reserve for waveform V2."],
            ["Lactate, electrolytes, glucose", "General laboratory context", "Descriptive / exploratory only", "Not required by the primary causal or measurement model."],
            ["Race and ethnicity", "Social descriptors", "Descriptive only", "Never substitute for directly measured pigmentation or physiologic context."],
        ], columns=["measure", "concept", "locked_role", "rule"])
        roles.to_csv(TABLES / "context_variable_lock.csv", index=False)
        display(roles)
        """
    ),
    md("## 8. Export the pair-keyed context map and QA"),
    code(
        """
        export_cols = [
            "pulse_row_id", "bloodgas_row_id", "patient_id", "encounter_id",
            "device_probe_key", "inferred_assignment_location", "so2",
            "pi", "log2_pi", "log2_pi_device_median", "log2_pi_device_robust_z",
            "warming", "finger_diameter", "age_at_encounter", "assigned_sex_normalized",
            "ph", "pco2", "po2", "cohb", "methb", "thb", "lactate", "p50",
            "ETCO2", "ETO2", "ScalcO2", "RR", "heart_rate_consensus",
            "heart_rate_source_count", "heart_rate_source_spread",
        ]
        context_map = ctx[export_cols].copy()
        context_map.to_csv(CONTEXT_PATH, index=False, compression="gzip")

        reloaded = pd.read_csv(
            CONTEXT_PATH,
            dtype={"patient_id": str, "encounter_id": str},
            low_memory=False,
        )
        qa = pd.DataFrame([
            ["row_count_preserved", len(reloaded) == len(cohort), len(reloaded), len(cohort)],
            ["pulse_row_id_unique", reloaded.pulse_row_id.is_unique, reloaded.pulse_row_id.nunique(), len(reloaded)],
            ["pulse_row_id_set_preserved", set(reloaded.pulse_row_id) == set(cohort.pulse_row_id), reloaded.pulse_row_id.nunique(), cohort.pulse_row_id.nunique()],
            ["outcome_columns_absent", {"saturation", "error"}.isdisjoint(reloaded.columns), ",".join(reloaded.columns), "no saturation/error"],
            ["pi_positive_when_present", (reloaded.loc[reloaded.pi.notna(), "pi"] > 0).all(), reloaded.pi.min(), ">0"],
            ["sex_categories_normalized", set(reloaded.assigned_sex_normalized.dropna().unique()).issubset({"male", "female", "unknown"}), sorted(reloaded.assigned_sex_normalized.dropna().unique()), "male/female/unknown"],
        ], columns=["check", "passed", "observed", "expected"])
        qa.to_csv(TABLES / "context_covariate_lock_qa.csv", index=False)
        display(qa)
        assert qa["passed"].all()
        print("Wrote:", CONTEXT_PATH)
        """
    ),
    md(
        """
        ## Locked interpretation

        1. **PI is a device-specific signal/perfusion indicator, not a harmonized
           cross-device unit.** Primary PI effects are estimated within reporting
           device/probe strata using `log2(PI)`. A pooled sensitivity may use the
           within-device robust standardized log2 value with device interactions.
        2. **No global PI <1 rule is authorized.** The repository extract lacks the
           scale codebook needed to establish that all four devices report percent
           modulation on the same scale.
        3. **Warming and mapped finger diameter are secondary context modifiers.**
           Their missingness is retained, not imputed for primary analysis.
        4. **The prespecified physiologic adjustment set is pH, PaCO2, total
           hemoglobin, carboxyhemoglobin, and methemoglobin**, with age and normalized
           assigned sex as baseline context. HR, RR, P50, and other laboratory fields
           remain sensitivity or exploratory variables.
        5. **Outcome seal passed.** These choices were made without loading SpO2 or
           SpO2 − SaO2 error.
        """
    ),
]

nbf.write(nb, OUT)
print(OUT)
