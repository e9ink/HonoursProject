# Data Stewardship Roles -- DEAP

**Dataset:** DEAP pipeline (this repository)
**Prepared by:** Kevin Hudoyo, UTS Honours
**Grounding:** Tallon, Ramirez, and Short (2013) information governance / accountability framework
**Citation:** Tallon, P. P., Ramirez, R. V., & Short, J. E. (2013). The information artifact in IT governance: Toward a theory of information governance. Journal of Management Information Systems, 30(3), 141-178. https://doi.org/10.2753/MIS0742-1222300306

---

## Overview

This document identifies four data governance roles and maps them to the DEAP pipeline.
The roles follow general data governance practice; Tallon et al. (2013) ground the
accountability framing. Tallon et al. discuss information governance in terms of
structural, procedural, and relational practices and mention data custodians and
stewards in passing (p. 153), but do not formally define the four-role model below.
The role definitions are general data governance practice informed by Tallon et al.'s
accountability framing.

---

## Role 1: Data Owner

**Definition:**
The data owner holds ultimate accountability for the data asset. The owner authorises
use, sets policy, and bears responsibility for how the data is managed.

**In the context of the original DEAP dataset:**
Sander Koelstra and collaborators (Queen Mary University of London) are the data owners
of the raw DEAP dataset. The dataset is distributed under a license agreement
(non-commercial research use; Koelstra et al. 2012, p. 18). This project uses the
dataset in accordance with that license.

**In the context of this pipeline's outputs:**
Kevin Hudoyo is the data owner of the pipeline outputs (quality reports, Silver label
CSVs, governance artefacts). Dr. Tobias Cibis holds oversight accountability for the
research project as a whole.

**Responsibilities in this project:**
- Deciding the scope of the pipeline (which checks apply, which are deferred).
- Ensuring raw data is handled in accordance with the DEAP license.
- Approving all pre-registered configurations before checks run.

---

## Role 2: Data Steward

**Definition:**
The data steward is responsible for data quality standards: defining what good data
means, ensuring standards are applied consistently, and documenting deviations.

**In the context of this pipeline:**
Stewardship is shared between Kevin Hudoyo and Dr. Tobias Cibis.

**Kevin Hudoyo (primary steward):**
- Proposes and documents quality thresholds and scope decisions in
  deap/config/thresholds.yaml and deap/config/rules.yaml.
- Pre-registers the cleaning rule in deap/config/cleaning.yaml.
- Runs all quality checks and records results in deap/reports/.
- Documents deviations (e.g. fault injection pre-registration deviation in
  deap/docs/fault_injection_deviation.md).
- Holds delegated authority for implementation decisions, subject to supervisor
  confirmation.

**Dr. Tobias Cibis (approving steward):**
- Signed off quality thresholds in deap/config/thresholds.yaml on 2026-11-18
  (meta.signed_off_by field; note: pending formal supervisor review).
- The pipeline enforces this sign-off as a hard gate: all five check modules and
  the quality report refuse to run while meta.signed_off is false.

**Responsibilities:**
- Defining which quality checks are applicable and which are deferred.
- Approving the authoritative label source (participant_ratings.xls).
- Deciding that physiological plausibility checking is deferred until units are confirmed.
- Documenting deviations from pre-registered designs.

---

## Role 3: Data Custodian

**Definition:**
The data custodian is responsible for the physical storage, security, and access
control of data. The custodian implements the policies set by the owner and steward.

**In the context of this pipeline:**
Kevin Hudoyo acts as data custodian for the local copy of DEAP.

**Responsibilities:**
- Maintaining the local machine where raw data resides. Raw DEAP .dat files are stored
  locally and in a personal OneDrive backup for research continuity (academic,
  non-commercial). The backup is not shared. Raw data is excluded from version control.
- Enforcing Bronze immutability: no pipeline code writes to or modifies bronze/ .dat
  files. Verified by git status after each pipeline run.
- Excluding raw data from version control: bronze/* is listed in .gitignore.
- Maintaining Silver layer outputs: label CSVs for all 32 participants in
  silver/DEAP/labels/.
- Ensuring Gold layer governance artefacts are committed to the repository:
  gold/DEAP/deap_gold_manifest.json and gold/DEAP/deap_lineage.json.

---

## Role 4: Data Consumer

**Definition:**
The data consumer uses the data for analysis or model development. The consumer relies
on the quality assurances provided by the steward and custodian.

**In the context of this pipeline:**
Kevin Hudoyo is the primary current consumer, using the Gold layer outputs for the
Honours research project.

**Responsibilities:**
- Reading and understanding quality reports before using data for modelling or analysis.
- Noting documented issues: Temp scale split, GSR negative values, undocumented
  sampling rate and preprocessing.
- Not redistributing raw data outside the DEAP license terms.
- Using Silver label CSVs (not Bronze labels) for training targets when labels are needed.

**What the consumer receives:**
- Bronze: read-only .dat files with physiological data array and original labels.
- Silver: corrected label CSVs (878 v2 inversions resolved; XLS as authoritative source).
- Gold / reports: quality reports, governance artefacts, before/after quality comparison,
  lineage and audit trail.
