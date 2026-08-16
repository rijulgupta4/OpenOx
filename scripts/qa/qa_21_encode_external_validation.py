"""Recompute selected ENCoDE checks through a separate scripted path."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.paths import PROJECT_ROOT

OUTPUT = PROJECT_ROOT / "encode_external_validation"
SOURCE = PROJECT_ROOT / "data" / "external" / "encode" / "MEASUREMENT.csv"


def main():
    summary = json.loads((OUTPUT / "encode_external_summary.json").read_text(encoding="utf-8"))
    pairs = pd.read_csv(OUTPUT / "encode_analysis_pairs.csv.gz")
    mst = pd.read_csv(OUTPUT / "encode_mst_primary_benchmark.csv")
    ita = pd.read_csv(OUTPUT / "encode_ita_associations.csv")
    gate = pd.read_csv(OUTPUT / "encode_risk_validation_gate.csv")
    source = pd.read_csv(
        SOURCE,
        usecols=["measurement_id", "person_id", "measurement_concept_id", "measurement_datetime", "value_as_number"],
        low_memory=False,
    )
    source["measurement_datetime"] = pd.to_datetime(source["measurement_datetime"], utc=True)
    sao2 = source.loc[
        source["measurement_concept_id"].eq(3016502) & source["value_as_number"].notna(),
        ["measurement_id", "person_id", "measurement_datetime", "value_as_number"],
    ].rename(columns={"measurement_datetime": "sao2_time", "value_as_number": "sao2"}).sort_values("sao2_time")
    spo2 = source.loc[
        source["measurement_concept_id"].eq(4196147) & source["value_as_number"].notna(),
        ["measurement_id", "person_id", "measurement_datetime", "value_as_number"],
    ].rename(columns={"measurement_datetime": "spo2_time", "value_as_number": "spo2"}).sort_values("spo2_time")
    reconstructed = pd.merge_asof(
        sao2,
        spo2,
        by="person_id",
        left_on="sao2_time",
        right_on="spo2_time",
        direction="backward",
        tolerance=pd.Timedelta(minutes=5),
    ).dropna(subset=["spo2"])
    reconstructed = reconstructed.loc[
        reconstructed["sao2"].between(70, 100) & reconstructed["spo2"].between(70, 100)
    ]
    eligible = reconstructed.loc[reconstructed["spo2"].between(92, 96)]

    pair_mst = mst.loc[mst["weighting"].eq("pair-weighted")].iloc[0]
    exact_ita = ita.loc[
        ita["weighting"].eq("pair-weighted") & ita["measure"].eq("Exact emitter-site ITA")
    ].iloc[0]
    checks = pd.DataFrame(
        {
            "check": [
                "Independent raw reconstruction returns 615 pairs",
                "Independent raw reconstruction returns 127 participants",
                "Exported pair file matches independent pair count",
                "Independent locked denominator returns 157 pairs",
                "Independent locked denominator contains zero events",
                "Summary and MST primary estimate agree",
                "Summary and MST simultaneous upper bound agree",
                "Summary and exact ITA estimate agree",
                "Exact ITA support remains false",
                "No risk predictions were produced",
                "All exported pair gaps are left-sided and <=5 minutes",
                "All exported outcomes satisfy the publication range restriction",
            ],
            "passed": [
                len(reconstructed) == 615,
                reconstructed["person_id"].nunique() == 127,
                len(pairs) == len(reconstructed),
                len(eligible) == 157,
                int((eligible["sao2"] < 88).sum()) == 0,
                np.isclose(summary["pigmentation"]["high_interval_MST_max_abs_difference"], pair_mst["max_abs_difference"]),
                np.isclose(summary["pigmentation"]["high_interval_MST_simultaneous_95_upper"], pair_mst["simultaneous_upper_abs"]),
                np.isclose(summary["pigmentation"]["exact_emitter_ITA_difference_per_100"], exact_ita["difference_per_100_degrees"]),
                not bool(exact_ita["standalone_support"]),
                not bool(gate["unchanged_model_scored"].iloc[0]) and "predicted_risk" not in pairs.columns,
                pairs["pair_delta_minutes"].between(0, 5).all(),
                pairs["sao2"].between(70, 100).all() and pairs["spo2"].between(70, 100).all(),
            ],
        }
    )
    checks.to_csv(OUTPUT / "encode_external_independent_qa.csv", index=False)
    if not checks["passed"].all():
        raise AssertionError(checks.loc[~checks["passed"]].to_string(index=False))
    print(checks.to_string(index=False))


if __name__ == "__main__":
    main()
