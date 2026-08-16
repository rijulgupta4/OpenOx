# Waveform Study: What Was Tested and Why It Stopped

> **Status:** Closed after the timing review. No waveform-based error model was developed.

## Why the study was considered

The completed OpenOx project examined when pulse-oximeter readings may differ from reference arterial oxygen measurements. A follow-up idea asked whether pulse-waveform characteristics could help explain some of those differences.

Waveforms can contain information about the strength, shape, and stability of the optical pulse signal. If the waveform surrounding an oxygen measurement were known, it might provide useful context about perfusion, movement, or recording quality.

Before testing that idea, the project first needed to confirm that each waveform section could be matched reliably to the correct oxygen measurement.

## How this differed from the completed V1 study

V1 used sample markers from a lower-frequency reference recording to help pair blood-gas results with pulse-oximeter readings. That pairing step was successful for a carefully selected subset of records.

The proposed waveform study used a different source: raw red and infrared pulse signals collected by a separate investigational recorder. These were not the internal signals produced by the commercial pulse oximeters being evaluated.

The earlier V1 pairing work therefore did not establish that the separate raw waveform recordings could be matched to individual oxygen comparisons.

## What was tested

The timing review asked a practical question:

> Could the correct section of the waveform recording be identified for each commercial-device SpO2 reading and reference SaO2 measurement?

Initial work found some records that appeared to line up. The timing rules were then tested on records from participants who were not used while those rules were being developed.

The final targeted check included 18 records. One passed both the timing rules set in advance and a separate visual review completed without seeing the automated result.

A broader review of the timing information across 309 waveform files did not find enough documentation to resolve the problem. The waveform recorder and the oxygen-measurement records came from separate systems, and the available files did not consistently show how the timing from one system should be matched to the other.

## Why the study stopped

The timing could not be matched reliably for enough records to support an analysis.

Without a dependable match, a waveform section could be assigned to the wrong oxygen measurement. That would make any apparent relationship between waveform characteristics and measurement error difficult to trust.

Additional adjustment of the matching rules might have produced more apparent matches, but it would not have supplied the missing timing information. The project therefore stopped before calculating waveform characteristics or testing them against oxygen-measurement errors.

## What this result means

The study showed that:

- raw red and infrared waveform recordings were available for an initial review;
- some individual records appeared capable of being matched;
- the available timing information was not sufficient to match enough records reliably;
- stopping before building a model avoided drawing conclusions from uncertain matches.

The study did not show that:

- waveform-based methods are ineffective;
- waveform characteristics cannot help explain pulse-oximeter error;
- the raw waveforms represented the commercial devices' internal signals;
- a waveform model was built, evaluated, or found to perform poorly.

This was a stopped study, not a negative model result.

## What a future study would need

The question could be revisited with a study designed around synchronized recording from the beginning. It would need:

- red and infrared pulse waveforms;
- readings from the pulse oximeter being evaluated;
- reference arterial oxygen measurements or clearly marked blood-sample times;
- clearly documented and synchronized timing across the recording systems;
- enough participants for separate model development and evaluation;
- timing rules defined before examining measurement errors;
- a new study plan and a separate, untouched validation group.

With those pieces in place, waveform characteristics could be tested without relying on uncertain timing matches.

## Public-release boundary

This page provides only the study rationale and aggregate outcome of the timing review.

The public repository does not include PhysioNet waveforms, waveform headers, filenames, timestamps, participant-level matching results, derived patient-level data, restricted-data figures, or restricted-data tables.

Access to the underlying resources remains governed by the PhysioNet requirements described in [`DATA_USE.md`](../DATA_USE.md).
