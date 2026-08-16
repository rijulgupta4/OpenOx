# OpenOx Project Hub

Frozen project record for the completed OpenOx V1 pulse-oximetry analysis. Historical language is retained where it documents the chronology; D036 controls the final interpretation.

**Last updated:** 2026-08-16
**Current phase:** V1 formally closed at D036; research-complete and frozen
**Environment:** Conda environment `openox`

## Project objective

Evaluate pulse-oximeter performance using paired SpO2 and arterial SaO2 measurements from OpenOximetry, with device-specific analyses centered on:

1. Overall device performance.
2. Occult hypoxemia.
3. Pigmentation and non-disparate performance.
4. Perfusion and physiologic context.

Predictive modeling is secondary. A separate waveform study was closed on 2026-08-11 because the available timing information could not reliably connect enough raw waveform sections to individual oxygen measurements. The study stopped before a waveform-based error model was developed.

## Roadmap status

| Stage | Status | Current interpretation |
|---|---|---|
| Data inputs and feasibility | Complete | Inventory, duplicate-key diagnostics, timestamp pairing, and pairing-window sensitivity complete. |
| Analysis plan lock | Complete | Pairing, endpoints, device/probe rules, repeated-measures inference, pigmentation/non-disparate specifications, and perfusion/physiologic-context roles are locked. |
| Analytic cohort construction | Complete | The QA-passed 28,693-row base cohort is frozen; one-to-one pigmentation and physiologic-context maps are available without changing row eligibility. |
| Analytic core | Complete | Device performance, occult hypoxemia, pigmentation/non-disparate performance, and perfusion/physiologic context are complete. |
| Secondary predictive modeling | Complete | The compact model is frozen and serialized for unchanged external evaluation; all enriched OpenOx-only models were rejected. |
| External transportability and validation | Complete | BOLD failed unchanged D028 probability transport; a locked post-validation SpO2-only diagnostic transported materially better but remained imperfect. ENCoDE provided a partial high-saturation pigmentation replication but failed the low-saturation, exact-ITA-coverage, and occult-event gates. |
| Outputs and manuscript | Complete (authorized workspace) | D036 closeout and local reporting package. Restricted-data-derived reports, figures, tables, and model artifacts are intentionally excluded from the public repository. |
| Waveform timing study | Closed | Raw pulse signals from a separate investigational recorder were reviewed, but the timing could not be matched reliably for enough records to support an analysis. No waveform-based error model was developed. |

## Data snapshot

Source: local OpenOximetry repository version 1.1.1.

| Item | Count |
|---|---:|
| Participants | 237 |
| Encounters | 907 |
| Blood-gas rows | 32,877 |
| Pulse-oximeter rows | 89,404 |
| Fitzpatrick coverage | 899 of 907 encounters |
| Monk coverage | Approximately 689 of 907 encounters in the initial inventory |

The repository is treated as controlled laboratory/prospective study data. The earlier proposed real-world-versus-laboratory split was removed because it was not supported as a useful primary structure for this release.

## Material findings

### Encounter/sample is not a unique blood-gas key

The nominal `encounter_id + sample` blood-gas key is unsafe for a naive join:

| Diagnostic | Result |
|---|---:|
| Complete blood-gas keys | 18,685 |
| Duplicate keys | 13,117 |
| Rows contained in duplicate keys | 27,052 |
| Exact duplicate groups | 526 |
| Duplicate keys with a conflict in SO2, PO2, PCO2, pH, or time | 13,093 |

Most duplicates are therefore not harmless copies. We will not use `drop_duplicates()`, choose the first row, or choose the most complete row as a general solution.

### Waveform markers can recover a high-confidence subset

The 2 Hz waveform files include sample markers and exact timestamps. These can help identify which blood-gas row is temporally closest to the recorded sample draw.

Safeguards used in the feasibility analysis:

- Exclude waveform marker keys spanning more than 5 seconds.
- Select a blood-gas row only when the nearest timestamp is unique.
- Leave tied nearest rows unresolved.
- Require nonmissing SpO2 and SaO2.
- Explicitly flag duplicate pulse-oximeter keys rather than choosing arbitrarily.
- Apply a provisional maximum timestamp gap of 180 seconds.

Provisional high-confidence cohort:

| Item | Result |
|---|---:|
| Paired SpO2/SaO2 readings | 28,693 |
| Participants | 123 |
| Encounters | 325 |
| Raw device labels | 81 |
| Fitzpatrick coverage across paired rows | 98.9% |
| Monk dorsal coverage across paired rows | 95.5% |

This is now the frozen base analytic cohort for the locked pairing and device/probe rules. It is not yet the final enriched cohort for pigmentation and perfusion analyses.

### Pairing-window sensitivity

The same deterministic pairing algorithm was rerun with maximum waveform-marker-to-blood-gas gaps of 60, 180, and 300 seconds. The resulting cohorts are nested: every 60-second pair is in the 180-second cohort, and every 180-second pair is in the 300-second cohort.

| Maximum gap | Pairs | Participants | Encounters | Device labels | Bias (SpO2 - SaO2) | A_RMS |
|---|---:|---:|---:|---:|---:|---:|
| 60 seconds | 20,587 | 123 | 325 | 81 | +1.087 | 3.411 |
| 180 seconds | 28,693 | 123 | 325 | 81 | +1.141 | 3.311 |
| 300 seconds | 29,751 | 123 | 325 | 81 | +1.167 | 3.316 |

Moving from 60 to 180 seconds adds 8,106 pairs (39.4%) without changing participant, encounter, or device-label coverage. Moving from 180 to 300 seconds adds only 1,058 pairs (3.7%). The incremental 180-to-300-second band is selectively more hypoxemic (median SaO2 82.2%; 68.2% below 88%) and has greater positive bias (+1.884) than the full cohorts. This may reflect genuine device behavior at lower saturation, greater timing uncertainty, or both; it is not proof of mispairing.

The evidence supports 180 seconds as the primary window, 60 seconds as the strict timing sensitivity analysis, and 300 seconds as an outer stress test. Overall bias and A_RMS are similar across all three full cohorts, while the 180-second choice retains substantially more data than 60 seconds and avoids making the small, selectively hypoxemic long-gap tail part of the primary cohort.

### Endpoint feasibility for analysis-plan lock

Current FDA guidance and the January 2025 draft guidance treat A_RMS, bias, saturation-stratified error, and repeated-measures agreement displays as core pulse-oximeter performance measures. The draft also emphasizes performance across directly measured skin pigmentation. These sources are methodological anchors for this academic repository analysis, not a basis for claiming regulatory validation.

| Candidate analysis | Eligible pairs | Participants | Key feasibility result |
|---|---:|---:|---|
| Accuracy, SaO2 70-100% | 27,891 | 123 | 97.2% of the 180-second cohort; pooled bias +1.130 and pooled A_RMS 3.237 |
| SaO2 70-<80% | 8,039 | 120 | Pooled A_RMS 4.192 |
| SaO2 80-<90% | 9,033 | 123 | Pooled A_RMS 3.230 |
| SaO2 90-100% | 10,819 | 123 | Pooled A_RMS 2.291 |
| Occult hypoxemia: SpO2 92-96%, SaO2 <88% | 6,062 | 123 | 261 events (4.3%) across 38 participants and 17 raw device labels |

The accuracy-range support is broad enough to lock a standards-aligned primary metric. The occult-hypoxemia definition is feasible overall, but device-specific event comparisons will require device/probe harmonization and prespecified support rules. Pair-level percentages are descriptive because repeated observations within participants are not independent.

### Device and probe harmonization

Raw device values contain formatting aliases and probe suffixes. After trimming whitespace and normalizing numeric forms, the 81 raw text labels in the 180-second cohort collapse to 65 device/probe strata. The normalized ambiguity rule retains all 28,693 pairs, 123 participants, and 325 encounters and exposes no additional duplicate keys.

The integer portion is treated as the base device-model ID and joins completely to `devices.csv` for every parseable base ID. A nonzero decimal suffix is retained as an explicit probe ID; an integer-only value is labeled probe unknown rather than probe zero. The three numeric `device_type` values remain opaque codes because the local release does not include their interpretation. Encounter assignment fields provide a unique exact or base-device location for 87.5% of raw pulse-oximeter rows, but 12.5% have no assignment and a small fraction are ambiguous. Therefore, inferred location is not used to invent missing probe identity.

| Device/probe reporting tier | Prespecified minimum support | Strata |
|---|---|---:|
| Core inferential accuracy | >=30 participants, >=300 accuracy pairs, and >=50 pairs in each SaO2 band | 11 |
| Extended descriptive accuracy | >=20 participants, >=200 accuracy pairs, and >=30 pairs in each SaO2 band | 11 |
| Exploratory descriptive accuracy | >=10 participants and >=100 accuracy pairs | 9 |
| Pooled analysis only | Below exploratory support | 34 |
| Standalone occult-hypoxemia rate | >=100 eligible pairs and >=10 events | 3 |

These are pragmatic academic-analysis tiers, not FDA pivotal-study sample-size claims. All strata remain available for pooled repeated-measures analyses; the tiers govern standalone device/probe estimates and the strength of interpretation.

### Repeated-measures feasibility and inference lock

The data are strongly clustered: 74 of 123 participants contribute more than one encounter, the median is two encounters per participant (90th percentile five; maximum ten), and participants contribute a median of 187 paired rows. Treating 28,693 rows as independent would therefore overstate precision.

All 11 core device/probe strata completed 2,000 participant-cluster bootstrap replicates. For illustration, the largest core stratum (`59|probe_unknown`) contains 5,133 accuracy-range pairs from 116 participants; its bias is +1.400 percentage points (participant-bootstrap 95% CI +1.135 to +1.683) and A_RMS is 2.307 (95% CI 2.027 to 2.597). These are analytical estimates, not regulatory pass/fail results.

A continuous-error feasibility model for that largest stratum used a quadratic SaO2 mean curve with participant-cluster robust covariance. A nested method-of-moments decomposition of residual dispersion attributed 35.5% to participant differences, 26.0% to encounters within participants, and 38.5% to within-encounter residual variation. This confirms that both participant and encounter levels are material for agreement displays.

The primary occult-hypoxemia denominator contains 6,062 rows, 261 events, and 123 participants. An independence-working binomial GEE with participant-cluster robust covariance converged in six iterations and reproduced the observed marginal event rate of 4.31%. Later subgroup models will be presented as standardized risks and risk differences rather than raw log-odds coefficients.

Implementation note: the NumPy/BLAS crash was traced to threaded MKL initialization. Setting `MKL_THREADING_LAYER=SEQUENTIAL`, `MKL_NUM_THREADS=1`, and `OMP_NUM_THREADS=1` restores stable native matrix solves in the `openox` environment. These settings are required for reproducible execution unless a later environment rebuild removes the defect.

### Pigmentation measurement and non-disparate-performance lock

Pigmentation predictors were mapped into the frozen cohort without loading or analyzing SpO2 error. Forehead Monk Skin Tone (MST) and objective colorimetry have high coverage and strong encounter-level agreement. Because the January 2025 FDA draft specifies separate forehead-MST and emitter-site-ITA analyses, the project will retain both as complementary co-primary pigmentation specifications rather than forcing a single measure to replace the other.

| Measure | Paired rows | Coverage | Participants | Role |
|---|---:|---:|---:|---|
| Fitzpatrick | 28,375 | 98.9% | 121 | Secondary sensitivity |
| Forehead MST | 27,408 | 95.5% | 119 | Co-primary MST groups |
| Forehead ITA | 26,926 | 93.8% | 116 | Standard-site sensitivity |
| Dorsal ITA | 26,926 | 93.8% | 116 | Finger-site mapping |
| Emitter-site ITA | 24,462 | 85.3% | 116 | Co-primary continuous |

At the encounter level, forehead MST and forehead ITA have Spearman rho -0.943; dorsal MST and dorsal ITA have rho -0.917; and forehead and dorsal ITA have rho +0.905. Negative MST-ITA correlations are expected because darker pigmentation has a higher MST number but a lower ITA. Fitzpatrick also correlates strongly with direct measures, but it remains secondary because it classifies sun-response phenotype rather than measuring skin color directly.

For emitter-site mapping, finger placements use median dorsal ITA and forehead placements use median forehead ITA. The analytic cohort lacks matched ear-site colorimetry, so ear and unknown-site rows are excluded from the co-primary emitter-site-ITA analysis but remain eligible for the forehead-MST analysis. No primary imputation across body sites is permitted.

Among the 11 D011 core device/probe strata, seven meet the pre-outcome support rule for standalone MST contrasts and nine meet the continuous ITA rule. Standalone MST contrasts require at least 10 participants and at least 50 pairs in each SaO2 interval for every MST group. Standalone ITA contrasts require at least 30 participants, at least 80% emitter-site-ITA coverage, at least a 100-degree ITA span, and at least 100 pairs in each SaO2 interval. Other strata may contribute to pooled or partially pooled models only.

The two co-primary estimands are: (1) the largest absolute adjusted pairwise difference in mean bias among forehead MST groups; and (2) the adjusted mean-bias difference over a 100-degree change in emitter-site ITA. Each is evaluated separately at SaO2 70-85% and >85-100%. The research benchmark margins are 3.5 percentage points in the lower interval and 1.5 points in the higher interval, with the upper limit of a two-sided 95% confidence interval required to fall below the margin. These FDA-draft criteria guide methodology only and do not convert this retrospective analysis into a pivotal regulatory study.

### Perfusion and physiologic-context lock

Candidate context fields were mapped without loading pulse-oximeter saturation or SpO2 − SaO2 error. The pair-keyed context map preserves all 28,693 frozen rows and unique `pulse_row_id` values.

| Context field | Frozen-row coverage | Locked role |
|---|---:|---|
| pH, PaCO2, total hemoglobin, COHb, MetHb | 100.0% each | Prespecified physiologic adjustment set |
| Age and normalized assigned sex | 99.7% each | Baseline adjustment and description |
| Heart-rate consensus | 99.6% | Exploratory/sensitivity |
| Warming status | 98.4% | Secondary procedural modifier |
| Respiratory rate | 96.1% | Exploratory/sensitivity |
| Mapped finger diameter among finger-assigned rows | 91.7% | Secondary sensor-fit modifier |
| Device-reported perfusion index | 51.2% | Primary perfusion modifier only where reported |
| P50 | 49.2% | Complete-case sensitivity only |

Device-reported PI is fully observed in five device/probe strata: four D011 core strata (`59|probe_unknown`, `60|probe_unknown`, `73|probe_unknown`, and `64|probe_unknown`) and one extended-descriptive stratum (`76|probe_unknown`). Native PI ranges differ radically: device 60 spans 0.06-17, device 59 spans 1-255, and device 64 spans 29-1128. Therefore raw PI values cannot be pooled across devices, and a universal PI <1 cutoff is not authorized without an authoritative scale codebook.

Within PI-reporting device/probe strata, perfusion effects will use `log2(PI)`, so a one-unit contrast represents a doubling of the device's native value. Any pooled sensitivity model must use within-device robust standardization and explicit device interaction terms. Warming is retained without primary imputation. Finger diameter is mapped only to the inferred instrumented finger and is undefined for ear and forehead placements.

The prespecified physiologic adjustment set is pH, PaCO2, total hemoglobin, carboxyhemoglobin, and methemoglobin, with age and normalized assigned sex as baseline context. PaO2, end-tidal O2, calculated O2 saturation, and end-tidal CO2 are excluded from the primary adjustment set because they are redundant with or downstream of the locked SaO2/PaCO2 structure. Heart rate, respiratory rate, and P50 remain sensitivity variables; sparse mixed-source blood-pressure fields were reserved for a possible later waveform study.

### Primary device-performance results

The first analytic-core analysis applied the locked D009, D011, and D012 rules to 20,002 SaO2 70-100% pairs from the 11 core device/probe strata. All strata completed 2,000 participant-cluster bootstrap replicates, met the minimum support rules, and reconciled exactly to the D012 point-estimate feasibility output.

| Device/probe stratum | Participants | Bias (95% CI) | A_RMS (95% CI) |
|---|---:|---:|---:|
| `21 / probe_unknown` | 31 | +0.132 (-0.121, +0.429) | 1.365 (1.231, 1.519) |
| `81 / probe_unknown` | 39 | +0.295 (+0.049, +0.530) | 1.738 (1.450, 2.042) |
| `75 / probe_01` | 44 | +1.084 (+0.800, +1.365) | 1.965 (1.696, 2.263) |
| `64 / probe_unknown` | 49 | +0.501 (+0.102, +0.930) | 2.113 (1.792, 2.424) |
| `59 / probe_unknown` | 116 | +1.400 (+1.133, +1.688) | 2.307 (2.025, 2.599) |
| `71 / probe_unknown` | 75 | +2.020 (+1.804, +2.276) | 2.472 (2.214, 2.758) |
| `79 / probe_unknown` | 33 | +1.516 (+0.973, +2.106) | 2.636 (2.073, 3.221) |
| `73 / probe_unknown` | 90 | +1.354 (+0.950, +1.754) | 2.748 (2.379, 3.080) |
| `78 / probe_unknown` | 32 | +1.974 (+1.416, +2.568) | 2.781 (2.104, 3.481) |
| `55 / probe_03` | 53 | +1.856 (+1.465, +2.252) | 2.798 (2.376, 3.208) |
| `60 / probe_unknown` | 122 | +1.974 (+1.333, +2.664) | 4.671 (4.087, 5.254) |

Ten core strata have A_RMS point estimates from 1.365 to 2.798. `60|probe_unknown` is the clear dispersion outlier at A_RMS 4.671, despite a mean bias similar to several other strata. Its SaO2 70-<80% band has bias +3.031 and A_RMS 6.461, showing that lower-saturation dispersion is a major contributor. This is a device-code-specific measurement finding, not a manufacturer causal claim.

Mean bias is positive in every core stratum; only `21|probe_unknown` has a 95% bias interval that includes zero. Modified Bland-Altman panels show nonconstant error behavior across saturation for several strata, so the saturation-band table must accompany overall metrics. Pair-level bias +/- 1.96 SD lines are descriptive; clustered bootstrap intervals remain the inferential basis. The 3.0 A_RMS line in the comparison figure is a methodological reference only, not a regulatory pass/fail determination.

### Workflow audit and current landscape

The complete workflow, artifact chain, current standards landscape, and closest published OpenOximetry analysis were re-audited before advancing. The project remains coherent and the frozen cohort does not need to be reopened. Its strongest contribution is now framed as an independently reproducible, full-repository extension centered on occult hypoxemia, physiologic/perfusion context, and later clinical transportability—not as the first report of OpenOximetry device accuracy or pigmentation differentials.

| Audit domain | Finding | Action |
|---|---|---|
| Artifact integrity | Notebooks 01 through 07 execute without errors; all three processed pair maps contain exactly 28,693 unique pulse rows. | Continue from the frozen cohort. |
| Observation weighting | Primary device estimates are pair-weighted; participant-cluster bootstrap corrects uncertainty but does not equalize participant influence. | Retain pair-weighted estimands and add participant-balanced sensitivity estimates. |
| Participant-balanced sensitivity | Across core strata, the largest absolute shift was 0.253 bias points and 0.230 A_RMS points. | Conclusions are preserved; report both approaches. |
| Recorded-reading selection | Accuracy is conditional on an SpO2 value being recorded and time-pairable. A limited assignment-pairing proxy ranges from 87.75% to 99.87% in six evaluable core strata; five lack sufficient assignment metadata. | Do not call this a no-read rate; state the conditional estimand and reserve availability analysis for richer metadata or waveforms. |
| Multiplicity | Multiple pigmentation measures, saturation intervals, and devices could invite selective conclusions. | Use an intersection-union rule: every prespecified co-primary component must meet its benchmark. |
| Device identity | Repository device codes remain opaque. | Make no manufacturer-level claims without an authoritative crosswalk. |

ISO 80601-2-61:2026 was published in April 2026 and supersedes the 2017 edition. FDA's January 2025 pulse-oximeter guidance remains draft, non-binding, and not for implementation. The 2026 Hughes et al. analysis from the same OpenOximetry research program evaluated A_RMS and skin-pigmentation differentials across 34 devices; therefore overlap with its device-accuracy endpoints will be described as replication and extension rather than novelty.

### Extended and exploratory device reporting

The locked reporting tiers were applied without promoting sparse strata to inferential status. Eleven extended and nine exploratory strata passed their respective descriptive support rules. These estimates broaden repository coverage but remain supplement-level descriptions.

| Reporting tier | Strata | Interpretation |
|---|---:|---|
| Core inferential | 11 | Participant-cluster intervals and primary device comparisons permitted. |
| Extended descriptive | 11 | Descriptive estimates only; no stable inferential device claim. |
| Exploratory descriptive | 9 | Signal-finding only. |

The most extreme descriptive signals were `20 / probe_unknown` in the extended tier (bias -5.819; A_RMS 8.216) and `42 / probe_02` in the exploratory tier (bias -3.772; A_RMS 6.901). These values warrant transparent reporting and possible follow-up, but sparse support and opaque device codes prevent manufacturer or causal interpretation.

### Occult-hypoxemia results

Under the locked primary definition—SpO2 92-96% with SaO2 <88%—the cohort contains 6,062 eligible pairs and 261 events, a descriptive pair-level frequency of 4.31%. Events occurred across 38 of 123 participants. This controlled-desaturation event frequency is not a clinical patient-risk estimate.

Only three device/probe strata meet the prespecified D011 standalone support rule. Standardized risks were estimated with participant-cluster binomial GEE and standardized over the pooled empirical SpO2 distribution.

| Device/probe stratum | Events / pairs | Standardized risk (95% CI) |
|---|---:|---:|
| `59 / probe_unknown` | 26 / 1,238 | 2.24% (0.64%, 3.83%) |
| `73 / probe_unknown` | 26 / 574 | 4.54% (0.70%, 8.38%) |
| `60 / probe_unknown` | 171 / 1,191 | 13.64% (7.50%, 19.79%) |

The standardized risk difference for device 59 versus 73 was -2.30 percentage points (95% CI -5.64 to +1.04), so those strata were not clearly separated. Device 60 was higher than device 59 by 11.40 points (95% CI 5.57 to 17.23) and higher than device 73 by 9.10 points (95% CI 3.51 to 14.69). Sensitivity frequencies were 2.80% when the upper SpO2 bound was removed and 4.37% when SaO2 <=88% defined the event.

### Pigmentation and non-disparate-performance results

The D013/D015 analysis opened outcomes only after the measures, saturation intervals, support rules, margins, and intersection-union interpretation were frozen. Models adjusted for a quadratic SaO2 mean curve and used participant-cluster robust covariance. Seven core device/probe strata supported standalone forehead-MST contrasts, nine supported emitter-site-ITA contrasts, and five supported all four co-primary components.

| Device/probe stratum | MST 70-85% | MST >85-100% | ITA 70-85% | ITA >85-100% | Complete conclusion |
|---|---|---|---|---|---|
| `55 / probe_03` | Meets | Inconclusive | Meets | Inconclusive | Inconclusive |
| `59 / probe_unknown` | Inconclusive | Inconclusive | Inconclusive | Inconclusive | Inconclusive |
| `71 / probe_unknown` | Meets | Inconclusive | Meets | Inconclusive | Inconclusive |
| `73 / probe_unknown` | Inconclusive | Inconclusive | Inconclusive | Inconclusive | Inconclusive |
| `75 / probe_01` | Meets | Inconclusive | Meets | Inconclusive | Inconclusive |

None of the five complete-support strata demonstrated all four benchmarks, but none had a component whose lower confidence bound exceeded its margin. Their overall conclusions are therefore inconclusive—not proof of equivalent performance and not proof of disparity. The stringent 1.5-point high-saturation margin was the most common source of uncertainty.

Two component-level signals exceeded a benchmark outside the five complete-support strata. For `60 / probe_unknown`, the maximum adjusted MST-group bias difference was 8.887 points at SaO2 70-85% (simultaneous 95% absolute bounds 7.344 to 10.430; margin 3.5) and 3.815 points at >85-100% (2.965 to 4.665; margin 1.5). Its adjusted mean bias rose from -0.118 in MST 1-4 to +8.768 in MST 8-10 in the lower interval, and from -0.400 to +3.415 in the higher interval. However, only 47.1% of its rows have emitter-site ITA, so it cannot receive a complete dual-measure conclusion.

For `79 / probe_unknown`, the high-saturation emitter-site-ITA difference was -3.151 points per 100 ITA degrees (95% CI -4.112 to -2.190), exceeding the 1.5-point absolute margin. The negative direction means lower ITA—darker measured pigmentation—was associated with greater positive SpO2 error. This stratum lacks sufficient MST 8-10 participant support and likewise cannot receive a complete conclusion.

Participant-balanced weighting preserved both component-level findings. The largest weighting-induced estimate shifts were 0.522 points for MST and 0.417 points for ITA. Common-site forehead-ITA and natural-spline sensitivities generally preserved the directional pattern but also showed that precision and possible nonlinearity vary by device. Emitter-site ITA missingness is structurally related to sensor site, so the primary ITA analysis remains a transparent complete-case analysis rather than an imputed one. Unadjusted Fitzpatrick descriptions showed increasing mean error from types I-II (+0.586) to III-IV (+1.056) and V-VI (+2.865), but Fitzpatrick is secondary and these raw values are not causal or equivalence estimates.

### Perfusion and physiologic-context results

The D014 analysis estimated the adjusted change in SpO2 minus SaO2 error for each doubling of device-reported PI, separately within the four core PI-reporting device/probe strata and the two locked saturation intervals. Models adjusted for a quadratic SaO2 curve, pH, PaCO2, total hemoglobin, COHb, MetHb, age, and assigned sex, with participant-cluster robust covariance.

| Device/probe stratum | PI effect at SaO2 70-85% | PI effect at SaO2 >85-100% | Interpretation |
|---|---:|---:|---|
| `59 / probe_unknown` | -0.751 (-0.989, -0.512) | -0.694 (-0.763, -0.625) | Higher PI consistently associated with less positive error. |
| `64 / probe_unknown` | -0.829 (-1.147, -0.510) | -0.832 (-1.139, -0.526) | Higher PI consistently associated with less positive error. |
| `60 / probe_unknown` | -0.280 (-0.754, +0.195) | -0.020 (-0.230, +0.189) | No clear linear average association. |
| `73 / probe_unknown` | +0.078 (-0.369, +0.526) | -0.204 (-0.529, +0.122) | No clear linear average association. |

For devices 59 and 64, lower perfusion is therefore associated with greater positive saturation error. Participant-balanced weighting preserved the primary conclusions; the largest PI-effect shift was 0.331 points. Quadratic sensitivities indicated possible nonlinearity for device 59 at SaO2 70-85%, device 60 above 85%, and device 73 in both intervals, so one linear slope should not be assumed across those devices' entire PI ranges.

In all-core secondary models, warming was associated with +0.095 error points (95% CI -0.295 to +0.484) and finger diameter with -0.063 points per millimeter (-0.197 to +0.071); neither interval excluded zero. Among the prespecified physiologic fields, total hemoglobin was associated with -0.360 points per 1-unit increase (-0.550 to -0.169). pH, PaCO2, COHb, MetHb, and age intervals included zero. Exploratory heart rate was associated with +0.257 points per 10 bpm (+0.075 to +0.438), while respiratory rate and P50 intervals included zero.

These are adjusted measurement-context associations, not causal effects. Native PI scales remain device-specific, no universal PI threshold is authorized, and the findings are conditional on a recorded, time-pairable SpO2 value.

### Secondary prediction-plan lock

The primary predictive target is the already-locked occult-hypoxemia event: SaO2 below 88% when SpO2 is 92-96%. The prediction cohort contains 6,062 pairs, 261 events, 123 participants, and only 38 event-positive participants. Effective event information is therefore participant-limited despite the larger pair count.

| Model tier | Locked features | Role |
|---|---|---|
| Baseline | SpO2 only | Required comparator. |
| Primary transportable | SpO2, age, assigned sex, heart rate, respiratory rate | Primary internally validated model and candidate for BOLD transportability. |
| OpenOx-enriched A | Primary set plus device/probe identity | Exploratory incremental value; OpenOx only. |
| OpenOx-enriched B | Primary set plus measured MST and emitter-site ITA | Exploratory pigmentation feature-value block; OpenOx only. |
| OpenOx-enriched C | Primary set plus within-device log2 PI, warming, and finger diameter | Exploratory context feature-value block; incomplete and not transportable. |

SaO2, PaO2, SpO2 error, the occult outcome, and all same-draw blood-gas results are forbidden predictors because they reveal the outcome or would not be available when the model is meant to trigger concern. Race and ethnicity are audit variables only; they are neither predictors nor substitutes for measured pigmentation.

Penalized logistic regression is the primary algorithm. Validation uses repeated five-fold stratified group cross-validation by participant, with grouped inner tuning and all preprocessing learned within training folds. Primary performance measures are calibration-in-the-large, calibration slope, Brier score, log loss, and precision-recall AUC. ROC AUC is secondary. Fixed 2%, 5%, and 10% risk thresholds prevent post hoc optimization. Uncertainty uses participant bootstrap over out-of-fold predictions, with participant-balanced metrics as sensitivity analyses.

The hash-verified BOLD 1.0 file contains 49,093 paired measurements from 44,902 ICU patients. Its SpO2 values precede SaO2 by up to five minutes and time-varying covariates are left-sided. The OpenOx primary model was frozen before being applied unchanged to BOLD. Any recalibration remains separate, and performance is reported by BOLD source database subject to event-support gates. Device, MST/ITA, and PI effects cannot be externally validated there.

### Sparse clustered-outcome amendment

The prediction denominator is now unambiguous: all fitting and evaluation are restricted to readings with SpO2 92-96%. Rows outside that band are excluded, not automatically labeled negative. Within the restricted population, the outcome is SaO2 below 88%. SpO2 remains the mandatory baseline predictor; a weak coefficient within this narrow range would be a meaningful result rather than a modeling defect.

The participant-level support requires an explicit pilot claim. The headline outcome has 261 positive readings from only 38 positive participants. A secondary pipeline-robustness target, absolute SpO2-SaO2 error of at least 3 points within the same restricted population, has 778 positive readings from 76 positive participants. It provides a more stable test of the modeling machinery but cannot validate the occult-hypoxemia model by proxy.

| Target in SpO2 92-96% population | Positive readings | Positive participants | Role |
|---|---:|---:|---|
| SaO2 <88% | 261 | 38 | Headline clinical target; pilot prediction evidence |
| Absolute error >=3 points | 778 | 76 | Secondary pipeline-robustness target |
| Absolute error >=4 points | 441 | 58 | Optional sensitivity only |

Ridge logistic regression remains primary for calibrated prediction. Intercept-corrected Firth logistic regression (FLIC, or FLAC if implemented) is a prespecified sensitivity for separation and finite-sample coefficient bias; ordinary Firth probabilities can be distorted toward 0.5, and no Firth variant by itself corrects within-participant dependence. The fixed compact feature set will not be expanded through unrestricted selection, interactions, or nonlinear searching. Device, pigmentation, and perfusion/context predictors will be tested as separate incremental blocks rather than accumulated into one high-dimensional full model.

Outer validation uses 50 repeats of five-fold participant-grouped cross-validation stratified on participant event status, targeting seven or eight positive participants per validation fold. Metrics are computed from the pooled out-of-fold predictions within each repeat and summarized across repeats. A small fixed ridge penalty grid is tuned only in grouped inner folds, with tuning-frequency and fixed-penalty sensitivity reporting. At least 500 participant-cluster bootstrap refits provide an optimism-correction cross-check; .632+ is secondary and used only for compatible loss metrics when out-of-bag event support is adequate.

Pair-weighted fitting remains primary, with inverse-participant-frequency weighting as sensitivity. Decision-curve net benefit is secondary, evaluated from 2% through 10% risk thresholds against flag-all and flag-none with participant-bootstrap uncertainty. It supplements calibration and discrimination; it does not establish clinical utility without accepting the threshold-specific tradeoff.

Pigmentation has two explicitly separate scientific roles. The completed equity analysis asks whether measurement performance differs by pigmentation. The future feature-value analysis asks whether adding measured pigmentation improves out-of-fold prediction. No incremental prediction gain would not disprove disparate performance, and a disparity finding would not automatically justify pigmentation as a predictor.

### Frozen prediction-resampling allocation

The nested participant-level split object was generated and frozen before model fitting. It contains 50 repeated five-fold outer partitions (250 outer validation sets) and four inner tuning folds within each outer training set (1,000 inner validation sets). Participants were stratified into three mutually exclusive categories: occult-positive, absolute-error-≥3-positive without occult hypoxemia, and neither.

| Validation layer | Sets | Participants per validation set | Occult-positive participants | Absolute-error-≥3-positive participants |
|---|---:|---:|---:|---:|
| Outer | 250 | 24-25 | 7-8 | 14-16 |
| Inner | 1,000 | 24-25 | 7-8 | 14-16 |

Every participant appears once per outer repeat, all 250 outer validation sets are unique, and no outer-validation participant appears in the corresponding inner allocation. Every fold contains positive readings for the locked target used at that layer. The saved assignment files are authoritative; future notebooks must load them rather than regenerate convenient splits.

Positive-reading counts remain variable because participant contribution is unequal: outer folds contain 12-134 occult-positive readings and 64-306 absolute-error-≥3 readings. This does not invalidate participant stratification. It reinforces the locked plan to pool all outer-fold predictions within each repeat and summarize repeat-level performance rather than treating individual-fold metrics as stable estimates.

### Initial internal validation: baseline versus compact ridge

The first authorized model-fitting notebook used the frozen D021 assignments without regenerating splits. Both the SpO2-only baseline and compact transportable model used ridge logistic regression with the fixed `C = 0.01, 0.1, 1, 10` grid. Inner-fold pooled log loss selected the penalty, and all imputation, missingness indicators, scaling, and categorical encoding were learned within training folds.

Across 50 repeat-level pooled out-of-fold evaluations, the compact model improved ranking and usually improved prediction loss:

| Pair-weighted metric | SpO2-only baseline, median | Compact ridge, median | Compact minus baseline, median | Repeats favoring compact |
|---|---:|---:|---:|---:|
| Brier score | 0.03953 | 0.03868 | -0.00082 | 84% |
| Log loss | 0.16112 | 0.15171 | -0.00939 | 94% |
| PR-AUC | 0.10547 | 0.17411 | +0.06643 | 100% |
| ROC-AUC | 0.73302 | 0.80104 | +0.06877 | 98% |

The compact model is promising but not yet final. The observed event rate was 4.31%, while its median predicted risk was 4.71%; median calibration-in-the-large was -0.105 and median calibration slope was 0.864. These values indicate modest average overprediction and some overfitting. The SpO2-only baseline was closer to calibration-in-the-large but materially weaker for ranking.

At the prespecified 5% threshold, the compact model's median sensitivity was approximately 71%, specificity 76%, PPV 12%, and NPV 98%. These threshold results describe a flagging tradeoff in controlled-desaturation data, not clinical utility or real-world prevalence. Participant-balanced results preserved the direction of the compact model's improvement.

All 606,200 saved out-of-fold predictions passed QA: every one of 6,062 readings was predicted exactly once per repeat and model, all 123 participants were represented, risks were bounded, and exactly one penalty was selected in every outer training set. Independent reload checks reproduced Brier score, log loss, PR-AUC, and ROC-AUC to numerical precision and verified every saved artifact hash.

### Rare-event and small-sample safeguards

The compact occult-hypoxemia model was stress-tested without changing its population or predictors. Four fixed ridge penalties and intercept-corrected Firth logistic regression (FLIC) were evaluated in all 250 frozen outer validation sets. FLIC fit the same compact feature set after fold-specific preprocessing; rank-deficient fold-specific preprocessing columns were removed before Jeffreys-penalized optimization. FLIC is a finite-sample/separation sensitivity and does not correct within-participant dependence.

| Method | Brier score | Log loss | PR-AUC | ROC-AUC | Mean predicted risk |
|---|---:|---:|---:|---:|---:|
| Fixed ridge, C=0.1 | 0.03840 | 0.15060 | 0.17824 | 0.80836 | 5.04% |
| Fixed ridge, C=1 | 0.03862 | 0.15118 | 0.17816 | 0.80541 | 4.39% |
| Nested-tuned ridge | 0.03868 | 0.15171 | 0.17411 | 0.80104 | 4.71% |
| FLIC | 0.03871 | 0.15218 | 0.17592 | 0.80341 | 4.32% |

The results are directionally stable across reasonable estimators: ranking remains near ROC-AUC 0.80 and PR-AUC 0.18, and FLIC produces nearly the observed 4.31% event rate on average. Fixed C=0.1 gives the best out-of-fold loss and ranking in this prespecified sensitivity grid, but its 5.04% mean risk overpredicts the event rate. It is therefore a sensitivity result, not a post hoc replacement selected from the test folds.

Five hundred participant-cluster bootstrap refits were completed for each of fixed C=0.1 and C=1. Optimism-corrected Brier scores were 0.03839 and 0.03863, corrected log losses were 0.14950 and 0.14993, corrected PR-AUC values were 0.18573 and 0.18501, and corrected ROC-AUC values were 0.82748 and 0.82760. These closely corroborate the frozen outer-validation results. The bootstrap is a fixed-specification cross-check, not a bootstrap of the entire nested tuning process.

All 250 FLIC fits met the adjusted-score acceptance rule, FLIC training means were intercept-corrected exactly, all 1,000 bootstrap refits completed, and all saved metrics were finite. The primary model remains pilot evidence because the target still occurs in only 38 participants.

### Richer absolute-error robustness target

The same baseline and compact ridge pipeline was then rerun for `abs(SpO2 - SaO2) >=3` within the same SpO2 92-96% population and the same frozen participant splits. This target contains 778 positive readings from 76 participants, providing substantially richer independent event support than occult hypoxemia.

| Pair-weighted metric | SpO2-only baseline, median | Compact ridge, median | Compact minus baseline, median | Interpretation |
|---|---:|---:|---:|---|
| Brier score | 0.11092 | 0.11611 | +0.00519 | Compact worse |
| Log loss | 0.38025 | 0.40553 | +0.02528 | Compact worse |
| PR-AUC | 0.17165 | 0.19096 | +0.01931 | Compact ranking better |
| ROC-AUC | 0.55982 | 0.59265 | +0.03283 | Compact ranking better |

The richer target confirms that the added bedside variables carry some ordering signal, but it does not support the compact specification as a well-calibrated probability model for broad absolute error. The compact model improves discrimination while worsening both proper scoring rules; its median calibration slope is only 0.225 and calibration-in-the-large is -0.232. The baseline is better calibrated and has lower prediction loss.

This is not contradictory to the occult result. Occult hypoxemia and large absolute error are different outcomes, and a feature set that ranks clinically hidden low SaO2 readings may not transfer unchanged to a heterogeneous mixture of over- and underestimation errors. The robustness target therefore carries methodological weight about pipeline behavior while remaining secondary; it does not validate or refute the occult model by proxy.

### Device and measured-pigmentation subgroup audit

The frozen compact-model out-of-fold predictions were audited at the prespecified 5% flagging threshold. Reporting required at least 100 readings, 10 events, 10 participants, and 5 event-positive participants; calibration-slope and discrimination reporting required at least 30 events, 10 event-positive participants, and 100 nonevents. Uncertainty below comes from 1,000 participant-cluster bootstrap samples of each participant's mean risk across the 50 repeated out-of-fold predictions.

| Supported group | Events / positive participants | Observed risk | Predicted risk | Calibration gap, predicted minus observed (95% CI) | Sensitivity at 5% (95% CI) |
|---|---:|---:|---:|---:|---:|
| MST 5-7 | 37 / 14 | 1.64% | 4.41% | +2.78 pp (+1.35 to +4.32) | 79.1% (64.1 to 93.3) |
| MST 8-10 | 211 / 21 | 13.50% | 5.52% | -8.02 pp (-12.78 to -3.71) | 69.4% (57.4 to 79.8) |
| Device 59 | 26 / 12 | 2.03% | 4.43% | +2.40 pp (+0.84 to +3.62) | 92.9% (81.3 to 100.0) |
| Device 60 | 171 / 29 | 14.36% | 5.52% | -8.78 pp (-15.20 to -3.11) | 68.9% (57.8 to 77.9) |
| Device 73 | 26 / 6 | 4.35% | 4.64% | +0.24 pp (-3.90 to +3.24) | 78.6% (44.4 to 100.0) |

The compact model materially underpredicts occult-hypoxemia risk in MST 8-10 and device 60, with false-negative rates near 31% at the fixed 5% threshold. It improves sensitivity and ranking relative to SpO2 alone in these high-risk groups, but the improvement does not remove the calibration deficit. MST 1-4 is not reportable under the locked support rule because it contains only four events from two positive participants.

Participant-balanced evaluation preserves underprediction for MST 8-10 (-6.38 percentage points) and device 60 (-6.11 points). In contrast, the apparent MST 5-7 overprediction becomes a small underprediction (-0.66 points), showing that its pair-weighted result is sensitive to unequal participant contribution.

As a continuous measured-pigmentation audit, a participant-clustered GEE with the model logit as an offset produced a median odds ratio of 0.711 per 10-unit increase in emitter-site ITA across repeats (2.5th-97.5th repeat quantiles 0.682-0.723). Because higher ITA denotes lighter pigmentation, darker skin retained higher residual occult-hypoxemia risk after accounting for the compact prediction. This is an audit association, not a causal effect or automatic justification for using pigmentation as a predictor. Device 60 and MST 8-10 also contain much of the same event concentration, so device, pigmentation, and protocol/case-mix effects cannot be separated by this audit alone.

The subgroup gate therefore fails for final model freeze. The compact model remains the reference specification for prespecified incremental-block testing, but device and measured-pigmentation enrichment must be evaluated before the decision-curve and final freeze/reject decision. Group-specific thresholds are not introduced post hoc.

### Incremental enrichment-block evaluation

Three OpenOx-only ridge models added device/probe identity, directly measured pigmentation, or perfusion/physiologic context separately to the compact reference. All models used the frozen 50-repeat, five-fold participant allocation, grouped inner tuning, fold-contained preprocessing, pair-weighted primary evaluation, participant-balanced sensitivity, and 1,000 participant-cluster bootstrap samples. Device levels below 2% of an outer-training sample were grouped inside that fold. The context model learned its within-device log2-PI median and IQR inside every training fold; no full-cohort PI standardization entered validation.

| Model | Pair Brier | Pair log loss | PR-AUC | ROC-AUC | Participant-balanced paired log-loss change vs compact | MST 8-10 calibration gap | Device 60 calibration gap | Internal gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Compact reference | 0.03868 | 0.15171 | 0.17411 | 0.80104 | Reference | -8.02 pp | -8.78 pp | Not final |
| Device block | 0.03451 | 0.13044 | 0.32169 | 0.87387 | -0.01431 | -8.02 pp | -0.52 pp | Fails MST-gap gate |
| Pigmentation block | 0.02897 | 0.10594 | 0.51368 | 0.92891 | +0.00202 | +0.25 pp | -4.06 pp | Fails participant-balanced loss gate |
| Perfusion/context block | 0.03293 | 0.12560 | 0.36457 | 0.88446 | -0.01179 | -6.44 pp | -4.55 pp | Advances to utility analysis |

The device block improves overall prediction and largely repairs device 60 calibration, but leaves the MST 8-10 underprediction unchanged; its bootstrap interval for change in the MST gap includes zero. The pigmentation block has the strongest pair-weighted ranking and loss, and reduces both supported high-risk gaps, but its participant-balanced paired log loss is worse than the compact reference and its participant-balanced sensitivity falls substantially. Its apparent value is therefore sensitive to unequal participant contribution and it is not promoted.

The perfusion/context block is the only block satisfying all current gates. Relative to compact, its participant-cluster bootstrap median improvements were -0.00572 in Brier score and -0.02687 in log loss. The reduction in underprediction was +1.54 percentage points for MST 8-10 (95% bootstrap interval +0.39 to +2.64) and +4.20 points for device 60 (+2.66 to +5.70). Median pair-weighted sensitivity was 78.0%, and participant-balanced sensitivity was 82.4%.

This result is promising rather than final. PI is observed in only 54% of eligible readings, its missingness is device-structured, and the context block also contains warming and finger-diameter missingness indicators. A component-ablation sensitivity must show whether the gain depends on actual within-device PI information, structured availability, or the other context fields. The context model is OpenOx-only and cannot replace the compact harmonizable model for BOLD or ENCoDE transfer.

### Context ablation, decision utility, and final internal decision

The full context model and four drop-one ablations were evaluated under the same frozen 50-repeat nested participant allocation. Each ablation removed exactly one prespecified component: actual within-device PI value, the PI-availability indicator, warming, or finger diameter. The compact and full-context out-of-fold predictions were reused; only the four ablations were refit. Decision curves used thresholds from 2% through 10% and 2,000 participant-cluster bootstrap samples.

The full context model retained better point probability estimates than compact. On the repeated out-of-fold summaries, participant-balanced median Brier score was 0.03697 versus 0.04092 and log loss was 0.13838 versus 0.15057. On the consensus participant-cluster bootstrap, the full-minus-compact medians were -0.00403 for Brier score and -0.01306 for log loss. However, the 95% intervals reached +0.00003 and +0.00521, respectively. The prespecified probability-loss gate required supported improvement in both pair- and participant-balanced analyses, so it failed.

Decision-curve findings were favorable but did not override that failure. The full context model had higher point net benefit than compact at all nine thresholds and had bootstrap-supported benefit over the better of flag-all and flag-none across the full 2%-10% range. Neither pair- nor participant-balanced analysis showed bootstrap-supported harm versus compact at any threshold. This supports potential flagging utility, but the full-versus-compact advantage remained too uncertain to justify freezing the larger model.

| Removed component | Participant Brier change, ablated minus full | Participant log-loss change, ablated minus full | Probability degradation supported | Utility degradation supported |
|---|---:|---:|---|---|
| Actual within-device PI value | +0.00313 | +0.01522 | Yes | Yes |
| PI availability indicator | +0.00041 | +0.00123 | Yes | No |
| Warming | -0.00166 | -0.00787 | No | No |
| Finger diameter | -0.00169 | -0.00664 | No | No |

Actual within-device PI is the clearest supported context signal: removing it worsened participant-balanced log loss with a 95% interval above zero and reduced decision utility. PI availability contributes modest probability information but no supported incremental utility. Warming and finger diameter show no supported incremental contribution; their removal has directionally better participant-balanced loss, although uncertainty includes no difference. These are predictive ablation results, not causal physiologic claims.

Under the frozen rule, the full OpenOx-only context model is rejected for progression and no enriched model is frozen. No post hoc reduced context model is substituted. The compact model remains the only harmonizable transportability candidate, explicitly as a pilot model with known OpenOx subgroup underprediction rather than a clinically endorsed model. Before unchanged external evaluation, its final training specification, preprocessing object, penalty, and coefficients must be frozen and serialized.

### Final compact-model derivation and external claim lock

D028 derives one final research-use model rather than averaging or ensembling the 250 outer-fold fits. The feature set, eligibility rule, preprocessing, estimator, and penalty grid remain unchanged. The final penalty was selected from the existing 250 frozen compact-model tuning contexts by minimum mean inner-fold pooled log loss, with mean Brier score and then smaller `C` as deterministic tie-breakers. `C=0.1` was selected: its mean inner log loss was 0.15214 versus 0.15265 for `C=1`, and its mean inner Brier score was 0.03869 versus 0.03897.

The compact pipeline was then fit once on all 6,062 eligible development readings from 123 participants, including 261 events from 38 event-positive participants. The serialized object contains the complete median-imputation-with-indicators, standardization, assigned-sex imputation and encoding, and L2 logistic-regression pipeline. A portable scoring specification separately records the raw feature order, training medians, scaling parameters, category map, transformed coefficients, intercept, software versions, source hashes, and claim boundaries. Reloaded predictions exactly matched the in-memory predictions, and a separate direct implementation of the exported transformations and coefficients independently reproduced the serialized pipeline.

This fit does not create a new performance estimate. Apparent full-development metrics are retained only as software sanity checks; internal-performance claims remain those from the frozen nested participant validation. The model is frozen for unchanged external research evaluation, not clinically endorsed deployment.

D029 locks the external subgroup and interpretation boundary. Overall BOLD performance cannot adjudicate the known device 60 or MST 8-10 calibration deficits because BOLD lacks OpenOx device identity and measured pigmentation. ENCoDE may examine measured-pigmentation behavior only if mapping and event-support gates pass, and it cannot test device 60. A clean overall external calibration result therefore cannot be described as resolving the OpenOx subgroup deficits.

The evidence chronology is also explicit. D020 established the hierarchy placing probability accuracy and calibration above decision-curve utility. The exact D027 intersection rule was formalized at the start of Notebook 18 after the D026 block result but before the four ablations and decision-curve bootstrap results. Cross-analysis PI findings are described as convergence supporting perfusion as relevant measurement context, not as replication of one causal mechanism: the analyses involve different devices, outcomes, and model structures.

### External transportability and ENCoDE assessment

ENCoDE is a credentialed PhysioNet resource from a prospective Duke acute-care cohort. The publication reports 521 SpO2-SaO2 pairs from 128 patients, using charted SpO2 values up to five minutes before ABG. Unlike BOLD, it includes directly measured skin tone: Fitzpatrick, Monk, Von Luschan, Delfin colorimetry, Konica Minolta and Variable spectrophotometry, plus multi-site temperature and image-derived color features. Measurements span sixteen body locations and are stored with linked EHR data in OMOP-format tables. The released v1.0.0 OMOP tables later reconstruct to 615 protocol-conforming pairs from 127 patients; their saturation summaries closely reproduce the publication, but the exact 521-row REDCap analytic extract is not identifiable in the public release.

This makes ENCoDE scientifically valuable, but not a drop-in validation set for every OpenOx model. It is single-center, the darkest tones are underrepresented, skin measurements can be incomplete or anatomically mismatched, and the published cohort is too small to assume adequate occult-hypoxemia event support. Device identity and OpenOx-native perfusion variables are not documented as harmonizable prediction inputs.

| Dataset | Prespecified role | What it can test | What it cannot establish |
|---|---|---|---|
| OpenOx | Development and internal validation | Primary transportable model plus exploratory device/pigmentation/perfusion enrichment | Real-world clinical calibration |
| BOLD | Quantitative external clinical transportability | Unchanged primary model; calibration and discrimination; source-database heterogeneity | Measured-pigmentation effects or device/PI enrichment |
| ENCoDE | Measured-pigmentation replication; conditional risk validation | Direction/magnitude of harmonized Monk and objective-pigmentation associations; unchanged primary model only if feature and event gates pass | Full enriched-model validation, precise subgroup calibration, or a pooled OpenOx/ENCoDE model |

The compact bedside model remains the primary prediction model; the richer OpenOx models remain exploratory internal extensions. This differs from making a full-feature model primary: only 38 OpenOx participants experience the target event, and the compact model better matches intended bedside availability and external evaluation. External datasets will never be added to training before raw-transfer performance is reported.

Before scoring either external dataset, the project will freeze a source-specific crosswalk for variables, units, timing, missingness, and target construction. Raw-transfer discrimination and calibration will be reported separately. Recalibration is model updating, not unchanged external validation, and will be reported only as a distinct secondary analysis. ENCoDE risk-model evaluation will proceed only if the accessible data contain the full primary feature set and enough eligible occult events; otherwise its role remains measured-pigmentation mechanistic replication.

Prediction reporting will follow TRIPOD+AI, which supersedes the original TRIPOD checklist, and will use PROBAST+AI as a structured quality, risk-of-bias, and applicability self-audit.

### Completed BOLD external validation

The hash-verified BOLD 1.0 release contains 49,093 selected SpO2-SaO2 pairs from 44,902 participants. This corrects the earlier project summary of 49,099 pairs from 44,907 participants without indicating file corruption: both the dataset and dictionary exactly match the distributed SHA256 manifest. Before loading external SaO2, D030 froze the source-specific mapping. The five required fields are available with compatible units and coding. SpO2 occurs 0-5 minutes before ABG; available heart and respiratory rates are left-sided by up to 240 minutes. The primary eligibility rule yields 11,880 pairs from 11,441 participants. Heart rate is missing in 9.9% and respiratory rate in 12.6%, handled by the unchanged OpenOx training medians and missingness indicators.

The unchanged D028 model failed raw-transfer probability validation. There were 671 occult-hypoxemia events from 667 participants, an observed rate of 5.65%, while the mean predicted risk was 21.10%. Calibration-in-the-large was -2.114 (95% participant-cluster bootstrap interval -2.231 to -2.012) and calibration slope was 0.119 (0.078-0.162). Brier score was 0.12690, log loss 0.42119, average precision 0.0735 (0.0653-0.0840), and ROC-AUC 0.5680 (0.5447-0.5931).

At the prespecified 5% threshold, sensitivity was 71.4% (67.9%-75.0%), specificity 32.8% (32.0%-33.6%), PPV 6.0% (5.4%-6.5%), and NPV 95.0% (94.4%-95.7%). Participant-balanced estimates were materially unchanged. Decision analysis did not establish a robust advantage across the locked range: flag-all was superior at 2%, the model was not distinguishable from flag-all at 5%, and the model was inferior to flag-none at 10%.

Source-specific interpretation is constrained. eICU supplies 655 of 671 events and reproduces severe overprediction and weak ranking. MIMIC-III has only six eligible events and fails the threshold-reporting gate. MIMIC-IV has ten events, permitting descriptive threshold estimates but not calibration-slope or discrimination reporting. The audit-only harmonized Black race/ethnicity category shows higher observed risk and worse ranking than White, but race/ethnicity is not measured pigmentation and cannot adjudicate the OpenOx MST 8-10 deficit.

The largest transported feature shift is age: eligible BOLD participants average 65.1 years, versus a 27.8-year OpenOx training center. Because the frozen age coefficient is positive, this shift is a prespecified explanation for much of the mean overprediction, not permission to revise the model after observing external outcomes. The compact model is not externally validated for unchanged ICU probability use. Any intercept or slope recalibration is a separate model update and must preserve this failed raw-transfer result.

### Completed BOLD SpO2-only diagnostic comparison

After D028's BOLD failure was known, D034 authorized one explicitly post-validation diagnostic comparator: the already-authorized SpO2-only ridge baseline from Notebook 13. No BOLD outcome informed its derivation. The full-development penalty was selected only from the 250 pre-existing frozen OpenOx baseline tuning contexts using the D028 aggregate inner-loss rule; `C=1.0` minimized mean inner log loss. The 6,062-row OpenOx fit, coefficients, portable scoring specification, and model lock were written before this run loaded BOLD SaO2 or the prior D028 BOLD predictions.

On the identical 11,880-pair BOLD denominator, the SpO2-only baseline predicted 4.38% risk versus 5.65% observed, compared with 21.10% from D028. Its calibration intercept was +0.281 (95% participant-bootstrap interval +0.201 to +0.362) and slope 0.611 (0.529-0.699), versus -2.114 and 0.119 for D028. The baseline therefore underpredicts on average and remains overfit, but its calibration is substantially less distorted than the compact model's.

The baseline also improved probability loss and ranking. Brier score was 0.05226 versus 0.12690, log loss 0.21301 versus 0.42119, average precision 0.0998 versus 0.0735, and ROC-AUC 0.6608 versus 0.5680. Paired participant-bootstrap intervals for baseline-minus-D028 differences excluded zero: Brier -0.07464 (-0.07848 to -0.07094), log loss -0.20819 (-0.22109 to -0.19695), PR-AUC +0.02623 (+0.01698 to +0.03541), and ROC-AUC +0.09283 (+0.06742 to +0.11695). Participant-balanced estimates were materially unchanged.

At the prespecified 5% threshold, the baseline had lower sensitivity (47.8% versus 71.4%) but higher specificity (76.7% versus 32.8%), PPV (10.9% versus 6.0%), NPV (96.1% versus 95.0%), and point net benefit (0.0154 versus 0.0069), while flagging 24.7% rather than 67.4%. These threshold contrasts are descriptive tradeoffs, not authorization to select the baseline clinically after seeing BOLD.

The diagnostic supports a focused explanation for D028's poor BOLD result: the combined added age, sex, heart-rate, and respiratory-rate block materially degraded transport under ICU case-mix and measurement-timing shift relative to the simpler SpO2 signal. It does not identify which added predictor is causal, convert the baseline into a confirmatorily validated or deployment-ready model, or justify outcome-informed model replacement. ENCoDE remains unscorable for this or any occult-risk model because its eligible denominator has zero events.

### Completed ENCoDE external assessment

The four core ENCoDE source files match the distributed SHA256 manifest. D032 freezes the standard concepts, timing, units, outcome, and pigmentation anatomy before target-event and pigmentation-effect estimation. SaO2 is OMOP concept 3016502, SpO2 is 4196147, heart rate is 3027018, respiratory rate is 3024171, and pulse-ox location is custom concept 2000000033. The reconstruction uses the closest SpO2 at or before each SaO2 within five minutes, retains SaO2 and SpO2 from 70% to 100%, and uses only left-sided heart and respiratory rates within four hours. Unknown and toe pulse-ox locations are not imputed into the primary emitter-site-ITA estimand.

The released files yield 615 pairs from 127 patients. Mean SaO2 is 95.72%, mean SpO2 is 97.36%, and mean SaO2-SpO2 bias is -1.65 points (SD 2.10), closely matching the publication's 95.7%, 97.3%, and -1.6 (SD 2.1). The pair-count difference remains a release-versus-analytic-extract limitation rather than evidence of a corrupted download.

Only three pairs occupy SaO2 70-85%, so the lower-interval MST and ITA components fail their prespecified support gates. At SaO2 >85-100%, 612 pairs from 127 patients support the forehead-MST model. Adjusted mean SpO2-SaO2 bias rises from 1.231 points in MST 1-4 to 1.645 in MST 5-7 and 1.991 in MST 8-10. The maximum adjusted contrast is 0.760 points; its simultaneous 95% absolute upper bound is 1.527, narrowly above the 1.5-point research margin. The high-saturation MST result is therefore directionally consistent with greater overestimation in darker skin but formally inconclusive, not evidence that the margin is met.

Exact emitter-site Delfin ITA is available for 425 high-saturation pairs from 78 patients (69.4% coverage), below the locked 80% support threshold. Its adjusted difference is -0.570 points per 100 ITA degrees (95% CI -1.844 to 0.704). Forehead ITA sensitivity is likewise negative at -0.446 (-1.097 to 0.205). Because higher ITA denotes lighter pigmentation, both estimates point toward greater positive SpO2 error in darker measured pigmentation, but both intervals cross zero and the exact objective specification lacks standalone support. Participant-balanced estimates preserve the direction.

The compact-model feature mapping passes: age and sex are complete, and left-sided heart/respiratory-rate values are missing in only 0.6% of the 157 pairs in the locked SpO2 92-96% denominator. However, those 157 pairs from 71 patients contain zero SaO2 <88% events. D033 therefore prohibits D028 scoring: ENCoDE contributes a partial high-saturation mechanistic replication only, not external risk-model calibration, discrimination, or threshold validation. Together with BOLD, the external phase shows failed unchanged clinical probability transport and incomplete but directionally concordant measured-pigmentation evidence.

## Decision register

### D001 — Remove the real-world/laboratory split

**Decision:** Do not organize the primary project around a real-world-versus-controlled-study comparison.

**Reasoning:** The available release and its strongest data are centered on controlled desaturation and prospective collection. A forced split would add complexity without a sufficiently supported comparison group.

**Status:** Accepted.

### D002 — Make predictive modeling secondary

**Decision:** Complete descriptive, device, equity, and physiologic-context analyses before predictive modeling.

**Reasoning:** Prediction should build on a validated cohort and clearly characterized measurement error. It should not substitute for foundational device-performance analysis.

**Status:** Accepted.

### D003 — Defer waveform analysis as a standalone pillar

**Decision:** Use waveform timestamps now only when necessary for pairing quality; reserve full PPG/waveform modeling for Version 2.

**Reasoning:** Full waveform analysis materially expands scope. Timestamp markers are nevertheless necessary to investigate duplicate blood-gas keys.

**Closeout clarification:** The lower-frequency reference markers used for V1 pairing and the raw pulse signals considered later came from different recording sources and served different purposes. The reference markers helped identify the closest blood-gas result. They did not establish which section of the separate raw pulse recording belonged with each commercial-device oxygen measurement.

**Status:** Accepted.

### D004 — Reject the naive encounter/sample join

**Decision:** Do not pair all pulse-oximeter and blood-gas rows using only `encounter_id + sample`.

**Reasoning:** There are 13,117 duplicate blood-gas keys, and 13,093 contain conflicting core measurements. A naive join would multiply observations and could select the wrong reference SaO2.

**Status:** Accepted.

### D005 — Use timestamp resolution for the primary-cohort candidate

**Decision:** Carry forward the subset with reliable waveform markers and a unique nearest blood-gas timestamp as the primary-cohort candidate.

**Reasoning:** It provides direct temporal evidence for resolving otherwise ambiguous blood-gas rows without arbitrary deduplication.

**Status:** Accepted for feasibility; final criteria await analysis-plan lock.

### D006 — Treat 180 seconds as provisional

**Decision:** Use a 180-second maximum timestamp difference for current feasibility calculations, but do not yet treat it as final.

**Reasoning:** The median difference was about 42 seconds and the 90th percentile about 158 seconds. A round 180-second threshold retained approximately 92% of uniquely resolved keys while excluding a long tail. The window is used to choose among duplicated blood-gas rows; it does not mean that an unrelated SpO2 value three minutes away is being paired with a draw. OpenOximetry's sample number still supplies the experimental SpO2/SaO2 link.

**Required confirmation:** Completed. The 60-, 180-, and 300-second sensitivity cohorts were compared before outcome analysis; see D008.

**Status:** Superseded by the accepted hierarchy in D008.

### D007 — Reserve BOLD as a conditional external-validation dataset

**Decision:** Preserve the BOLD dataset as a candidate for external validation of a secondary model only when that model can be expressed using predictors available in both OpenOximetry and BOLD.

**Reasoning:** The hash-verified BOLD 1.0 file contains 49,093 SpO2/SaO2 pairs representing 44,902 ICU patients across MIMIC-III, MIMIC-IV, and eICU-CRD. Its clinical setting is meaningfully different from OpenOximetry's controlled laboratory setting, making it useful for testing transportability. However, BOLD uses charted SpO2 values preceding arterial blood gas measurements by up to 5 minutes, retains only the first pair per hospitalization, and does not document pulse-oximeter device/probe identity or direct skin-pigmentation measures such as Monk or Fitzpatrick. Race and ethnicity cannot be treated as interchangeable with measured skin pigmentation.

**Permitted use:** External validation of a parsimonious model for measurement error or occult hypoxemia based on harmonizable inputs such as SpO2, SaO2-defined outcome, age, sex, and selected shared physiologic variables.

**Not sufficient for:** External validation of device-specific effects, Monk/Fitzpatrick or quantitative-pigmentation effects, perfusion-index effects, or waveform models.

**Validation interpretation:** Because BOLD is a retrospective ICU-EHR cohort with a different pairing process, performance in BOLD should be described as external clinical transportability validation or a domain-shift stress test. Calibration should be evaluated separately from discrimination, and results should be stratified by BOLD source database when possible.

**Evidence:** [BOLD PhysioNet record](https://www.physionet.org/content/blood-gas-oximetry/1.0/) and [BOLD Scientific Data paper](https://www.nature.com/articles/s41597-024-03225-z).

**Status:** Candidate; final suitability depends on the locked feature set, outcome definition, data access, and harmonization audit.

### D008 — Lock the pairing-window sensitivity hierarchy

**Decision:** Use a 180-second maximum timestamp gap for the primary analytic-cohort candidate, a 60-second window for the strict timing sensitivity analysis, and a 300-second window only as an outer stress test.

**Reasoning:** The 60-, 180-, and 300-second cohorts include the same 123 participants, 325 encounters, and 81 raw device labels. Relative to 60 seconds, 180 seconds retains 8,106 additional pairs (39.4%) with closely similar overall bias and A_RMS. Extending to 300 seconds adds only 1,058 pairs (3.7%), and this added band is selectively more hypoxemic and has greater positive bias. Keeping those long-gap observations outside the primary cohort reduces exposure to timing uncertainty without discarding their value as a robustness check.

**Interpretation constraint:** These comparisons are descriptive and do not yet model repeated observations within encounters or participants. The hierarchy locks the pairing-window role, not the final endpoint models or inferential methods.

**Status:** Accepted for analysis-plan lock.

### D009 — Lock the primary device-accuracy endpoint

**Decision:** Define error as SpO2 minus SaO2. Use device-specific A_RMS over paired observations with SaO2 from 70% through 100% inclusive as the primary device-accuracy metric. Report mean bias, error standard deviation, and repeated-measures Bland-Altman limits of agreement as key complementary measures; also report results by SaO2 bands of 70-<80%, 80-<90%, and 90-100%.

**Reasoning:** A_RMS is the principal accuracy metric in FDA pulse-oximeter guidance, while bias and agreement displays show whether similar A_RMS values arise from systematic overestimation or dispersion. In OpenOx, 27,891 pairs (97.2% of the accepted 180-second cohort) fall in the 70-100% range, with representation across all 123 participants and 81 raw device labels. Accuracy worsens at lower saturation, supporting prespecified saturation-band reporting rather than a pooled metric alone.

**Inference constraint:** All uncertainty estimates and tests must account for repeated observations within participants. The exact clustered interval method will be locked with the repeated-measures model. Values below SaO2 70% will be described separately and will not be included in the primary standards-aligned A_RMS calculation.

**Regulatory constraint:** FDA criteria are used as methodological benchmarks only. This retrospective, multi-device repository analysis is not a pivotal manufacturer study and will not make a regulatory pass/fail claim.

**Evidence:** [FDA 2013 pulse-oximeter guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/pulse-oximeters-premarket-notification-submissions-510ks-guidance-industry-and-food-drug), [FDA January 2025 draft guidance](https://www.fda.gov/media/184896/download), and [OpenOximetry Repository v1.1.1](https://www.physionet.org/content/openox-repo/1.1.1/).

**Status:** Endpoint definition accepted; clustered uncertainty implementation remains to be locked.

### D010 — Lock the primary occult-hypoxemia definition

**Decision:** Define primary occult hypoxemia as SaO2 <88% when the paired SpO2 is 92-96% inclusive. Prespecify sensitivity analyses using SpO2 >=92% and using SaO2 <=88% to assess the effect of the upper SpO2 bound and measurement rounding.

**Reasoning:** This is the definition used in the influential Sjoding et al. study and is clinically interpretable. In the 180-second OpenOx cohort it yields 6,062 eligible pairs and 261 events (4.3%) across 38 participants. Expanding to SpO2 >=92% yields 10,849 eligible pairs and 304 events (2.8%); changing the SaO2 boundary to <=88% adds only four primary-window events, showing limited sensitivity to rounding.

**Inference constraint:** The descriptive pair-level event rate is not a participant-level risk estimate. Primary comparisons will require repeated-measures modeling, and device-specific occult-hypoxemia estimates will be reported only for device/probe groups meeting prespecified support criteria.

**Evidence:** [Sjoding et al., NEJM 2020](https://doi.org/10.1056/NEJMc2029240).

**Status:** Accepted for analysis-plan lock.

### D011 — Lock device/probe identity and reporting tiers

**Decision:** Normalize device strings before uniqueness checks, use the integer portion as the base device-model ID, and retain a nonzero decimal suffix as the probe ID. Treat integer-only device values as probe unknown. The primary device-specific reporting entity is the normalized device/probe stratum; do not merge known probes with probe-unknown rows or with one another without external equivalence evidence.

**Accuracy reporting tiers:** Core inferential estimates require at least 30 participants, 300 SaO2 70-100% pairs, and 50 pairs in each of the 70-<80%, 80-<90%, and 90-100% bands. Extended descriptive estimates require at least 20 participants, 200 accuracy-range pairs, and 30 pairs per band. Exploratory estimates require at least 10 participants and 100 accuracy-range pairs. Strata below these thresholds contribute only to pooled analyses.

**Occult-hypoxemia reporting rule:** Publish a standalone device/probe occult-hypoxemia rate only with at least 100 eligible SpO2 92-96% pairs and at least 10 events. Strata below this rule may contribute to pooled or partially pooled repeated-measures models but will not receive unstable standalone rates.

**Reasoning:** Raw formatting inflated 65 normalized device/probe strata to 81 apparent labels in the accepted cohort. Normalization changes no paired-row eligibility and creates no new ambiguous keys. The conservative tiering preserves 11 well-supported core strata, 11 extended descriptive strata, and nine exploratory strata while preventing overinterpretation of 34 sparse strata. Only three strata support a standalone occult rate.

**Metadata constraint:** Preserve `device_type` as an opaque code and preserve raw probe-location codes. Encounter-derived location labels may be used for QA or exploratory analyses, but not as a substitute for missing probe identity until the absent data dictionary or another authoritative codebook is recovered.

**Evidence:** [OpenOximetry Repository v1.1.1 description and release notes](https://www.physionet.org/content/openox-repo/1.1.1/).

**Status:** Accepted for analysis-plan lock.

### D012 — Lock repeated-measures inference

**Decision:** Use the participant as the primary resampling and robust-variance unit. Estimate device/probe bias and A_RMS uncertainty with 2,000 participant-cluster bootstrap replicates and percentile 95% intervals. For pairwise device/probe contrasts, use the same globally resampled participant roster across strata so covariance from participants measured on multiple devices is preserved.

**Continuous-error analysis:** Fit the mean error curve with participant-cluster robust covariance. Use a modified Bland-Altman display of SpO2 minus SaO2 versus SaO2 and explicitly decompose participant, encounter-within-participant, and residual dispersion. The current implementation uses a transparent nested method-of-moments decomposition because dense library encodings are not memory safe in this environment; participant bootstrap remains the inferential foundation.

**Occult-hypoxemia analysis:** Use a binomial GEE clustered by participant with an independence working correlation and robust sandwich covariance. Present standardized marginal risks and risk differences. Do not force standalone device/probe rates below the D011 support rule; sparse strata remain eligible for pooled models.

**Reasoning:** Seventy-four participants have repeated encounters, and the largest device/probe feasibility model assigns substantial residual dispersion to both participant (35.5%) and encounter (26.0%) levels. All 11 core strata completed every prespecified bootstrap replicate, and the occult GEE converged with 261 events across 38 participants.

**Sensitivity:** Compare primary percentile intervals with BCa or studentized bootstrap intervals for the final co-primary estimates. Revisit an exchangeable GEE working correlation under the stable sequential-MKL configuration; robust independence-working inference is the current stable specification.

**Evidence:** [FDA 2013 pulse-oximeter guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/pulse-oximeters-premarket-notification-submissions-510ks-guidance-industry-and-food-drug), [FDA January 2025 draft guidance](https://www.fda.gov/media/184896/download), [Bland and Altman 2007](https://doi.org/10.1080/10543400701329422), and [statsmodels GEE documentation](https://www.statsmodels.org/stable/gee.html).

**Status:** Accepted for analysis-plan lock.

### D013 — Lock pigmentation measures, estimands, and non-disparate margins

**Decision:** Use two complementary co-primary pigmentation specifications: encounter-specific forehead MST grouped as 1-4, 5-7, and 8-10; and continuous encounter-specific ITA at the emitter contact site. Map fingertip rows to dorsal ITA and forehead rows to forehead ITA, taking the median of repeated colorimeter readings. Do not impute primary ear-site ITA from another body site.

**Estimands:** Within SaO2 70-85% and >85-100%, estimate (1) the largest absolute adjusted pairwise difference in mean bias among MST groups and (2) the adjusted mean-bias difference for a 100-degree change in emitter-site ITA. The ITA primary functional form is linear; a restricted cubic spline is a sensitivity analysis.

**Margins:** Use 3.5 percentage points in the 70-85% interval and 1.5 points in the >85-100% interval. A benchmark is met only if the upper limit of the two-sided 95% confidence interval for the absolute contrast is below the corresponding margin. Use participant-cluster inference under D012.

**Secondary measures:** Fitzpatrick is sensitivity/descriptive only. Forehead ITA, melanin index, and alternate Monk body sites are concordance or robustness variables. Race and ethnicity are descriptive social variables and will not be substituted for measured pigmentation.

**Reporting support:** Standalone MST contrasts require at least 10 participants and 50 pairs per SaO2 interval in every MST group. Standalone ITA contrasts require at least 30 participants, 80% emitter-site-ITA coverage, a 100-degree ITA span, and 100 pairs per SaO2 interval. Sparse strata can contribute to pooled or partially pooled models but not standalone benchmark conclusions.

**Reasoning:** Forehead MST covers 95.5% and emitter-site ITA covers 85.3% of frozen cohort rows. Direct measures agree strongly, and the dual specification follows the structure of FDA's January 2025 draft guidance while addressing missing ear-site colorimetry transparently. The outcome remained sealed while these rules were selected.

**Evidence:** [FDA January 2025 draft pulse-oximeter guidance](https://www.fda.gov/media/184896/download) and [OpenOximetry Repository v1.1.1](https://www.physionet.org/content/openox-repo/1.1.1/).

**Status:** Accepted for analysis-plan lock; equity outcome analysis is now authorized only under this specification.

### D014 — Lock perfusion and physiologic-context roles

**Decision:** Analyze device-reported PI only within reporting device/probe strata, using `log2(PI)` as the primary functional form. Do not pool raw PI and do not apply a universal PI <1 cutoff unless an authoritative codebook confirms comparable percent-modulation units. Warming and mapped finger diameter are secondary modifiers without primary imputation.

**Physiologic adjustment:** Prespecify pH, PaCO2, total hemoglobin, carboxyhemoglobin, and methemoglobin, with age and normalized assigned sex as baseline context. Retain heart-rate consensus, respiratory rate, and P50 for sensitivity analyses. Exclude oxygenation-redundant variables and sparse mixed-source blood pressure fields from primary tabular adjustment.

**Reasoning:** PI covers 51.2% of frozen rows but is confined to five strata, and native device ranges are plainly non-comparable. The core physiologic fields are complete, while the excluded and sensitivity variables are either redundant, incomplete, source-ambiguous, or poorly suited to the primary measurement model. All choices were made with SpO2 and error sealed.

**Evidence:** [OpenOximetry Repository v1.1.1](https://www.physionet.org/content/openox-repo/1.1.1/), [FDA January 2025 draft pulse-oximeter guidance](https://www.fda.gov/media/184896/download), and [Low Perfusion and Missed Diagnosis of Hypoxemia by Pulse Oximetry in Darkly Pigmented Skin](https://pubmed.ncbi.nlm.nih.gov/38109495/).

**Status:** Accepted. The analysis-plan lock is complete, and prespecified outcome analyses are authorized.

### D015 — Accept workflow-audit safeguards and revised novelty

**Decision:** Keep pair-weighted primary estimands but report participant-balanced sensitivity estimates; describe all accuracy findings as conditional on a recorded, time-pairable SpO2 value; require every prespecified pigmentation co-primary component to pass its benchmark under an intersection-union interpretation; and retain opaque device codes without manufacturer attribution.

**Reasoning:** Clustered uncertainty alone does not equalize participant contribution, incomplete assignment metadata cannot establish a true device no-read rate, and the growing OpenOximetry literature means raw A_RMS and pigmentation-differential analyses are no longer independently novel. The audit found no material artifact or cohort defect and participant-balanced estimates preserved the device-performance conclusions.

**Landscape:** ISO 80601-2-61:2026 is now the current published standard. FDA's January 2025 guidance remains draft. Hughes et al. 2026 provides the closest same-program device and pigmentation comparison.

**Status:** Accepted. No cohort reopening is required.

### D016 — Lock the pigmentation-result interpretation

**Decision:** Report the five fully supported device/probe conclusions as inconclusive under the four-component intersection-union rule. Report the device 60 MST and device 79 high-saturation ITA findings as supported component-level differences that exceed their research margins, without promoting either to a complete dual-measure device conclusion.

**Reasoning:** Every complete non-disparate-performance conclusion requires supported MST and emitter-site-ITA results in both saturation intervals. Device 60 lacks adequate emitter-site-ITA coverage and device 79 lacks adequate MST-group support. Participant-balanced estimates preserve both component signals, but the data do not authorize filling the missing co-primary evidence through imputation or a substitute pigmentation measure.

**Interpretation constraint:** “Inconclusive” means the available confidence bounds do not establish that every contrast is below its margin; it does not prove disparity. Conversely, a component that exceeds a margin is evidence about that supported estimand only, not a regulatory or manufacturer-level determination.

**Status:** Accepted. Pigmentation and non-disparate-performance analysis is complete.

### D017 — Lock the perfusion/context-result interpretation

**Decision:** Treat the inverse PI-error associations for devices 59 and 64 as supported within-device findings in both saturation intervals. Treat devices 60 and 73 as lacking a clear linear average association and preserve their nonlinear sensitivities. Do not pool native PI, impose a universal PI cutoff, or interpret warming, finger size, hemoglobin, or heart-rate coefficients causally.

**Reasoning:** PI scales differ radically across devices. Devices 59 and 64 show participant-robust associations in both intervals, while devices 60 and 73 have intervals spanning zero and evidence that a single linear form may be inadequate. Warming and finger-diameter intervals include zero. Total hemoglobin and exploratory heart rate retain adjusted associations but may reflect physiologic or design context rather than causal mechanisms.

**Status:** Accepted. The four-pillar analytic core is complete.

### D018 — Lock the secondary prediction design

**Decision:** Predict occult hypoxemia within the SpO2 92-96% denominator. Use SpO2-only as the baseline and a compact transportable bedside feature set of SpO2, age, assigned sex, heart rate, and respiratory rate as the primary model. Restrict device, measured pigmentation, PI, warming, and finger diameter to exploratory OpenOx-enriched models.

**Validation:** Use participant-separated repeated nested cross-validation, fold-contained preprocessing, penalized logistic regression, calibration-first reporting, precision-recall AUC, participant-bootstrap uncertainty, and prespecified risk thresholds. Do not use random row splits, post hoc threshold selection, or unrestricted model/feature searching.

**Leakage boundary:** Exclude SaO2, PaO2, error, ABG-derived results, future information, and post-ABG treatments. Race and ethnicity are audit variables only.

**External boundary:** BOLD is eligible only for unchanged transportability testing of harmonized bedside features after a units, coding, timing, and missingness audit. Recalibration, if performed, is reported separately.

**Status:** Accepted. Internal model development is authorized only under this specification.

### D019 — Add ENCoDE with dataset-specific external-validation claims

**Decision:** Add a formal external transportability phase after internal validation. Use BOLD as the workhorse quantitative evaluation cohort for the frozen primary transportable model. Use ENCoDE primarily to replicate measured-pigmentation associations in acute care and conditionally to evaluate the frozen primary risk model only if exact feature and occult-event feasibility gates pass.

**Reasoning:** ENCoDE uniquely supplies measured skin tone and paired clinical SpO2-SaO2 observations, allowing a stronger test of pigmentation logic than race-based EHR auditing. It does not reproduce OpenOx device, PI, and sensor-context fields, contains only 128 patients and 521 pairs, and may contain too few events in the locked SpO2 92-96% denominator for stable prediction metrics. Calling it unconditional full-model validation would therefore overstate its evidentiary role.

**Model hierarchy:** Keep the compact transportable bedside model primary. Keep device, measured-pigmentation, and perfusion-enriched models exploratory and internally validated only. Do not pool BOLD or ENCoDE into OpenOx model training before unchanged raw-transfer evaluation.

**Evaluation boundary:** Report calibration and discrimination separately in every external dataset. Any recalibration is a clearly labeled model update after raw-transfer results. Race/ethnicity is never substituted for measured pigmentation.

**Reporting:** Use TRIPOD+AI for reporting and PROBAST+AI for the structured quality/risk-of-bias/applicability audit.

**Evidence:** [ENCoDE PhysioNet record](https://www.physionet.org/content/encode-skin-color/1.0.0/), [ENCoDE prospective cohort paper](https://pubmed.ncbi.nlm.nih.gov/39268149/), [TRIPOD+AI](https://www.bmj.com/content/385/bmj-2023-078378), and [PROBAST+AI](https://www.bmj.com/content/388/bmj-2024-082505).

**Status:** Accepted. The roadmap now contains an explicit external transportability and validation phase.

### D020 — Amend the prediction lock for sparse clustered outcomes

**Decision:** Restrict the prediction population to SpO2 92-96%, retain occult hypoxemia as the headline but explicitly pilot target, and add `abs(error) >=3` within the same population as a richer-event pipeline robustness target.

**Model safeguards:** Keep fixed low-dimensional ridge logistic regression primary; add FLIC or FLAC as a separation/finite-sample sensitivity; test enrichment blocks separately; and prohibit unrestricted selection, interaction, or nonlinear searches. Firth penalization is not treated as a clustering correction.

**Validation safeguards:** Use 50 repeats of five-fold participant-grouped cross-validation stratified by participant event status, pooled out-of-fold metrics within each repeat, grouped inner tuning, participant-balanced fitting sensitivity, and at least 500 participant-cluster bootstrap refits. Treat .632+ as a secondary loss-estimation cross-check only when out-of-bag event support is adequate.

**Interpretation safeguards:** Separate pigmentation disparate-performance findings from pigmentation feature-value findings. Add decision-curve net benefit at 2%-10% thresholds as a secondary analysis, not as proof of clinical utility.

**Evidence:** [Puhr et al. on Firth prediction correction](https://pubmed.ncbi.nlm.nih.gov/28295456/), [Heinze and Schemper on separation](https://onlinelibrary.wiley.com/doi/10.1002/sim.1047), [Riley et al. on prediction-model sample size](https://pmc.ncbi.nlm.nih.gov/articles/PMC6710621/), [Efron and Tibshirani on .632+](https://www.tandfonline.com/doi/abs/10.1080/01621459.1997.10474007), and [decision-curve reporting guidance](https://pubmed.ncbi.nlm.nih.gov/27247223/).

**Status:** Accepted. Model fitting is authorized only after the participant-stratified resampling allocation passes QA.

### D021 — Freeze the nested participant-level resampling allocation

**Decision:** Use the saved 50-repeat, five-fold outer allocation and four-fold inner allocation for all internal prediction work. Stratify participants using the mutually exclusive occult-positive, absolute-error-≥3-only, and neither categories.

**QA result:** All 250 outer validation sets are unique; every participant appears once per repeat; each outer fold contains 7-8 occult-positive and 14-16 richer-target-positive participants; all 1,000 inner validation sets contain positive participants; and no outer-validation participant enters its corresponding inner allocation.

**Interpretation:** Participant stratification balances independent event contributors, not the number of repeated positive readings. Unequal reading counts are retained transparently. Metrics must be pooled across outer folds within each repeat.

**Reproducibility:** The outer and inner assignment manifests are content-hashed and saved with base seed `20260726`. Saved assignments supersede ad hoc regeneration.

**Status:** Accepted. Baseline and compact ridge model fitting are now authorized under D018-D021.

### D022 — Treat the compact ridge result as promising but provisional

**Decision:** Carry the compact transportable ridge model forward to the prespecified small-sample, subgroup, and robustness checks. Do not yet freeze final coefficients or claim external readiness.

**Evidence:** Relative to the SpO2-only baseline, the compact model improved median pair-weighted Brier score by 0.00082, log loss by 0.00939, PR-AUC by 0.06643, and ROC-AUC by 0.06877. Ranking improved in nearly every repeat, but median calibration slope was 0.864 and median predicted risk modestly exceeded the observed event rate.

**Interpretation:** The added bedside variables contain useful signal, but the 38-positive-participant effective sample and calibration shrinkage require the already-prespecified FLIC/FLAC, clustered-bootstrap, richer-target, and subgroup checks. Repeat quantiles are resampling-distribution summaries, not confidence intervals from 50 independent studies.

**Status:** Accepted as an internal-validation checkpoint. Final model selection remains open.

### D023 — Retain the compact occult model after rare-event safeguards

**Decision:** Retain the compact occult-hypoxemia ridge model for the remaining subgroup and incremental-block checks. Keep nested-tuned ridge as the primary internal-validation analysis, with fixed-penalty ridge, FLIC, and participant-cluster bootstrap as prespecified sensitivities. Do not select C=0.1 post hoc as a new primary specification.

**Evidence:** Across frozen out-of-fold predictions, fixed ridge C=0.1, fixed ridge C=1, nested-tuned ridge, and FLIC produced ROC-AUC values of 0.808, 0.805, 0.801, and 0.803 and PR-AUC values of 0.178, 0.178, 0.174, and 0.176. Fixed-specification cluster-bootstrap optimism correction produced Brier scores of 0.03839-0.03863 and ROC-AUC values of 0.82748-0.82760.

**Interpretation:** The primary signal is not an artifact of one penalty or ordinary maximum-likelihood behavior. FLIC corrects finite-sample/separation bias but not clustering; the cluster bootstrap addresses participant resampling but does not repeat the complete tuning pipeline. Agreement between these checks is reassuring without overcoming the 38-positive-participant limitation.

**Status:** Accepted. The occult model remains promising, pilot-level internal evidence rather than a finalized clinical model.

### D024 — Keep the absolute-error target as a diagnostic robustness analysis

**Decision:** Retain `abs(SpO2 - SaO2) >=3` as a secondary pipeline robustness outcome, but do not promote the current compact model for this target and do not use it as proxy validation of the occult model.

**Evidence:** With 778 events across 76 participants, the compact model improved median PR-AUC from 0.172 to 0.191 and ROC-AUC from 0.560 to 0.593, but worsened median Brier score from 0.11092 to 0.11611 and log loss from 0.38025 to 0.40553. Its median calibration slope was 0.225.

**Interpretation:** Additional bedside variables contain limited ranking information for large absolute error, but the unchanged compact linear specification is poorly calibrated for this broader, bidirectional outcome. Discrimination and probability accuracy must remain separate claims.

**Status:** Accepted as a robustness finding. No final absolute-error prediction model is selected.

### D025 — Do not freeze the compact model after the subgroup audit

**Decision:** Retain the compact occult-hypoxemia model as the reference for prespecified device, pigmentation, and perfusion/context incremental-block tests, but do not freeze its final specification or coefficients. Do not introduce post hoc group-specific thresholds.

**Evidence:** At the fixed 5% threshold, the participant-cluster bootstrap estimated calibration gaps of -8.02 percentage points in MST 8-10 and -8.78 points in device 60, with sensitivities of 69.4% and 68.9%. Participant-balanced analysis preserved underprediction in both groups. Continuous emitter-site ITA remained associated with residual outcome risk after offsetting the compact prediction (median odds ratio 0.711 per 10-unit higher ITA).

**Interpretation:** The compact model improves high-risk-group sensitivity and ranking over SpO2 alone but does not provide reliable subgroup probability calibration. Event concentration and overlap between device 60 and MST 8-10 prevent causal attribution. Pigmentation disparity and pigmentation feature value remain separate questions.

**Status:** Accepted as an internal gate. Final model selection remains open pending separate incremental-block and decision-curve analyses.

### D026 — Advance the perfusion/context block to utility analysis

**Decision:** Carry the perfusion/context ridge model forward alongside the compact reference for a component-ablation sensitivity and prespecified decision-curve analysis. Do not promote the device or pigmentation blocks, do not accumulate the three blocks into a full model, and do not freeze final coefficients.

**Evidence:** The context block improved median pair-weighted Brier score from 0.03868 to 0.03293, log loss from 0.15171 to 0.12560, PR-AUC from 0.17411 to 0.36457, and ROC-AUC from 0.80104 to 0.88446. Participant-balanced paired Brier and log-loss changes were -0.00387 and -0.01179. Bootstrap intervals supported reductions in underprediction for both MST 8-10 and device 60. The device block did not improve the MST 8-10 calibration gap, and the pigmentation block worsened participant-balanced paired log loss by 0.00202.

**Safeguards:** Within-device PI centering and scaling are fit only in training folds. The next analysis must separate actual PI information from PI availability and the warming/finger-diameter components, then compare net benefit from 2%-10% against flag-all and flag-none. The context model remains OpenOx-only; the compact model remains the harmonizable external-evaluation candidate.

**Status:** Accepted as an internal candidate-selection gate. No final OpenOx prediction model is frozen.

### D027 — Reject the full OpenOx-only context model after utility analysis

**Decision:** Do not freeze or progress the full perfusion/context prediction model. Do not substitute a post hoc reduced context model. Retain the compact bedside model as the sole harmonizable candidate for a prespecified final refit and external transportability testing, with its pilot and subgroup-calibration limitations carried forward.

**Evidence:** The full context model improved participant-balanced point estimates versus compact, but participant-cluster 95% intervals for the Brier and log-loss differences included zero: -0.00403 (-0.00811 to +0.00003) and -0.01306 (-0.02739 to +0.00521). It exceeded flag-all and flag-none with bootstrap support at all thresholds from 2%-10%, had positive point net benefit versus compact at all nine thresholds, and showed no supported harm versus compact. The probability-loss gate nevertheless failed under the prespecified intersection rule.

**Ablation interpretation:** Actual within-device PI value is supported for probability accuracy and utility. PI availability has a small supported probability contribution but no supported utility contribution. Warming and finger diameter have no supported incremental contribution. These findings do not authorize selecting a new PI-only model after observing the ablations.

**Status:** Accepted. Internal enriched-model selection is closed; no OpenOx-only enriched prediction model is frozen.

### D028 — Freeze and serialize one final compact external-evaluation model

**Decision:** Fit one compact pipeline on the complete locked development population. Do not average coefficients or ensemble the 250 outer-fold models. Select the final ridge penalty from the original grid using the lowest mean inner pooled log loss across all 250 frozen compact tuning contexts, with mean Brier score and then smaller `C` as tie-breakers. Do not reopen features, preprocessing, thresholds, or model class.

**Evidence:** `C=0.1` had the lowest aggregate inner loss: mean log loss 0.15214 and mean Brier score 0.03869, compared with 0.15265 and 0.03897 for `C=1`. The final pipeline was fit once on 6,062 eligible readings from 123 participants, with 261 events from 38 participants. The serialized pipeline, portable scoring specification, coefficients, preprocessing state, software versions, and source hashes were saved. Reloaded predictions matched exactly, and an independent manual implementation reproduced all scores within numerical tolerance.

**Interpretation:** The refit supplies one immutable object for raw external scoring; it does not replace nested cross-validation as the internal performance estimate. The model remains a pilot research risk flag and is not a diagnostic product or ABG replacement.

**Status:** Accepted. Phase 5 internal development is complete; the compact model is frozen for unchanged external evaluation.

### D029 — Lock external subgroup and evidence-interpretation boundaries

**Decision:** Do not interpret acceptable overall BOLD or ENCoDE performance as resolving the known OpenOx device 60 or MST 8-10 calibration deficits. BOLD cannot test either deficit directly because it lacks OpenOx device identity and measured pigmentation. ENCoDE may assess measured-pigmentation behavior only if harmonization and event-support gates pass, and cannot test device 60.

**Chronology and mechanism boundary:** D020 established the probability/calibration-over-utility hierarchy. The exact D027 intersection rule was formalized before Notebook 18 ablation and bootstrap results, but after D026 identified the context block as the only advancing block. PI evidence across the descriptive and predictive analyses is cross-analysis convergence, not a replicated causal mechanism, because the devices, outcomes, and model structures differ.

**Status:** Accepted. These limitations must appear prominently in external-validation reporting and the manuscript.

### D030 — Freeze the BOLD source crosswalk before external outcome analysis

**Decision:** Map BOLD `SpO2`, `admission_age`, `vitals_heart_rate`, `vitals_resp_rate`, and `sex_female` to the unchanged D028 inputs. Retain only SpO2 92-96% inclusive and define the external outcome as SaO2 below 88%. Use `unique_subject_id` for clustering. Preserve the distributed selected SpO2 timing of 0-5 minutes before ABG and the available left-sided vitals, which may be up to 240 minutes old. Apply the frozen OpenOx training imputers, scalers, encoding, coefficients, and intercept without refitting.

**Evidence:** The dataset and dictionary hashes match the supplied BOLD manifest. The pair key is unique, SpO2 is complete, every SpO2 delta is between -5 and 0 minutes, every available heart/respiratory-rate delta is between -240 and 0 minutes, age is in years, and sex coding is restricted to 0/1. The eligible pre-outcome cohort contains 11,880 rows from 11,441 participants.

**Status:** Accepted and frozen before loading BOLD SaO2 for performance analysis.

### D031 — Record failed unchanged BOLD probability transport

**Decision:** Do not claim that the D028 compact model externally validates as an unchanged ICU probability model. Preserve BOLD raw-transfer results as the external finding and prohibit outcome-informed feature or coefficient revision from being relabeled validation. Any later recalibration is explicit model updating.

**Evidence:** Across 11,880 eligible readings, observed risk was 5.65% and mean predicted risk was 21.10%; calibration intercept was -2.114 and slope 0.119. PR-AUC was 0.0735 and ROC-AUC 0.5680. The locked 5% threshold yielded 71.4% sensitivity, 32.8% specificity, 6.0% PPV, and 95.0% NPV. All 1,000 participant-cluster bootstrap replicates completed, participant-balanced estimates were materially unchanged, and a separate scripted QA path reproduced headline metrics and artifact hashes.

**Utility and heterogeneity:** The model did not robustly outperform the appropriate default strategy across 2%-10%. eICU dominated event support; MIMIC-III and MIMIC-IV did not support full standalone validation. Race/ethnicity results remain audit-only and cannot be translated into pigmentation claims.

**Status:** Accepted. BOLD raw-transfer validation is complete and unsuccessful for unchanged probability use.

### D032 — Freeze the ENCoDE source and pigmentation crosswalk

**Decision:** Use the hash-verified ENCoDE v1.0.0 OMOP release. Pair concept 4196147 SpO2 backward to concept 3016502 SaO2 within five minutes; retain both values from 70% to 100%; and map only left-sided heart rate and respiratory rate within four hours. Use median forehead MST for the locked MST groups. Map known left/right finger placements to ipsilateral dorsal-finger Delfin ITA and forehead placements to forehead ITA. Do not substitute toe or unknown locations in the primary emitter-site-ITA analysis.

**Evidence:** All four core file hashes match `SHA256SUMS.txt`. The official record, tutorial, and publication establish the concept semantics, 0-5-minute pre-ABG pairing, 70%-100% range restriction, and within-admission clinical context. Crosswalk QA confirms unique pair identifiers, nonfuture covariates, valid units and ranges, and anatomy-preserving pigmentation mapping.

**Status:** Accepted. The crosswalk is frozen for ENCoDE target-event and pigmentation-effect estimation.

### D033 — Record partial ENCoDE pigmentation replication and failed risk gate

**Decision:** Report the supported high-saturation forehead-MST result and objective-pigmentation sensitivities as a partial mechanistic replication. Do not claim complete dual-interval non-disparate performance, a supported primary emitter-site-ITA conclusion, or unchanged D028 risk-model validation.

**Evidence:** The release reconstructs 615 protocol-conforming pairs from 127 patients, versus 521/128 in the publication's earlier analytic extract, with closely matching saturation summaries. Only three pairs fall at SaO2 70-85%. At >85-100%, adjusted bias rises from 1.231 points in MST 1-4 to 1.991 in MST 8-10; the maximum contrast is 0.760 with a simultaneous 95% upper bound of 1.527 against the 1.5-point margin. Exact emitter-site ITA covers 69.4% and has an adjusted -0.570-point difference per 100 degrees (95% CI -1.844 to 0.704). The locked SpO2 92-96% denominator contains 157 pairs, 71 patients, and zero occult events.

**Status:** Accepted. ENCoDE assessment is complete as partial mechanistic replication; quantitative risk-model validation is not supported.

### D034 — Record the BOLD SpO2-only post-validation diagnostic

**Decision:** Retain the frozen SpO2-only BOLD comparison as an exploratory diagnostic of D028 transport failure. Do not relabel it as a second confirmatory external validation, do not select it as a rescue model, and do not revise D028 or initiate BOLD recalibration within this analysis.

**Evidence:** The baseline specification was selected solely from pre-existing frozen OpenOx tuning artifacts and locked before BOLD outcome access within the run. On the identical 11,880-pair BOLD denominator, it predicted 4.38% risk versus 5.65% observed, with calibration intercept +0.281, slope 0.611, Brier 0.05226, log loss 0.21301, PR-AUC 0.0998, and ROC-AUC 0.6608. Every paired participant-bootstrap interval for its Brier, log-loss, PR-AUC, and ROC-AUC difference versus D028 excluded zero. Independent QA passed all 18 checks.

**Interpretation:** The combined compact predictor block materially degraded BOLD transport relative to SpO2 alone. The baseline still underpredicts overall and has a slope below one, so this result diagnoses the failed multivariable transport rather than establishing a clinically ready alternative.

**Status:** Accepted as post-validation diagnostic evidence. No model promotion or updating is authorized.

## Open methodological questions

- Can the missing OpenOximetry data dictionary or another authoritative codebook resolve device-type, probe-location, and PI-scale codes?
- Can expected-reading or waveform metadata support a defensible device availability/no-read analysis, rather than the current limited assignment-pairing proxy?
- Should a separately prespecified BOLD intercept/slope recalibration study be performed, given that it would be model updating rather than external validation?
- What dataset-construction and case-mix factors explain the concentration of 655 of 671 eligible BOLD events in eICU?
- What release-construction or REDCap-selection rule explains the public v1.0.0 reconstruction of 615 protocol-conforming pairs from 127 patients versus the publication's 521 pairs from 128 patients?

## Reproducible artifacts

### Notebooks

- `01_data_inventory.ipynb` — source-table inventory, keys, coverage, and initial feasibility.
- `01b_pairing_diagnostics.ipynb` — duplicate-key diagnosis, waveform timestamp recovery, provisional pairing cohort, and QA.
- `01c_pairing_window_sensitivity.ipynb` — nested 60-, 180-, and 300-second cohort comparison, incremental-band diagnostics, figures, and QA.
- `02_endpoint_feasibility.ipynb` — standards and literature review translated into reproducible accuracy-range, occult-hypoxemia, and device-support feasibility checks.
- `03_device_harmonization.ipynb` — raw-label normalization, device/probe parsing, encounter-assignment QA, cohort-impact check, and reporting-tier support analysis.
- `04_repeated_measures_feasibility.ipynb` — cluster-structure profile, 2,000-replicate participant bootstrap, continuous-error hierarchy check, occult-hypoxemia GEE, method lock, and QA.
- `05_pigmentation_measure_lock.ipynb` — predictor-only pigmentation mapping, missingness, repeated-colorimeter QA, cross-measure agreement, device support, estimand/margin lock, and outcome-seal QA.
- `06_perfusion_context_lock.ipynb` — predictor-only PI, warming, sensor-fit, baseline, and physiology mapping; scale/support diagnostics; variable-role lock; and outcome-seal QA.
- `07_device_performance.ipynb` — locked 11-stratum bias, precision, A_RMS, participant-cluster bootstrap intervals, saturation-band profiles, modified Bland-Altman displays, reconciliation, and QA.
- `07b_workflow_audit.ipynb` — artifact-chain audit, participant-balanced sensitivity, recorded-reading completeness proxy, current-landscape safeguards, and QA.
- `07c_device_descriptive_tiers.ipynb` — extended and exploratory device-tier estimates, saturation-band profiles, reporting constraints, and QA.
- `08_occult_hypoxemia.ipynb` — locked event definition, support-gated raw rates, participant-cluster GEE standardized risks and risk differences, sensitivities, and QA.
- `09_pigmentation_non_disparate.ipynb` — locked MST and emitter-site-ITA models, simultaneous margins, intersection-union conclusions, participant-balanced and alternate-measure sensitivities, spline checks, and QA.
- `10_perfusion_physiologic_context.ipynb` — within-device PI-doubling models, participant-balanced and nonlinear sensitivities, warming, sensor-fit, physiologic-context associations, and QA.
- `11_prediction_plan_lock.ipynb` — target support, temporally eligible feature tiers, leakage exclusions, participant-separated validation rules, BOLD crosswalk, and outcome-model seal.
- `11b_prediction_small_sample_amendment.ipynb` — participant-level event support, restricted-population clarification, rare-event safeguards, richer target, decision-curve plan, and QA.
- `12_prediction_resampling_qa.ipynb` — frozen nested participant assignments, target-support audit, leakage checks, hashes, figure, and QA.
- `13_prediction_baseline_compact_ridge.ipynb` — frozen nested validation of the SpO2-only baseline and compact transportable ridge model, fold-contained preprocessing/tuning, pooled repeat metrics, threshold results, figures, saved predictions, and QA.
- `14_prediction_small_sample_safeguards.ipynb` — fixed-penalty ridge sensitivity, validated FLIC implementation, 250 frozen outer-fold FLIC fits, 1,000 participant-cluster bootstrap refits, optimism correction, figure, and QA.
- `15_prediction_abs3_robustness.ipynb` — frozen nested validation for the richer absolute-error-at-least-3 target using the unchanged baseline/compact tiers, saved predictions, calibration and discrimination results, figure, and QA.
- `16_prediction_subgroup_audit.ipynb` — support-gated device and measured-pigmentation calibration, sensitivity, false-negative, participant-balanced, cluster-bootstrap, and residual-ITA audits of frozen out-of-fold predictions.
- `17_prediction_enrichment_blocks.ipynb` — separate device, measured-pigmentation, and perfusion/context ridge blocks under frozen nested validation; corrected participant-balanced metrics; fold-contained PI scaling; cluster-bootstrap promotion gates; and QA.
- `18_prediction_context_ablation_utility.ipynb` — four prespecified drop-one context ablations, 2%-10% pair- and participant-balanced decision curves, 2,000 participant-cluster bootstrap samples, component evidence, freeze/reject gate, figure, hashes, and QA.
- `19_prediction_final_compact_lock.ipynb` — D028 final penalty derivation, one full-development compact refit, pipeline serialization, portable scoring contract, coefficients, hashes, exact reload check, and QA.
- `20_bold_external_validation.ipynb` — D030 pre-outcome crosswalk freeze, unchanged D028 scoring, overall/source/race support gates, participant-balanced sensitivity, 1,000 participant-cluster bootstrap intervals, decision curves, and separate scripted QA.
- `21_encode_external_validation.ipynb` — D032 ENCoDE hash and crosswalk lock, released-pair reconstruction, support-gated high-saturation MST and ITA replication, participant-balanced sensitivity, conditional risk gate, figure, manifest, and separate scripted QA.
- `22_bold_spo2_baseline_validation.ipynb` — D034 post-validation SpO2-only OpenOx fit lock, unchanged BOLD scoring, paired baseline-versus-D028 participant bootstrap, calibration-by-SpO2 table, chronology audit, artifact hashes, and separate scripted QA.

### BOLD external-validation outputs

- `bold_external_validation/bold_crosswalk_lock.json`
- `bold_external_validation/bold_external_support.csv`
- `bold_external_validation/bold_external_performance.csv`
- `bold_external_validation/bold_external_bootstrap_intervals.csv`
- `bold_external_validation/bold_external_decision_curve.csv`
- `bold_external_validation/bold_external_feature_shift.csv`
- `bold_external_validation/bold_external_predictions.csv.gz`
- `bold_external_validation/bold_external_artifact_manifest.csv`
- `bold_external_validation/bold_external_independent_qa.csv`

### ENCoDE external-validation outputs

- `encode_external_validation/encode_crosswalk_lock.json`
- `encode_external_validation/encode_source_hash_qa.csv`
- `encode_external_validation/encode_pair_reconstruction.csv`
- `encode_external_validation/encode_pigmentation_support.csv`
- `encode_external_validation/encode_mst_adjusted_group_bias.csv`
- `encode_external_validation/encode_mst_pairwise_contrasts.csv`
- `encode_external_validation/encode_mst_primary_benchmark.csv`
- `encode_external_validation/encode_ita_associations.csv`
- `encode_external_validation/encode_risk_validation_gate.csv`
- `encode_external_validation/encode_analysis_pairs.csv.gz`
- `encode_external_validation/encode_pigmentation_replication.png`
- `encode_external_validation/encode_external_summary.json`
- `encode_external_validation/external_validation_evidence_summary.csv`
- `encode_external_validation/encode_external_artifact_manifest.csv`
- `encode_external_validation/encode_external_independent_qa.csv`

### BOLD SpO2-only diagnostic outputs

- `bold_spo2_baseline_validation/baseline_model_lock.json`
- `bold_spo2_baseline_validation/openox_spo2_only_occult_ridge_v1_scoring_spec.json`
- `bold_spo2_baseline_validation/baseline_penalty_selection.csv`
- `bold_spo2_baseline_validation/baseline_coefficients.csv`
- `bold_spo2_baseline_validation/bold_baseline_performance.csv`
- `bold_spo2_baseline_validation/bold_baseline_vs_compact.csv`
- `bold_spo2_baseline_validation/bold_baseline_bootstrap_intervals.csv`
- `bold_spo2_baseline_validation/bold_baseline_vs_compact_bootstrap_differences.csv`
- `bold_spo2_baseline_validation/bold_baseline_calibration_by_spo2.csv`
- `bold_spo2_baseline_validation/bold_baseline_predictions.csv.gz`
- `bold_spo2_baseline_validation/baseline_run_audit.json`
- `bold_spo2_baseline_validation/bold_baseline_artifact_manifest.csv`
- `bold_spo2_baseline_validation/bold_baseline_independent_qa.csv`

### Important aggregate outputs

- `outputs/tables/data_inventory.csv`
- `outputs/tables/pairing_feasibility.csv`
- `outputs/tables/bloodgas_duplicate_diagnostics.csv`
- `outputs/tables/bloodgas_conflict_by_column.csv`
- `outputs/tables/time_pairing_feasibility.csv`
- `outputs/tables/time_pairing_gap_quantiles.csv`
- `outputs/tables/time_resolved_cohort_coverage.csv`
- `outputs/tables/pairing_window_sensitivity_summary.csv`
- `outputs/tables/pairing_window_incremental_summary.csv`
- `outputs/tables/pairing_window_skin_distribution.csv`
- `outputs/tables/pairing_window_device_distribution.csv`
- `outputs/tables/endpoint_sao2_range_coverage.csv`
- `outputs/tables/endpoint_occult_hypoxemia_feasibility.csv`
- `outputs/tables/endpoint_device_support.csv`
- `outputs/tables/device_label_normalization_summary.csv`
- `outputs/tables/device_label_normalization_audit.csv`
- `outputs/tables/device_assignment_coverage.csv`
- `outputs/tables/probe_location_crosswalk_audit.csv`
- `outputs/tables/device_normalization_cohort_impact.csv`
- `outputs/tables/device_probe_inference_support.csv`
- `outputs/tables/device_probe_support_summary.csv`
- `outputs/tables/repeated_measures_cluster_overview.csv`
- `outputs/tables/repeated_measures_cluster_distribution.csv`
- `outputs/tables/core_device_participant_bootstrap.csv`
- `outputs/tables/continuous_error_hierarchy_feasibility.csv`
- `outputs/tables/continuous_error_nested_variance_components.csv`
- `outputs/tables/occult_gee_feasibility.csv`
- `outputs/tables/occult_gee_coefficients.csv`
- `outputs/tables/repeated_measures_method_lock.csv`
- `outputs/tables/pigmentation_colorimeter_repeats.csv`
- `outputs/tables/pigmentation_measure_coverage.csv`
- `outputs/tables/pigmentation_emitter_site_mapping.csv`
- `outputs/tables/pigmentation_measure_agreement.csv`
- `outputs/tables/pigmentation_ita_range.csv`
- `outputs/tables/pigmentation_mst_group_support.csv`
- `outputs/tables/pigmentation_device_support.csv`
- `outputs/tables/pigmentation_measure_lock.csv`
- `outputs/tables/pigmentation_measure_lock_qa.csv`
- `outputs/tables/context_covariate_coverage.csv`
- `outputs/tables/finger_diameter_coverage.csv`
- `outputs/tables/perfusion_index_device_support.csv`
- `outputs/tables/warming_device_support.csv`
- `outputs/tables/finger_diameter_device_support.csv`
- `outputs/tables/heart_rate_consensus_qa.csv`
- `outputs/tables/physiology_range_qa.csv`
- `outputs/tables/context_variable_lock.csv`
- `outputs/tables/context_covariate_lock_qa.csv`
- `outputs/tables/device_performance_core_results.csv`
- `outputs/tables/device_performance_by_sao2_band.csv`
- `outputs/tables/device_performance_reconciliation.csv`
- `outputs/tables/device_performance_core_qa.csv`
- `outputs/tables/workflow_audit_findings.csv`
- `outputs/tables/device_weighting_sensitivity.csv`
- `outputs/tables/device_assignment_pairing_completeness_proxy.csv`
- `outputs/tables/project_artifact_audit.csv`
- `outputs/tables/device_performance_all_reporting_tiers.csv`
- `outputs/tables/device_performance_descriptive_tiers_by_sao2_band.csv`
- `outputs/tables/device_descriptive_tiers_qa.csv`
- `outputs/tables/occult_hypoxemia_overall_summary.csv`
- `outputs/tables/occult_hypoxemia_overall_gee.csv`
- `outputs/tables/occult_hypoxemia_reportable_raw_rates.csv`
- `outputs/tables/occult_hypoxemia_standardized_device_risks.csv`
- `outputs/tables/occult_hypoxemia_device_risk_differences.csv`
- `outputs/tables/occult_hypoxemia_definition_sensitivity.csv`
- `outputs/tables/occult_hypoxemia_qa.csv`
- `outputs/tables/pigmentation_mst_adjusted_group_bias.csv`
- `outputs/tables/pigmentation_mst_pairwise_contrasts.csv`
- `outputs/tables/pigmentation_mst_primary_benchmarks.csv`
- `outputs/tables/pigmentation_ita_primary_benchmarks.csv`
- `outputs/tables/pigmentation_intersection_union_components.csv`
- `outputs/tables/pigmentation_intersection_union_summary.csv`
- `outputs/tables/pigmentation_mst_participant_balanced_sensitivity.csv`
- `outputs/tables/pigmentation_ita_participant_balanced_sensitivity.csv`
- `outputs/tables/pigmentation_forehead_ita_sensitivity.csv`
- `outputs/tables/pigmentation_mst_weighting_sensitivity.csv`
- `outputs/tables/pigmentation_ita_weighting_sensitivity.csv`
- `outputs/tables/pigmentation_emitter_ita_missingness_context.csv`
- `outputs/tables/pigmentation_fitzpatrick_descriptive_sensitivity.csv`
- `outputs/tables/pigmentation_ita_spline_sensitivity.csv`
- `outputs/tables/pigmentation_non_disparate_qa.csv`
- `outputs/tables/perfusion_pi_device_models.csv`
- `outputs/tables/perfusion_pi_primary_effects.csv`
- `outputs/tables/physiologic_context_primary_effects.csv`
- `outputs/tables/physiologic_context_sensitivity_effects.csv`
- `outputs/tables/perfusion_physiologic_context_qa.csv`
- `outputs/tables/prediction_target_lock.csv`
- `outputs/tables/prediction_feature_coverage.csv`
- `outputs/tables/prediction_feature_set_lock.csv`
- `outputs/tables/prediction_leakage_lock.csv`
- `outputs/tables/prediction_validation_lock.csv`
- `outputs/tables/prediction_bold_crosswalk.csv`
- `outputs/tables/prediction_plan_lock_qa.csv`
- `outputs/tables/prediction_external_validation_lock.csv`
- `outputs/tables/prediction_small_sample_target_support.csv`
- `outputs/tables/prediction_small_sample_method_amendments.csv`
- `outputs/tables/prediction_small_sample_lock_qa.csv`
- `outputs/tables/prediction_participant_event_profile.csv`
- `outputs/tables/prediction_outer_fold_assignments.csv.gz`
- `outputs/tables/prediction_inner_fold_assignments.csv.gz`
- `outputs/tables/prediction_outer_fold_support.csv`
- `outputs/tables/prediction_inner_fold_support.csv`
- `outputs/tables/prediction_resampling_manifest.csv`
- `outputs/tables/prediction_resampling_qa.csv`
- `outputs/tables/prediction_internal_oof_predictions.csv.gz`
- `outputs/tables/prediction_internal_repeat_metrics.csv`
- `outputs/tables/prediction_internal_threshold_metrics.csv`
- `outputs/tables/prediction_internal_tuning.csv`
- `outputs/tables/prediction_internal_fold_coefficients.csv.gz`
- `outputs/tables/prediction_internal_model_comparison.csv`
- `outputs/tables/prediction_internal_calibration_bins.csv`
- `outputs/tables/prediction_internal_metric_summary.csv`
- `outputs/tables/prediction_internal_qa.csv`
- `outputs/tables/prediction_internal_artifact_manifest.csv`
- `outputs/tables/prediction_safeguard_fixed_penalty_oof.csv.gz`
- `outputs/tables/prediction_safeguard_flic_oof.csv.gz`
- `outputs/tables/prediction_safeguard_flic_diagnostics.csv`
- `outputs/tables/prediction_safeguard_repeat_metrics.csv`
- `outputs/tables/prediction_safeguard_summary.csv`
- `outputs/tables/prediction_safeguard_cluster_bootstrap.csv.gz`
- `outputs/tables/prediction_safeguard_optimism_summary.csv`
- `outputs/tables/prediction_safeguard_qa.csv`
- `outputs/tables/prediction_safeguard_artifact_manifest.csv`
- `outputs/tables/prediction_abs3_oof_predictions.csv.gz`
- `outputs/tables/prediction_abs3_repeat_metrics.csv`
- `outputs/tables/prediction_abs3_threshold_metrics.csv`
- `outputs/tables/prediction_abs3_tuning.csv`
- `outputs/tables/prediction_abs3_fold_coefficients.csv.gz`
- `outputs/tables/prediction_abs3_model_comparison.csv`
- `outputs/tables/prediction_abs3_calibration_bins.csv`
- `outputs/tables/prediction_abs3_metric_summary.csv`
- `outputs/tables/prediction_abs3_qa.csv`
- `outputs/tables/prediction_abs3_artifact_manifest.csv`
- `outputs/tables/prediction_subgroup_support.csv`
- `outputs/tables/prediction_subgroup_summary.csv`
- `outputs/tables/prediction_subgroup_bootstrap_summary.csv`
- `outputs/tables/prediction_subgroup_ita_summary.csv`
- `outputs/tables/prediction_subgroup_model_comparison.csv`
- `outputs/tables/prediction_subgroup_qa.csv`
- `outputs/tables/prediction_subgroup_artifact_manifest.csv`
- `outputs/tables/prediction_enrichment_block_lock.csv`
- `outputs/tables/prediction_enrichment_overall_summary.csv`
- `outputs/tables/prediction_enrichment_bootstrap_delta_summary.csv`
- `outputs/tables/prediction_enrichment_model_comparison.csv`
- `outputs/tables/prediction_enrichment_promotion_gate.csv`
- `outputs/tables/prediction_enrichment_qa.csv`
- `outputs/tables/prediction_enrichment_artifact_manifest.csv`
- `outputs/tables/prediction_context_ablation_lock.csv`
- `outputs/tables/prediction_context_ablation_repeat_summary.csv`
- `outputs/tables/prediction_context_bootstrap_loss_delta_summary.csv`
- `outputs/tables/prediction_context_decision_curve_summary.csv`
- `outputs/tables/prediction_context_decision_curve_delta_summary.csv`
- `outputs/tables/prediction_context_component_evidence.csv`
- `outputs/tables/prediction_context_freeze_decision.csv`
- `outputs/tables/prediction_context_ablation_qa.csv`
- `outputs/tables/prediction_context_ablation_artifact_manifest.csv`
- `outputs/tables/prediction_final_model_lock.csv`
- `outputs/tables/prediction_final_penalty_selection.csv`
- `outputs/tables/prediction_final_coefficients.csv`
- `outputs/tables/prediction_final_feature_contract.csv`
- `outputs/tables/prediction_final_development_summary.csv`
- `outputs/tables/prediction_final_apparent_checks_only.csv`
- `outputs/tables/prediction_final_source_hashes.csv`
- `outputs/tables/prediction_final_qa.csv`
- `outputs/tables/prediction_final_independent_qa.csv`
- `outputs/tables/prediction_final_artifact_manifest.csv`

### Frozen prediction objects

- `outputs/models/openox_compact_occult_ridge_v1.joblib` — complete scikit-learn preprocessing and ridge-logistic pipeline for unchanged external scoring.
- `outputs/models/openox_compact_occult_ridge_v1_scoring_spec.json` — portable raw-feature, preprocessing, coefficient, eligibility, and claim-boundary specification.
- `outputs/models/openox_compact_occult_ridge_v1_environment.json` — Python and package versions used for serialization.

### Figures

- `outputs/figures/pairing_window_retention.png`
- `outputs/figures/pairing_window_incremental_bands.png`
- `outputs/figures/pigmentation_measure_coverage.png`
- `outputs/figures/forehead_ita_by_mst_group.png`
- `outputs/figures/context_covariate_coverage.png`
- `outputs/figures/perfusion_index_by_device.png`
- `outputs/figures/device_performance_core_intervals.png`
- `outputs/figures/device_performance_modified_bland_altman.png`
- `outputs/figures/device_weighting_sensitivity.png`
- `outputs/figures/device_performance_reporting_tiers.png`
- `outputs/figures/occult_hypoxemia_standardized_device_risks.png`
- `outputs/figures/pigmentation_non_disparate_benchmark_results.png`
- `outputs/figures/perfusion_pi_doubling_effects.png`
- `outputs/figures/prediction_feature_availability.png`
- `outputs/figures/prediction_target_participant_support.png`
- `outputs/figures/prediction_resampling_fold_support.png`
- `outputs/figures/prediction_internal_baseline_compact.png`
- `outputs/figures/prediction_small_sample_safeguards.png`
- `outputs/figures/prediction_abs3_baseline_compact.png`
- `outputs/figures/prediction_subgroup_audit.png`
- `outputs/figures/prediction_enrichment_blocks.png`
- `outputs/figures/prediction_context_ablation_utility.png`

### Processed data

- `data/processed/analytic_cohort_180s.csv.gz` — 28,693-row frozen base cohort containing only the QA-passed pairing, normalized device/probe identity, measurements, timing gap, and repository participant/encounter identifiers needed downstream. This avoids repeatedly loading the full waveform timestamp inventory.
- `data/processed/pigmentation_covariates_by_pair.csv.gz` — 28,693-row, one-to-one predictor map keyed by `pulse_row_id`; contains locked Monk, Fitzpatrick, quantitative-pigmentation, emitter-site mapping, and missingness fields without changing the frozen base cohort.
- `data/processed/context_covariates_by_pair.csv.gz` — 28,693-row, one-to-one map keyed by `pulse_row_id`; contains the locked PI transformations, warming, mapped finger diameter, baseline covariates, physiology, and sensitivity fields without changing the frozen base cohort.

## Environment and dependencies

Activate the project environment with:

```powershell
conda activate openox
```

Packages used so far include Python, pandas, NumPy, SciPy, statsmodels, scikit-learn, Matplotlib, seaborn, PyArrow, Jupyter, IPython, ipykernel, nbformat, nbclient, patsy, joblib, and Pillow. No package was added for D013-D034; BOLD validation used the frozen portable scoring specification with NumPy and pandas, ENCoDE used NumPy/pandas with an explicitly implemented CR1 participant-cluster covariance and Pillow figure, and the D034 diagnostic reused the existing scikit-learn pipeline and participant-bootstrap implementation. Add packages only when implementation requires them, and record material dependency changes here.

**Required runtime settings:** The prior NumPy/BLAS crash is controlled by `MKL_THREADING_LAYER=SEQUENTIAL`, `MKL_NUM_THREADS=1`, and `OMP_NUM_THREADS=1`. Native solves now run under that configuration. Preserve these settings during notebook execution unless a later environment rebuild is explicitly revalidated.

## D035 — bounded BOLD recalibration comparison (post-validation model updating)

After D030-D034 were complete, four fixed calibration methods were compared for both frozen scores: intercept-only, logistic intercept-plus-slope, isotonic, and a four-knot cubic spline. The comparison used 20 repeats of five-fold patient-level cross-validation, identical folds across candidates, source-by-outcome stratification, and a locked selection rule of median pair-weighted log loss, then Brier score, then lower complexity. A separate eICU-only analysis was secondary and could not win the overall comparison.

Logistic recalibration of the SpO2-only score was selected. Its median cross-fitted log loss was 0.20762 and Brier score 0.05208, versus 0.21301 and 0.05226 for unchanged SpO2-only and 0.42119 and 0.12690 for unchanged D028. Isotonic and spline calibration of SpO2-only were essentially tied on probability loss but added complexity without a meaningful gain. The best recalibrated D028 candidate (spline) remained worse at log loss 0.21474 and Brier 0.05304. eICU-specific results led to the same choice.

D035 is model updating, not another external validation: BOLD outcomes were used for calibration and candidate selection. The final BOLD-fit logistic recalibrator is a research object that requires a third untouched cohort before any transport or deployment claim. No original coefficients were refit and no clinical threshold was optimized.

## D036 — formal V1 closeout

V1 is research-complete and frozen. The final closeout independently reverified the 28,693-pair cohort, 6,062-reading model denominator, 261 events from 38 event-positive participants, one-to-one predictor joins, participant-separated resampling, fold-contained preprocessing, and evidence-role separation. The deterministic closeout pipeline regenerated 15 tables and six figures; 16 automated tests, 14 scientific invariants, and 51 public/private closeout manifest entries passed at sign-off.

The locked conclusion is: **Internal performance did not translate cleanly across cohorts. External recalibration improved the simpler SpO2-only model in BOLD, while richer predictor enrichment did not demonstrate reliable transportable benefit. Further independent validation is required before clinical use.**

The BOLD-fitted recalibrator is model updating, not independent external validation. V1 may be reopened only for a verified implementation defect, a materially corrected source release, or a prespecified evaluation in a genuinely untouched cohort.

The separate waveform study also remains closed. Its timing review did not support moving forward to waveform-based error modeling. This result does not show that waveform methods are ineffective; a future attempt would require synchronized recordings and a new study plan. See [`WAVEFORM_STUDY.md`](WAVEFORM_STUDY.md) for a reader-facing explanation of what was tested, why the work stopped, and what would be needed to revisit the question.

## Post-closeout next steps

1. Do not tune further on OpenOx or BOLD.
2. Identify a third untouched cohort before treating the selected BOLD-fit recalibrator as transportable.
3. Use the final D036 reporting package for dissemination while preserving raw-transfer failure and uncertainty.
4. Keep the ENCoDE 615-versus-521 reconstruction question open for author/data-curator clarification; do not post hoc select 521 rows from v1.0.0.

## Change log

| Date | Change |
|---|---|
| 2026-07-18 | Created hub; recorded roadmap, inventory, pairing diagnostics, provisional cohort, and decisions D001–D006. |
| 2026-07-18 | Added D007: reserve BOLD as a conditional external clinical transportability dataset for a shared-feature secondary model. |
| 2026-07-18 | Completed the 60-/180-/300-second pairing-window sensitivity analysis; accepted D008 and advanced to analysis-plan lock. |
| 2026-07-18 | Completed endpoint-feasibility analysis; accepted the device-accuracy endpoint (D009) and occult-hypoxemia definition (D010). |
| 2026-07-18 | Normalized device/probe identities, established reporting tiers, and accepted D011 without changing cohort eligibility. |
| 2026-07-18 | Froze the 28,693-row base analytic cohort; completed repeated-measures feasibility; accepted D012; documented the NumPy/BLAS defect. |
| 2026-07-22 | Mapped pigmentation predictors without opening outcomes; accepted D013; locked dual MST/ITA estimands and FDA-draft benchmark margins; recorded the stable sequential-MKL runtime configuration. |
| 2026-07-23 | Mapped perfusion and physiologic context with outcomes sealed; accepted D014; created a QA-passed 28,693-row context map; closed the analysis-plan lock and advanced to device performance. |
| 2026-07-23 | Completed the primary 11-stratum device-performance analysis with 2,000 participant-cluster bootstrap replicates, saturation-band profiles, agreement displays, exact D012 reconciliation, and QA. |
| 2026-07-23 | Re-audited the complete workflow and current landscape; accepted D015; added participant-balanced sensitivity, recorded-reading selection constraints, multiplicity protection, and revised novelty framing without reopening the cohort. |
| 2026-07-23 | Completed extended and exploratory descriptive-tier device reporting with locked support constraints and QA. |
| 2026-07-23 | Completed the locked occult-hypoxemia analysis with support-gated standalone rates, participant-cluster GEE standardized risks and risk differences, definition sensitivities, and QA. |
| 2026-07-23 | Completed the locked pigmentation/non-disparate-performance analysis; accepted D016; retained five complete-support device conclusions as inconclusive and identified supported component-level margin exceedances for device 60 MST and device 79 high-saturation ITA. |
| 2026-07-26 | Completed the locked perfusion/physiologic-context analysis; repaired an inherited PI complete-case filter before handoff; accepted D017; identified inverse PI-error associations for devices 59 and 64 and completed the four-pillar analytic core. |
| 2026-07-26 | Completed the prediction-plan lock without fitting a model; accepted D018; froze the occult-hypoxemia target, bedside transportable features, leakage exclusions, participant-separated nested validation, calibration metrics, and BOLD boundary. |
| 2026-07-26 | Independently assessed ENCoDE; accepted D019; added a formal external transportability phase with BOLD quantitative validation, ENCoDE measured-pigmentation replication, conditional ENCoDE risk validation, and TRIPOD+AI/PROBAST+AI reporting safeguards. |
| 2026-07-26 | Accepted D020; clarified the restricted prediction population, labeled the 38-positive-participant occult model as pilot evidence, added the richer absolute-error target, and locked repeated grouped CV, FLIC/FLAC, clustered bootstrap, feature-role separation, and decision-curve safeguards. |
| 2026-07-26 | Accepted D021; froze and QA-passed 250 unique outer and 1,000 nested inner participant-level validation sets, saved content hashes, and authorized baseline and compact ridge fitting. |
| 2026-07-26 | Completed the first frozen internal-validation run; accepted D022; found materially better compact-model ranking and generally lower prediction loss, documented modest calibration overprediction/overfitting, and kept final model selection open pending small-sample, robustness, and subgroup checks. |
| 2026-07-26 | Completed rare-event safeguards; accepted D023; confirmed stable occult-model signal across fixed ridge penalties, FLIC, and 1,000 participant-cluster bootstrap refits without changing the pilot-level claim boundary. |
| 2026-07-26 | Completed the richer absolute-error robustness model; accepted D024; found modestly better compact-model ranking but worse probability loss and calibration, and retained the target as diagnostic rather than proxy validation. |
| 2026-07-27 | Completed the support-gated device and measured-pigmentation prediction audit; accepted D025; identified persistent compact-model underprediction in MST 8-10 and device 60, retained the compact model only as the reference for enrichment testing, and kept final model selection open. |
| 2026-07-28 | Completed separate device, pigmentation, and perfusion/context enrichment evaluation; repaired participant-balanced threshold metrics and fold-contained PI scaling; accepted D026; advanced only the context block to ablation and decision-curve analysis. |
| 2026-07-28 | Completed four context-component ablations and 2%-10% decision curves with 2,000 participant-cluster bootstrap samples; accepted D027; rejected the full OpenOx-only context model because participant-level loss improvement was not bootstrap-supported, despite favorable net benefit; retained actual PI as a supported mechanistic signal and the compact model as the external candidate. |
| 2026-07-28 | Accepted D028-D029; selected `C=0.1` from aggregate loss across the 250 frozen tuning contexts; fit and serialized one full-development compact pipeline; independently reproduced its scores; locked the BOLD/ENCoDE subgroup claim boundary, D027 chronology, and perfusion-convergence interpretation; completed Phase 5. |
| 2026-08-03 | Accepted D030-D031; hash-verified and froze the BOLD crosswalk before outcome analysis; applied the D028 model unchanged to 11,880 eligible BOLD pairs; completed 1,000 participant-cluster bootstrap samples, source and race/ethnicity audits, decision analysis, and separate scripted QA; recorded failed raw-transfer calibration and weak discrimination without model revision. |
| 2026-08-04 | Accepted D032-D033; hash-verified and froze the ENCoDE crosswalk; reconstructed 615 protocol-conforming pairs; completed support-gated high-saturation forehead-MST and objective-ITA analyses with participant-cluster covariance and participant-balanced sensitivity; recorded the 615-versus-521 release discrepancy, three-pair low interval, 69.4% exact-ITA coverage, and zero-event risk gate; did not score D028. |
| 2026-08-04 | Accepted D034 as post-validation diagnostic evidence; derived and locked the pre-existing SpO2-only OpenOx baseline from frozen tuning contexts, applied it unchanged to the identical BOLD denominator, completed paired 1,000-participant bootstrap and an 18-check separate QA path, and found materially better but still imperfect transport without model promotion. |
| 2026-08-05 | Accepted D035 as post-validation model updating; compared four fixed recalibrators for both frozen BOLD scores with 20x5 patient-level cross-validation; selected logistic recalibration of SpO2-only, completed 1,000-replicate paired participant-bootstrap uncertainty and a 15-check separate QA path, and froze the result as a research bridge requiring a third untouched cohort. |
| 2026-08-12 | Accepted D036; formally closed V1 as research-complete, preserved the negative external result, completed reporting/reproducibility/audit artifacts, and prohibited further retrospective tuning. The separate waveform study remains closed. |
| 2026-08-16 | Added a public, aggregate-only explanation of the separate waveform timing study, why it stopped, what it did not show, and what a future study would need. No waveform files or participant-level timing results were added. |
