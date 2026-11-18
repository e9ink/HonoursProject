# Data Impact Assessment -- DEAP

**Dataset:** DEAP (Database for Emotion Analysis using Physiological Signals)
**Prepared by:** Kevin Hudoyo, UTS Honours
**Scope:** Risks of using DEAP for AI model training in affective computing contexts

---

## 1. Data Characteristics and Limitations

**Sample size:**
32 participants. This is a small sample by machine learning standards.
Statistical estimates derived from this sample carry wide confidence intervals and
limited generalisability to other populations.

**Population representativeness:**
22 males, 10 females; mean age 26.9 years (Koelstra et al. 2012, p. 4). Ethnic and
cultural composition: not documented. The study was conducted at Queen Mary University
of London. Any model trained on this data may not generalise to populations with
different demographic compositions, including children, older adults, or non-Western
populations.

**Stimuli validity:**
Emotional responses to music video clips may not represent the range, intensity, or
phenomenology of naturalistic emotion experienced in daily life. Self-report labels are
retrospective and may not accurately capture momentary physiological states during
the clip.

**Known quality findings from this pipeline:**

1. *v2 label inversion artefact:* 878 of 5120 Valence/Arousal label entries in the v2
   mirror followed v2 = 9 - v1, where v1 is the XLS value. This affected some
   participants across multiple trials and two dimensions. 163 of these inverted values
   were below the SAM minimum of 1 (since 9 - v1 < 1 when v1 > 8). The pipeline
   detects the inversions (cross-source consistency check) and corrects them in the
   Silver layer using participant_ratings.xls as the authoritative source.
   Reports: deap/reports/deap_consistency.json, deap/reports/deap_cleaning.json.

2. *Temp channel scale split:* Participants split into two groups by Temp channel scale
   (Group A s01-s23, s25: small baseline-corrected values; Group B s24, s26-s32: large
   raw values). Source of the split is not documented in available sources. Models
   treating Temp as a uniform channel across participants would learn from incompatible
   scales.

3. *GSR negative values:* The GSR channel has negative values across participants.
   Koelstra et al. (2012, p. 10) describes subtracting a 256-point moving average from
   GSR as part of the paper's own analysis. Whether this was applied to the released
   preprocessed files is not stated, so negative GSR is a possible consequence. Models
   that assume non-negative GSR (conductance) would need to account for this.

4. *Sampling rate not stated:* 128 Hz is inferred from array length. Neither the paper
   nor the dataset website states the sampling rate for the released preprocessed files.
   The paper documents downsampling to 256 Hz for its own analysis (p. 10), not for
   the released files.

---

## 2. Privacy and Re-identification Considerations

**Pseudonymisation:**
Participants are identified by codes s01-s32. No names or direct identifiers appear
in any data file (confirmed by directory inspection of bronze/DEAP/).

**Access-agreement constraints:**
DEAP is restricted to registered users who have signed the DEAP license agreement
(non-commercial research use). This pipeline excludes all raw data from version
control (bronze/* in .gitignore). The Gold layer governance outputs, quality reports,
and pipeline code do not contain participant physiological measurements and are
therefore version-controlled.

**Physiological signal sensitivity:**
EEG, GSR, BVP, and skin temperature signals can be used for inference beyond emotion
detection, including health and mental state inference. The sensitivity is higher than
typical demographic data.

---

## 3. Risks if Quality Issues Went Undetected

**Risk 1: Label inversion biasing emotion models**
If the 878 v2 inversion entries were used as training labels without correction, a model
would learn from inverted affective ratings for affected trials. For the 163 OOR values
(below SAM min), this would constitute physically invalid training targets. The
pipeline detects and corrects these in the Silver layer.

**Risk 2: Temp scale split causing silent feature incompatibility**
If participants from Group A and Group B are combined without accounting for the Temp
scale split, the Temp feature would have incompatible distributions between groups.
A model trained on mixed data could learn spurious associations. The pipeline flags
this in the descriptive consistency report (deap/reports/deap_consistency.json,
consistency_scale_descriptive sub-check).

**Risk 3: Undocumented sampling rate and preprocessing**
If the inferred 128 Hz sampling rate is incorrect, any frequency-domain analysis
(e.g. EEG band power) would yield incorrect values. If the preprocessing applied
to the released files differs from what is documented in the paper, bandpass and
reference choices may not match expectations. These risks cannot be resolved from
available sources.

**Risk 4: GSR unit ambiguity**
If GSR is treated as raw conductance (uS) without accounting for drift subtraction,
negative values would be treated as errors rather than intentional baseline corrections.
The pipeline documents this as a known issue but cannot confirm the exact preprocessing.

---

## 4. Documented Limitations of This Framework

**Physiological plausibility not checked:**
Peripheral channel units and preprocessing are not documented in available sources.
This check is deferred until official DEAP documentation confirms units.
Decision recorded in deap/config/thresholds.yaml and deap/config/rules.yaml.

**Timeliness not applicable:**
All 40 channels share a single sample clock per participant (Biosemi ActiveTwo system,
Koelstra et al. 2012, p. 5). No cross-device temporal alignment is needed.

**Accuracy not measured:**
No ground-truth physiological reference was recorded alongside participant ratings.
Self-report on the SAM scale is the only label source.

**Consistency: within-bounds label errors not tested:**
The fault injection design injects errors that cross thresholds. Small systematic label
errors that remain within [1,9] would not be detected by the current label_plausibility
check. Cross-source consistency would detect them if they differ from XLS, but only if
they differ by more than the tolerance of 1e-4.
