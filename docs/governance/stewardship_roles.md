# Data Stewardship Roles

**Dataset:** WESAD pipeline (this repository)
**Prepared by:** Kevin Hudoyo, UTS Honours
**Grounding:** Tallon, Ramirez, and Short (2013) information governance / accountability framework
**Citation:** Tallon, P. P., Ramirez, R. V., & Short, J. E. (2013). The information artifact in IT governance: Toward a theory of information governance. Journal of Management Information Systems, 30(3), 141-178. https://doi.org/10.2753/MIS0742-1222300306

---

## Overview

Tallon et al. (2013) define information governance in terms of accountability structures: who is responsible for what decisions, and how that responsibility is maintained over time. This document applies those structures to the WESAD pipeline, identifying four roles and mapping them to the project where the mapping is factual.

---

## Role 1: Data Owner

**Definition (from Tallon et al., 2013):**
The data owner holds ultimate accountability for the data asset. The owner authorises use, sets policy, and bears responsibility for how the data is managed and what decisions are made with it.

**In the context of the original WESAD dataset:**
[KEVIN TO COMPLETE: the research institution or group that created and maintains WESAD is the data owner of the raw dataset. The access agreement governs what this project may do with the data.]

**In the context of this pipeline's outputs:**
The data owner of the pipeline outputs (quality reports, governance artefacts, Silver layer cleaned data) is Kevin Hudoyo as the responsible researcher. Dr. Tobias Cibis, as supervising academic, holds oversight accountability for the research project as a whole.

**Responsibilities in this project:**
- Deciding the scope of the pipeline (which datasets, which signals, which checks).
- Approving the completeness definition change (documented in `docs/progress_log.md`, dated 2026-10-12).
- Deciding which signals are excluded from plausibility checking and why (documented in `docs/progress_log.md`).
- Ensuring raw data is handled in accordance with the access agreement (raw data excluded from version control via `.gitignore`).

---

## Role 2: Data Steward

**Definition (from Tallon et al., 2013):**
The data steward is responsible for data quality standards: defining what "good data" means, ensuring those standards are applied consistently, and documenting deviations and decisions.

**In the context of this pipeline:**
The stewardship function is shared between Kevin Hudoyo and Dr. Tobias Cibis.

**Kevin Hudoyo (primary steward):**
- Proposes and documents quality thresholds, physiological ranges, and scope decisions.
- Runs all CCP checks and alignment detection.
- Records all decisions and deviations in `docs/progress_log.md`.
- Holds delegated authority for implementation decisions, subject to supervisor confirmation.

**Dr. Tobias Cibis (approving steward):**
- Signed off quality thresholds in `config/thresholds.yaml` on 2026-09-09 (source: `config/thresholds.yaml`, `meta.signed_off_by` and `meta.date_locked`).
- Signed off physiological ranges in `config/physiological_ranges.yaml` on 2026-09-09 (source: `config/physiological_ranges.yaml`, `meta.signed_off_by`).
- Confirmed exclusion of BVP and IBI from plausibility checking (source: `config/physiological_ranges.yaml`, comments for BVP and IBI entries).
- The pipeline enforces this sign-off as a hard gate: plausibility checks and the quality report refuse to run while `meta.signed_off` is false (source: `config/thresholds.yaml` gate comment, `src/checks/plausibility.py`).

**Responsibilities:**
- Defining what constitutes a plausible physiological value (physiological ranges config).
- Deciding which signals require cleaning versus flag-and-retain.
- Approving the completeness definition (intentional removals excluded).
- Documenting scope decisions so they are reversible and traceable.

---

## Role 3: Data Custodian

**Definition (from Tallon et al., 2013):**
The data custodian is responsible for the physical storage, security, and access control of data. The custodian implements the policies set by the owner and steward but does not set those policies.

**In the context of this pipeline:**
Kevin Hudoyo acts as data custodian for the local copy of WESAD.

**Responsibilities:**
- Maintaining the local machine where raw data resides. [KEVIN TO COMPLETE: backup and retention policy.]
- Enforcing Bronze immutability: the pipeline is designed so that no code writes to, moves, or modifies anything in `bronze/`. This is a pipeline-design constraint, not a filesystem permission. Bronze immutability was verified during the profiling task (git status confirmed `bronze/WESAD/` was never staged as modified after profiling ran) (source: `docs/progress_log.md`, Task 2 section).
- Excluding raw data from version control: `bronze/*` and `archive.zip` are listed in `.gitignore` (source: `.gitignore`).
- Maintaining Silver layer outputs: cleaned TEMP.csv files for all 15 participants in `silver/WESAD/`.
- Ensuring Gold layer governance artefacts are committed to the repository: lineage (`gold/WESAD/wesad_lineage.json`) and audit trail (`reports/wesad_governance.json`).

---

## Role 4: Data Consumer

**Definition (from Tallon et al., 2013):**
The data consumer uses the data for analysis or model development. The consumer relies on the quality assurances provided by the steward and custodian, and is responsible for using the data within its documented scope.

**In the context of this pipeline:**
Kevin Hudoyo is the primary current consumer, using the Gold layer outputs for the Honours research project. Future consumers may include other researchers who access the pipeline outputs.

**Responsibilities:**
- Reading and understanding the quality reports before using data for modelling or analysis.
- Noting documented exclusions (BVP, IBI, RespiBAN EDA/TEMP plausibility) and the known quality findings (TEMP warm-up artefact, sensor attachment issues for S2/S17).
- Not redistributing raw data outside the terms of the access agreement.
- Using Silver layer TEMP files (not Bronze) when working with the cleaned E4 TEMP channel.

**What the consumer receives:**
- Bronze: raw, immutable physiological data.
- Silver: cleaned E4 TEMP (warm-up NaN at indices 0-3 per participant); all other signals identical to Bronze.
- Gold / reports: quality reports, governance artefacts, before/after quality comparison, lineage and audit trail.
