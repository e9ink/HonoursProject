"""
Label plausibility check for DEAP dataset.

Checks that every label value is within the SAM scale [1, 9].
Threshold: max_out_of_range = 0.
Source: Koelstra et al. (2012), p. 6: "numbers 1-9 printed below" the SAM.

Output: deap/reports/deap_label_plausibility.json (deterministic, sorted keys).
Never modifies bronze/ data.

Run from project root:
    python -c "from deap.src.checks.label_plausibility import run; run()"
"""

import json
import os
import sys

import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_ROOT = os.path.dirname(ROOT)
DAT_DIR = os.path.join(DATA_ROOT, "bronze", "DEAP", "deap-dataset",
                        "data_preprocessed_python")
CONFIG = os.path.join(ROOT, "config", "thresholds.yaml")
OUTPUT = os.path.join(ROOT, "reports", "deap_label_plausibility.json")

sys.path.insert(0, DATA_ROOT)
from deap.src.loader import load_dat  # noqa: E402

LABEL_DIMS = ["valence", "arousal", "dominance", "liking"]


def check_participant(dat_path: str, thresholds: dict) -> dict:
    d = load_dat(dat_path)
    pid = os.path.splitext(os.path.basename(dat_path))[0]
    labels = d["labels"]  # (40, 4)

    cfg = thresholds["label_plausibility"]
    lo = float(cfg["min_label_value"])
    hi = float(cfg["max_label_value"])
    tol = 1e-9

    violations = []
    for trial_idx in range(labels.shape[0]):
        for dim_idx, dim_name in enumerate(LABEL_DIMS):
            val = float(labels[trial_idx, dim_idx])
            if val < lo - tol or val > hi + tol:
                violations.append({
                    "trial_index": trial_idx,
                    "experiment_id": trial_idx + 1,
                    "dim": dim_name,
                    "value": round(val, 6),
                })

    return {
        "participant": pid,
        "total_out_of_range": len(violations),
        "threshold": cfg["max_out_of_range"],
        "pass": len(violations) <= cfg["max_out_of_range"],
        "violations": violations,
    }


def run(dat_dir: str = DAT_DIR, output_path: str = OUTPUT) -> dict:
    with open(CONFIG) as f:
        thresholds = yaml.safe_load(f)

    if not thresholds.get("meta", {}).get("signed_off"):
        raise RuntimeError(
            "deap/config/thresholds.yaml is not signed off "
            "(meta.signed_off is not true). Label plausibility check refused."
        )

    dat_files = sorted(
        os.path.join(dat_dir, fn)
        for fn in os.listdir(dat_dir)
        if fn.endswith(".dat")
    )

    results = []
    for path in dat_files:
        print(f"  label_plausibility: {os.path.basename(path)}", file=sys.stderr)
        results.append(check_participant(path, thresholds))

    overall_pass = all(r["pass"] for r in results)
    total_oor = sum(r["total_out_of_range"] for r in results)

    report = {
        "check": "label_plausibility",
        "scale": "SAM 1-9 (Koelstra et al. 2012, p. 6)",
        "threshold_source": "deap/config/thresholds.yaml",
        "participant_count": len(results),
        "overall_pass": overall_pass,
        "total_out_of_range_all_participants": total_oor,
        "participants": {r["participant"]: r for r in results},
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"  label_plausibility report -> {output_path}", file=sys.stderr)
    return report


if __name__ == "__main__":
    run()
