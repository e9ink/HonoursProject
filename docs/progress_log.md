# Progress Log

Project: Designing a Data Quality and Governance Framework for Multimodal Behavioural Datasets  
Owner: Kevin Hudoyo (24790848), UTS Honours  
Supervised by: Dr. Tobias Cibis

---

## Task 1 — Environment and Repo Scaffold

**Commit:** `chore: scaffold repo, folders, and config templates`

### Folder structure

The following tree was created, matching section 4 of the hand-off doc exactly:

```
bronze/          raw WESAD/DEAP files (immutable after landing)
silver/          validated, aligned, cleaned data
gold/            quality-assured output + governance attachments
reports/         before/after quality reports, reliability logs
docs/            governance document drafts, standards-mapping table
config/
    thresholds.yaml
    physiological_ranges.yaml
src/
    profiling.py
    checks/
        conformance.py
        completeness.py
        plausibility.py
    alignment.py
    cleaning.py
    governance.py
    report.py
tests/
```

Each empty folder received a `.gitkeep` so it appears in git. All `src/` Python files were created as empty stubs at this stage.

### Config files

Both `config/thresholds.yaml` and `config/physiological_ranges.yaml` are template files with the correct keys and **no values filled in**. All values are left blank for Kevin to supply.

Both files open with a `meta:` gate block:

```yaml
meta:
  locked: false
  signed_off: false
  signed_off_by:
  date_locked:
```

**Gate dependency:** Tasks 5 (plausibility check) and 11 (before/after quality report) must read this flag and refuse to run while `signed_off: false`. This is noted in a comment at the top of each file. No threshold or physiological range value may be filled in by automated pipeline code; the pipeline is read-only with respect to these files.

### Design decisions in `thresholds.yaml`

The quality dimensions from the source document (Batini et al., 2009; Wang & Strong, 1996) are mapped to pipeline metrics as follows:

| Dimension    | Metric key(s)                                              | Rationale |
|--------------|------------------------------------------------------------|-----------|
| completeness | `max_missingness_rate`                                     | Direct mapping: proportion of absent samples. |
| validity     | `max_conformance_violation_rate`, `max_plausibility_failure_rate` | Both conformance (format/range/sampling rules) and plausibility (physiological bounds) are forms of validity in the document's framework. |
| timeliness   | `max_cross_modal_offset_seconds`                           | Cross-modal temporal misalignment is the timeliness concern identified in the document. |
| consistency  | *(no metric)*                                              | See below. |
| accuracy     | *(absent)*                                                 | The source document names no accuracy metric; rule 8 of the hand-off doc prohibits inventing one. A limitation note will appear in the quality report instead. |

**Consistency flag for Kevin:** The source document does not define a dedicated consistency metric separate from conformance and plausibility. A comment in `thresholds.yaml` flags this for Kevin to decide: either add a metric (e.g. sampling-rate deviation, or internal cross-signal agreement) or confirm the dimension is intentionally unmeasured in this project. Nothing has been chosen or invented.

### Environment

- Python 3.11.9 (virtual environment at `.venv/`)
- Pandas 3.0.5
- pytest 9.1.1
- PyYAML 6.0.3 (pre-approved in section 4a for reading YAML config files)
- `requirements.txt` generated with pinned versions (`pip freeze`)
- `.venv/`, `__pycache__/`, and `*.py[cod]` excluded via `.gitignore`

---

## Task 2 — Bronze Ingestion and Profiling (WESAD)

**Commit:** `feat: bronze profiling produces baseline quality report`

### What the raw files look like

The WESAD archive was extracted from `archive.zip` into `bronze/WESAD/`. There are 15 participants: S2–S9, S10–S11, S13–S17 (S1 and S12 are absent from this release of the dataset). Each participant directory contains two distinct raw data sources:

**1. E4 wristband data (`S##_E4_Data/`)** — six CSV files:

| File     | Signal                        | Rate   | Columns |
|----------|-------------------------------|--------|---------|
| ACC.csv  | 3-axis accelerometry (±2g)    | 32 Hz  | 3 (x, y, z) |
| BVP.csv  | Blood volume pulse            | 64 Hz  | 1 |
| EDA.csv  | Electrodermal activity (µS)   | 4 Hz   | 1 |
| HR.csv   | Heart rate (from BVP)         | 1 Hz   | 1 |
| TEMP.csv | Skin temperature (°C)         | 4 Hz   | 1 |
| IBI.csv  | Inter-beat intervals          | event-based | 2 (time offset, duration) |

CSV format for fixed-rate files: row 0 = Unix start timestamp; row 1 = declared sample rate (Hz); rows 2 onwards = data values. IBI is different: row 0 is `"timestamp, IBI"` (the second field is a string label, not a rate), and rows 1 onwards are `(time_offset_seconds, ibi_duration_seconds)` pairs.

**2. RespiBAN chest sensor (`S##_respiban.txt`)** — tab-separated text with a 3-line header:

```
# OpenSignals Text File Format
# {JSON metadata including sampling rate and channel mapping}
# EndOfHeader
nSeq  DI  CH1  CH2  CH3  CH4  CH5  CH6  CH7  CH8  <trailing tab>
```

Declared sampling rate: 700 Hz (read from the JSON metadata). Channel mapping (from the same JSON): CH1=ECG, CH2=EDA, CH3=EMG, CH4=TEMP, CH5=ACC_x, CH6=ACC_y, CH7=ACC_z, CH8=RESP. Each row ends with a trailing tab, producing 11 tokens; the 11th is always empty.

The `.pkl` files (one per participant, ~800 MB each uncompressed) are Python-serialized combined data objects. They are present in `bronze/` but are **not profiled**; the raw sensor data is fully available in the CSV and txt files, which are the actual instrument recordings. See the decision note below.

### Libraries used

Only **Pandas** (`pd.read_csv`) and Python built-ins (`json`, `pathlib`, `os`). No library beyond what was already installed was needed or added.

### What `src/profiling.py` does, step by step

1. **Locates participants.** Scans `bronze/WESAD/` for subdirectories, sorts them by name for deterministic ordering.

2. **For each participant, profiles E4 fixed-rate CSVs (ACC, BVP, EDA, HR, TEMP):**
   - Reads the file with `dtype=str` (avoids type-inference problems on the mixed-length header rows).
   - Extracts `start_time_unix` from `iloc[0, 0]` and `declared_hz` from `iloc[1, 0]`.
   - Reads data rows (`iloc[2:]`), converts to numeric with `pd.to_numeric(errors='coerce')`.
   - Computes missingness, gap locations, and implied duration (see metric definitions below).

3. **Profiles IBI separately** as event-based: extracts start time from row 0, counts events and NaN cells in rows 1 onwards. No missingness rate is computed (there is no expected-sample-count baseline for an event-driven signal).

4. **Profiles the RespiBAN chest file:**
   - Opens the file, reads the second `#`-comment line, strips the `# ` prefix, and parses it as JSON to extract `sampling rate` and the channel list.
   - Loads the data with `pd.read_csv(sep='\t', skiprows=3, header=None, usecols=range(10))` — `skiprows=3` skips the three header lines; `usecols=range(10)` discards the trailing-tab empty column.
   - Assigns column names `["nSeq", "DI", "CH1"…"CH8"]`.
   - Detects sequence gaps and computes per-channel NaN rates (see metric definitions below).

5. **Writes `reports/wesad_baseline.json`** using `json.dump(sort_keys=True)`. Sort order ensures the file is identical across runs regardless of any dict-insertion ordering.

### How each metric is calculated

**Missingness — E4 fixed-rate:**  
`missingness_rate = n_nan / (n_samples × n_columns)`  
`n_nan` is the total count of `NaN` cells after `pd.to_numeric(errors='coerce')`. For ACC (3 columns), a row is treated as having a gap if any of its three cells is NaN. `n_columns` is 3 for ACC, 1 for all others.

**Missingness — RespiBAN (sequence-gap component):**  
`sequence_gap_missingness_rate = total_dropped_samples / expected_n_from_nseq`  
where `expected_n_from_nseq = nseq_end − nseq_start + 1` and `total_dropped_samples` is the sum of dropped samples across all sequence gaps. This is reported separately from the per-channel NaN rate (see below).

**Missingness — RespiBAN (per-channel NaN component):**  
`nan_rate = n_nan_in_channel / n_actual_rows`  
Computed independently per channel (ECG, EDA, EMG, TEMP, ACC_x/y/z, RESP) to distinguish between dropped-sample gaps and individual corrupt cell values.

**Sampling-rate consistency — E4:**  
E4 CSV files contain no per-sample timestamps, only a start time and a declared rate. The actual inter-sample interval cannot be verified from the file alone. The declared rate is reported and a note is attached: `"E4 CSV format provides no per-sample timestamps; actual sampling rate cannot be independently verified."` This is a structural limitation of the E4 export format, not a data quality failure.

**Sampling-rate consistency — RespiBAN:**  
The declared rate (700 Hz) is read from the JSON header. An implied duration is derived as `(nseq_end − nseq_start + 1) / declared_hz`. No independent clock reference is available in the file to verify the rate, but the `nSeq` counter provides an exact sample-count record from which any dropped samples are recoverable.

**Gap and anomaly location — E4:**  
A gap is defined as a contiguous run of rows where at least one column is NaN. Each gap is reported as `{start_sample, end_sample, n_samples, start_seconds, end_seconds}` where `start_seconds = start_sample / declared_hz` (time offset from session start).

**Gap and anomaly location — RespiBAN:**  
A gap is a position where `nSeq[i] − nSeq[i−1] ≠ 1`. Each gap is reported as `{at_row, prev_nseq, next_nseq, dropped_samples, approx_start_seconds}` where `approx_start_seconds = prev_nseq / declared_hz`.

### Acceptance criteria — how each was verified

**Never writes to `bronze/`:**  
After both runs, `git status --short` showed `bronze/WESAD/` as `??` (untracked, never staged or modified). No file in `bronze/` appeared as `M` (modified). The script contains no write, move, or delete operations targeting `bronze/`.

**Identical output across two runs:**  
SHA-256 hash of `reports/wesad_baseline.json` was computed before and after the second run:  
Both hashes: `51BE4096478110617B5B1035E057DF3DDE9F92DFB2A8CD8DFFC1BB7BE2014366`  
Sources of non-determinism that were explicitly excluded: no `datetime.now()` or wall-clock value in the JSON; participant and key ordering is enforced via `sorted()` and `json.dump(sort_keys=True)`; `pd.read_csv` output ordering is deterministic for fixed files.

### Decisions made where the source document or hand-off doc was silent

**1. `.pkl` files not profiled.**  
The hand-off doc says "inspect what is on disk" and notes the raw format is unspecified. Each participant directory contains a `.pkl` file (~800 MB uncompressed) alongside the CSV and txt files. The `.pkl` files are Python-serialised objects containing the preprocessed and merged signals; the raw instrument recordings are in the CSV (E4) and txt (RespiBAN) files. Profiling was therefore built on the CSV/txt files. The `.pkl` files remain in `bronze/` untouched.  
*Flag:* If Kevin or Tobi want the pkl files profiled instead of or in addition to the raw files, that is a straightforward extension.

**2. Raw data files not committed to git.**  
The 16 GB of extracted WESAD files are excluded via `.gitignore` entries for `bronze/WESAD/` and `archive.zip`. Rule 4 (bronze immutability) is enforced by the pipeline code never writing to `bronze/`, not by git. Committing 16 GB of binary data to git would make the repository impractical.  
*Flag:* If the project requires the data to be version-controlled (e.g. with Git LFS or a separate data registry), that needs a decision from Kevin.

**3. E4 sampling-rate consistency cannot be independently verified.**  
The E4 CSV export format does not include per-sample timestamps. The declared rate is reported and a note is attached to every E4 modality entry in the report. This is not flagged as a quality failure in the baseline; it is a structural property of the file format.

**4. IBI has no missingness rate.**  
IBI is event-driven (no fixed expected sample count), so a missingness rate cannot be defined in the same way as for fixed-rate signals. The report records only event count and NaN count for IBI.

---

## Threshold decisions

*Date: 2026-08-22. Authority: Kevin holds delegated authority for cleaning-strategy and quality-dimension decisions per supervisor sign-off, on condition of documented justification and revision if evidence warrants it. These decisions are pre-registered: they are recorded before any check runs and must not be adjusted to fit results.*

---

### Completeness — `max_missingness_rate: 0.0`

**Decision:** set to 0.0.

**Justification:** Bronze baseline profiling (Task 2) found exactly 0.0 missingness across every E4 modality (ACC, BVP, EDA, HR, TEMP) and every RespiBAN channel (ECG, EDA, EMG, TEMP, ACC_x/y/z, RESP) for all 15 participants. There are no NaN cells, no sequence gaps, and no dropped samples anywhere in the raw data. Batini et al. (2009) and Wang & Strong (1996) define completeness as the ratio of present to expected values; that ratio is already 1.0 at Bronze. This threshold is therefore a **preservation floor**: the pipeline must not introduce missingness, and the Gold output must match the Bronze baseline.

Setting a more lenient threshold (e.g. 0.01) would permit the pipeline to degrade a dataset that arrived complete. That is not acceptable given the clean baseline.

---

### Consistency — no metric defined (intentionally unmeasured for WESAD)

**Decision:** consistency carries no metric for WESAD and no threshold is set.

**Justification:** The source document does not define a consistency check separate from conformance and plausibility. Both of those are already mapped to the validity dimension (`max_conformance_violation_rate` and `max_plausibility_failure_rate`). The one cross-modal structural issue the WESAD baseline reveals — a systematic ~19-minute timing mismatch between the E4 wristband and the RespiBAN chest sensor, present in all 15 participants — is a **timeliness and alignment** matter. It is captured by `max_cross_modal_offset_seconds` (timeliness) and addressed operationally by the cross-modal alignment step (Task 7). Treating it as a consistency violation as well would double-count the same phenomenon against two separate thresholds.

Consistency is therefore intentionally unmeasured for WESAD. This decision will be revisited for DEAP (Task 14) if that dataset presents a genuine consistency issue not captured by another dimension.

---

### Timeliness — `max_cross_modal_offset_seconds` — **not yet set**

Deliberately unset. The threshold requires a baseline cross-modal offset measurement, which will come from Task 7 (cross-modal temporal alignment). The value will be set from that output before Task 11 runs.

---

### Validity — `max_conformance_violation_rate` and `max_plausibility_failure_rate` — **not yet set**

Both deliberately unset.

- `max_conformance_violation_rate`: to be set after Task 3 (conformance check) establishes what violation rates the raw data presents.
- `max_plausibility_failure_rate`: blocked on literature-sourced physiological ranges (`config/physiological_ranges.yaml`), which must be supplied by Tobi before Task 5 can run. The gate (`meta.signed_off: false`) remains in force.

---

## Physiological range decisions — supervisor confirmation

*Date: 2026-08-27. Authority: Dr. Tobias Cibis confirmed each decision listed below in a supervision meeting. Kevin holds delegated authority to implement these decisions in the config file. `meta.signed_off` remains false pending a formal sign-off call (scheduled 2026-09-09).*

---

### BVP (E4 photoplethysmograph) — **excluded from plausibility checking**

**Decision:** no physiological range defined; BVP is excluded from Task 5 and Task 11.

**Justification:** BVP is a relative, qualitative measure of blood-volume change with no absolute physical unit. Its autonomic-arousal content is better captured by HRV. HRV is out of scope for this project. The WESAD documentation (wesad_readme.pdf, info.txt) provides no unit, transfer function, or range for BVP, making a credible bound impossible to define from available sources. Supervisor confirmed exclusion on 2026-08-27. *(Replaces the earlier "flag for Tobi" marker — this decision is now closed.)*

---

### IBI (E4 inter-beat intervals) — **excluded from plausibility checking**

**Decision:** no plausibility bound defined; IBI is excluded from Task 5.

**Justification:** the primary useful derivation from IBI is HRV, which requires ≥3 minutes of consecutive intervals and a different timescale/discretisation that is incompatible with the frame-level ingestion pipeline. HRV is out of scope. Supervisor confirmed exclusion on 2026-08-27. The previously suggested provisional 0.24–3.0 s IBI bound is dropped entirely.

---

### RespiBAN accelerometry — **±1 g calibrated range confirmed; data-span check cancelled**

**Decision:** keep the −1 to +1 g plausibility bound derived from the calibration transfer function. Cancel the previously planned data-span check.

**Justification:** the RespiBAN accelerometer is calibrated to the Cmin/Cmax window (28000–38000 ADC), and the ±1 g output range already accounts for the effect of gravity on a static sensor. Supervisor confirmed (2026-08-27) that no additional widening is needed and that the ±1 g reference range will not produce systematic false positives. The earlier note suggesting ±1 g might be wrong and needs widening is removed.

---

### EDA (E4 wristband) — **bound changed from 0–60 to 0–100 µS; reframed as device-capacity bound**

**Decision:** set `min: 0`, `max: 100` µS.

**Justification:** the physiological literature (e.g. Boucsein, 2012) places typical EDA up to ~60 µS. However, the Empatica E4 hardware ceiling is ~100 µS. Supervisor endorsed reframing the bound as a device-capacity limit rather than a physiological limit (2026-08-27). Consequence for the quality report (Task 11): values at or near 100 µS should be flagged as "device reached measurement capacity" rather than treated as physiologically genuine — this is a quality annotation, not a rejection. The 0–60 µS physiological ceiling remains documented as context but is not the operative threshold.

---

### Heart rate (E4 HR) — **20–250 bpm confirmed; provenance to-do flagged**

**Decision:** keep `min: 20`, `max: 250` bpm as a corruption/plausibility bound.

**Justification:** this bound is a data-integrity gate (detecting obviously corrupted values), not a healthy-resting-HR screen. Lower bound represents extreme bradycardia; upper bound captures the VT/artifact ceiling. Supervisor confirmed the range is appropriate for this use. **Provenance to-do (Kevin):** some sources used to ground these limits (e.g. record-low resting-HR figures) are non-peer-reviewed. Both limits should be re-sourced from a medical textbook (e.g. Guyton & Hall, *Medical Physiology*) before the final report. This is flagged in `config/physiological_ranges.yaml`.

---

### ECG, EMG — unchanged

−1.5 to +1.5 mV (device rail-detection, from transfer function). No change from prior derivation.

### Respiration (RespiBAN CH8) — unchanged

−50 to +50 % (device rail-detection, from transfer function). No change from prior derivation.

### Skin temperature (E4) — unchanged

15 to 42 °C. Pending formal re-sourcing from a medical textbook before the final report.

### E4 accelerometry — unchanged

−2 to +2 g (from E4 hardware specification in info.txt)

---

## Conformance check finding: E4 TEMP warm-up artifact (Task 3)

*Date: 2026-09-09. Authority: Kevin holds delegated authority for cleaning-strategy decisions per supervisor sign-off, on condition of documented justification.*

---

### The finding

The E4 TEMP channel outputs an unphysical sentinel value (~382 °C, either 382.18 or 382.21 depending on firmware version) for the first 4 samples of every participant's recording — approximately 1 second at 4 Hz. This occurs while the Empatica E4's NTC thermistor stabilises after recording begins. The pattern is identical in shape across all 15 participants: indices [0, 1, 2, 3], always above-max, never below-min, no other out-of-range TEMP values anywhere in the dataset.

Detected by the Task 3 conformance range check against the configured bound of 15–42 °C (`config/physiological_ranges.yaml`, `wesad.skin_temperature`, signed off 2026-09-09).

| Statistic | Value |
|---|---|
| Participants affected | 15 / 15 |
| Samples per participant | 4 |
| Total violating samples | 60 |
| Total cells checked (all signals) | 514,713,128 |
| Overall range violation rate | 1.2e-7 |
| Threshold (`max_conformance_violation_rate`) | 0.0 |
| Pre-cleaning status | **fails threshold** (expected — see decision below) |

---

### Why baseline profiling did not detect this

Task 2 profiling (Bronze baseline) measured missingness: it counted NaN cells, sequence gaps, and dropped samples. These 60 samples are **present and numerically valid** — they are not NaN, not missing, not gaps. A missingness check cannot detect present-but-implausible values. The range conformance check in Task 3 is precisely the mechanism designed to catch this class of artifact.

This is a positive example of the CCP framework working as intended: a pre-registered conformance check (registered before any check ran, in the threshold and range config files) surfaces an artifact that the Bronze baseline did not and could not detect. The framework is catching something real.

---

### Decision

**Keep `max_conformance_violation_rate: 0.0` unchanged.**

The threshold is a Gold-output preservation floor, not a Bronze-state description. It asserts that the Silver and Gold pipeline steps must not introduce conformance violations — it does not assert that the raw Bronze data is already clean. The current pre-cleaning "fail" is the correct and expected result: it documents that the raw data contains a known artifact and motivates the cleaning step that removes it.

Loosening the threshold to, e.g., 0.001 to accommodate this artifact would:
1. Permit the Gold output to contain up to 0.1% out-of-range values with no flag — far more than the 60 warm-up samples warrant.
2. Undermine the preservation-floor principle: if cleaning is successful, the Gold rate should be 0.0, so there is nothing to accommodate.

The threshold stays at 0.0. Task 3 correctly reports "fails threshold" for the pre-cleaning data. Task 11 (before/after quality report) will show the rate drop from 1.2e-7 to 0.0 as evidence that cleaning resolved the artifact.

---

### Carried-forward task: Task 8 cleaning requirement

**Task 8 (Silver cleaning) must strip the first 4 TEMP samples per participant** — the thermistor warm-up window. Specifically:

- Signal: E4 TEMP only (no other signal shows this pattern).
- Action: remove samples at indices [0, 1, 2, 3] (the first 1 second of each TEMP recording).
- Scope: all 15 participants.
- Verification: after stripping, re-run conformance on the Silver TEMP data and confirm violation rate = 0.0.
- Do NOT strip additional samples: only the 4 identified warm-up samples per participant are affected. The rest of the TEMP data is clean.

---

## Alignment detection rebuilt: result and limitation

*Date: 2026-09-23. Commit: `c007ad5`.*

### What was done

The hardcoded `offset_after_s = 0.0` placeholder in `src/alignment.py` was replaced with a real 5-point measurement. The rebuilt code reconstructs each sensor's timeline from its absolute start time and declared sample rate, then compares the two reconstructed timelines at 0%, 25%, 50%, 75%, and 100% of the overlap window. At each evaluation point, the nearest discrete sample from each device is identified via integer rounding, and `offset_s = E4_reconstructed_T − RespiBAN_reconstructed_T` is recorded. `offset_after_s` is the maximum absolute offset across the five points.

### Result

- 12/15 participants show 0.000 s at all five points. The evaluation instants happen to land on exact E4 4 Hz grid boundaries for these participants, so no rounding residual accumulates — a legitimate computational result, not a tautology.
- S2, S3, S4 show small non-zero residuals, up to 0.107 s (S2). This is within the ±0.125 s quantization bound of the 4 Hz E4 EDA reference signal, and the non-zero values confirm the measurement is genuinely computed rather than hardcoded.
- `drift_indicator_s` (offset at 100% minus offset at 0%) is approximately 0 for all participants — no inter-device clock drift detected.
- All 15 participants pass the 1.0 s threshold. Dataset-wide mean residual: 0.019 s; maximum: 0.107 s.

### Limitation (stated plainly)

This measurement verifies that the two sensors' reconstructed sample grids stay mutually consistent across the overlap window with no inter-device drift. It does **not** independently verify that the absolute start times are correct, because the RespiBAN start time is reconstructed from a wall-clock string under an assumed UTC+2 (CEST) timezone. A shared start-time error — for example, a wrong timezone — would shift both reconstructed timelines together and would not appear as a within-overlap offset; instead it would show up as a large constant value at all five points. The observed near-zero offsets indicate no such gross error is present, but they do not prove the UTC+2 assumption is exactly right.

Per the supervisor decision recorded in the 9 Sept meeting (Meeting 4), fully resolving absolute cross-sensor alignment is out of scope for this project. The rebuilt detector flags inter-device clock drift and gross constant start-time errors, which is the agreed scope. The S2/S3/S4 residuals are quantization-level and are not a data quality concern.

---

## Plausibility check open issues (Task 5)

*Date: 2026-09-09. Status: both issues are OPEN, pending supervisor conversation. No config value or bound has been changed.*

---

### Issue 1 — RespiBAN accelerometer bound vs observed motion

**Finding:** the plausibility check flagged 201,687 values on the RespiBAN accelerometer (almost entirely CH5 / x-axis) for exceeding the configured ±1 g calibrated bound. Example: participant S2 alone had ~25,000 above-Cmax violations on CH5. All were classified as `device_rail` (not `physiological_implausible`), so the total failure rate (0.00052) still passed the 0.01 threshold and the genuine physiological finding was not obscured.

**Why this matters:** these are legitimate motion values, not corruption. Normal body movement plus the effect of gravity routinely produces accelerations above 1 g on a chest-worn device. The values are not implausible — they are simply outside the calibration window.

**Apparent conflict:** supervisor guidance (Dr. Tobias Cibis, 2026-08-27) stated that the ±1 g calibrated range "already accounts for gravity" and is not a false-positive risk. The finding suggests this is not quite right: ±1 g is the calibration reference range (Cmin=28000 to Cmax=38000 ADC), not the sensor's physical measurement ceiling. Dynamic movement causes the raw ADC to go outside [28000, 38000], producing converted values beyond ±1 g. The check is technically correct; the bound may not be the right one for plausibility.

**Status: OPEN — pending supervisor input (next available meeting).**

Options to put to Tobi:
- (a) Widen the `accelerometry_respiban` bound to the sensor's true full-scale range (e.g. ±8 g or ±16 g for the BITalino/RespiBAN sensor), so only physically impossible values fail.
- (b) Exclude this channel from plausibility checking entirely (as was done for BVP), treating the calibration window as a conformance check only.

**No bound will be changed until Tobi confirms a direction.**

---

### Issue 2 — RespiBAN chest EDA and TEMP channels (CH2, CH4) skipped

**Finding:** the plausibility check skipped RespiBAN CH2 (EDA) and CH4 (TEMP) with the note "no config bound defined." The skip happens by default (absence of a bound) rather than by deliberate documented decision.

**Why this matters:** the E4 wrist EDA and skin-temperature bounds (0–100 µS, 15–42 °C) describe physiological properties that are independent of measurement site. The chest-mounted EDA and TEMP sensors, once their transfer functions are applied, measure the same physiological quantities. In principle the same bounds could apply. Leaving them unchecked by default is a silent omission.

**Status: OPEN — Kevin's decision.**

Options:
- (a) Add config bounds for CH2/CH4 in `config/physiological_ranges.yaml` under new keys (e.g. `EDA_chest`, `TEMP_chest`), reusing the same physiological range values with a note that these are site-independent bounds.
- (b) Explicitly scope them out of plausibility checking with a recorded reason (e.g. "RespiBAN EDA/TEMP are redundant measurements; quality is assessed via the E4 signals only").

**No bounds will be added or changed until Kevin makes the call.**

---

### Continuity note — 60 physiological_implausible flags

The 60 `physiological_implausible` flags in the Task 5 output are the same E4 TEMP warm-up artifact already identified in Task 3 (conformance), documented above, and already queued for stripping in Task 8. No new action is needed for these.

---

## Internal validation finding: non-numeric junk gap (Task 6)

**Date:** 2026-09-09

### Gap found

During Task 6 (internal validation), the test suite revealed that a non-numeric value placed in a numeric channel — for example the string "bad" sitting where an integer ADC reading is expected — slipped through **both** the conformance check and the completeness check without being counted or flagged.

- **Conformance path (both E4 and RespiBAN):** pd.to_numeric(..., errors="coerce") silently converted the non-numeric string to NaN. Because NaN < min and NaN > max are both False in pandas, the cell was never counted as a range violation.
- **Completeness path for RespiBAN:** check_chest reads channel columns without numeric coercion. col.isnull() returns False for a string object, so the non-numeric value was not counted as missing either.
- **Completeness path for E4:** _check_e4_fixed does apply pd.to_numeric(..., errors="coerce"), so the value became NaN and *was* counted in 
_nan. The E4 chain therefore worked; only the RespiBAN chest path had a full slip-through.

### Why it matters

A data-quality framework must catch malformed values even where the current dataset does not contain them. The current WESAD Bronze data is clean — no non-numeric junk strings appear in any channel. However, the gap is a coverage risk: if future datasets (e.g. DEAP) contain export artefacts or encoding issues that produce non-numeric channel values, they would pass silently through both CCP checks.

### Decision

**Assign non-numeric detection clearly to conformance.** The reasoning: a non-numeric value where a numeric value is expected is a *format* problem (malformed data), not an *absence* problem (missing data). This matches the CCP framework's intent — conformance is responsible for format and structural integrity.

The fix was applied consistently across both sensor paths in src/checks/conformance.py:

- **E4 path (_check_e4_modality):** After coercing to numeric, cells that became NaN are tested against the original raw string. If the raw cell was non-empty (i.e. not a genuine null or blank), the cell is counted in a new 
on_numeric.n_non_numeric field in the findings, separate from range violations.
- **RespiBAN path (check_respiban):** Same logic per channel; each channel entry gains 
_non_numeric, and the ange_summary gains 	otal_non_numeric. The aggregate _aggregate() tracks 	otal_non_numeric_violations and main() includes it in the passes_threshold gate.

**Authority:** This is a check-design decision within Kevin's delegated authority over the pipeline implementation. It does not change any physiological bound or threshold, does not affect signed-off config files, and does not require supervisor sign-off.

### Real-data verification

After applying the fix, the conformance check was re-run on the full WESAD Bronze dataset (15 participants). Result:

- 	otal_non_numeric_violations: 0 — no false positives introduced.
- 	otal_range_violations: 60 — unchanged (TEMP warm-up artifact, pre-existing).
- 
_format_errors: 0, 
_sampling_violations: 0 — unchanged.

The real WESAD data contains no non-numeric channel values. This fix closes a coverage gap rather than correcting observed corruption.

### Internal validation tests

New test class TestNonNumericConformance in 	ests/test_conformance.py asserts:
- A "bad" string in an E4 channel is counted in 
on_numeric.n_non_numeric and NOT in ange.n_violations.
- A "bad" string in a RespiBAN channel is counted in per_channel_range.n_non_numeric and NOT in 
_violations.
- A genuinely empty cell (empty string or NaN) is NOT counted as a non-numeric violation on either path — it remains completeness's concern.

---

## Task 7 alignment: offset_after_s is not a real measurement (OPEN)

**Date noted:** 2026-09-09

### The problem

In `src/alignment.py`, `offset_after_s` is a hardcoded literal `0.0`, not a value derived from data:

```python
offset_after_s = 0.0
passes_threshold = offset_after_s <= threshold_s
```

The timeliness threshold check (`offset_after_s <= max_cross_modal_offset_seconds`) is therefore vacuous: it passes for every participant by construction and is structurally incapable of failing. Only `offset_before_s` (the raw sensor activation-window difference, ~920–1416 s per participant) is a genuine measurement. The timeliness dimension currently has no real evaluation behind it.

### Why it matters

The pipeline is supposed to verify that, after co-registering E4 and RespiBAN onto a shared timeline, the residual timestamp offset within the overlap window is within the pre-registered threshold (1.0 s). That verification does not happen. A report based on the current output would misrepresent the timeliness dimension as having been evaluated when it has not.

### Sources of real misalignment a proper metric must be able to catch

Identified by tracing the clock assumptions in the current code:

1. **Relative clock drift** — both devices use independent crystal oscillators with no synchronisation signal. Typical drift is 10–100 ppm; over a ~2-hour (7200 s) recording that accumulates to 0.07–0.72 s of progressive divergence, which sits at or near the 1.0 s threshold. Drift is invisible to any start-anchored metric because it grows sample-by-sample from t=0.

2. **RespiBAN header start-time precision** — the OpenSignals header records wall-clock time to one decimal place (e.g., `"9:39:1.0"`), giving at best 0.1 s resolution. This is a systematic floor on how precisely the RespiBAN start can be reconstructed.

3. **Timezone-conversion error** — the UTC+2 (CEST) assumption was verified as consistent across all 15 participants, but a wrong timezone assumption would manifest as a large constant offset (e.g., ±3600 s for a one-hour error). The current metric cannot detect this because the same conversion error would be applied at both the start anchor and any interior comparison point — only a check against an independent reference could catch it.

4. **nSeq counter rollover** — the RespiBAN 16-bit sequence counter wraps at 65535; at 700 Hz that is every ~93.6 s, wrapping approximately 77 times over a 2-hour recording. Any miscounting of rollovers in the implied end time propagates silently into overlap duration estimates.

### Status

**OPEN — pending discussion with Tobi.**

This is a measurement-methodology question in his domain (physiological signal timing). Two candidate approaches to raise with him before any implementation:

**(a) Sample-count reconstruction residual** — reconstruct each device's implied timestamp at multiple points across the overlap window from `start_unix + sample_index / hz`, then measure the residual offset between the two reconstructed timelines at each interior point. This requires no signal content and is computable purely from the existing CSVs, but its accuracy is bounded by clock-drift uncertainty and the 0.1 s start-time resolution.

**(b) Signal cross-correlation on a shared physiological event** — identify a signal that both devices capture (e.g., a gross body movement visible in both E4 ACC and RespiBAN ACC), compute the lag at which their cross-correlation peaks within the overlap window, and use that lag as the residual. This is physically grounded but requires a detectable shared event and is sensitive to signal preprocessing choices.

**Do not modify `alignment.py` until the approach is chosen.**

---

## Supervisor decisions, 9 Sept meeting (Meeting 4)

**Date:** 2026-09-09  
**Attendees:** Kevin Hudoyo, Dr. Tobias Cibis

---

### Decision 1 — RespiBAN accelerometer plausibility bound: ±8 g (RESOLVED)

**Resolved:** supervisor set the bound at **±8 g**.

Kevin had proposed ±5 g. Tobi raised it to ±8 g. Reasoning: the WESAD study involves driving tasks, and genuine high-g events (e.g. hard cornering) can produce body accelerations that exceed ±5 g. A ±8 g bound admits real motion peaks while still flagging sensor-floor artefacts such as the S3 raw-ADC = 0 event (which produces −6.6 g under the transfer function and lies inside the ±8 g window, consistent with a floor-hit rather than a plausibility violation).

**Resolves:** the earlier open item "RespiBAN accelerometer bound — ±1g calibrated vs motion — pending Tobi input."

`config/ranges.yaml` and `src/checks/plausibility.py` have not yet been updated; this decision is recorded here until implementation begins.

---

### Decision 2 — Out-of-bounds handling: flag and retain, never delete (RESOLVED)

**Resolved:** out-of-range values are **flagged in metadata and retained in place**. Deletion is prohibited.

Reasoning: the WESAD data is a strictly evenly-spaced time series for both devices. Deleting samples changes recording length, breaks sample-count-based timing reconstruction, and corrupts temporal alignment between channels and devices. Instead, out-of-range values are left at their original positions and annotated in the quality metadata so that downstream analysts are aware and can decide per their own context and use case.

This confirms the transparent-reporting approach over sample-level exclusion, and applies to accelerometer out-of-bounds values, and more broadly to any out-of-range signal in the pipeline.

---

### Decision 3 — Multi-layered, frequency-based flagging (design principle, TO IMPLEMENT)

**Decided:** flagging granularity should **scale with occurrence frequency** to avoid metadata explosion.

Design principle:
- **Low-frequency out-of-range values** (isolated or occasional): flag individually (per-sample or per-event annotation).
- **High-frequency occurrences** (approaching every sample in a column or recording): flag at the **column or recording level** rather than per-value — a single flag on the segment is sufficient and avoids a metadata object as large as the data itself.

This is a new design instruction to be incorporated into the flagging and reporting logic (Tasks 8–11). It has not yet been built. Note it as a refinement to implement, not an existing behaviour.

---

### Decision 4 — Chest EDA and TEMP plausibility bounds: use the same ranges as wrist (RESOLVED)

**Resolved:** apply the **same physiologically-reasonable bounds** for EDA and skin temperature to the RespiBAN chest channels (CH2 and CH4) as are already defined for the E4 wrist equivalents.

Reasoning: physiological plausibility is a body-wide property, not specific to measurement site. The same EDA and temperature ranges that are physiologically implausible on the wrist are equally implausible on the chest. Temperature bounds must be specified as **skin surface temperature**, not core body temperature (the sensor is a surface contact sensor on both devices).

**Resolves:** the earlier open item "RespiBAN CH2/CH4 plausibility scope — pending Kevin's decision."

`config/ranges.yaml` has not yet been updated; this decision is recorded here until implementation begins.

---

### Decision 5 — Cross-modal alignment: detect and flag, do NOT attempt to fix (RESOLVED)

**Resolved:** the pipeline should **measure and report misalignment**, but must **not attempt to correct it**.

Reasoning: correcting cross-sensor clock misalignment is a major research problem in its own right, requiring either a shared trigger stream (not present in WESAD) or full resampling with interpolation (which introduces its own artefacts and is out of scope for this project). Attempting a fix would be technically unsound.

The timeliness check is therefore reframed: its job is **detection and reporting**, not achieving alignment. Concretely:

- The pipeline should reconstruct each sensor's implied timeline at multiple points across the overlap window (using `start_unix + sample_index / hz` for both E4 and RespiBAN) and measure the residual offset at those interior points — replacing the current hardcoded `offset_after_s = 0.0` placeholder with a real computed value.
- If that residual exceeds the threshold (`max_cross_modal_offset_seconds: 1.0 s`), the result is flagged and reported; no resampling or timestamp correction follows.
- No alignment-correction code is to be written.

**Resolves:** the earlier open item "Task 7 alignment: offset_after_s is not a real measurement (OPEN)" — the approach is now decided (sample-count reconstruction residual, option (a) from that section). Implementation of `alignment.py` update is pending.

---

## Frequency-based flagging: deferred to DEAP (decision)

**Date:** 2026-09-23

### Context

Supervisor (Dr. Tobias Cibis, 9 Sept 2026, Meeting 4) described a multi-layered, frequency-based flagging refinement: flag individual values when out-of-range occurrences are rare; flag at the column or recording level when frequent, to avoid excessive flag metadata. This was recorded as Decision 3 in the Meeting 4 section above as a design principle to implement.

### Finding that drove this decision

A flag-frequency analysis of the existing conformance, completeness, and plausibility reports (read-only, no re-runs) found exactly one flagged signal across all of WESAD:

| Signal | Participants | Total flags | Total samples | Mean frequency | Shape |
|---|---|---|---|---|---|
| E4 TEMP warm-up | 15/15 | 60 | 427,736 | 0.0141% | Contiguous, always indices [0–3] |

Every other signal, channel, participant, and check (conformance, completeness, plausibility) is completely clean. Zero violations. WESAD therefore contains only the "rare / individual-flag" case. It has no "frequent" case — no signal approaches a per-sample or per-column flag frequency that would require escalation to column- or recording-level flagging. There is no data against which to calibrate or validate a rare-vs-frequent threshold.

### Decision

**Kevin (2026-09-23): implement only the confirmed behaviour WESAD requires now — per-value flag-and-retain — and defer the frequency-based escalation mechanism until DEAP.**

Rationale:

- WESAD needs only the individual-flag branch. Building the escalation mechanism now would produce code that is never exercised by any WESAD data, and would require choosing a rare-vs-frequent threshold with no empirical grounding.
- DEAP is messier and more likely to exercise the "frequent" branch, making it the appropriate point to design and validate the escalation mechanism against real cases rather than against an assumption.
- This follows the project's general principle of not building untested machinery on assumed inputs.

The supervisor's frequency-escalation principle is **deferred, not dropped**. It is retained here for the DEAP stage (Task 14).

### Status

**DEFERRED — to be revisited at Task 14 (DEAP).**

---
