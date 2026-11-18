"""
DEAP quality pipeline runner.

Runs all quality checks and governance steps in order.
Run from the project root:
    python deap/run_pipeline.py

Stages:
   1. profiling         (Bronze baseline)
   2. completeness      (Bronze data array)
   3. conformance       (Bronze data array and shape)
   4. label_plausibility (Bronze labels)
   5. consistency       (Bronze structure + cross-source)
   6. quality_report    (before: Bronze state)
   7. cleaning          (Silver labels from XLS)
   8. post_cleaning     (Silver label checks)
   9. label_audit       (v1/v2 mirror vs XLS; inversion rule)
  10. quality_report    (after: before/after comparison)
  11. governance        (lineage + audit trail)
  12. gold_manifest     (SHA-256 manifest)
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from deap.src.checks.completeness import run as run_completeness
from deap.src.checks.conformance import run as run_conformance
from deap.src.checks.consistency import run as run_consistency
from deap.src.checks.label_plausibility import run as run_label_plausibility
from deap.src.checks.post_cleaning import run as run_post_cleaning
from deap.src.cleaning import run as run_cleaning
from deap.src.gold_manifest import generate_manifest
from deap.src.governance import main as run_governance
from deap.src.label_audit import run_audit
from deap.src.report import run as run_report


def _run_profiling():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "profiling",
        os.path.join(os.path.dirname(__file__), "src", "profiling.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    bronze_dir = os.path.join(
        PROJECT_ROOT, "bronze", "DEAP", "deap-dataset", "data_preprocessed_python"
    )
    output_path = os.path.join(
        os.path.dirname(__file__), "reports", "deap_baseline.json"
    )
    mod.run_profiling(bronze_dir, output_path)


def main():
    print("=== DEAP quality pipeline ===", flush=True)

    print("[1/12] Bronze profiling ...", flush=True)
    try:
        _run_profiling()
        print("       done", flush=True)
    except Exception as exc:
        print(f"       WARNING: profiling skipped ({exc})", flush=True)

    print("[2/12] Completeness check ...", flush=True)
    comp = run_completeness()
    print(f"       overall_pass={comp['overall_pass']}", flush=True)

    print("[3/12] Conformance check ...", flush=True)
    conf = run_conformance()
    print(f"       overall_pass={conf['overall_pass']}", flush=True)

    print("[4/12] Label plausibility check ...", flush=True)
    lp = run_label_plausibility()
    print(f"       overall_pass={lp['overall_pass']}", flush=True)

    print("[5/12] Consistency check ...", flush=True)
    cons = run_consistency()
    print(f"       overall_pass={cons['overall_pass']}", flush=True)

    print("[6/12] Quality report (Bronze baseline) ...", flush=True)
    report = run_report()
    print(f"       overall_pass={report['overall_pass']}", flush=True)

    print("[7/12] Silver cleaning ...", flush=True)
    cleaning = run_cleaning()
    print(f"       total_corrections={cleaning['total_corrections']}", flush=True)

    print("[8/12] Post-cleaning check ...", flush=True)
    post = run_post_cleaning()
    print(f"       overall_pass={post['overall_pass']}", flush=True)

    print("[9/12] Label audit (v1/v2 mirror vs XLS; inversion rule) ...", flush=True)
    run_audit()
    print("       done", flush=True)

    print("[10/12] Quality report (before/after) ...", flush=True)
    report = run_report()
    print(f"       overall_pass={report['overall_pass']}", flush=True)

    print("[11/12] Gold governance ...", flush=True)
    run_governance()

    print("[12/12] Gold manifest ...", flush=True)
    generate_manifest()

    print("=== Pipeline complete ===", flush=True)
    print("Reports written to deap/reports/", flush=True)
    print("Gold artefacts written to gold/DEAP/", flush=True)


if __name__ == "__main__":
    main()
