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
40 channels. Each trial array contains 8064 samples. The paper documents a 60-second
stimulus per trial (Koelstra et al. 2012, p. 5); at 128 Hz, 8064 samples span 63 s.
Neither the sampling rate of the released files nor the composition of the extra 3 s
is documented in the sources held. The dataset website lists the preprocessed files as
"downsampling, EOG removal, filtering, segmenting etc." without per-channel detail
(https://www.eecs.qmul.ac.uk/mmv/datasets/deap/readme.html).

EEG channels (32): Fp1, AF3, F3, F7, FC5, FC1, C3, T7, CP5, CP1, P3, P7, PO3, O1,
Oz, Pz, Fp2, AF4, Fz, F4, F8, FC6, FC2, Cz, C4, T8, CP6, CP2, P4, P8, PO4, O2.

Peripheral channels (8): hEOG, vEOG, zEMG, tEMG, GSR, Resp, BVP, Temp.

Self-report labels (4 per trial): valence, arousal, dominance, liking.
Scale: SAM (Self-Assessment Manikin), 1-9 (Koelstra et al. 2012, p. 6).

**Is there any missing data?**
No NaN or Inf values detected in the v2 mirror (see deap/reports/deap_completeness.json).

**Are there any known issues with the data?**

1. GSR (galvanic skin response) has negative values in the preprocessed data.
   Koelstra et al. (2012, p. 10) describe GSR detrending for their own analysis,
   but whether this applies to the released preprocessed files is not stated.
   Negative GSR values are not treated as errors in this framework.

2. Temp channel splits into two groups across participants:
   - Group A (s01-s23, s25): small value range (under 10 per participant)
   - Group B (s24, s26-s32): large value range (over 500 per participant); cause undocumented
   This anomaly is flagged in the descriptive consistency report but not treated as
   a threshold violation because Temp units and preprocessing are undocumented in the paper.

3. Sampling rate not stated in the paper or on the dataset website for the Python
   preprocessed files. 128 Hz inferred from 8064 samples per trial; the paper
   documents a 60-second stimulus; at 128 Hz this spans 63 s, but the extra 3 s
   composition is not documented in sources held.

4. Label inversion in v2 mirror: 878 of 5120 entries in the v2 mirror differed from
   participant_ratings.xls. All inversions followed the pattern v2 = 9 - v1 for
   Valence and Arousal only. v1 mirror matched XLS exactly. The 163 out-of-range
   label values flagged by the label_plausibility check are a subset of these
   inverted entries: an inverted value (9 minus the original XLS rating) falls below
   the SAM minimum of 1 whenever the original rating was above 8. Inconsistency
   logged in deap/docs/governance/deap_provenance.md and in the cross-source
   consistency report.

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
The dataset website (https://www.eecs.qmul.ac.uk/mmv/datasets/deap/readme.html) describes
the preprocessed Python files as having undergone "downsampling, EOG removal, filtering,
segmenting etc." No per-channel detail is given for the released files.

Koelstra et al. (2012) describes the preprocessing applied in the paper's own analysis
pipeline (pp. 9-10), which includes downsampling to 256 Hz (p. 10) and removing ECG and
GSR drift using a 256-point moving average (p. 10). Whether these steps were applied to
the released preprocessed files in the same way is not stated.

The following are therefore not documented in available sources for the released files:
- EEG bandpass filter cutoffs (e.g. 4-45 Hz)
- EOG artefact removal method (e.g. BSS-CCA)
- Common average reference application
- Exact downsampling target for the released files (128 Hz is inferred from array length)

Frontal face video was extracted for 22 of the 32 participants (Koelstra et al. 2012,
abstract and conclusion).

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
- Silver: corrected label CSVs in silver/DEAP/labels/sXX_labels.csv (one per participant).
  Labels taken from participant_ratings.xls (authoritative source). 878 v2 inversion
  artefacts corrected. The 40-channel physiological data array is not in Silver; it is
  read directly from Bronze .dat files.
- Gold: manifest with SHA-256 checksums for all 32 Silver label CSVs
  (gold/DEAP/deap_gold_manifest.json). Lineage document: gold/DEAP/deap_lineage.json.

**Before/after quality summary:**
| Dimension | Before (Bronze) | After (Silver) | Threshold | Pass |
|---|---|---|---|---|
| Completeness | 0 NaN, 0 Inf | unchanged | max=0 | PASS |
| Conformance | 0 violations | unchanged | max=0 | PASS |
| Label plausibility | 163 OOR | 0 OOR | max=0 | PASS (after) |
| Consistency cross-source | 878 mismatches | 0 mismatches | max=0 | PASS (after) |
| Physiological plausibility | not applied | not applied | -- | N/A |
| Timeliness | not applicable | not applicable | -- | N/A |

**Key finding from quality checks:**
The 878-entry label inversion in the v2 mirror is detected by the cross-source
consistency check and the 163 out-of-range violations by the label_plausibility check.
Both are resolved by writing Silver label CSVs from participant_ratings.xls
(authoritative source). After cleaning, all measured dimensions pass.
See deap/reports/deap_cleaning.json and deap/reports/deap_post_cleaning.json.
