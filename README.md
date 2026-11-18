# Data Quality and Governance Framework for Multimodal Behavioural Datasets

This project designs and implements a data quality and governance framework for the WESAD (Wearable Stress and Affect Detection) dataset, collected with an Empatica E4 wristband and a RespiBAN Professional chest device. The framework applies a medallion architecture (Bronze, Silver, Gold) and runs three checks (Conformance, Completeness, Plausibility) plus cross-modal alignment detection. These checks inform assessments across five quality dimensions: accuracy, completeness, consistency, timeliness (partly assessed -- the 5-point reconstruction method relies on each device's own recorded timestamps and confirms the two streams are consistent with their own clocks, but cannot detect an offset in one device's clock; fault injection confirmed that shifts from 0.5 s to 3600 s applied to one device all went undetected), and validity; accuracy is unmeasured because no ground-truth reference instrument was recorded alongside WESAD; consistency is unmeasured because WESAD presents no distinct consistency issue: its one cross-modal structural issue (the start-time gap between devices) is a timeliness matter, and counting it under consistency as well would double-count it (see docs/progress_log.md, Threshold decisions: Consistency). Quality thresholds and physiological bounds are pre-registered in config/ and gated by a sign-off flag; design decisions and their justifications are recorded in docs/progress_log.md.

---

## Folder structure

Each dataset has its own subfolder. Data layers (Bronze, Silver, Gold) live at the project
root and are shared across datasets.

```
bronze/          Raw, immutable participant data. Never written to by any pipeline code.
silver/          Cleaned participant data (E4 TEMP warm-up artefact replaced with NaN).
gold/            Gold dataset manifest and governance outputs:
                   WESAD/wesad_lineage.json       Provenance chain for each signal.
                   WESAD/wesad_gold_manifest.json Analysis-ready dataset manifest.
docs/            Project-wide decision log:
                   progress_log.md         Full history of all threshold and design decisions.
deap/            DEAP dataset pipeline (self-contained):
  run_pipeline.py  One-command DEAP pipeline runner (12 stages).
  config/          YAML configuration files:
                     cleaning.yaml               Pre-registered label correction rule.
                     experiments.yaml            Pre-registered fault injection design.
                     rules.yaml                  Pre-registered quality rules with citations.
                     thresholds.yaml             Decision thresholds for each dimension.
  src/             Python source code:
                     profiling.py            Bronze profiling.
                     checks/completeness.py  Completeness check.
                     checks/conformance.py   Conformance check.
                     checks/label_plausibility.py  Label plausibility check.
                     checks/consistency.py   Consistency checks (structure, cross-source, scale).
                     cleaning.py             Silver label cleaning (XLS as authoritative source).
                     checks/post_cleaning.py Post-cleaning label checks on Silver CSVs.
                     governance.py           Gold governance artefacts (lineage and audit trail).
                     report.py               Before/after quality report.
                     gold_manifest.py        Gold label manifest generator and verifier.
                     experiments/            Fault injection harness and runner.
                     figures/                Figure and table generation for the thesis.
  tests/           pytest unit tests (25 tests across 7 files).
  reports/         Pipeline measurement outputs (JSON). One file per check.
  figures/         Generated figures (PNG + PDF) and tables (CSV + Markdown).
  final_checks/    Reference numbers and verification script.
  docs/governance/ Data Impact Assessment, Datasheet, Policy Hierarchy, Stewardship Roles.
wesad/           WESAD dataset pipeline (self-contained):
  run_pipeline.py  One-command WESAD pipeline runner.
  config/          YAML configuration files:
                     experiments.yaml            Pre-registered fault injection design.
                     physiological_ranges.yaml   Per-signal physiological/device bounds.
                     thresholds.yaml             Decision thresholds for each dimension.
  src/             Python source code:
                     profiling.py            Bronze profiling.
                     checks/conformance.py   Conformance check.
                     checks/completeness.py  Completeness check.
                     checks/plausibility.py  Plausibility check.
                     alignment.py            Cross-modal temporal alignment.
                     cleaning.py             Silver cleaning.
                     checks/post_cleaning.py Post-cleaning re-checks.
                     governance.py           Governance artefacts (lineage and audit trail).
                     report.py               Final quality report.
                     gold_manifest.py        Gold dataset manifest generator and verifier.
                     experiments/            Fault injection harness and runner.
                     figures/                Figure and table generation for the thesis.
  tests/           pytest unit tests for check modules and injectors.
  reports/         Pipeline measurement outputs (JSON). One file per check.
                     wesad_baseline.json               Bronze profiling summary.
                     wesad_conformance.json            Conformance check results.
                     wesad_completeness.json           Completeness check results.
                     wesad_plausibility.json           Plausibility check results.
                     wesad_alignment.json              Cross-modal temporal alignment.
                     wesad_cleaning.json               Silver cleaning actions and indices.
                     wesad_*_post_cleaning.json        Post-cleaning re-checks.
                     wesad_governance.json             Governance audit trail.
                     wesad_quality_report.json         Final before/after summary.
                     experiments/                      Fault injection results (when run).
  figures/         Generated figures (PNG + PDF) and tables (CSV + Markdown).
  final_checks/    Fact-checking notes for the thesis write-up.
  docs/governance/ Data Impact Assessment, Datasheet, Policy Hierarchy, Stewardship Roles.
README.md        This file.
requirements.txt Python dependencies.
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
.venv\Scripts\python.exe wesad/run_pipeline.py
.venv\Scripts\python.exe -m pytest wesad/tests/
```

All commands below assume `.venv\Scripts\python.exe` wherever `python` is written.

All commands should be run from the **project root** (the folder containing `wesad/`, `bronze/`, `silver/`, etc.).

---

## Placing the WESAD data

The pipeline reads from the project root's `bronze/WESAD/` folder (data layers are at the project root, not inside `wesad/`). Place participant directories there:

```
bronze/WESAD/S2/
bronze/WESAD/S3/
...
bronze/WESAD/S17/   (S1 and S12 are absent: two participants' data were
                     discarded due to sensor malfunction, Schmidt et al., 2018)
```

Each participant directory should contain the files as distributed by the WESAD dataset authors. Raw data is covered by the dataset access agreement and must never be committed to the repository. The `.gitignore` entries that prevent tracking are:

```
bronze/*
silver/*
archive.zip
experiments/scratch/
experiments/scratch_dirty/
```

The fault injection harness now writes scratch copies to the system temporary directory (outside the repository), so the `experiments/scratch/` and `experiments/scratch_dirty/` entries are retained as a safeguard only.

---

## Usage

### Run the full DEAP pipeline

From the project root:

```
python deap/run_pipeline.py
```

Runs 12 stages: Bronze profiling, completeness, conformance, label plausibility, consistency, baseline quality report, Silver cleaning (label correction), post-cleaning checks, label audit (v1/v2 mirror vs XLS; inversion rule), before/after quality report, Gold governance, Gold manifest. Each stage prints its name and elapsed time.

### Run the DEAP tests

```
python -m pytest deap/tests/ -v
```

### Generate DEAP figures and tables

```
python deap/src/figures/make_figures.py
```

Saves Figure 4.4 (label audit before/after) and Figure 4.5 (Temp channel scale split) plus two tables to `deap/figures/`.

### Verify DEAP reference numbers

```
python deap/final_checks/compare_ref_numbers.py
```

Checks 17 reference numbers against the live pipeline reports. All must pass.

### Verify DEAP Gold manifest checksums

```python
import sys
sys.path.insert(0, '.')
from deap.src.gold_manifest import verify_manifest
verify_manifest()
```

---

### Run the full WESAD pipeline

From the project root:

```
python wesad/run_pipeline.py
```

Each stage prints its name and elapsed time. The runner stops immediately with a clear error message if any stage fails. To list the stages without running them:

```
python wesad/run_pipeline.py --dry-run
```

### Run the tests

From the project root:

```
python -m pytest wesad/tests/ -v
```

### Generate figures and tables

From the project root:

```
python wesad/src/figures/make_figures.py
```

Saves four figures (PNG and PDF, 300 dpi) and three CSV/Markdown tables to `wesad/figures/`.

### Run the fault injection experiments

The fault injection experiments use the pre-registered design in `wesad/config/experiments.yaml`. They copy participant data to a local temporary directory (outside the project folder) and write results to `wesad/reports/experiments/fault_injection_results.json`.

From the project root:

```
python wesad/src/experiments/run_fault_injection.py
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
| `reports/wesad_governance.json` | Governance audit trail. Lineage is in `gold/WESAD/wesad_lineage.json`. |
| `reports/wesad_quality_report.json` | Final before/after comparison across all quality dimensions with threshold verdicts. |
| `gold/WESAD/wesad_lineage.json` | Per-participant, per-signal provenance document for the Gold layer. |
| `reports/experiments/fault_injection_results.json` | Fault injection results (written after running the experiment harness). |

---

## Governance and decision history

Governance documents (Data Impact Assessment, Datasheet, Policy Hierarchy, Stewardship Roles) are in `docs/governance/`.

The full history of every threshold decision, design choice, and supervisor sign-off is in `docs/progress_log.md`.

Five modules gate on a `meta.signed_off` flag before running:

- `src/checks/conformance.py`, `src/checks/plausibility.py`, `src/cleaning.py`, and `src/checks/post_cleaning.py` each check `meta.signed_off` in `config/physiological_ranges.yaml` before using any physiological bounds.
- `src/report.py` checks `meta.signed_off` in `config/thresholds.yaml` before producing the final quality report.

Setting either flag requires formal sign-off from the project owner and supervisor.

---

## Known limitations

**Timeliness is partly assessed.**
The 5-point reconstruction method relies on each device's own recorded timestamps. It confirms the two streams are consistent with their own clocks but cannot detect an offset in one device's clock. Fault injection confirmed that start-time shifts from 0.5 s to 3600 s applied to one device all went undetected. Signal-based alignment (for example accelerometer cross-correlation) is future work. See docs/progress_log.md (Timeliness section) and reports/experiments/fault_injection_results.json.

**Within-bounds faults are not tested.**
The fault injection harness only injects faults that push values outside the configured physiological bounds. Faults that keep all values within bounds (e.g. a small systematic offset to a signal) would not be detected by the current conformance or plausibility checks. This is a known gap in the validation coverage.

**Accuracy is not measured.**
No ground-truth reference instrument was recorded alongside WESAD. Accuracy in the Wang and Strong (1996) sense cannot be assessed without a reference. This is documented in reports/wesad_quality_report.json (dimensions.accuracy) and config/thresholds.yaml.

**Consistency is not assessed.**
No dedicated consistency metric is defined for WESAD. The only cross-modal structural issue (the ~19-minute start-time gap between devices) is captured under the timeliness dimension. Defining a separate consistency metric would double-count the same phenomenon. See config/thresholds.yaml and docs/progress_log.md.
