# Policy Hierarchy -- DEAP

**Dataset:** DEAP pipeline (this repository)
**Prepared by:** Kevin Hudoyo, UTS Honours
**Grounding:** Abraham, Schneider, and vom Brocke (2019) data governance framework
**Citation:** Abraham, R., Schneider, J., & vom Brocke, J. (2019). Data governance: A conceptual framework, structured review, and research agenda. International Journal of Information Management, 49, 424-438. https://doi.org/10.1016/j.ijinfomgt.2019.07.008

---

## Overview

This document organises the policies enforced by the DEAP pipeline into a three-tier
structure built around the three data governance domains Abraham et al. (2019) identify:
data principles, data quality, and metadata management. The three-tier structure is this
project's design choice; Abraham et al. provide the domain framework that motivates and
names it. For each policy this document cites where in the pipeline it is enforced.

---

## Tier 1: Data Principles

### Policy 1.1 -- Bronze Immutability

**Statement:** Raw data in bronze/ (including all .dat files) is never written to, moved,
modified, or deleted by any pipeline stage. Bronze is the single authoritative source
of truth for the raw DEAP dataset.

**Enforcement:**
- Pipeline design: no Python module in deap/src/ opens any file in bronze/ in write mode.
  Cleaning writes to silver/DEAP/labels/, not bronze/.
- Verification: after running all pipeline stages, git status confirms bronze/DEAP/ is
  never staged as modified.

### Policy 1.2 -- Access-Agreement Data Excluded from Version Control

**Statement:** Raw physiological data covered by the DEAP access agreement is never
committed to the repository or pushed to a remote.

**Enforcement:**
- .gitignore rule: bronze/* excludes all raw DEAP .dat files.
- silver/* excludes Silver label CSVs (corrected labels are excluded, as they are
  derived from raw self-report data subject to the DEAP license).
- Gold governance artefacts (gold/DEAP/deap_gold_manifest.json,
  gold/DEAP/deap_lineage.json) contain only paths, checksums, and counts;
  no physiological measurements.

### Policy 1.3 -- Authoritative Label Source is XLS

**Statement:** participant_ratings.xls is the authoritative label source. Where labels
in the .dat files conflict with XLS (the v2 inversion artefact), XLS prevails.

**Rationale:** The v1 mirror matched XLS exactly, confirming XLS as the original
self-report record. The v2 mirror has 878 Valence/Arousal entries following v2 = 9 - v1,
which is a known mirror artefact, not a corrected rating.

**Enforcement:**
- deap/config/cleaning.yaml pre-registers the correction rule with authoritative_source
  field pointing to participant_ratings.xls.
- deap/src/cleaning.py reads XLS for all participants; writes Silver label CSVs.
- deap/src/checks/post_cleaning.py re-verifies Silver labels against XLS: 0 mismatches.

---

## Tier 2: Data Quality Policies

### Policy 2.1 -- Pre-registered Thresholds, Signed Off Before Checks Run

**Statement:** Thresholds are set and signed off before any check is built and run.
For DEAP specifically, the thresholds were set after Bronze profiling because peripheral
channel units are undocumented in the available sources; this was disclosed in
deap/config/thresholds.yaml and was approved by the supervisor (Dr Tobias Cibis) on
2026-11-18. No threshold was adjusted after seeing check results.

**Enforcement:**
- deap/config/thresholds.yaml: thresholds set and signed off (meta.signed_off: true;
  note records supervisor approval and date).
- Sign-off gate in all five check modules and the quality report: each reads
  meta.signed_off from thresholds.yaml and raises RuntimeError if false.

### Policy 2.2 -- Cleaning Rule Pre-registered Before Cleaning Runs

**Statement:** The label correction rule must be defined and signed off before cleaning
runs. The cleaning module refuses to run if cleaning.yaml is not signed off.

**Enforcement:**
- deap/config/cleaning.yaml: cleaning rule pre-registered with meta.signed_off: true.
- deap/src/cleaning.py: checks meta.signed_off in cleaning.yaml and raises RuntimeError
  if false.

### Policy 2.3 -- Physiological Plausibility Deferred Until Units Confirmed

**Statement:** Physiological plausibility checking for peripheral channels is deferred
until official DEAP documentation confirms channel units and preprocessing.

**Rationale:** Applying bounds without confirmed units would produce misleading verdicts.
Peripheral channel units are not documented in available sources (Koelstra et al. 2012).

**Enforcement:**
- deap/config/thresholds.yaml: physiological_plausibility.applied: false with rationale.
- deap/config/rules.yaml: physiological_plausibility_not_applied rule with full citation.
- deap/src/report.py: physiological_plausibility status = "not_applied" in every quality
  report run.

### Policy 2.4 -- Deterministic Processing

**Statement:** Given the same input files, every pipeline stage must produce deterministic
substantive output on every run. Non-deterministic values (run timestamps) are isolated
in a labelled run_context field.

**Enforcement:**
- All report writers use json.dump(..., sort_keys=True).
- deap/src/governance.py and deap/src/gold_manifest.py isolate generated_at timestamps
  in run_context fields labelled "This field is non-deterministic. Strip it for diffing."
- Fault injection confirmed byte-identical output across three runs.

---

## Tier 3: Metadata Management Policies

### Policy 3.1 -- Lineage Documentation

**Statement:** Every transformation applied to data must be recorded with its cause,
scope, input, output, and the assertion that Bronze was not modified.

**Enforcement:**
- deap/src/governance.py generates per-participant lineage in gold/DEAP/deap_lineage.json.
  For participants with corrections: transformations entry records action, n_corrections,
  authoritative source, and silver_output. For participants without corrections:
  transformations entry records action = "no_correction_needed".
- Schema: deap_lineage_v1 (source: gold/DEAP/deap_lineage.json).

### Policy 3.2 -- Audit Trail

**Statement:** All pipeline stages are recorded in chronological order with their report
locations and outcomes.

**Enforcement:**
- deap/src/governance.py generates a 7-stage audit trail in deap/reports/deap_governance.json:
  profiling, completeness, conformance, label_plausibility, consistency, cleaning, and
  post_cleaning. Each entry records the stage name, report path, and outcome summary.

### Policy 3.3 -- Scope Decisions Are Documented, Not Silent

**Statement:** Any decision to exclude a check, defer a dimension, or apply a non-standard
definition must be recorded with its rationale in the config files and documentation.

**Enforcement:**
- deap/config/thresholds.yaml: physiological_plausibility and timeliness entries include
  explicit applied: false and reason fields.
- deap/config/rules.yaml: physiological_plausibility_not_applied and
  timeliness_not_applicable rules include full rationale and deferred_until fields.
- deap/docs/fault_injection_deviation.md: records the pre-registration deviation and
  the alternative evaluation criterion applied.

### Policy 3.4 -- Gold Layer Does Not Contain Participant Physiological Data

**Statement:** Governance artefacts committed to the repository must not contain raw
or cleaned physiological measurements.

**Enforcement:**
- gold/DEAP/deap_lineage.json: records participant IDs, file paths, and transformation
  descriptions; does not reproduce any measurement values or labels.
- deap/reports/deap_governance.json: records stage outcomes in text; does not reproduce
  any measurement values or labels.
- deap/reports/deap_quality_report.json and related reports: record aggregate statistics
  (counts) and threshold verdicts; do not reproduce per-trial label values.
- gold/DEAP/deap_gold_manifest.json: records SHA-256 checksums and correction counts;
  does not reproduce any label values.
- silver/ is excluded from version control via .gitignore.
