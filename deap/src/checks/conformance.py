"""
Conformance check for DEAP dataset.

Checks data shape (40, 40, 8064), labels shape (40, 4), and float64 dtype.
Threshold: max_violations = 0.

Output: deap/reports/deap_conformance.json (deterministic, sorted keys).
Never modifies bronze/ data.

Run from project root:
    python -c "from deap.src.checks.conformance import run; run()"
"""

import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_ROOT = os.path.dirname(ROOT)
DAT_DIR = os.path.join(DATA_ROOT, "bronze", "DEAP", "deap-dataset",
                        "data_preprocessed_python")
CONFIG = os.path.join(ROOT, "config", "thresholds.yaml")
OUTPUT = os.path.join(ROOT, "reports", "deap_conformance.json")

sys.path.insert(0, DATA_ROOT)
from deap.src.loader import load_dat  # noqa: E402


def check_participant(dat_path: str, thresholds: dict) -> dict:
    d = load_dat(dat_path)
    pid = os.path.splitext(os.path.basename(dat_path))[0]
    data = d["data"]
    labels = d["labels"]

    cfg = thresholds["conformance"]
    expected_data_shape = tuple(cfg["expected_data_shape"])
    expected_labels_shape = tuple(cfg["expected_labels_shape"])
    expected_dtype = cfg["expected_dtype"]

    violations = []

    actual_data_shape = tuple(data.shape)
    if actual_data_shape != expected_data_shape:
        violations.append({
            "field": "data_shape",
            "expected": list(expected_data_shape),
            "actual": list(actual_data_shape),
        })

    actual_labels_shape = tuple(labels.shape)
    if actual_labels_shape != expected_labels_shape:
        violations.append({
            "field": "labels_shape",
            "expected": list(expected_labels_shape),
            "actual": list(actual_labels_shape),
        })

    actual_dtype = str(data.dtype)
    if actual_dtype != expected_dtype:
        violations.append({
            "field": "data_dtype",
            "expected": expected_dtype,
            "actual": actual_dtype,
        })

    actual_labels_dtype = str(labels.dtype)
    if actual_labels_dtype != expected_dtype:
        violations.append({
            "field": "labels_dtype",
            "expected": expected_dtype,
            "actual": actual_labels_dtype,
        })

    return {
        "participant": pid,
        "data_shape": list(actual_data_shape),
        "labels_shape": list(actual_labels_shape),
        "data_dtype": actual_dtype,
        "labels_dtype": actual_labels_dtype,
        "violation_count": len(violations),
        "violations": violations,
        "pass": len(violations) == 0,
    }


def run(dat_dir: str = DAT_DIR, output_path: str = OUTPUT) -> dict:
    with open(CONFIG) as f:
        thresholds = yaml.safe_load(f)

    dat_files = sorted(
        os.path.join(dat_dir, fn)
        for fn in os.listdir(dat_dir)
        if fn.endswith(".dat")
    )

    results = []
    for path in dat_files:
        print(f"  conformance: {os.path.basename(path)}", file=sys.stderr)
        results.append(check_participant(path, thresholds))

    overall_pass = all(r["pass"] for r in results)
    total_violations = sum(r["violation_count"] for r in results)

    report = {
        "check": "conformance",
        "threshold_source": "deap/config/thresholds.yaml",
        "participant_count": len(results),
        "overall_pass": overall_pass,
        "total_violations": total_violations,
        "participants": {r["participant"]: r for r in results},
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"  conformance report -> {output_path}", file=sys.stderr)
    return report


if __name__ == "__main__":
    run()
