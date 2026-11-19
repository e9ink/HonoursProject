# Thesis facts -- WESAD pipeline

Compiled from repository sources only. All file paths are relative to the project root.
No numbers are inferred; each is sourced from the file listed.

---

## 1. Pipeline stages in run_pipeline.py (in order) with output files

Source: `run_pipeline.py` lines 20-31; output file names from module docstrings.

| # | Label | Module | Output file |
|---|---|---|---|
| 1 | Profiling (Bronze baseline) | `src.profiling` | `reports/wesad_baseline.json` |
| 2 | Conformance check | `src.checks.conformance` | `reports/wesad_conformance.json` |
| 3 | Completeness check | `src.checks.completeness` | `reports/wesad_completeness.json` |
| 4 | Plausibility check | `src.checks.plausibility` | `reports/wesad_plausibility.json` |
| 5 | Temporal alignment | `src.alignment` | `reports/wesad_alignment.json` |
| 6 | Silver cleaning | `src.cleaning` | `reports/wesad_cleaning.json` |
| 7 | Post-cleaning checks | `src.checks.post_cleaning` | `reports/wesad_*_post_cleaning.json` |
| 8 | Governance artefacts | `src.governance` | `reports/wesad_governance.json`; `gold/WESAD/wesad_lineage.json` |
| 9 | Quality report | `src.report` | `reports/wesad_quality_report.json` |
| 10 | Gold manifest | `src.gold_manifest` | `gold/WESAD/wesad_gold_manifest.json` |

---

## 2. Files the pipeline reads; use of .pkl and labels

Source: `docs/progress_log.md` Task 2 section; `src/profiling.py` docstring.

The pipeline reads:
- E4 wristband: `{pid}_E4_Data/ACC.csv`, `BVP.csv`, `EDA.csv`, `HR.csv`, `TEMP.csv`, `IBI.csv` -- fixed-rate CSVs with Unix start timestamp on row 0, Hz on row 1, data from row 2.
- RespiBAN chest: `{pid}_respiban.txt` -- tab-separated text with a 3-line OpenSignals header (JSON metadata on line 2).
- After Stage 6, Silver TEMP: `silver/WESAD/{pid}/{pid}_E4_Data/TEMP.csv`.
- Config files: `config/thresholds.yaml` and `config/physiological_ranges.yaml`.
- Reports from prior stages (each stage reads the JSON from the preceding stage it depends on).

The `.pkl` files are **not used**. `docs/progress_log.md` Task 2 section states: "The `.pkl` files are Python-serialised objects containing the preprocessed and merged signals; the raw instrument recordings are in the CSV and txt files. Profiling was therefore built on the CSV/txt files. The `.pkl` files remain in `bronze/` untouched." There are no labels files read by any pipeline stage; condition labels are in the `.pkl` files, which are not profiled.

---

## 3. Threshold justifications (source: `config/thresholds.yaml` and `docs/progress_log.md`)

**completeness: max_missingness_rate = 0.0**
`config/thresholds.yaml` lines 16-23: "Baseline profiling (Task 2) found 0.0 missingness across every E4 modality and every RespiBAN channel for all 15 participants. This threshold is a PRESERVATION FLOOR: the pipeline must not introduce missingness. Grounding: Batini et al. (2009) and Wang & Strong (1996) define completeness as the ratio of present to expected values; the baseline establishes that ratio is already 1.0, and this threshold requires the Gold output to maintain it."

**validity: max_conformance_violation_rate = 0.0**
`config/thresholds.yaml` lines 28-34: "Conformance: preservation floor. Baseline profiling (Task 2) found no format, range, or sampling violations across all 15 participants. This threshold is a PRESERVATION FLOOR: the pipeline must not introduce any conformance violations. Grounding: same principle as completeness -- if the raw data is clean, the processed output must be no worse."

**validity: max_plausibility_failure_rate = 0.01**
`config/thresholds.yaml` lines 36-47: "Baseline data is physiologically clean, so the 0.01 (1%) tolerance does not permit genuine physiological errors. It covers the narrow case where a signal (primarily EDA) is legitimately pinned at its hardware ceiling (~100 uS) and is FLAGGED AND RETAINED as 'device reached measurement capacity' per supervisor guidance (Dr. Tobias Cibis, 2026-08-27), rather than treated as corrupt and removed. 1% is a conservative ceiling that cannot be reached by ordinary physiological variation."

**timeliness: max_cross_modal_offset_seconds = 1.0 s**
`config/thresholds.yaml` lines 50-61: "Threshold = 1.0 s, approximately one sample of the slowest contributing E4 stream (HR at 1 Hz; EDA/TEMP at 4 Hz = 0.25 s). At or below the coarsest sampling interval, no signal is misattributed to the wrong time bin, which is the requirement for valid multi-signal analysis."

**consistency: no metric defined**
`config/thresholds.yaml` lines 62-72: "No dedicated consistency metric for WESAD. Rationale: the source document handles sampling/format constraints under conformance (mapped to validity), and the one cross-modal issue this dataset presents, a systematic ~19 min timing mismatch between the E4 wrist and RespiBAN chest sensors, is a timeliness/alignment matter measured under max_cross_modal_offset_seconds. Treating it as consistency as well would double-count the same phenomenon. Consistency is therefore intentionally unmeasured for WESAD."

---

## 4. Sources cited for physiological bounds

Source: `config/physiological_ranges.yaml`.

**EDA (0 to 100 uS):**
"Device-capacity bound. Physiological literature (e.g. Boucsein, 2012) places typical EDA up to ~60 uS, but the Empatica E4 hardware ceiling is ~100 uS. Bound set at the device limit per supervisor endorsement (Dr. Tobias Cibis, 2026-08-27). Values pinned at 100 uS should be flagged in the quality report as 'device reached measurement capacity,' not treated as physiologically genuine readings. This reframe was confirmed by supervisor."

**Skin temperature (15 to 42 degC):**
"Clinical plausibility bound for surface skin temperature recorded at the wrist. Lower bound reflects cold extremities in realistic lab conditions; upper bound is below fever-range tissue damage. Pending formal re-sourcing from a medical textbook before the final report."
No external citation is given. The provenance note explicitly flags it as pending re-sourcing.

**Heart rate (20 to 250 bpm):**
"Corruption/plausibility bound (not a healthy resting-HR range). Lower bound represents extreme bradycardia; upper bound captures VT/artifact ceiling. This bound is confirmed as a data-integrity gate, not a health-screening gate. NOTE (Kevin, 2026-08-27): some sources used to ground this range (e.g. record-low resting-HR figures) are non-peer-reviewed. Re-source both limits from a medical textbook (e.g. Guyton & Hall) before the final report."
No specific peer-reviewed citation is currently recorded; the note explicitly flags this as a to-do before the final report.

---

## 5. Section of WESAD documentation for ECG/EMG and respiration bounds

Source: `config/physiological_ranges.yaml`.

**ECG and EMG (+-1.5 mV):**
"Device rail-detection bound. Transfer function from wesad_readme.pdf §II.1: ((signal/65536 - 0.5) * 3). Full-scale output at ADC extremes is +-1.5 mV."

**Respiration (+-50%):**
"Device rail-detection bound. Transfer function from wesad_readme.pdf §II.1: ((signal/65536 - 0.5) * 100). Full-scale output is +-50%."

Both cite **wesad_readme.pdf §II.1**.

---

## 6. Modules that check the signed_off flag

The flag is read from two config files. Modules that gate on it:

**physiological_ranges.yaml (meta.signed_off):**
- `src/checks/conformance.py` lines 91-98: aborts if `signed_off` is not true before running range checks.
- `src/checks/plausibility.py` lines 114-120: aborts if `signed_off` is not true.
- `src/checks/post_cleaning.py` lines 47-53: aborts if `signed_off` is not true.
- `src/cleaning.py` lines 44-52: aborts if `signed_off` is not true before loading skin-temp bounds.

**thresholds.yaml (meta.signed_off):**
- `src/report.py` lines 428-434: aborts with "Quality report refused" if `signed_off` is false.

---

## 7. Exact cleaning rule in cleaning.py for TEMP warm-up samples

Source: `src/cleaning.py` lines 38-39, 97-99.

Constant defined at module level:
```python
TEMP_WARMUP_INDICES = [0, 1, 2, 3]
```

For each participant, the function `_clean_participant` reads the Bronze TEMP.csv without parsing (raw lines), then:
```python
for idx in TEMP_WARMUP_INDICES:
    if idx < len(out_lines):
        out_lines[idx] = "NaN"
```
The literal string `"NaN"` is written to the Silver TEMP.csv at indices 0, 1, 2, 3 (data rows, i.e. rows 2-5 of the file counting from row 0). The row is not deleted; channel length is preserved. Pandas default NA detection (`keep_default_na=True`) reads `"NaN"` as `numpy.nan`.

---

## 8. Five-point alignment method: how it works and where UTC+2 comes from

Source: `src/alignment.py` lines 35-38, 114-175.

**Five points chosen:** At fractions 0.0, 0.25, 0.50, 0.75, and 1.00 of the overlap window duration. Constant `_OVERLAP_FRACTIONS = [0.0, 0.25, 0.50, 0.75, 1.0]` (`src/alignment.py` line 35).

**Residual calculation:** At each evaluation instant `T`:
- E4 nearest sample: `n_e4 = round((T - e4_earliest_start) * e4_ref_hz)`, then `e4_T = e4_earliest_start + n_e4 / e4_ref_hz`. Reference modality: EDA at 4 Hz (preferred) or highest-priority available modality.
- RespiBAN nearest sample: `n_rb = round((T - rb_start) * rb_hz)`, then `rb_T = rb_start + n_rb / rb_hz` (700 Hz).
- `offset_s = e4_T - rb_T`.
- `offset_after_s = max absolute offset across the five points`.

**UTC+2 assumption:** `src/alignment.py` lines 38-39:
```python
# UTC+2 = CEST (Central European Summer Time, Germany summer)
# Verified against all 15 participants: produces consistent ~15-24 min E4-before-RespiBAN offsets
CEST = timezone(timedelta(hours=2))
```
The wall-clock date/time in the RespiBAN OpenSignals header is interpreted as UTC+2 (CEST). The assumption is justified in `docs/progress_log.md` Task 7 alignment section: "The UTC+2 (CEST) assumption was verified as consistent across all 15 participants." No independent external time source is available; the assumption is validated only by the internal consistency of the resulting offsets (all participants showing 15-24 min E4-before-RespiBAN gaps, never negative or wildly inconsistent).

---

## 9. Per-participant alignment residuals (offset_after_s)

Source: `reports/wesad_alignment.json`, per-participant entries, field `offset_after_s`.

| Participant | offset_after_s (s) | Exactly zero? |
|---|---|---|
| S2 | 0.107143 | No |
| S3 | 0.102857 | No |
| S4 | 0.075714 | No |
| S5 | 0.0 | Yes |
| S6 | 0.0 | Yes |
| S7 | 0.0 | Yes |
| S8 | 0.0 | Yes |
| S9 | 0.0 | Yes |
| S10 | 0.0 | Yes |
| S11 | 0.0 | Yes |
| S13 | 0.0 | Yes |
| S14 | 0.0 | Yes |
| S15 | 0.0 | Yes |
| S16 | 0.0 | Yes |
| S17 | 0.0 | Yes |

**Exactly zero: 12 out of 15 participants.**
Non-zero: S2 (0.107143 s), S3 (0.102857 s), S4 (0.075714 s). All are within the +-0.125 s quantization bound of the 4 Hz EDA reference.

---

## 10. Source of "E4 heart rate starts 10 s after the other wrist signals"

Source: `src/alignment.py` line 191 comment and `src/checks/conformance.py` lines 11-12.

`src/alignment.py` line 191:
```python
# HR is documented to begin 10 s after other E4 streams (E4 firmware behaviour)
```

`src/checks/conformance.py` lines 11-12:
```
E4 HR start_time_unix is always exactly 10 s later than other E4 channels.
This is a documented E4 firmware export behaviour, not a recording defect.
```

The 10-second offset is empirically verifiable in every participant's raw data (e.g. `reports/wesad_alignment.json` S2 entry: ACC start = 1495437325.0, HR start = 1495437335.0, difference = 10 s exactly). The codebase attributes this to "documented E4 firmware export behaviour" but does not cite a specific external document or Empatica technical note. No primary source reference appears anywhere in the repository.

---

## 11. Test counts by file

Source: `pytest tests/ --collect-only -q` run against the repository.

| File | Tests |
|---|---|
| `tests/test_completeness.py` | 17 |
| `tests/test_conformance.py` | 24 |
| `tests/test_fault_injection.py` | 42 |
| `tests/test_gold_manifest.py` | 8 |
| `tests/test_plausibility.py` | 18 |
| **Total** | **109** |

---

## 12. Commit 9c27b5d: fault-injection design

Source: `git show 9c27b5d --stat` and `config/experiments.yaml`.

Commit message: "feat: amend fault injection design before first run". Six pre-registration amendments applied before any experiment was run.

**Fault types and signals:**

| Fault type | Signals targeted |
|---|---|
| `completeness_scattered_nan` | E4/TEMP, E4/EDA, E4/HR, RespiBAN/ECG |
| `completeness_contiguous_dropout` | E4/TEMP, E4/EDA, E4/HR, RespiBAN/ECG |
| `conformance_non_numeric` | E4/TEMP, E4/EDA, E4/HR, RespiBAN/ECG |
| `conformance_out_of_device_range` | RespiBAN/ECG only (ADC value 70000) |
| `conformance_sampling_rate_fault` | E4/EDA only |
| `plausibility_physiological_impossible` | E4/TEMP (50.0 degC), E4/HR (300.0 bpm), E4/EDA (-1.0 uS) |
| `timeliness_start_shift` | E4/EDA only |

**Sampling-rate fault injection** (`config/experiments.yaml` lines 160-179):
Row 1 of the EDA.csv file (the declared sampling rate) is changed from 4.0 Hz to 8.0 Hz. This is a file-level structural fault. No severity loop is applied; each participant produces one record (detected: true/false). The harness function is `inject_e4_sampling_rate(csv_path, new_hz)`.

**Timeliness shift injection** (`config/experiments.yaml` lines 215-243):
The E4 EDA start timestamp (row 0 of EDA.csv) is incremented by the offset in seconds. All other E4 files and the RespiBAN file are copied unchanged. Device: E4 wristband only. Offsets: 0.5 s, 2.0 s, 10.0 s, 60.0 s, 3600.0 s. The harness calls internal helper functions from `src/alignment.py` directly (`_e4_modality_info`, `_respiban_info`, `_measure_overlap_offsets`) because `_align_participant` hardcodes the Bronze path at module level and cannot be redirected to a scratch directory.

---

## 13. Files in the Gold manifest

Source: `gold/WESAD/wesad_gold_manifest.json`, fields `summary.total_signal_files` and `summary.signal_files_per_participant`.

The manifest contains **105 files** (not 90). Summary states: "15 participants, 6 E4 signal files + 1 RespiBAN file per participant = 105 signal files total" (`docs/progress_log.md` line matching Q13 gold manifest coverage). The 7 files per participant are:
- E4: `ACC.csv`, `BVP.csv`, `EDA.csv`, `HR.csv`, `IBI.csv`, `TEMP.csv` (6 files)
- RespiBAN: `{pid}_respiban.txt` (1 file)

TEMP for all 15 participants is sourced from Silver (cleaned); all other files are from Bronze. Each entry carries an `authoritative_path` and a `sha256` checksum.

---

## 14. Stewardship roles and impact-assessment risks

Source: `docs/governance/stewardship_roles.md`; `docs/governance/data_impact_assessment_wesad.md`.

**Role names defined in stewardship_roles.md:**
1. Data Owner
2. Data Steward
3. Data Custodian
4. Data Consumer

**Risks listed in data_impact_assessment_wesad.md (Section 3):**
- Risk 1: TEMP warm-up artefact entering training data
- Risk 2: Cross-modal misalignment biasing multi-signal models
- Risk 3: Sensor attachment issue in chest TEMP (S2, S17)
- Risk 4: Undefined signals used as features (BVP excluded from plausibility; IBI excluded by supervisor decision)

---

## 15. RespiBAN accelerometer bound change: ±1 g to ±8 g

Source: `docs/progress_log.md`, sections "Plausibility check open issues (Task 5) Issue 1" and "Supervisor decisions, 9 Sept meeting (Meeting 4) Decision 1".

**Values flagged by the original ±1 g bound:** 201,687 values on the RespiBAN accelerometer (mostly CH5 / x-axis). S2 alone had approximately 25,000 above-Cmax violations on CH5. All were classified as `device_rail`, not `physiological_implausible`. Rate was 0.00052, which still passed the 0.01 threshold.

**Date changed:** Decided at the 9 September 2026 supervisor meeting (Meeting 4), Decision 1. Committed 2026-09-18, commit `beea8ae`.

**Justification:** From `docs/progress_log.md`, Meeting 4 Decision 1: "The maximum observed genuine movement across participants was approximately +-4.5 g (S3 raw-ADC-zero floor-hit excluded); +-8 g provides headroom for vigorous movement while flagging physically implausible values." Kevin had proposed +-5 g; Dr. Tobias Cibis raised it to +-8 g. `config/physiological_ranges.yaml` records: "Bound set at +-8 g by supervisor (Dr. Tobias Cibis, 9 Sept 2026, Meeting 4). The S3 raw-ADC-zero hit (transfer function yields -6.6 g for ADC = 0) lies inside +-8 g and is correctly retained as a device artefact rather than a plausibility violation. Previous bound was +-1 g (calibrated Cmin/Cmax window); revised upward on supervisor instruction."

---

## 16. Hardware and run times

Source: `run_pipeline.py`; all report files.

**Run times:** not recorded in any output file. `run_pipeline.py` prints elapsed time per stage to stdout at runtime (line 62: `print(f"  done ({elapsed:.1f}s)"`) but does not write this to any report or log file. No hardware specification appears in any config, report, or progress-log entry.

---

## 17. Number verification

Source: `reports/wesad_quality_report.json`; `reports/wesad_alignment.json`; `reports/wesad_baseline.json`; `reports/experiments/fault_injection_results.json`.

| Claim | Verdict | Source and actual value |
|---|---|---|
| 18,073,707 E4 cells checked | CONFIRMED | `reports/wesad_quality_report.json` dimensions.completeness.before.cells_checked = 18073707 |
| 62,935,498 expected RespiBAN samples | CONFIRMED | Sum of `expected_n_from_nseq` across all 15 participants in `reports/wesad_baseline.json` = 62,935,498 |
| Conformance violation rate 1.2e-07 | CONFIRMED | `reports/wesad_quality_report.json` dimensions.validity_conformance.before.violation_rate = 1.2e-07 (60 violations / 514,713,128 cells) |
| Plausibility failure rate 1.5e-07 before cleaning | CONFIRMED | `reports/wesad_quality_report.json` dimensions.validity_plausibility.before.failure_rate = 1.5e-07 (60 violations / 388,842,132 samples) |
| Mean alignment residual 0.019 s | CONFIRMED | `reports/wesad_alignment.json` summary.mean_offset_after_s = 0.019048 |
| Max alignment residual 0.107 s | CONFIRMED | `reports/wesad_alignment.json` summary.max_offset_after_s = 0.107143 (S2) |
| Mean start-time gap 1,181.2 s, range 920 to 1,416 s | CONFIRMED | `reports/wesad_alignment.json` summary: mean_offset_before_s = 1181.2, min = 920.0, max = 1416.0 |
| Fault-injection maximum timeliness residual 0.126 s | CONFIRMED (rounded) | `reports/experiments/fault_injection_results.json`: max dirty_residual_s = 0.125714 (S8 at offsets 2, 10, 60 s). 0.125714 rounds to 0.126 at 3 d.p. |
| TEMP 1% rates: 0.00998 (S2, 314 of 31,474) | PARTIALLY WRONG | The injected count is correct (314 for S2). The denominator is wrong: available Silver TEMP samples for S2 = 31,492 (31,496 total minus 4 NaN), not 31,474. Rate = 314/31,492 = 0.009972. Source: `src/cleaning.py` TEMP_WARMUP_INDICES and `reports/wesad_baseline.json` S2 TEMP n_samples = 31,496. |
| TEMP 1% rates: 0.01000 (S8 and S15, 265 of 26,503) | WRONG | Injected count correct (265 for both). Denominator wrong: available Silver TEMP for S8 = 26,548 (26,552 - 4), for S15 = 26,564 (26,568 - 4); neither is 26,503. Rates: S8 = 265/26,548 = 0.00998; S15 = 265/26,564 = 0.00998. Both round to 0.01000 only if stated to 4 d.p. with rounding, but 0.00998 does not round to 0.01000. Source: `reports/wesad_baseline.json` TEMP n_samples for S8 and S15. |
| ECG 0.1% injected counts 4,442 / 3,959 / 3,936 | CONFIRMED | `reports/experiments/fault_injection_results.json` completeness_scattered_nan, RespiBAN_ECG, severity=0.001: S2 n_injected=4442, S8=3959, S15=3936 |

---

## Summary and flags

All checked numbers confirm except two items in Q17:

1. **TEMP 1% denominator for S2:** claimed 31,474; actual 31,492. Difference: 18. Rate 314/31,492 = 0.009972, not 0.00998.

2. **TEMP 1% denominator for S8 and S15:** claimed 26,503 for both; actual 26,548 (S8) and 26,564 (S15). Rate is 0.00998 for both, not 0.01000.

The injected counts themselves (314 for S2, 265 for S8/S15) are correct. The error is in the denominators; they may have come from an earlier version of the data or a miscalculation. Update the thesis text to use the correct denominators and rates.

The Gold manifest contains 105 files, not 90 as Q13 assumed. The question text should be updated.

No external primary source is cited for the HR 10-second offset; the codebase attributes it to "documented E4 firmware export behaviour" with empirical confirmation from the raw data. If this claim needs a citation in the thesis, a specific Empatica E4 technical document should be located.

The skin-temperature bound (15-42 degC) and heart-rate bound (20-250 bpm) are both explicitly flagged in `config/physiological_ranges.yaml` as pending re-sourcing from a medical textbook before the final report. No formal citation exists yet.
