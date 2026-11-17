# Policy Hierarchy

**Dataset:** WESAD pipeline (this repository)
**Prepared by:** Kevin Hudoyo, UTS Honours
**Grounding:** Abraham, Schneider, and vom Brocke (2019) data governance framework
**Citation:** Abraham, R., Schneider, J., & vom Brocke, J. (2019). Data governance: A conceptual framework, structured review, and research agenda. International Journal of Information Management, 49, 424-438. https://doi.org/10.1016/j.ijinfomgt.2019.07.008

---

## Overview

This document organises the policies enforced by this pipeline into a three-tier structure, built around the three data governance domains Abraham et al. (2019) identify: data principles, data quality, and metadata management. The three-tier structure is this project's design choice; Abraham et al. provide the domain framework that motivates and names it. For each policy this document cites where in the pipeline it is enforced.

---

## Tier 1: Data Principles

These are the foundational, non-negotiable rules that all other policies serve. They cannot be overridden by any pipeline run.

### Policy 1.1 -- Bronze Immutability

**Statement:** Raw data in `bronze/` is never written to, moved, modified, or deleted by any pipeline stage. Bronze is the single authoritative source of truth for the raw dataset.

**Rationale:** Once raw data is altered, the ability to audit what the pipeline did and to rerun checks from scratch is lost. Immutability ensures every quality finding refers to known, fixed source data.

**Enforcement:**
- Pipeline design: no Python module in `src/` opens any file in `bronze/` in write mode. Cleaning writes to `silver/`, not `bronze/`.
- Verification: after running all pipeline stages, `git status` confirms `bronze/WESAD/` is never staged as modified (verified in `docs/progress_log.md`, Task 2 section).
- Scope: applies to all pipeline stages including profiling (`src/profiling.py`), all checks (`src/checks/`), alignment (`src/alignment.py`), and cleaning (`src/cleaning.py`).

### Policy 1.2 -- Access-Agreement Data Excluded from Version Control

**Statement:** Raw physiological data covered by the WESAD access agreement is never committed to the repository or pushed to a remote.

**Rationale:** The access agreement constrains redistribution. Version control systems retain history indefinitely; a single accidental commit could expose participant data permanently.

**Enforcement:**
- `.gitignore` rules: `bronze/*` (with exception for `bronze/.gitkeep`), `archive.zip` (source: `.gitignore`).
- The Silver layer contains only processed outputs (NaN-substituted TEMP.csv) and is also excluded (`silver/*` with exception for `silver/.gitkeep`) (source: `.gitignore`).
- Gold layer governance artefacts (`gold/WESAD/wesad_lineage.json`) do not contain participant physiological measurements and are committed.

### Policy 1.3 -- Flag-and-Retain over Silent Deletion

**Statement:** Out-of-range values that are not documented artefacts are flagged and retained with quality annotations, not silently removed or overwritten.

**Rationale:** Silent deletion conceals data quality problems. Retaining flagged values with annotations allows downstream users to make informed decisions about how to handle them.

**Enforcement:**
- `src/cleaning.py` (`reports/wesad_cleaning.json`, field `note_flag_and_retain`): "Out-of-range values in all other signals are flag-and-retain: recorded in reports/wesad_conformance.json and reports/wesad_plausibility.json, NOT removed or altered here."
- Only the E4 TEMP warm-up artefact is removed, because it is a documented hardware initialisation artefact with a known cause, not a physiological measurement. All other out-of-range values (e.g. EDA values at the device ceiling of 100 µS) are flagged as "device reached measurement capacity" and retained (source: `config/physiological_ranges.yaml`, EDA provenance note; `docs/progress_log.md`, flag-and-retain decision).
- Supervisor confirmed the flag-and-retain approach for EDA rail-hits (source: `config/thresholds.yaml`, validity comment referencing Dr. Tobias Cibis, 2026-08-27).

---

## Tier 2: Data Quality Policies

These policies govern how quality is measured and assured. They translate the Tier 1 principles into operational checks.

### Policy 2.1 -- Pre-registered Thresholds, Locked Before Checks Run

**Statement:** Quality thresholds must be defined and signed off before any check runs. No threshold may be set, adjusted, or overridden after seeing the data.

**Rationale:** Post-hoc threshold adjustment invalidates the quality assessment. A threshold set after seeing the results is not a quality gate; it is a rationalisation of whatever the data shows.

**Enforcement:**
- `config/thresholds.yaml`: thresholds are set by Kevin and signed off by Dr. Tobias Cibis. The file includes `meta.locked: true` and `meta.signed_off: true` with `date_locked: 2026-09-09` (source: `config/thresholds.yaml`).
- Gate in `src/report.py`: reads `meta.signed_off` from `config/thresholds.yaml` and raises `RuntimeError` if it is false, refusing to run.
- `docs/progress_log.md` (Task 1 section, design-decisions entry dated 2026-08-22): thresholds were pre-registered before any check ran.

### Policy 2.2 -- Completeness Measures Unintended Absence Only

**Statement:** The missingness rate counts only unintended absence. Samples documented as intentionally removed during cleaning are excluded from the rate and reported separately.

**Rationale:** A threshold of 0.0 missingness is a preservation floor; it should not penalise documented quality-improvement actions. Conflating intentional removals with unintended missingness would make the threshold logically incoherent. Decision by Kevin, 2026-10-12 (source: `docs/progress_log.md`, "Completeness definition: intentional removals excluded" section).

**Enforcement:**
- `src/checks/completeness.py`, function `_check_e4_fixed`: accepts `intentional_removal_indices` parameter; computes `missingness_rate` from `n_unintentional_nan` only; reports intentional removals in a separate `intentional_removals` field.
- `src/checks/post_cleaning.py`: loads intentional removal indices from `reports/wesad_cleaning.json` and passes them to `check_e4`.
- Post-cleaning completeness report `reports/wesad_completeness_post_cleaning.json`: summary includes `e4_intentional_removals: 60` and `e4_overall_missingness_rate: 0.0`.

### Policy 2.3 -- Conformance Ranges Must Be Signed Off

**Statement:** Physiological range bounds used for conformance and plausibility checks must be signed off before any check runs. No bound may be invented by pipeline code.

**Rationale:** Range bounds are domain-knowledge claims, not computational facts. They require expert review.

**Enforcement:**
- `config/physiological_ranges.yaml`: `meta.signed_off: true`, `signed_off_by: Dr. Tobias Cibis`, `date_locked: 2026-09-09` (source: `config/physiological_ranges.yaml`).
- Gate in `src/checks/conformance.py` (`load_config`), `src/checks/plausibility.py` (`_load_config`), `src/cleaning.py` (`_load_skin_temp_bounds`), and `src/checks/post_cleaning.py` (`_load_ranges`): all four check `meta.signed_off` in `config/physiological_ranges.yaml` and raise `RuntimeError` if it is false, refusing to run.
- Comment at top of `config/physiological_ranges.yaml`: "never edited or invented by automated pipeline code."

### Policy 2.4 -- Deterministic Processing

**Statement:** Given the same input files, every pipeline stage must produce deterministic substantive output on every run. Non-deterministic values (run timestamps in governance outputs) are isolated in a clearly labelled `run_context` field and do not affect the substantive content.

**Rationale:** Non-deterministic outputs make audit trails unreliable. If the same input produces different outputs on two runs, it is impossible to know which output the pipeline "really" produced.

**Enforcement:**
- All report writers use `json.dump(..., sort_keys=True)` to ensure consistent field ordering (source: `src/profiling.py`, `src/checks/conformance.py`, `src/checks/completeness.py`, `src/checks/plausibility.py`).
- No timestamps are included in main report content; run context (timestamp) is isolated in clearly labelled fields when needed (source: `src/governance.py`, `run_context` field with note "non-deterministic; strip for diffing").
- Verified by SHA-256 hash comparison of `reports/wesad_baseline.json` across two consecutive runs (source: `docs/progress_log.md`, Task 2 determinism verification section).

---

## Tier 3: Metadata Management Policies

These policies govern how the pipeline documents its own provenance, lineage, and decision history. Grounded in Abraham et al. (2019), which provides a data governance framework identifying three domains: data principles, data quality, and metadata management.

### Policy 3.1 -- Lineage Documentation

**Statement:** Every transformation applied to data must be recorded with its cause, scope, input, output, and the assertion that Bronze was not modified.

**Rationale:** Without lineage records, it is impossible to know what changed between Bronze and Gold, or why.

**Enforcement:**
- `src/governance.py` generates per-signal, per-participant lineage in `gold/WESAD/wesad_lineage.json`. Only E4 TEMP has a `transformations` entry (the warm-up NaN substitution). All other signals record `source: bronze` with no transformation.
- Schema: `wesad_lineage_v1`. Each participant entry includes `e4` (5 signals) and `respiban` (8 channels) (source: `gold/WESAD/wesad_lineage.json`).

### Policy 3.2 -- Audit Trail

**Statement:** All pipeline stages are recorded in chronological order with their report locations and outcomes.

**Rationale:** An audit trail allows reconstruction of the full processing history and supports accountability (Tallon et al., 2013).

**Enforcement:**
- `src/governance.py` generates a 6-stage audit trail in `reports/wesad_governance.json`: profiling, conformance, completeness, plausibility, alignment, and cleaning. Each entry records the stage name, report file path, and a summary of the outcome (source: `reports/wesad_governance.json`, `audit_trail` array).

### Policy 3.3 -- Scope Decisions Are Documented, Not Silent

**Statement:** Any decision to exclude a signal, skip a check, or apply a non-standard definition must be recorded with its rationale in `docs/progress_log.md`.

**Rationale:** Silent omissions cannot be reviewed or reversed. Documented decisions can.

**Enforcement:**
- `docs/progress_log.md` contains formal decision entries for: consistency not measured (2026-08-22); BVP excluded from plausibility (2026-08-27); IBI excluded from plausibility (2026-08-27); RespiBAN chest EDA/TEMP scoped out of plausibility checking (2026-10-09); completeness definition change (2026-10-12).
- `config/physiological_ranges.yaml` includes inline justification comments for each excluded signal (BVP, IBI, RespiBAN CH2, RespiBAN CH4).

### Policy 3.4 -- Gold Layer Does Not Contain Participant Physiological Data

**Statement:** Governance artefacts committed to the repository (in `gold/` and `reports/`) must not contain raw or cleaned physiological measurements.

**Rationale:** Committing physiological data would violate the access agreement constraint in Policy 1.2.

**Enforcement:**
- `gold/WESAD/wesad_lineage.json`: records signal names, file paths, and transformation descriptions; does not reproduce any measurement values.
- `reports/wesad_governance.json`: records stage outcomes in text; does not reproduce any measurement values.
- `reports/wesad_quality_report.json` and related reports: record aggregate statistics (counts, rates) and threshold verdicts; do not reproduce per-sample values.
- `silver/` (excluded from version control via `.gitignore`) is the only location where cleaned sample values exist outside `bronze/`.
