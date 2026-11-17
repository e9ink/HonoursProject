"""
DEAP quality pipeline runner.

Runs all quality checks in order, then generates the quality report and fault injection.
Run from the project root:
    python deap/run_pipeline.py

Stages:
  1. completeness
  2. conformance
  3. label_plausibility
  4. consistency
  5. quality report
  6. fault injection
"""

import os
import sys

# Ensure project root is on sys.path so imports work from project root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from deap.src.checks.completeness import run as run_completeness
from deap.src.checks.conformance import run as run_conformance
from deap.src.checks.consistency import run as run_consistency
from deap.src.checks.label_plausibility import run as run_label_plausibility
from deap.src.experiments.fault_injection import run as run_fault_injection
from deap.src.report import run as run_report


def main():
    print("=== DEAP quality pipeline ===", flush=True)

    print("[1/6] Completeness check ...", flush=True)
    comp = run_completeness()
    print(f"      overall_pass={comp['overall_pass']}", flush=True)

    print("[2/6] Conformance check ...", flush=True)
    conf = run_conformance()
    print(f"      overall_pass={conf['overall_pass']}", flush=True)

    print("[3/6] Label plausibility check ...", flush=True)
    lp = run_label_plausibility()
    print(f"      overall_pass={lp['overall_pass']}", flush=True)

    print("[4/6] Consistency check ...", flush=True)
    cons = run_consistency()
    print(f"      overall_pass={cons['overall_pass']}", flush=True)

    print("[5/6] Quality report ...", flush=True)
    report = run_report()
    print(f"      overall_pass={report['overall_pass']}", flush=True)

    print("[6/6] Fault injection ...", flush=True)
    fi = run_fault_injection()
    print(f"      all_expected_outcomes_met={fi['all_expected_outcomes_met']}", flush=True)

    print("=== Pipeline complete ===", flush=True)
    print("Reports written to deap/reports/", flush=True)


if __name__ == "__main__":
    main()
