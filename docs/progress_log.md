# Progress Log

Project: Designing a Data Quality and Governance Framework for Multimodal Behavioural Datasets  
Owner: Kevin Hudoyo (24790848), UTS Honours  
Supervised by: Dr. Tobias Cibis

---

## Current Status

Summary table of every active decision. Check the referenced section for the full rationale. Superseded entries are marked in their original sections.

| Item | Current value | Date set | Section |
|---|---|---|---|
| max_missingness_rate | 0.0 | 2026-09-06 (commit 78b2acb); signed off 2026-09-09 | Threshold decisions: Completeness |
| max_conformance_violation_rate | 0.0 | 2026-09-06 (commit 78b2acb); signed off 2026-09-09 | Threshold decisions: Validity |
| max_plausibility_failure_rate | 0.01 | 2026-09-06 (commit 78b2acb); signed off 2026-09-09 | Threshold decisions: Validity |
| max_cross_modal_offset_seconds | 1.0 s | 2026-09-06 (commit 78b2acb); signed off 2026-09-09 | Threshold decisions: Timeliness |
| RespiBAN ACC bound | plus-or-minus 8 g | 2026-09-09 Meeting 4; committed 2026-09-18 (fe7d396) | Supervisor decisions Meeting 4, Decision 1 |
| E4 ACC bound | plus-or-minus 2 g | 2026-08-22 (from hardware spec) | Physiological range decisions |
| E4 EDA bound | 0-100 uS | 2026-08-27 (supervisor confirmed) | Physiological range decisions: EDA |
| E4 TEMP bound | 15-42 degrees C | 2026-08-27 | Physiological range decisions: Skin temperature |
| E4 HR bound | 20-250 bpm | 2026-08-27 (supervisor confirmed) | Physiological range decisions: Heart rate |
| RespiBAN ECG/EMG bound | plus-or-minus 1.5 mV | 2026-08-22 (device rail) | Physiological range decisions |
| RespiBAN RESP bound | plus-or-minus 50 % | 2026-08-22 (device rail) | Physiological range decisions |
| BVP | Excluded from plausibility | 2026-08-27 (supervisor confirmed) | Physiological range decisions: BVP |
| IBI | Excluded from plausibility | 2026-08-27 (supervisor confirmed) | Physiological range decisions: IBI |
| RespiBAN CH2 (EDA), CH4 (TEMP) | Excluded from plausibility | 2026-10-09 (Kevin, delegated) | Chest EDA/TEMP channels scoped out |
| Completeness definition | Unintended absence only; intentional removals excluded | 2026-10-12 (Kevin) | Completeness definition: intentional removals excluded |
| Alignment approach | Detect and report only; 5-point reconstruction residual | 2026-09-23 (commit c007ad5) | Alignment detection rebuilt |
| Frequency-based flagging | Deferred to DEAP | 2026-09-23 (Kevin) | Frequency-based flagging: deferred to DEAP |
| Consistency | Intentionally unmeasured for WESAD | 2026-08-22 (Kevin) | Threshold decisions: Consistency |

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

> **SUPERSEDED BY:** [Supervisor decisions, 9 Sept meeting (Meeting 4) Decision 5] and commit `78b2acb` (2026-09-06). Value set to 1.0 s; signed off 2026-09-09.

Deliberately unset. The threshold requires a baseline cross-modal offset measurement, which will come from Task 7 (cross-modal temporal alignment). The value will be set from that output before Task 11 runs.

---

### Validity — `max_conformance_violation_rate` and `max_plausibility_failure_rate` — **not yet set**

> **SUPERSEDED BY:** commit `78b2acb` (2026-09-06). max_conformance_violation_rate set to 0.0; max_plausibility_failure_rate set to 0.01; signed off 2026-09-09.

Both deliberately unset.

- `max_conformance_violation_rate`: to be set after Task 3 (conformance check) establishes what violation rates the raw data presents.
- `max_plausibility_failure_rate`: blocked on literature-sourced physiological ranges (`config/physiological_ranges.yaml`), which must be supplied by Tobi before Task 5 can run. The gate (`meta.signed_off: false`) remains in force.

---

## Threshold values set — addendum

*Source: `git log --format="%H %ad %s" --date=short -- config/thresholds.yaml` and commits for each check.*

All four threshold values were first committed in `78b2acb` ("feat: silver conformance check", 2026-09-06). The file's `meta.date_locked: 2026-09-09` reflects the formal supervisor sign-off date.

| Threshold | Value | Committed | First check ran | Set before check? |
|---|---|---|---|---|
| max_missingness_rate | 0.0 | 78b2acb, 2026-09-06 | 09e0f30 ("feat: silver completeness check"), 2026-09-08 | Yes |
| max_conformance_violation_rate | 0.0 | 78b2acb, 2026-09-06 | 78b2acb, 2026-09-06 (same commit) | Same commit |
| max_plausibility_failure_rate | 0.01 | 78b2acb, 2026-09-06 | 69956d7 ("feat: silver plausibility check"), 2026-09-08 | Yes |
| max_cross_modal_offset_seconds | 1.0 | 78b2acb, 2026-09-06 | 14e9606 ("feat: cross-modal temporal alignment"), 2026-09-09 | Yes |

Note: max_conformance_violation_rate was committed in the same commit as the conformance check first ran. The threshold value and the check implementation were introduced together. The pre-registration intent (thresholds declared before checks run) is satisfied for max_missingness_rate, max_plausibility_failure_rate, and max_cross_modal_offset_seconds. For max_conformance_violation_rate the threshold and first check run are co-committed.

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

> **SUPERSEDED BY:** [Supervisor decisions, 9 Sept meeting (Meeting 4) Decision 1]. Bound raised to ±8 g; committed 2026-09-18 (commit `fe7d396`).

**Decision:** keep the −1 to +1 g plausibility bound derived from the calibration transfer function. Cancel the previously planned data-span check.

**Justification:** the RespiBAN accelerometer is calibrated to the Cmin/Cmax window (28000–38000 ADC), and the ±1 g output range already accounts for the effect of gravity on a static sensor. Supervisor confirmed (2026-08-27) that no additional widening is needed and that the ±1 g reference range will not produce systematic false detections. The earlier note suggesting ±1 g might be wrong and needs widening is removed.

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

## Completeness picture after TEMP cleaning

*Date: 2026-09-24. Commit: `e76ea15`.*

Before Task 8 cleaning, WESAD showed zero missingness across all signals and all 15 participants.

After the TEMP warm-up cleaning (commit `e76ea15`), the E4 TEMP channel now contains 4 NaN values per participant (60 total across 15 participants) at indices 0–3, where the ~382°C NTC thermistor warm-up artefact was replaced with the literal text `NaN`. Channel length is unchanged — the rows are present, the values are marked missing.

This is an **intended cleaning outcome, not a data defect**. A known sensor artefact was removed and honestly marked missing rather than left in place (where it would inflate conformance violation counts) or replaced with a fabricated value (which would corrupt the signal). The completeness check will correctly report these 60 NaN samples as missing going forward.

Net effect: the honest completeness statement for cleaned WESAD is *"zero missingness except 60 intentionally-removed TEMP warm-up samples."* This is a stronger and more transparent result than the pre-cleaning *"zero missingness,"* because the pre-cleaning zeros included four invalid sentinel values per participant that were never real temperature readings.

---

## Plausibility check open issues (Task 5)

*Date: 2026-09-09. Status: both issues are OPEN, pending supervisor conversation. No config value or bound has been changed.*

---

### Issue 1 — RespiBAN accelerometer bound vs observed motion

> **SUPERSEDED BY:** [Supervisor decisions, 9 Sept meeting (Meeting 4) Decision 1]. Bound set to ±8 g; committed 2026-09-18 (commit `fe7d396`).

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

> **SUPERSEDED BY:** [Chest EDA/TEMP channels scoped out of plausibility checking (decision)], 2026-10-09.

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
- **Completeness path for E4:** _check_e4_fixed does apply pd.to_numeric(..., errors="coerce"), so the value became NaN and *was* counted in n_nan. The E4 chain therefore worked; only the RespiBAN chest path had a full slip-through.

### Why it matters

A data-quality framework must catch malformed values even where the current dataset does not contain them. The current WESAD Bronze data is clean — no non-numeric junk strings appear in any channel. However, the gap is a coverage risk: if future datasets (e.g. DEAP) contain export artefacts or encoding issues that produce non-numeric channel values, they would pass silently through both CCP checks.

### Decision

**Assign non-numeric detection clearly to conformance.** The reasoning: a non-numeric value where a numeric value is expected is a *format* problem (malformed data), not an *absence* problem (missing data). This matches the CCP framework's intent — conformance is responsible for format and structural integrity.

The fix was applied consistently across both sensor paths in src/checks/conformance.py:

- **E4 path (_check_e4_modality):** After coercing to numeric, cells that became NaN are tested against the original raw string. If the raw cell was non-empty (i.e. not a genuine null or blank), the cell is counted in a new non_numeric.n_non_numeric field in the findings, separate from range violations.
- **RespiBAN path (check_respiban):** Same logic per channel; each channel entry gains n_non_numeric, and the range_summary gains total_non_numeric. The aggregate _aggregate() tracks total_non_numeric_violations and main() includes it in the passes_threshold gate.

**Authority:** This is a check-design decision within Kevin's delegated authority over the pipeline implementation. It does not change any physiological bound or threshold, does not affect signed-off config files, and does not require supervisor sign-off.

### Real-data verification

After applying the fix, the conformance check was re-run on the full WESAD Bronze dataset (15 participants). Result:

- total_non_numeric_violations: 0 -- no false detections introduced.
- total_range_violations: 60 -- unchanged (TEMP warm-up artifact, pre-existing).
- n_format_errors: 0, n_sampling_violations: 0 -- unchanged.

The real WESAD data contains no non-numeric channel values. This fix closes a coverage gap rather than correcting observed corruption.

### Internal validation tests

New test class TestNonNumericConformance in tests/test_conformance.py asserts:
- A "bad" string in an E4 channel is counted in non_numeric.n_non_numeric and NOT in range.n_violations.
- A "bad" string in a RespiBAN channel is counted in per_channel_range.n_non_numeric and NOT in n_violations.
- A genuinely empty cell (empty string or NaN) is NOT counted as a non-numeric violation on either path — it remains completeness's concern.

---

## Task 7 alignment: offset_after_s is not a real measurement (OPEN)

> **SUPERSEDED BY:** [Supervisor decisions, 9 Sept meeting (Meeting 4) Decision 5] and [Alignment detection rebuilt: result and limitation] (commit `c007ad5`, 2026-09-23).

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

Kevin had proposed ±5 g. Tobi raised it to ±8 g. Reasoning: the maximum observed genuine movement across participants was approximately ±4.5 g (S3 raw-ADC-zero floor-hit excluded); ±8 g provides headroom for vigorous movement while flagging physically implausible values. Bound correctly retains the S3 raw-ADC = 0 event (which produces −6.6 g under the transfer function and lies inside the ±8 g window, consistent with a device floor-hit rather than a plausibility violation). Bound set by supervisor on 9 Sept 2026.

**Resolves:** the earlier open item "RespiBAN accelerometer bound — ±1g calibrated vs motion — pending Tobi input."

`config/physiological_ranges.yaml` and `src/checks/plausibility.py` have not yet been updated; this decision is recorded here until implementation begins.

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

> **SUPERSEDED BY:** [Chest EDA/TEMP channels scoped out of plausibility checking (decision)], 2026-10-09. Transfer-function complexity made implementation disproportionate; channels are excluded from plausibility checking with documented rationale.

**Resolved:** apply the **same physiologically-reasonable bounds** for EDA and skin temperature to the RespiBAN chest channels (CH2 and CH4) as are already defined for the E4 wrist equivalents.

Reasoning: physiological plausibility is a body-wide property, not specific to measurement site. The same EDA and temperature ranges that are physiologically implausible on the wrist are equally implausible on the chest. Temperature bounds must be specified as **skin surface temperature**, not core body temperature (the sensor is a surface contact sensor on both devices).

**Resolves:** the earlier open item "RespiBAN CH2/CH4 plausibility scope — pending Kevin's decision."

`config/physiological_ranges.yaml` has not yet been updated; this decision is recorded here until implementation begins.

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

## Chest EDA/TEMP channels scoped out of plausibility checking (decision)

**Date:** 9 Oct 2026  
**Decision maker:** Kevin Hudoyo (delegated authority; to be confirmed with supervisor on return)

### Context

At the 9 Sept 2026 Meeting 4, Dr. Tobias Cibis suggested adding plausibility bounds for the RespiBAN chest EDA (CH2) and TEMP (CH4) channels, reusing the same physiological ranges already applied to their E4 wrist equivalents (EDA 0–100 µS; skin surface temperature 15–42°C), on the principle that physiological plausibility applies body-wide.

### Complication found during implementation

These chest channels are stored as raw sensor values, not physical units. Checking them against physiological bounds would require implementing two raw-to-unit transfer functions: a linear scaling for EDA (CH2) and a non-linear thermistor conversion for TEMP (CH4). The thermistor conversion is non-trivial. This implementation cost was not known at the time of the supervisor's suggestion.

### Decision

**Scope the RespiBAN chest EDA (CH2) and TEMP (CH4) channels OUT of plausibility checking.**

Reasoning:

- These two channels measure the same physiological quantities — skin conductance and skin temperature — that are already plausibility-checked on the E4 wrist channels. They are duplicate coverage of the same physiology, not additional coverage of new physiology.
- Implementing two transfer functions, including a non-linear thermistor conversion, for signals whose physiological plausibility is already verified on the wrist was judged disproportionate to the value added.
- The E4 wrist EDA and TEMP checks provide complete coverage of these physiological quantities.

### Governance note

This is a deliberate, documented scope decision, not a silent omission. The channels are consciously excluded with stated reasoning, consistent with the project's documented-governance principle. The existing `plausibility.py` code already records a hardcoded exclusion comment for CH2 and CH4; this entry provides the formal rationale behind that exclusion.

### Status

**Decided under delegated authority. Reversible.** To be confirmed with Dr. Tobias Cibis on his return from overseas. He may request that the transfer functions be added, in which case this decision is revisited. Low priority given the duplicate-coverage rationale.

---

## Completeness definition: intentional removals excluded (decision)

**Date:** 12 Oct 2026
**Decision maker:** Kevin Hudoyo

### Context

The E4 TEMP warm-up artefact cleaning (Task 8) replaced 4 samples per participant (indices 0–3) with NaN across all 15 participants — 60 samples total. These are documented intentional removals recorded in `reports/wesad_cleaning.json`.

The completeness threshold is `max_missingness_rate: 0.0`, a preservation floor that ensures the pipeline does not introduce unintended data loss.

### Problem

After cleaning, computing missingness naively (all NaN / total cells) yields ~3.3e-06, which technically exceeds the 0.0 threshold. The original quality report marked this as "PASS (intended outcome)" — a qualifier that is logically contradictory: the report was both calling it a failure and overriding the verdict, which is not a sound basis for a quality framework.

### Decision

**Missingness measures UNINTENDED absence only.**

Samples documented as intentionally removed during cleaning are excluded from the missingness rate and reported separately as `intentional_removals`. After cleaning, unintentional missingness = 0.0, which genuinely passes the 0.0 threshold.

This is consistent with the purpose of the threshold: the 0.0 floor was designed to prevent the pipeline from silently losing genuine signal. Removing a documented artefact is not losing genuine signal; it is correcting a false reading. The threshold should not penalise a decision made for quality reasons.

### Implementation

- `_check_e4_fixed` in `src/checks/completeness.py` accepts `intentional_removal_indices` (optional, backward-compatible).
- Post-cleaning checks run via `src/checks/post_cleaning.py`, which reads Silver TEMP + Bronze for everything else, loads intentional removal indices from `reports/wesad_cleaning.json`, and writes separate `*_post_cleaning.json` reports.
- `src/report.py` reads the post-cleaning measured reports for "after" values; no values are derived or hardcoded.

### Status

**Decided.** Intentional-removal exclusion is now the operational definition of missingness in this framework.

---

## Fault injection: harness fixes before first complete run

**Date:** 2026-10-28

Two fix commits were applied to `src/experiments/fault_injection.py` before the first complete experiment run. Neither changes the experimental design or any pre-registered expectation. `config/experiments.yaml` is unchanged from the amendment commit `59454f0`.

### Commit 1: `8328e32` -- fix: separate clean and injected scratch copies in fault injection harness

**What was fixed:** A path-collision bug in the harness caused the injected (dirty) copy to overwrite the clean reference copy, because both `_copy_participant_to_scratch` calls returned `SCRATCH_DIR / pid` -- the same path. When the dirty copy was deleted at the end of an inner loop iteration, the next modality iteration failed reading from the now-deleted clean directory. No results were produced from the attempted run.

**Changes:** Added `SCRATCH_DIRTY` constant and `_copy_to_dirty_scratch(pid)` function, which uses `SCRATCH_DIRTY / pid` for injection copies. All `scratch2`/`scratch3`/`scratch5`/`scratch_sr` calls in the experiment runners now use `_copy_to_dirty_scratch`. Directory leaf name is still `pid`, so `participant_dir.name` remains correct for all check functions.

### Commit 2 -- fix: make fault injection harness efficient and reproducible on Windows

**What was fixed:**

- *.pkl files (large processed data files, not read by any check) were being copied into scratch on every participant copy. Excluded via `shutil.ignore_patterns("*.pkl")`, substantially reducing copy time and memory.
- Scratch directories were inside the OneDrive-synced project folder, causing Windows file-locking errors from the sync client. Moved to `tempfile.gettempdir() / "wesad_fault_injection"`, defined in one place (`_SCRATCH_BASE`). Participant data copies never enter the cloud.
- Windows read-only file errors on `shutil.rmtree` (Bronze files have read-only permissions set by `copytree`) were previously patched at the call site of an external wrapper script. A `_rmtree` helper is now built into the harness; all `shutil.rmtree` calls inside the harness use it.
- Redundant clean-reference check calls: the clean result was recomputed for every modality in the inner loop. It is now computed once per participant/severity combination and reused, reducing check function invocations by roughly 4x.
- Added `src/experiments/run_fault_injection.py` as a foreground runner with per-participant and per-section progress output.
- The external wrapper script used during the first failed run (`run_experiments.py` in the system temp folder) was deleted.

**Design and expectations:** Unchanged. `config/experiments.yaml` is identical to commit `59454f0`.

---

## Fault injection: performance fix before first complete run

**Date:** 2026-10-28
**Commit:** `8e67a64` -- perf: speed up fault injection harness without changing measurements

### Motivation

A timed run on participant S2 revealed that the completeness section alone could not complete in three hours. Profiling traced three dominant costs:

- `_read_respiban` (pure-Python tab parser): 21 s per call on the 4.4 M-row S2 file. This was called once just to count rows, and again inside every RespiBAN injection.
- `inject_respiban_sequence_gaps` / `inject_respiban_non_numeric` / `inject_respiban_value`: each loaded the full 4.4 M rows into Python lists, filtered or modified entries, then rewrote with `_write_respiban`. The combined read-filter-write consumed over 300 s and exhausted available RAM (OOM) on the test machine.
- `check_chest` (pandas, 250 MB): called for every E4-only fault, wasting 7.3 s per iteration on data irrelevant to the fault.

### Changes

**Fast binary RespiBAN helpers** (`_inject_rb_gaps_bytes`, `_inject_rb_contiguous_bytes`, `_inject_rb_non_numeric_bytes`, `_inject_rb_value_bytes`): stream raw binary lines without tab-splitting, write kept lines back as bytes. Injection time: 2.4 s (was >300 s or OOM).

**Fast row counter** (`_count_rb_rows`): counts data lines in a binary pass without parsing tab columns. Time: 0.58 s (was 21 s via `_read_respiban`).

**Device-specific copy functions** (`_copy_e4_to_dirty_scratch`, `_copy_rb_to_dirty_scratch`): copy only the relevant device's files rather than the full 250 MB + E4 bundle for every fault.

**Device-specific check wrappers** (`_run_completeness_e4`, `_run_completeness_chest`, `_run_conformance_e4`, `_run_conformance_rb`, `_run_plausibility_e4`, `_run_plausibility_chest`): call only the sub-check for the device under test. Eliminates the 7.3 s pandas RespiBAN read for every E4 fault and the 0.7 s E4 scan for every RespiBAN fault.

**Clean references computed once per participant** in all three experiment runners (previously once per severity in plausibility and once per fault-type/severity in conformance).

**Double-read bug fixed** in the contiguous RespiBAN completeness path: `_read_respiban` was called twice (once discarding the header, once discarding the rows). Replaced with `_inject_rb_contiguous_bytes` which does a single pass.

The original `inject_respiban_*` functions are preserved in the module for use by existing tests; the experiment runners now call the fast binary variants.

### Before and after timings (completeness_scattered_nan, 1% severity, S2)

| Step | Before | After |
|---|---|---|
| Row count (`n_rb`) | 21 s (`_read_respiban`) | 0.58 s (`_count_rb_rows`) |
| RespiBAN injection | >300 s / OOM | 2.4 s (`_inject_rb_gaps_bytes`) |
| E4 TEMP (copy + inject + check) | ~8.3 s (full copy + full check) | 0.79 s (E4-only copy + E4-only check) |
| E4 EDA | ~8.3 s | 0.76 s |
| E4 HR | ~8.3 s | 0.73 s |
| RespiBAN total (copy + inject + check) | >300 s | 7.8 s |
| One condition total | >300 s (did not complete) | 15.5 s |

### Equivalence check

Condition: completeness_scattered_nan, 1% severity, S2.

E4 signals: `_run_completeness_e4` returns the identical E4 dict as `_run_completeness` for all modalities (same `check_e4` call; field-by-field match confirmed).

RespiBAN injection: empirical equivalence verified on 2026-10-29 using a truncated real file (3 header lines + first 100,000 data rows from `bronze/WESAD/S2/S2_respiban.txt`, copied in binary mode to preserve original line endings). Each of the four new binary injectors was compared against the corresponding old injector at 1% severity (n_faults=1,000) and 10% severity (n_faults=10,000), using the same seed (42) on separate file copies.

| Pair | Old function | New function | Returned values | Byte-identical | check_chest / check_respiban diffs |
|---|---|---|---|---|---|
| gaps 1% | `inject_respiban_sequence_gaps` | `_inject_rb_gaps_bytes` | identical | yes | 0 |
| gaps 10% | `inject_respiban_sequence_gaps` | `_inject_rb_gaps_bytes` | identical | yes | 0 |
| contiguous 1% | old in-line logic | `_inject_rb_contiguous_bytes` | identical | yes | 0 |
| contiguous 10% | old in-line logic | `_inject_rb_contiguous_bytes` | identical | yes | 0 |
| non_numeric 1% | `inject_respiban_non_numeric` | `_inject_rb_non_numeric_bytes` | identical | no* | 0 |
| non_numeric 10% | `inject_respiban_non_numeric` | `_inject_rb_non_numeric_bytes` | identical | no* | 0 |
| value 1% | `inject_respiban_value` | `_inject_rb_value_bytes` | identical | no* | 0 |
| value 10% | `inject_respiban_value` | `_inject_rb_value_bytes` | identical | no* | 0 |

*Non-identical bytes reflect line-ending normalisation: the old `inject_respiban_non_numeric` and `inject_respiban_value` rewrite all rows through `_write_respiban` (text mode, Unix `\n` endings); the new binary variants rewrite only the injected rows, leaving the original line endings on untouched rows. `conformance.check_respiban` and `plausibility.check_respiban` (both pandas-based) produce zero field differences between the two output files at both severities.

Post-fix field values for all four signals (TEMP, EDA, HR, RespiBAN_ECG): n_injected == n_detected, detection_rate = 1.0, false_positive_count = 0, verdict_flip = True.

### Projected runtime

Completeness: ~4 min. Conformance: ~4 min. Plausibility: ~1 min. Timeliness: ~11 s. Control: ~38 s. Total: ~10 min.

### Design and expectations

Unchanged. `config/experiments.yaml` is identical to commit `59454f0`. `pytest`: 101 passed.

---

## Fault injection experiments: results (WESAD)

**Date:** 2026-10-29
**Design commit:** `59454f0` -- feat: amend fault injection design before first run
**Harness commits:** `8328e32`, `8513480`, `8e67a64`
**Results file:** `reports/experiments/fault_injection_results.json` (213 records)

The experiment was executed manually by running `python -m src.experiments.run_fault_injection` in a terminal, after confirming `config/experiments.yaml` matches `59454f0` and `src/experiments/` matches `8e67a64`.

### Determinism check

`conformance_non_numeric` for S2 was re-run by calling `_run_conformance_experiments` directly (without modifying any harness or design file). All 16 records (4 signals x 4 severities) matched the main results file exactly, field by field.

### Scratch directory cleanup

The scratch directories (`<tmp>/wesad_fault_injection/clean` and `.../dirty`) were present after the run but empty -- the harness deletes each participant's copy as it goes. Both directories were removed after confirming they held no participant data.

---

### Table 1: Control condition

| Participant | Completeness flags | Conformance flags | Plausibility flags | Timeliness passes | any_flag | Matches expectation |
|---|---|---|---|---|---|---|
| S2 | 0 | 0 | 0 | Yes | False | Yes |
| S8 | 0 | 0 | 0 | Yes | False | Yes |
| S15 | 0 | 0 | 0 | Yes | False | Yes |

Pre-registered expectation: `any_flag == false` for all participants. Met.

---

### Table 2: Fault injection results

All three participants produced identical detection rate, false detection count, and verdict flip for every row shown below. n_injected varies by session length (S2 longest, S8 and S15 similar).

#### Completeness: scattered NaN and contiguous dropout

Both fault types, all signals, all severities, all participants: detection rate = 1.0, false detections = 0, verdict flip = True. No cross-check detections by conformance or plausibility.

| Fault type | Signal | 0.1% n_inj (S2/S8/S15) | dr | fd | vf | Expectation |
|---|---|---|---|---|---|---|
| scattered_nan | E4_TEMP | 31/26/26 | 1.0 | 0 | True | Met |
| scattered_nan | E4_EDA | 31/26/26 | 1.0 | 0 | True | Met |
| scattered_nan | E4_HR | 7/6/6 | 1.0 | 0 | True | Met |
| scattered_nan | RespiBAN_ECG | 4442/3959/3936 | 1.0 | 0 | True | Met |
| contiguous_dropout | E4_TEMP | 31/26/26 | 1.0 | 0 | True | Met |
| contiguous_dropout | E4_EDA | 31/26/26 | 1.0 | 0 | True | Met |
| contiguous_dropout | E4_HR | 7/6/6 | 1.0 | 0 | True | Met |
| contiguous_dropout | RespiBAN_ECG | 4442/3959/3936 | 1.0 | 0 | True | Met |

Results at 1%, 5%, and 10% (n_injected scaled proportionally) follow the same pattern.

#### Conformance: non-numeric

All signals, all severities, all participants: detection rate = 1.0, false detections = 0, verdict flip = True.

| Signal | 0.1% n_inj (S2/S8/S15) | dr | fd | vf | Expectation |
|---|---|---|---|---|---|
| E4_TEMP | 31/26/26 | 1.0 | 0 | True | Met |
| E4_EDA | 31/26/26 | 1.0 | 0 | True | Met |
| E4_HR | 7/6/6 | 1.0 | 0 | True | Met |
| RespiBAN_ECG | 4442/3959/3936 | 1.0 | 0 | True | Met |

Results at 1%, 5%, and 10% follow the same pattern.

#### Conformance: out-of-device-range (RespiBAN ECG, fault value 70000)

Conformance (ADC range check, ceiling 65535) detected all injected values. Plausibility (ECG transfer function physical-unit bound 1.5 mV) independently detected all injected values as a cross-check. Both checks flagged every fault at every severity.

| Severity | n_inj (S2/S8/S15) | Conf dr | Pls cross-detections (S2/S8/S15) | fd | vf | Expectation |
|---|---|---|---|---|---|---|
| 0.1% | 4442/3959/3936 | 1.0 | 4442/3959/3936 | 0 | True | Met |
| 1% | 44420/39599/39369 | 1.0 | 44420/39599/39369 | 0 | True | Met |
| 5% | 222103/197995/196848 | 1.0 | 222103/197995/196848 | 0 | True | Met |
| 10% | 444206/395991/393697 | 1.0 | 444206/395991/393697 | 0 | True | Met |

#### Conformance: sampling-rate fault (E4 EDA, 4 Hz declared as 8 Hz)

| Participant | Original Hz | Injected Hz | Detected | Verdict flip |
|---|---|---|---|---|
| S2 | 4.0 | 8.0 | Yes | Yes |
| S8 | 4.0 | 8.0 | Yes | Yes |
| S15 | 4.0 | 8.0 | Yes | Yes |

Pre-registered expectation: detected=True, verdict_flip=True. Met.

#### Plausibility: physiological impossible values (E4_TEMP=50 deg C, E4_EDA=-1.0 uS, E4_HR=300 bpm)

Detection rate = 1.0 at all severities for all signals and all participants. Conformance detected the same faults via shared range bounds (cross_check_conformance = n_injected in all cases). False detections = 0. Verdict flip depends on whether the injected rate exceeds the 0.01 threshold.

| Signal | Severity | n_inj (S2/S8/S15) | dr | fd | Cross-conf (S2/S8/S15) | vf | Expectation |
|---|---|---|---|---|---|---|---|
| E4_TEMP | 0.1% | 31/26/26 | 1.0 | 0 | 31/26/26 | False | Met |
| E4_TEMP | 1% | 314/265/265 | 1.0 | 0 | 314/265/265 | False | See mismatches |
| E4_TEMP | 5% | 1574/1327/1328 | 1.0 | 0 | 1574/1327/1328 | True | Met |
| E4_TEMP | 10% | 3149/2655/2656 | 1.0 | 0 | 3149/2655/2656 | True | Met |
| E4_EDA | 0.1% | 31/26/26 | 1.0 | 0 | 31/26/26 | False | Met |
| E4_EDA | 1% | 314/265/265 | 1.0 | 0 | 314/265/265 | False | Met |
| E4_EDA | 5% | 1574/1327/1328 | 1.0 | 0 | 1574/1327/1328 | True | Met |
| E4_EDA | 10% | 3149/2655/2656 | 1.0 | 0 | 3149/2655/2656 | True | Met |
| E4_HR | 0.1% | 7/6/6 | 1.0 | 0 | 7/6/6 | False | Met |
| E4_HR | 1% | 78/66/66 | 1.0 | 0 | 78/66/66 | False | Met |
| E4_HR | 5% | 393/331/331 | 1.0 | 0 | 393/331/331 | True | Met |
| E4_HR | 10% | 786/662/663 | 1.0 | 0 | 786/662/663 | True | Met |

---

### Table 3: Timeliness

E4 EDA start timestamp shifted by the listed offset. Detector uses each sensor's own timestamps; the overlap window shifts with the injected start time, so the measured residual does not change with the offset. All dirty residuals remain below the 1.0 s threshold. No verdict flips at any offset.

| Participant | Baseline residual (s) | Offset injected (s) | Dirty residual (s) | Change (s) | Exceeds 1.0 s | Detected | Expectation |
|---|---|---|---|---|---|---|---|
| S2 | 0.107 | 0.5 | 0.107 | 0.000 | No | No | Met |
| S2 | 0.107 | 2.0 | 0.107 | 0.000 | No | No | Met |
| S2 | 0.107 | 10.0 | 0.107 | 0.000 | No | No | Met |
| S2 | 0.107 | 60.0 | 0.107 | 0.000 | No | No | Met |
| S2 | 0.107 | 3600.0 | 0.107 | 0.000 | No | No | Met |
| S8 | 0.000 | 0.5 | 0.000 | 0.000 | No | No | Met |
| S8 | 0.000 | 2.0 | 0.126 | 0.126 | No | No | Met |
| S8 | 0.000 | 10.0 | 0.126 | 0.126 | No | No | Met |
| S8 | 0.000 | 60.0 | 0.126 | 0.126 | No | No | Met |
| S8 | 0.000 | 3600.0 | 0.016 | 0.016 | No | No | Met |
| S15 | 0.000 | 0.5 | 0.000 | 0.000 | No | No | Met |
| S15 | 0.000 | 2.0 | 0.000 | 0.000 | No | No | Met |
| S15 | 0.000 | 10.0 | 0.000 | 0.000 | No | No | Met |
| S15 | 0.000 | 60.0 | 0.000 | 0.000 | No | No | Met |
| S15 | 0.000 | 3600.0 | 0.123 | 0.123 | No | No | Met |

Pre-registered expectation: all offsets go undetected, all residuals bounded by approximately 0.126 s (E4 EDA quantization noise at 4 Hz). Largest observed dirty residual: 0.126 s. All 15 records met the expectation.

---

### Mismatches with pre-registered expectations

**One mismatch (uncertain pre-registered case):**

**E4_TEMP plausibility, 1% severity**: the pre-registered expectation was `verdict_flip: session_length_dependent` -- explicitly marked as uncertain, because the injected rate (int(N*0.01) / (N-4)) was predicted to be "slightly above 0.01" but could go either way depending on floor rounding. Observed: verdict_flip = False for all three participants. S2: 314 injected out of 31474 valid TEMP samples, rate = 0.00998, which is below the 0.01 threshold. S8 and S15: 265 injected out of 26503 valid samples, rate = 0.01000, exactly at the threshold; because the check uses `rate <= threshold`, this also passes. Neither participant triggers a flip. This is consistent with the pre-registered reasoning; the floor rounding resolves to no-flip for all three session lengths in this dataset.

**No other mismatches.** Detection rate = 1.0 and false detections = 0 for every fault type, signal, severity, and participant. All pre-registered verdict flip predictions (excluding the session-length-dependent TEMP 1% case) were met exactly. Conformance sampling-rate faults were detected for all three participants. Timeliness faults went undetected at all five offsets for all three participants.

---

### Alignment limitation note

The timeliness results confirm the limitation discussed with the supervisor: the timestamp-anchoring timeliness detector verifies internal consistency of each sensor's own timeline but cannot detect a uniform shift applied to one sensor's recorded start time. Even a 3600 s offset (simulating a timezone conversion error) produces no change in the measured alignment residual. The dirty residual remains bounded by quantization noise (~0.126 s) regardless of the injected shift magnitude. This limitation is noted in the pre-registered design and bears on the scope of the timeliness check.

---

## Gold dataset manifest

**Date:** 2026-10-29
**Commit:** feat: gold dataset manifest

### Approach

The Gold layer in this project uses a manifest rather than a physical copy of the data. The manifest () lists every participant and signal file with:

- The authoritative file path (Silver for E4 TEMP, Bronze for all other signals)
- Its SHA-256 checksum
- Its row or sample count
- The post-cleaning check outcomes for that signal (drawn from , , and )
- Any documented intentional removals (E4 TEMP warm-up indices 0-3 replaced with NaN, recorded in )
- Exclusion flags for signals not covered by certain checks: E4 BVP and IBI from plausibility, E4 IBI from conformance range checks, RespiBAN EDA_chest and TEMP_chest from plausibility

The manifest also records a top-level summary: participant list, signal list, reference to , and a definition statement.

A  function in  recomputes every checksum and reports any mismatches.

### Why no physical copy

The WESAD raw data may not be redistributed; copying it into gold/ would create a duplicate that violates the dataset's terms of use and adds no analytical value. The only cleaned file is Silver TEMP (one CSV per participant, replacing warm-up indices 0-3 with NaN); the manifest points directly to those Silver files. All other signals are unchanged Bronze. Analysis code reads from the paths in the manifest, not from a separate gold/ copy.

### Coverage

15 participants, 6 E4 signal files + 1 RespiBAN file per participant = 105 signal files total. All post-cleaning checks pass for all participants and signals (gold_passes_all_measured_thresholds = true).

### pytest: 109 passed.

---

## Gold dataset manifest

**Date:** 2026-10-29
**Commit:** feat: gold dataset manifest

### Approach

The Gold layer in this project uses a manifest rather than a physical copy of the data. The manifest (`gold/WESAD/wesad_gold_manifest.json`) lists every participant and signal file with:

- The authoritative file path (Silver for E4 TEMP, Bronze for all other signals)
- Its SHA-256 checksum
- Its row or sample count
- The post-cleaning check outcomes for that signal (drawn from the three `*_post_cleaning.json` reports)
- Any documented intentional removals (E4 TEMP warm-up indices 0-3 replaced with NaN, recorded in `reports/wesad_cleaning.json`)
- Exclusion flags for signals not covered by certain checks: E4 BVP and IBI from plausibility, E4 IBI from conformance range checks, RespiBAN EDA_chest and TEMP_chest from plausibility

The manifest includes a top-level summary: participant list, signal list, reference to `reports/wesad_quality_report.json`, and a definition statement. A `verify_manifest` function in `src/gold_manifest.py` recomputes every checksum and reports any mismatches.

### Why no physical copy

The WESAD raw data may not be redistributed; copying it into gold/ would create a duplicate that violates the dataset terms of use and adds no analytical value. The only cleaned file is Silver TEMP (one CSV per participant, replacing warm-up indices 0-3 with NaN); the manifest points directly to those Silver files. All other signals are unchanged Bronze. Analysis code reads from the paths in the manifest.

### Coverage

15 participants, 6 E4 signal files + 1 RespiBAN file per participant = 105 signal files total. All post-cleaning checks pass for all participants and signals (`gold_passes_all_measured_thresholds = true`).

### pytest: 109 passed.

---

## Restructure: moved WESAD pipeline into wesad/ subfolder

**Date:** 2026-11-17
**Branch:** wesad-folder (merged to master as v1.4-wesad-folder)
**Why:** Preparing to add a second dataset (DEAP). Each dataset pipeline is kept in its own subfolder so config, reports, figures, tests, and source code do not collide. Data layers (bronze/, silver/, gold/) stay at the project root because they are shared across datasets (each dataset already has its own WESAD/ subdirectory within them).

**What moved into wesad/:** run_pipeline.py, src/, config/, tests/, reports/, figures/, final_checks/, docs/governance/.

**What stayed at the project root:** bronze/, silver/, gold/, README.md, requirements.txt, .gitignore, docs/progress_log.md.

**Path changes:** All Python modules now derive a WESAD root (wesad/) and a data root (project root) separately. No check logic, threshold values, or physiological bounds were changed. All 109 tests pass and reference numbers are unchanged.

---

## DEAP: replaced incomplete mirror with complete mirror

**Date:** 2026-11-17
**Branch:** deap-profile

The original DEAP archive (archive_DEAP.zip, now renamed archive_DEAP_v1.zip) contained only 12 of 32 participants. A more complete mirror (archive_DEAP_V2.zip, all 32 participants) was provided by the user and extracted to bronze/DEAP/deap-dataset/.

A cross-mirror label audit (deap/src/label_audit.py) compared both mirrors and v2 against participant_ratings.xls. The physiological data arrays are identical across both mirrors. The labels differ: mirror v1 matches the XLS reference ratings exactly (1920/1920 entries); mirror v2 has 878/5120 label entries where the Valence or Arousal value equals 9 minus the XLS value. All 32 v2 participants are affected. The source of the inversion is not explained by the archive. No label values have been modified; the discrepancy is recorded in deap/docs/governance/deap_provenance.md and deap/reports/deap_label_audit.json.
