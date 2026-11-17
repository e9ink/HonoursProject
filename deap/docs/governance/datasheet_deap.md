# Datasheet: DEAP Dataset

**Version:** v2 mirror (32 participants)
**Framework pipeline version:** deap-profile branch, 2026-11-17
**Author:** Kevin Hudoyo (24790848), UTS Honours
**Supervisor:** Dr. Tobias Cibis

---

## Motivation

**For what purpose was the dataset created?**
DEAP was created to investigate human affective states using physiological signals and
video content. Participants watched music video clips and self-reported their emotional
state on four dimensions: valence, arousal, dominance, and liking.

**Who created the dataset, and on behalf of which entity?**
Sander Koelstra, Christian Muhl, Mohammad Soleymani, Jong-Seok Lee, Ashkan Yazdani,
Touradj Ebrahimi, Thierry Pun, Anton Nijholt, and Ioannis Patras.
Published in: Koelstra et al. (2012). DEAP: A Database for Emotion Analysis Using
Physiological Signals. IEEE Transactions on Affective Computing, 3(1):18-31.

**Who funded the creation of the dataset?**
Not stated in the paper.

---

## Composition

**What do the instances represent?**
Each instance is one participant's data for one 60-second music video trial.
32 participants, 40 trials each. 1,280 total trial instances.

**How many instances are there?**
32 .dat files (one per participant), each containing:
- data: numpy array of shape (40, 40, 8064) -- 40 trials, 40 channels, 8064 samples
- labels: numpy array of shape (40, 4) -- 40 trials, 4 self-report dimensions

**What data does each instance consist of?**
40 channels at 128 Hz (inferred from 8064 samples / 63 s; not explicitly stated
in the paper -- paper states downsampled to 256 Hz, then further to 128 Hz):

EEG channels (32): Fp1, AF3, F3, F7, FC5, FC1, C3, T7, CP5, CP1, P3, P7, PO3, O1,
Oz, Pz, Fp2, AF4, Fz, F4, F8, FC6, FC2, Cz, C4, T8, CP6, CP2, P4, P8, PO4, O2.

Peripheral channels (8): hEOG, vEOG, zEMG, tEMG, GSR, Resp, BVP, Temp.

Self-report labels (4 per trial): valence, arousal, dominance, liking.
Scale: SAM (Self-Assessment Manikin), 1-9 (Koelstra et al. 2012, p. 6).

**Is there any missing data?**
No NaN or Inf values detected in the v2 mirror (see deap/reports/deap_completeness.json).

**Are there any known issues with the data?**

1. GSR (galvanic skin response) has negative values in the preprocessed data.
   Source: Koelstra et al. (2012), p. 10: "baseline removal" via subtraction of
   256-point moving average. This is expected preprocessing, not a data error.

2. Temp channel splits into two groups across participants:
   - Group A (s01-s23, s25): small baseline-corrected values (typically -1 to 1 degC)
   - Group B (s24, s26-s32): extreme raw values (source unknown; may differ preprocessing)
   This anomaly is flagged in the descriptive consistency report but not treated as
   a threshold violation because Temp units and preprocessing are undocumented in the paper.

3. Sampling rate not documented in paper for the Python preprocessed files.
   128 Hz inferred from: 8064 samples / 63 seconds = 128 Hz.

4. Label inversion in v2 mirror: 878 of 5120 entries in the v2 mirror differed from
   participant_ratings.xls. All inversions followed the pattern v2 = 9 - v1 for
   Valence and Arousal only. v1 mirror matched XLS exactly. Inconsistency logged in
   deap/docs/governance/deap_provenance.md and in the cross-source consistency report.

---

## Collection Process

**How was the data associated with each instance acquired?**
EEG recorded with a 32-channel Biosemi ActiveTwo EEG system (Koelstra et al. 2012, p. 3).
Peripheral signals (GSR, Resp, BVP, Temp, EOG, EMG) recorded simultaneously.
Participants watched 40 one-minute music video excerpts. Self-report collected after
each clip via SAM questionnaire on a 1-9 scale.

**Who was involved in the data collection process?**
32 participants (22 males, 10 females; mean age 26.9 years).
Data collection took place at EECS, Queen Mary University of London
(Koelstra et al. 2012, p. 4).

**Over what timeframe was the data collected?**
Not stated in the paper.

**Were any ethical review processes conducted?**
Not explicitly stated. DEAP is distributed publicly for research use.

---

## Preprocessing

**Was any preprocessing/cleaning/labeling of the data done?**
Yes. Per Koelstra et al. (2012), p. 9-10:
- EEG: EOG artefact removal using blind source separation (BSS-CCA).
- EEG: Downsampled from 512 Hz to 128 Hz.
- EEG: Common average reference.
- EEG: Bandpass filtered 4-45 Hz.
- EEG: Frontal face video extracted for 32 participants.
- Peripheral signals: 60-second baseline recording subtracted.
- GSR: Drift removed by subtracting 256-point moving average.
- All signals downsampled to 128 Hz.

**Is the software that was used to preprocess/clean/label the data available?**
Not publicly released by the authors. The preprocessed Python pickle files are
provided directly.

---

## Uses

**Has the dataset been used for any tasks already?**
Yes. DEAP has been widely used in affective computing research, particularly for
emotion recognition using EEG and peripheral signals.

**What tasks is the dataset not appropriate for?**
- Clinical or diagnostic use (not a clinical dataset).
- Applications requiring ground-truth emotion labels (self-report only).
- Generalization to populations outside the original sample demographics.

---

## Distribution

**How is the dataset distributed?**
Via the DEAP project website: http://www.eecs.qmul.ac.uk/mmv/datasets/deap/
Access requires signing a license agreement (non-commercial research use).

**Is the dataset subject to any copyright or other intellectual property (IP) license?**
Yes. DEAP is for non-commercial research use only. See the DEAP license agreement.

**Is the dataset publicly available?**
Access is restricted to registered users who have signed the DEAP license.

---

## Maintenance

**Who maintains the dataset?**
Sander Koelstra and collaborators at Queen Mary University of London.

**Will the dataset be updated?**
No updates announced.

---

## Framework application notes

**Quality checks applied in this framework:**
- Completeness: NaN and Inf detection (threshold: 0 per participant).
- Conformance: array shape (40, 40, 8064), labels shape (40, 4), dtype float64.
- Label plausibility: SAM range [1.0, 9.0] per trial per dimension.
- Consistency: structure (uniform shapes), cross-source (dat vs XLS), descriptive scale.
- Physiological plausibility: not applied (units undocumented for peripheral channels).
- Timeliness: not applied (all channels share a single sample clock per participant).

**Data in this framework:**
- Bronze: read-only .dat files in bronze/DEAP/deap-dataset/data_preprocessed_python/
- No Silver layer: no cleaning was needed (no warm-up artefact or similar issue found).
- No Gold layer: not generated for DEAP (no cross-device alignment to verify).

**Key finding from quality checks:**
The 878-entry label inversion in the v2 mirror is detected by the cross-source
consistency check, which compares .dat labels against participant_ratings.xls.
The check fails for all v2 participants affected by the inversion.
See deap/reports/deap_consistency.json for details.
