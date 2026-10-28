# Data Quality and Governance Framework for Multimodal Behavioural Datasets

This project designs and implements a data quality and governance framework for the WESAD (Wearable Stress and Affect Detection) dataset, collected with an Empatica E4 wristband and a RespiBAN Professional chest device. The framework applies a medallion architecture (Bronze, Silver, Gold) and evaluates five quality dimensions: Conformance, Completeness, Plausibility, Temporal Alignment, and Consistency. All quality decisions and thresholds are recorded before measurement and require formal supervisor sign-off before the final report is produced.

---

## Folder structure

```
bronze/          Raw, immutable participant data. Never written to by any pipeline code.
silver/          Cleaned participant data (E4 TEMP warm-up artefact replaced with NaN).
gold/            Governance outputs: lineage metadata (gold/WESAD/wesad_lineage.json).
config/          YAML configuration files:
                   experiments.yaml        Pre-registered fault injection experiment design.
                   physiological_ranges.yaml  Per-signal physiological and device bounds.
                   thresholds.yaml         Decision thresholds for each quality dimension.
reports/         Pipeline measurement outputs (JSON). One file per check per dataset.
                   wesad_baseline.json               Bronze profiling summary.
                   wesad_conformance.json            Conformance check results.
                   wesad_completeness.json           Completeness check results.
                   wesad_plausibility.json           Plausibility check results.
                   wesad_alignment.json              Cross-modal temporal alignment.
                   wesad_cleaning.json               Silver cleaning actions and indices.
                   wesad_conformance_post_cleaning.json   Post-cleaning re-check.
                   wesad_completeness_post_cleaning.json  Post-cleaning re-check.
                   wesad_plausibility_post_cleaning.json  Post-cleaning re-check.
                   wesad_governance.json             Governance audit trail.
                   wesad_quality_report.json         Final before/after summary report.
                   experiments/                      Fault injection results (when run).
src/             Python source code:
                   profiling.py            Bronze profiling (Task 3).
                   checks/conformance.py   Conformance check (Task 4).
                   checks/completeness.py  Completeness check (Task 5).
                   checks/plausibility.py  Plausibility check (Task 6).
                   alignment.py            Cross-modal temporal alignment (Task 7).
                   cleaning.py             Silver cleaning (Task 8).
                   checks/post_cleaning.py Post-cleaning re-checks (Tasks 9 and 10).
                   governance.py           Governance artefacts -- lineage and audit (Task 10).
                   report.py               Final quality report (Task 11).
                   experiments/            Fault injection harness and runner.
tests/           pytest unit tests for check modules and injectors.
docs/            Decision log and governance documents:
                   progress_log.md         Full history of all threshold and design decisions.
                   governance/             Data Impact Assessment, Datasheet, Policy Hierarchy,
                               and Stewardship Roles documents.
run_pipeline.py  One-command pipeline runner (see Usage below).
```

---

## Setup (Windows)

Python 3.11 is required (the project was developed and tested with Python 3.11.9).

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

PowerShell's default execution policy may block `.venv\Scripts\Activate.ps1`. You do not need to activate the virtual environment; invoke Python directly:

```
.venv\Scripts\python.exe run_pipeline.py
.venv\Scripts\python.exe -m pytest tests/
```

All commands below assume `.venv\Scripts\python.exe` wherever `python` is written.

---

## Placing the WESAD data

The pipeline expects participant directories under `bronze/WESAD/`:

```
bronze/WESAD/S2/
bronze/WESAD/S3/
...
bronze/WESAD/S17/   (S1 and S12 are excluded by the original dataset)
```

Each participant directory should contain the files as distributed by the WESAD dataset authors (Schmidt et al., 2018). Raw data is covered by the dataset access agreement and must never be committed to the repository. The files `bronze/WESAD/`, `silver/WESAD/`, and `archive.zip` are listed in `.gitignore` and will not be tracked by git.

---

## Usage

### Run the full pipeline

```
python run_pipeline.py
```

Each stage prints its name and elapsed time. The runner stops immediately with a clear error message if any stage fails. To list the stages without running them:

```
python run_pipeline.py --dry-run
```

### Run the tests

```
python -m pytest tests/ -v
```

### Run the fault injection experiments

The fault injection experiments use the pre-registered design in `config/experiments.yaml`. They copy participant data to a local temporary directory (outside the project folder) and write results to `reports/experiments/fault_injection_results.json`.

```
python -m src.experiments.run_fault_injection
```

The harness prints progress per participant and per fault type. Results contain aggregate figures only; participant data copies are deleted after each run.

---

## Outputs

| File | Contents |
|---|---|
| `reports/wesad_baseline.json` | Per-participant, per-signal sample counts, data types, and NaN counts from Bronze. |
| `reports/wesad_conformance.json` | Sampling rate, range, and non-numeric conformance results per signal. |
| `reports/wesad_completeness.json` | Missingness rates and sequence gap counts per signal. |
| `reports/wesad_plausibility.json` | Physiological plausibility violation counts per signal. |
| `reports/wesad_alignment.json` | Cross-modal start-time offsets and overlap measurements per participant. |
| `reports/wesad_cleaning.json` | Indices replaced with NaN during Silver cleaning, per participant. |
| `reports/wesad_*_post_cleaning.json` | Re-run of conformance, completeness, and plausibility on Silver data. |
| `reports/wesad_governance.json` | Lineage and audit trail for governance review. |
| `reports/wesad_quality_report.json` | Final before/after comparison across all quality dimensions with threshold verdicts. |
| `gold/WESAD/wesad_lineage.json` | Per-participant, per-signal provenance document for the Gold layer. |
| `reports/experiments/fault_injection_results.json` | Fault injection results (written after running the experiment harness). |

---

## Governance and decision history

Governance documents (Data Impact Assessment, Datasheet, Policy Hierarchy, Stewardship Roles) are in `docs/governance/`.

The full history of every threshold decision, design choice, and supervisor sign-off is in `docs/progress_log.md`.

The `meta.signed_off` flag in `config/thresholds.yaml` must be set to `true` before `src.report` (Task 11) and `src.governance` (Task 5 gate) will execute. Setting it requires formal sign-off from the project owner and supervisor.
