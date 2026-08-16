# Glossary

## Clinical and measurement terms

| Term | Meaning in OpenOx |
|---|---|
| **SpO2** | Peripheral oxygen saturation estimated noninvasively by a pulse oximeter. |
| **SaO2** | Arterial oxygen saturation measured from an arterial blood-gas sample; the study reference measurement. |
| **Pulse-oximeter error** | `SpO2 - SaO2`. Positive values mean the pulse oximeter reads higher than the arterial reference. |
| **Occult hypoxemia** | The locked outcome `SaO2 < 88%` while the displayed `SpO2` is 92–96%. |
| **ABG** | Arterial blood gas, an invasive blood test used here as the oxygen-saturation reference. |
| **Perfusion index** | A device-derived measure related to pulsatile signal strength and peripheral perfusion. |
| **Investigational waveform recorder** | A separate research device that collected raw red and infrared pulse signals. It was not one of the commercial pulse oximeters whose accuracy was evaluated. |
| **Signal-quality indicator (SQI)** | A device-generated measure of how reliable its signal may be. The separate raw waveforms in this project were not the commercial devices' internal signal-quality indicators. |
| **Synchronized timing** | Timing information that makes it possible to determine which recordings and measurements occurred together. The available files did not provide this consistently across the waveform and oxygen-measurement systems. |
| **MST** | Monk Skin Tone scale, used as a directly measured/assigned pigmentation measure in the relevant cohorts. |
| **ITA** | Individual Typology Angle, a colorimetry-derived pigmentation measure. Measurements depend on instrument and anatomical site. |

## Modeling and evaluation terms

| Term | Meaning in OpenOx |
|---|---|
| **D028 model** | The frozen compact ridge-logistic model using SpO2, age, assigned sex, heart rate, and respiratory rate. |
| **SpO2-only score** | The frozen simple comparator using only SpO2. It was defined from the OpenOx record before its BOLD evaluation. |
| **Participant-grouped validation** | Resampling that keeps all observations from one participant together, reducing leakage across training and validation folds. |
| **Raw transfer** | Applying a frozen model unchanged to a new cohort. |
| **Recalibration** | Updating a model's predicted probabilities using outcomes in a new cohort. It is model updating, not independent validation of the updated model. |
| **Calibration** | Agreement between predicted probabilities and observed event frequency. |
| **Discrimination** | Ability to rank higher-risk observations above lower-risk observations. |
| **Brier score** | Mean squared error of predicted probabilities; lower is better. |
| **Log loss** | Probability loss that penalizes confident incorrect predictions; lower is better. |
| **PR-AUC** | Area under the precision-recall curve; useful when events are uncommon. Higher is better within a comparable population. |
| **ROC-AUC** | Probability that the model ranks a randomly selected event above a randomly selected non-event. |
| **Support gate** | A prespecified minimum-data rule that determines whether an analysis is interpretable enough to run or report. |
| **Frozen/locked** | Prespecified and protected from retrospective tuning after outcome information became available. |

## Dataset roles

| Dataset | Role |
|---|---|
| **OpenOximetry / OpenOx** | Controlled-desaturation development cohort and internal-validation evidence. |
| **BOLD** | Large ICU-derived external cohort used first for unchanged model transfer and later, separately, for bounded recalibration. |
| **ENCoDE** | Acute-care cohort with directly measured skin tone, used for mechanistic replication and a conditional risk-model feasibility gate. |

For claim boundaries, see [`FINAL_STATUS.md`](FINAL_STATUS.md). For access requirements and dataset citations, see [`DATA_USE.md`](../DATA_USE.md).
