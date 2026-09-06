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

−2 to +2 g (from E4 hardware specification in info.txt).
