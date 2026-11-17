# Data Impact Assessment -- WESAD

**Dataset:** WESAD (Wearable Stress and Affect Detection)
**Prepared by:** Kevin Hudoyo, UTS Honours
**Scope:** Risks of using WESAD for AI model training in mental-health-adjacent contexts

---

## 1. Data Characteristics and Limitations

**Sample size:**
15 participants (S2-S17, with S1 and S12 absent from this release). This is a small sample by machine learning standards (source: `reports/wesad_baseline.json`, field `n_participants`).

Implication: models trained solely on this dataset will have high variance and limited generalisability. Statistical estimates derived from this sample carry wide confidence intervals.

**Population representativeness:**
The 15 participants range in age from 24 to 35 years, with 12 male and 3 female participants (source: per-participant readme files, `bronze/WESAD/<pid>/<pid>_readme.txt`; Schmidt et al., 2018, p. 3). Ethnic and cultural composition: not documented in the available sources. The study was conducted by researchers affiliated with Robert Bosch GmbH (Renningen, Germany) and the University of Siegen, Germany (Schmidt et al., 2018, p. 1). Any model trained on this data may not generalise to populations with different demographic compositions, including children, older adults, or populations with different physiological baselines.

**Lab conditions:**
Data was collected in a controlled laboratory setting using induced stress protocols. Lab-induced stress (e.g. the TSST interview task, referenced in S6 and S14 readme notes) may not represent the range, intensity, or phenomenology of naturalistic stress experienced in everyday environments. Participants were asked to avoid caffeine and tobacco in the hour before the experiment, do no strenuous exercise on the day of the study, and not feel ill (Schmidt et al., 2018, p. 3; confirmed in per-participant readme files). These pre-conditions constrain ecological validity.

**Known quality findings from this pipeline:**

1. *E4 TEMP warm-up artefact:* The Empatica E4 temperature channel records approximately 382 degC for the first 4 samples (indices 0-3) of every participant's recording -- one second at 4 Hz -- due to NTC thermistor initialisation. This affects all 15 participants identically and produced 60 conformance violations and 60 plausibility violations before cleaning (source: `reports/wesad_quality_report.json`, dimensions.validity_conformance.before). After cleaning, these samples are NaN in the Silver layer; channel lengths are preserved. Report: `reports/wesad_cleaning.json`.

2. *RespiBAN TEMP sensor attachment:* Two participants (S2, S17) have the note "The RespiBAN temperature sensor was not fully attached throughout the entire duration of the study protocol" (source: `bronze/WESAD/S2/S2_readme.txt`, `bronze/WESAD/S17/S17_readme.txt`). The pipeline does not attempt to detect or correct this; it is a data-collection issue that may affect chest TEMP values for those participants.

3. *Cross-modal start-time gap:* The E4 wristband activates 15-24 minutes before the RespiBAN chest device in every participant (mean gap: 1181.2 s, source: `reports/wesad_alignment.json`, `summary.mean_offset_before_s`). After aligning to the shared overlap window, the within-overlap residual is small (max 0.107 s, all 15 participants pass the 1.0 s threshold; timeliness is partly assessed -- the 5-point method relies on each device's own recorded timestamps and cannot detect an offset in one device's clock). Analyses that do not account for this gap risk including E4 data that has no RespiBAN counterpart.

4. *Individual participant anomalies:* Per-participant readme notes document individual confounders: one participant may have fallen asleep during meditation (S5), another was not stressed during the TSST due to prior interview experience and had a stressful week prior to the study (S6), and one had a stressful day prior to the study (S8). These are field notes, not quality violations, but they affect the validity of condition labels for those participants.

---

## 2. Privacy and Re-identification Considerations

**Pseudonymisation:**
Participants are identified by codes S2-S17. No names or direct identifiers appear in any data file (source: directory inspection of `bronze/WESAD/`).

**Quasi-identifiers in readme files:**
Each per-participant readme records age, gender, height, weight, and dominant hand. Combined with the study context, these fields could contribute to re-identification for individuals with distinctive profiles.

**Access-agreement constraints:**
Raw physiological data is subject to the dataset's terms of use (academic, non-commercial research; citation of Schmidt et al., 2018). This pipeline excludes all raw data from version control (`bronze/*`, `silver/*`, and `archive.zip` in `.gitignore`). The Gold layer governance outputs, quality reports, and pipeline code do not contain participant physiological measurements and are therefore version-controlled (source: `.gitignore`).

**Physiological signal sensitivity:**
Physiological signals including ECG, EDA, and skin temperature can be used for inference beyond stress detection.

---

## 3. Risks if Quality Issues Went Undetected

**Risk 1: TEMP warm-up artefact entering training data**
If the 60 E4 TEMP warm-up samples (~382 degC) were not detected and removed before model training, a model could learn a spurious association between near-382 degC readings and whatever condition label coincides with the study start (typically baseline or pre-study). Consequences could include: a model that classifies sensor initialisation noise as a physiological state; biased feature distributions for any TEMP-derived feature; incorrect normalisation of the temperature channel. This pipeline detects and removes these samples. The detection is documented in `reports/wesad_conformance.json` and `reports/wesad_plausibility.json`.

**Risk 2: Cross-modal misalignment biasing multi-signal models**
If the E4 and RespiBAN signals are not aligned to a common time base, samples from the two devices at the same frame index will correspond to different moments in the session. For a multi-input model that treats both devices as synchronous, this is a silent data-quality error. The pipeline measures and documents cross-modal alignment. All 15 participants pass the 1.0 s threshold (source: `reports/wesad_alignment.json`; timeliness is partly assessed -- see Section 4). The residual is within E4 EDA quantisation noise (+- 0.125 s at 4 Hz).

**Risk 3: Sensor attachment issue in chest TEMP (S2, S17)**
If chest TEMP values for S2 and S17 are degraded due to the documented attachment problem and this is not noted, models trained on chest TEMP features may learn artefactual patterns for those participants. This pipeline does not detect or correct the attachment issue; it is flagged here for downstream use.

**Risk 4: Undefined signals used as features**
BVP is excluded from plausibility checking because the WESAD documentation provides no unit, transfer function, or physiological range for BVP -- no credible bound can be defined from the available sources (source: `config/physiological_ranges.yaml`, BVP comment; `docs/progress_log.md`, physiological range decisions). IBI is excluded by supervisor decision on 2026-08-27: useful analysis of IBI requires HRV computation over windows of approximately three minutes, which is out of scope for this project's frame-level ingestion pipeline. A 0.24-3.0 s bound was considered but not adopted (source: `docs/progress_log.md`, IBI section). A downstream user who includes BVP or IBI features in a model without independent validation of their plausibility has no quality assurance backing for those signals from this pipeline.

---

## 4. Documented Limitations of This Framework

The following limitations are recorded deliberately. They are not silent omissions.

**No accuracy metric:**
Accuracy (Wang and Strong, 1996) cannot be assessed because no ground-truth reference instrument was recorded alongside WESAD. This is recorded in `reports/wesad_quality_report.json` (dimensions.accuracy) and `config/thresholds.yaml`.

**Consistency not measured:**
No dedicated consistency metric is defined for WESAD. The one cross-modal structural issue (start-time gap) is captured by the timeliness dimension. Treating it as both timeliness and consistency would double-count the same phenomenon. Decision documented in `config/thresholds.yaml` and `docs/progress_log.md`.

**Alignment detection cannot verify absolute start times:**
The 5-point reconstruction method measures whether E4 and RespiBAN are internally consistent within the overlap window. It cannot detect a uniform timezone-conversion error applied at both ends, which would cancel out in the difference. If the UTC+2 (CEST) timezone assumption for RespiBAN is wrong, the alignment check would not detect it (source: `docs/progress_log.md`, alignment decision section). Timeliness is therefore partly assessed.

**RespiBAN chest EDA and TEMP not plausibility-checked:**
RespiBAN CH2 (EDA) and CH4 (TEMP) are stored as raw ADC values. Plausibility checking requires physical-unit transfer functions (a linear scaling for EDA; a non-linear thermistor conversion for TEMP). These are not implemented. The exclusion is documented in `docs/progress_log.md` (Chest EDA/TEMP channels scoped out section). `config/physiological_ranges.yaml` does not define entries for these chest channels. E4 wrist EDA and TEMP are checked, providing coverage of the same physiological quantities from a different sensor location.

**Single-site, single-protocol dataset:**
Quality conclusions from WESAD (e.g. that E4 TEMP has a warm-up artefact) may not transfer to other datasets collected with different devices or protocols. Each dataset requires its own quality assessment.
