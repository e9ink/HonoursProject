"""
Completeness check for DEAP dataset.

Checks for NaN and Inf values in the data array per channel per participant.
Threshold: max_nan_count = 0, max_inf_count = 0 (from deap/config/thresholds.yaml).

Output: deap/reports/deap_completeness.json (deterministic, sorted keys).
Never modifies bronze/ data.

Run from project root:
    python -c "from deap.src.checks.completeness import run; run()"
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
OUTPUT = os.path.join(ROOT, "reports", "deap_completeness.json")

sys.path.insert(0, DATA_ROOT)
from deap.src.loader import load_dat  # noqa: E402


CHANNEL_NAMES = [
    "Fp1", "AF3", "F3", "F7", "FC5", "FC1", "C3", "T7",
    "CP5", "CP1", "P3", "P7", "PO3", "O1", "Oz", "Pz",
    "Fp2", "AF4", "Fz", "F4", "F8", "FC6", "FC2", "Cz",
    "C4", "T8", "CP6", "CP2", "P4", "P8", "PO4", "O2",
    "hEOG", "vEOG", "zEMG", "tEMG", "GSR", "Resp", "BVP", "Temp",
]


def check_participant(dat_path: str, thresholds: dict) -> dict:
    d = load_dat(dat_path)
    pid = os.path.splitext(os.path.basename(dat_path))[0]
    data = d["data"]  # (40, 40, 8064)

    max_nan = thresholds["completeness"]["max_nan_count"]
    max_inf = thresholds["completeness"]["max_inf_count"]

    total_nan = 0
    total_inf = 0
    per_channel = {}

    for ch_idx, ch_name in enumerate(CHANNEL_NAMES):
        if ch_idx >= data.shape[1]:
            break
        ch_data = data[:, ch_idx, :].ravel()
        nan_count = int(np.sum(np.isnan(ch_data)))
        inf_count = int(np.sum(np.isinf(ch_data)))
        total_nan += nan_count
        total_inf += inf_count
        per_channel[ch_name] = {"nan_count": nan_count, "inf_count": inf_count}

    nan_pass = total_nan <= max_nan
    inf_pass = total_inf <= max_inf

    return {
        "participant": pid,
        "total_nan": total_nan,
        "total_inf": total_inf,
        "nan_threshold": max_nan,
        "inf_threshold": max_inf,
        "nan_pass": nan_pass,
        "inf_pass": inf_pass,
        "pass": nan_pass and inf_pass,
        "per_channel": per_channel,
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
        print(f"  completeness: {os.path.basename(path)}", file=sys.stderr)
        results.append(check_participant(path, thresholds))

    overall_pass = all(r["pass"] for r in results)
    total_nan = sum(r["total_nan"] for r in results)
    total_inf = sum(r["total_inf"] for r in results)

    report = {
        "check": "completeness",
        "threshold_source": "deap/config/thresholds.yaml",
        "participant_count": len(results),
        "overall_pass": overall_pass,
        "total_nan_all_participants": total_nan,
        "total_inf_all_participants": total_inf,
        "participants": {r["participant"]: r for r in results},
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"  completeness report -> {output_path}", file=sys.stderr)
    return report


if __name__ == "__main__":
    run()
