"""
One-command runner for the WESAD data quality pipeline.

Runs each stage in order, prints elapsed time, and stops immediately if any
stage raises an exception.

Usage:
    python run_pipeline.py           # run all stages
    python run_pipeline.py --dry-run # list stages without running them
"""

import argparse
import importlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

STAGES = [
    ("Profiling (Bronze baseline)",        "src.profiling",               "main"),
    ("Conformance check",                  "src.checks.conformance",      "main"),
    ("Completeness check",                 "src.checks.completeness",     "main"),
    ("Plausibility check",                 "src.checks.plausibility",     "main"),
    ("Temporal alignment",                 "src.alignment",               "main"),
    ("Silver cleaning",                    "src.cleaning",                "main"),
    ("Post-cleaning checks",               "src.checks.post_cleaning",    "main"),
    ("Governance artefacts",               "src.governance",              "main"),
    ("Quality report",                     "src.report",                  "main"),
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the WESAD data quality pipeline.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the stages in order without running them.",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("Pipeline stages (dry run -- not executing):")
        for i, (label, module, _) in enumerate(STAGES, 1):
            print(f"  {i:2}. {label}  ({module})")
        return

    total_start = time.monotonic()
    for i, (label, module_path, fn_name) in enumerate(STAGES, 1):
        print(f"[{i}/{len(STAGES)}] {label} ...", flush=True)
        t0 = time.monotonic()
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, fn_name)
            fn()
        except Exception as exc:
            elapsed = time.monotonic() - t0
            print(f"  FAILED after {elapsed:.1f}s: {exc}")
            sys.exit(1)
        elapsed = time.monotonic() - t0
        print(f"  done ({elapsed:.1f}s)")

    total = time.monotonic() - total_start
    print(f"\nAll {len(STAGES)} stages complete. Total: {total:.1f}s")


if __name__ == "__main__":
    main()
