# Datasheet for WESAD

**Dataset:** WESAD (Wearable Stress and Affect Detection)
**Prepared by:** Kevin Hudoyo
**Framework:** Gebru, T., Morgenstern, J., Vecchione, B., Vaughan, J. W., Wallach, H., Daume, H., III, & Crawford, K. (2021). Datasheets for datasets. Communications of the ACM, 64(12), 86-92. https://doi.org/10.1145/3458723

---

## 1. Motivation

**For what purpose was the dataset created?**
WESAD was created to support research into wearable-based stress and affect detection using multimodal physiological signals. The dataset provides simultaneous recordings from a wrist-worn and a chest-worn sensor device to enable multi-device, multi-signal analysis of three affective states (neutral, stress, amusement). A baseline benchmark was also created on the dataset using well-known features and standard machine learning methods (Schmidt et al., 2018, p. 1 abstract).

**Who created the dataset and on whose behalf?**
The dataset was created by Philip Schmidt, Attila Reiss, Robert Duerichen, and Claus Marberger (Robert Bosch GmbH, Renningen, Germany) and Kristof Van Laerhoven (University of Siegen, Germany) (Schmidt et al., 2018, p. 1).

**Who funded the creation of the dataset?**
Not documented in the available sources.

**Any other comments?**
WESAD was created both as a research dataset and as a benchmark: the paper provides baseline classification results on the dataset using well-known features and standard machine learning methods (Schmidt et al., 2018, p. 1 abstract).

---

## 2. Composition

**What do the instances represent?**
Each instance is a continuous physiological recording from one participant across a structured study session. The study session includes multiple experimental conditions (source: participant readme files in `bronze/WESAD/`).

**How many instances are there?**
15 participants, identified as S2 through S17 with S1 and S12 absent from this release of the dataset (source: `docs/progress_log.md` and directory listing of `bronze/WESAD/`).

**Device 1: Empatica E4 wristband**
Signals and sample rates (source: `bronze/WESAD/S2/S2_E4_Data/info.txt`):

| Signal | Rate | Unit | Notes |
|---|---|---|---|
| ACC | 32 Hz | 1/64 g | 3-axis, range declared as [-2 g, 2 g] |
| BVP | 64 Hz | (relative) | Photoplethysmograph; no absolute unit |
| EDA | 4 Hz | µS | Electrodermal activity |
| HR | 1 Hz | bpm | Derived from BVP; start time 10 s later than other channels |
| IBI | event-based | s | Inter-beat intervals derived from BVP |
| TEMP | 4 Hz | degC | Skin surface temperature |

**Device 2: RespiBAN Professional (chest)**
Signals and sample rate (source: `reports/wesad_baseline.json`, `config/physiological_ranges.yaml`):

| Signal | Rate | Unit | Notes |
|---|---|---|---|
| ECG | 700 Hz | mV (via transfer fn) | Transfer function: (raw/65536 - 0.5) * 3 |
| EDA | 700 Hz | (raw ADC) | No transfer function applied in this pipeline |
| EMG | 700 Hz | mV (via transfer fn) | Same transfer function as ECG |
| RESP | 700 Hz | % (via transfer fn) | Transfer function: (raw/65536 - 0.5) * 100 |
| TEMP | 700 Hz | (raw ADC) | No transfer function applied in this pipeline |
| ACC_x, ACC_y, ACC_z | 700 Hz | g (via transfer fn) | Bound set at +-8 g by supervisor |

**File format:**
- E4 CSV: row 0 = Unix timestamp (UTC); row 1 = sample rate (Hz); rows 2+ = data values. (source: `bronze/WESAD/S2/S2_E4_Data/info.txt`)
- IBI CSV: row 0 = start timestamp; rows 1+ = (offset_seconds, ibi_duration_seconds). (source: `bronze/WESAD/S2/S2_E4_Data/info.txt`)
- RespiBAN TXT: 3-line header; line 2 = JSON device metadata (sampling rate, sensor names); rows 3+ = tab-separated numeric data; wall-clock recorded in UTC+2 (CEST) -- this is this pipeline's timezone assumption, not independently verified (source: `reports/wesad_alignment.json`, field `timezone_assumption`).

**Participant demographics (from per-participant readme files in `bronze/WESAD/`):**

| Attribute | Observed values |
|---|---|
| Count | 15 |
| Age range | 24-35 years |
| Gender | 12 male, 3 female |
| Dominant hand | 14 right, 1 left (S8) -- tallied from all 15 per-participant readmes; E4 worn on non-dominant hand (Schmidt et al., 2018, p. 3) |

Demographic data is stored per-participant in `bronze/WESAD/<pid>/<pid>_readme.txt`. Each readme also records study pre-requisites (coffee, sports, smoking, illness status).

**Experimental conditions:**
The study elicited three affective states: neutral (baseline), stress, and amusement. The stress condition used the TSST (Trier Social Stress Test). A guided meditation was used to de-excite participants after the stress and amusement conditions. There were two counterbalanced protocol versions: Version A (Baseline -- Amusement -- Medi I -- Stress -- Rest -- Medi II) and Version B (Baseline -- Stress -- Rest -- Medi I -- Amusement -- Medi II) (Schmidt et al., 2018, p. 3 and Figure 2). Ground truth for the baseline experiments was the study protocol. Subjective self-reports were collected via PANAS, STAI, SAM, and SSSQ questionnaires (Schmidt et al., 2018, p. 3-4).

**Quality annotations:**
Two participants (S2, S17) have the note "The RespiBAN temperature sensor was not fully attached throughout the entire duration of the study protocol" (source: `bronze/WESAD/S2/S2_readme.txt`, `bronze/WESAD/S17/S17_readme.txt`). S6 notes the participant was not stressed during the TSST due to prior interview experience. S5 notes the participant may have fallen asleep during the first meditation.

**Does the dataset contain confidential data?**
Participant physiological data is covered by an access agreement. Raw data files in `bronze/WESAD/` are excluded from version control via `.gitignore` and must not be shared without authorisation (source: `.gitignore`).

---

## 3. Collection Process

**How was data collected?**
Data was collected in a controlled laboratory setting using two simultaneous wearable devices: the Empatica E4 wristband and the RespiBAN Professional chest device (source: `config/physiological_ranges.yaml`). The study protocol included at minimum a baseline condition, a stress induction condition (TSST), and a meditation condition (source: participant readme files, `bronze/WESAD/`).

**Study pre-requisites:**
Each participant was asked to confirm: no coffee within the last hour; no sports that day; non-smoker or no smoking within the last hour; not feeling ill. Responses are recorded in per-participant readme files (source: `bronze/WESAD/<pid>/<pid>_readme.txt`).

**Participant recruitment:**
In total, 17 subjects participated in the study. Due to sensor malfunction, the data of two participants had to be discarded, leaving 15 subjects (Schmidt et al., 2018, p. 3). Pre-requisites: participants were asked to avoid caffeine within one hour, avoid sports on the study day, not smoke within one hour, and not feel ill (Schmidt et al., 2018, p. 3; confirmed in per-participant readme files). Inclusion/exclusion criteria and ethics approval: not documented in the available sources.

**Was the data collection validated?**
The E4 does not include per-sample timestamps; declared sampling rates are taken on trust and cannot be independently verified from the exported CSV files (source: profiling note in `reports/wesad_baseline.json`, field `sampling_rate_note`). The RespiBAN records a sequential counter (nSeq) that allows gap detection. Baseline profiling found zero sequence gaps across all 15 participants (source: `reports/wesad_baseline.json`).

**Are there known gaps or issues at collection time?**
Two participants have documented sensor attachment problems for the RespiBAN chest TEMP channel (S2, S17) (source: readme files). S3 readme states: "During the baseline condition, the subject was sitting in a sunny workplace." The E4 activates 15-24 minutes before the RespiBAN per participant, creating a systematic start-time difference (source: `reports/wesad_alignment.json`, `note_offset_before`).

---

## 4. Preprocessing, Cleaning, and Labeling

This section documents what the UTS Honours pipeline (this repository) did to the data. It does not describe any preprocessing performed by the original dataset creators.

**Profiling (Task 2 -- Bronze baseline):**
A baseline quality profile was generated covering all 15 participants: E4 sample counts, declared rates, missingness (NaN cells), and RespiBAN sequence-gap analysis. Result: zero missingness, zero sequence gaps, and zero NaN cells across all signals and participants. Report: `reports/wesad_baseline.json`.

**Conformance check (Task 3):**
Format, sampling rate, non-numeric, and range checks were applied to all signals against bounds in `config/physiological_ranges.yaml` (signed off: Dr. Tobias Cibis, 2026-09-09). Findings before cleaning: 60 range violations on the E4 TEMP channel only (indices 0-3 per participant, value approximately 382 degC, caused by NTC thermistor warm-up). All other signals: zero violations. Report: `reports/wesad_conformance.json`.

**Completeness check (Task 4):**
Missingness measured as n_NaN / (n_samples x n_columns). E4 cells checked: 18,073,707. Bronze missingness rate: 0.0. Report: `reports/wesad_completeness.json` (source: `reports/wesad_quality_report.json`, dimensions.completeness.before).

**Plausibility check (Task 5):**
Physiological range checks applied to signals with defined bounds. Before cleaning: 60 violations on E4 TEMP (same 60 warm-up samples as conformance). Overall failure rate: 1.5e-07 (below the 0.01 threshold). BVP, IBI, RespiBAN EDA (CH2), and RespiBAN TEMP (CH4) are excluded from plausibility checking; reasons documented in `config/physiological_ranges.yaml` and `docs/progress_log.md`. Report: `reports/wesad_plausibility.json`.

**Alignment detection (Task 7):**
Cross-modal temporal alignment was measured between E4 and RespiBAN using a 5-point nearest-sample reconstruction method across the shared overlap window. Start-time gap (sensor activation difference): mean 1181.2 s (range 920-1416 s) -- this is not a defect but a sensor activation-window difference. Within-overlap residual after alignment: mean 0.019 s, max 0.107 s. All 15 participants pass the 1.0 s threshold (timeliness is partly assessed -- the check cannot detect a uniform start-time shift applied to both devices simultaneously). Report: `reports/wesad_alignment.json`.

**Cleaning (Task 8 -- Silver layer):**
The E4 TEMP warm-up artefact (indices 0-3, all 15 participants, 60 samples total) was replaced with NaN in Silver layer files. Bronze data was not modified. Channel lengths are preserved. Cleaned files are in `silver/WESAD/<pid>/<pid>_E4_Data/TEMP.csv`. Report: `reports/wesad_cleaning.json`.

**Post-cleaning quality measurement:**
After cleaning, conformance and plausibility were re-measured on the effective cleaned dataset (Silver TEMP + Bronze for all other signals). Results: 0 violations for both. Completeness unintentional missingness: 0.0 (60 intentional removals tracked separately). Reports: `reports/wesad_conformance_post_cleaning.json`, `reports/wesad_completeness_post_cleaning.json`, `reports/wesad_plausibility_post_cleaning.json`.

**Before / after summary (source: `reports/wesad_quality_report.json`):**

| Dimension | Before (Bronze) | After (Gold) | Threshold | Passes |
|---|---|---|---|---|
| Completeness | 0.0 | 0.0 (+ 60 intentional removals) | 0.0 | Yes |
| Conformance rate | 1.20e-07 | 0.0 | 0.0 | Yes |
| Plausibility rate | 1.50e-07 | 0.0 | 0.01 | Yes |
| Timeliness (max offset) | n/a (19-min gap) | 0.107 s | 1.0 s | Yes |

Timeliness is partly assessed. The 5-point reconstruction method verifies internal consistency of each sensor's own timeline within the shared overlap window, but cannot detect a uniform start-time shift applied to both devices simultaneously. Fault injection experiments confirmed that shifts of 0.5 s to 3600 s all went undetected (source: `docs/progress_log.md`, Timeliness table; `reports/experiments/fault_injection_results.json`).

**Labels:**
The study protocol (condition assignment) served as ground truth for the baseline experiments in Schmidt et al. (2018). Subjective labels were collected at five self-report points via: PANAS (20 items, 5-point Likert, positive and negative affect); STAI (6 items, 4-point Likert, anxiety); SAM (Self-Assessment Manikins, valence-arousal space); and SSSQ (9 items after TSST, measuring worry, engagement, and distress) (Schmidt et al., 2018, p. 3-4). 

---

## 5. Uses

**Has the dataset been used for any tasks already?**
Schmidt et al. (2018) provides the baseline benchmark on WESAD. Using all physiological features, the best classification accuracy reported was 80.34% for the three-class problem (baseline vs. stress vs. amusement) and 93.12% for the binary problem (stress vs. non-stress), both using chest-based modalities (Schmidt et al., 2018, p. 8 and abstract).

**What tasks is the dataset suited for?**
Wearable-based stress and affect detection; multimodal physiological signal analysis; sensor fusion research.

**Are there tasks for which the dataset should not be used?**
Clinical diagnosis; population-level inference beyond the study population; deployment in high-stakes automated decision-making without additional validation.

The 15-participant sample size limits generalisation. Lab-induced stress may not reflect naturalistic stress responses. These constraints apply to any model trained on this data.

---

## 6. Distribution

**How is the dataset distributed?**
Schmidt et al. (2018) describes the dataset as publicly available but does not provide an access URL in the available 9-page paper. Access request process: not documented in the available sources. [KEVIN TO COMPLETE: current repository URL and access request process.] Total recorded: 17 subjects participated; 2 were discarded due to sensor malfunction; 15 remain in this release (Schmidt et al., 2018, p. 3). No larger release is documented in the available sources.

**Has the dataset been shared under an access agreement?**
Yes. Raw physiological data is covered by an access agreement. It is excluded from this project's version control repository via `.gitignore` (`bronze/*` and `archive.zip` excluded) and must not be redistributed (source: `.gitignore`).

**Is any personally identifiable information present?**
Participants are pseudonymised using codes S2-S17. Per-participant readme files contain age, gender, height, and weight. These files are stored in `bronze/` and are excluded from version control (source: `.gitignore`).

---

## 7. Maintenance

**Who maintains the original dataset?**
The original dataset was created by Philip Schmidt, Attila Reiss, Robert Duerichen, Claus Marberger (Robert Bosch GmbH), and Kristof Van Laerhoven (University of Siegen) (Schmidt et al., 2018, p. 1). 

**Who maintains this pipeline and its governance outputs?**
Kevin Hudoyo (UTS Honours, student ID 24790848), supervised by Dr. Tobias Cibis. Pipeline source: this repository. Quality thresholds and physiological ranges signed off by Dr. Tobias Cibis on 2026-09-09 (source: `config/thresholds.yaml` and `config/physiological_ranges.yaml`, `meta.signed_off_by`).

**Will the dataset be updated?**
Not documented in the available sources.

**Are there mechanisms for error reporting?**
Not documented in the available sources.
