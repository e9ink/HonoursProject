"""
Runner for the pre-registered fault injection experiments.

Usage (from project root):
    python wesad/src/experiments/run_fault_injection.py

Runs in the foreground and prints progress per participant and fault type.
Results are written to reports/experiments/fault_injection_results.json.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.experiments.fault_injection import run_all_experiments, RESULTS_PATH


def main() -> None:
    """Run all fault-injection scenarios and write results to experiments/results/."""
    print("=" * 60)
    print("Fault injection experiments -- WESAD")
    print("Design: config/experiments.yaml")
    print(f"Output: {RESULTS_PATH}")
    print("=" * 60)
    t0 = time.monotonic()
    try:
        run_all_experiments()
    except KeyboardInterrupt:
        print("\nInterrupted by user. No results written.")
        sys.exit(1)
    elapsed = time.monotonic() - t0
    print(f"\nDone. Elapsed: {elapsed:.0f}s")


if __name__ == "__main__":
    main()
