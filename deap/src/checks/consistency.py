"""
Consistency checks for DEAP dataset.

Three sub-checks:
1. consistency_structure: array shapes and channel/trial counts identical across participants.
2. consistency_cross_source: each label value matches participant_ratings.xls
   (trials matched by Experiment_id order: dat labels[i] <-> Experiment_id == i+1).
3. consistency_scale: descriptive per-channel min/max/range comparison (no threshold).

Output: deap/reports/deap_consistency.json (deterministic, sorted keys).
Never modifies bronze/ data.

Run from project root:
    python -c "from deap.src.checks.consistency import run; run()"
"""

import json
import os
import sys

import numpy as np
import xlrd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_ROOT = os.path.dirname(ROOT)
DAT_DIR = os.path.join(DATA_ROOT, "bronze", "DEAP", "deap-dataset",
                        "data_preprocessed_python")
XLS_PATH = os.path.join(DATA_ROOT, "bronze", "DEAP", "deap-dataset",
                         "Metadata", "participant_ratings.xls")
CONFIG = os.path.join(ROOT, "config", "thresholds.yaml")
OUTPUT = os.path.join(ROOT, "reports", "deap_consistency.json")

sys.path.insert(0, DATA_ROOT)
from deap.src.loader import load_dat  # noqa: E402

LABEL_DIMS = ["valence", "arousal", "dominance", "liking"]
CHANNEL_NAMES = [
    "Fp1", "AF3", "F3", "F7", "FC5", "FC1", "C3", "T7",
    "CP5", "CP1", "P3", "P7", "PO3", "O1", "Oz", "Pz",
    "Fp2", "AF4", "Fz", "F4", "F8", "FC6", "FC2", "Cz",
    "C4", "T8", "CP6", "CP2", "P4", "P8", "PO4", "O2",
    "hEOG", "vEOG", "zEMG", "tEMG", "GSR", "Resp", "BVP", "Temp",
]


def _load_xls(xls_path: str) -> dict:
    """Returns {pid_int: {exp_id: {dim: value}}}."""
    wb = xlrd.open_workbook(xls_path)
    sh = wb.sheet_by_index(0)
    header = sh.row_values(0)
    col = {h: i for i, h in enumerate(header)}
    ratings = {}
    for row_idx in range(1, sh.nrows):
        row = sh.row_values(row_idx)
        pid = int(row[col["Participant_id"]])
        exp_id = int(row[col["Experiment_id"]])
        ratings.setdefault(pid, {})[exp_id] = {
            "valence": row[col["Valence"]],
            "arousal": row[col["Arousal"]],
            "dominance": row[col["Dominance"]],
            "liking": row[col["Liking"]],
        }
    return ratings


def check_structure(all_data: list, thresholds: dict) -> dict:
    """Check shapes and counts are identical across all participants."""
    expected_data_shape = tuple(thresholds["conformance"]["expected_data_shape"])
    expected_labels_shape = tuple(thresholds["conformance"]["expected_labels_shape"])

    mismatches = []
    shapes_seen = set()
    for item in all_data:
        pid = item["participant"]
        ds = tuple(item["data_shape"])
        ls = tuple(item["labels_shape"])
        shapes_seen.add(ds)
        if ds != expected_data_shape:
            mismatches.append({
                "participant": pid, "field": "data_shape",
                "expected": list(expected_data_shape), "actual": list(ds),
            })
        if ls != expected_labels_shape:
            mismatches.append({
                "participant": pid, "field": "labels_shape",
                "expected": list(expected_labels_shape), "actual": list(ls),
            })

    return {
        "sub_check": "consistency_structure",
        "total_mismatches": len(mismatches),
        "threshold": thresholds["consistency_structure"]["max_mismatches"],
        "pass": len(mismatches) == 0,
        "unique_data_shapes": sorted([list(s) for s in shapes_seen]),
        "mismatches": mismatches,
    }


def check_cross_source(all_data: list, xls_ratings: dict,
                        tolerance: float) -> dict:
    """Compare .dat labels against participant_ratings.xls by Experiment_id."""
    mismatches = []
    total_compared = 0

    for item in all_data:
        pid_str = item["participant"]
        pid_int = int(pid_str[1:])
        labels = item["labels"]

        if pid_int not in xls_ratings:
            continue

        xls_pid = xls_ratings[pid_int]
        for exp_id in range(1, 41):
            trial_idx = exp_id - 1
            if exp_id not in xls_pid:
                continue
            xls_row = xls_pid[exp_id]
            for dim_idx, dim in enumerate(LABEL_DIMS):
                dat_val = float(labels[trial_idx, dim_idx])
                xls_val = float(xls_row[dim])
                total_compared += 1
                if abs(dat_val - xls_val) > tolerance:
                    mismatches.append({
                        "participant": pid_str,
                        "experiment_id": exp_id,
                        "trial_index": trial_idx,
                        "dim": dim,
                        "dat_value": round(dat_val, 6),
                        "xls_value": round(xls_val, 6),
                        "difference": round(abs(dat_val - xls_val), 6),
                    })

    return {
        "sub_check": "consistency_cross_source",
        "matching_method": (
            "dat labels[i] corresponds to XLS row with Experiment_id == i+1 "
            "(trials in Experiment_id order per EDA_DEAP.ipynb notebook)"
        ),
        "total_entries_compared": total_compared,
        "total_mismatches": len(mismatches),
        "tolerance": tolerance,
        "threshold": 0,
        "pass": len(mismatches) == 0,
        "mismatches": mismatches,
    }


def check_scale_descriptive(all_data: list) -> dict:
    """Descriptive per-channel range comparison. No threshold."""
    per_channel_ranges = {ch: [] for ch in CHANNEL_NAMES}

    for item in all_data:
        data = item["data"]  # (40, 40, 8064)
        for ch_idx, ch_name in enumerate(CHANNEL_NAMES):
            if ch_idx >= data.shape[1]:
                break
            ch_flat = data[:, ch_idx, :].ravel()
            finite = ch_flat[np.isfinite(ch_flat)]
            if finite.size > 0:
                per_channel_ranges[ch_name].append({
                    "participant": item["participant"],
                    "min": float(np.min(finite)),
                    "max": float(np.max(finite)),
                    "range": float(np.max(finite) - np.min(finite)),
                })

    summary = {}
    for ch_name, entries in per_channel_ranges.items():
        if not entries:
            summary[ch_name] = None
            continue
        ranges = [e["range"] for e in entries]
        mins = [e["min"] for e in entries]
        maxs = [e["max"] for e in entries]
        median_range = float(np.median(ranges))
        # Flag participants whose range deviates by more than 10x from median
        outliers = [
            e["participant"] for e in entries
            if median_range > 0 and (e["range"] / median_range > 10 or e["range"] / median_range < 0.1)
        ]
        summary[ch_name] = {
            "across_participant_min": round(min(mins), 6),
            "across_participant_max": round(max(maxs), 6),
            "median_range": round(median_range, 6),
            "min_range": round(min(ranges), 6),
            "max_range": round(max(ranges), 6),
            "range_outlier_participants": sorted(outliers),
        }

    return {
        "sub_check": "consistency_scale_descriptive",
        "note": "Descriptive only. No pass/fail threshold.",
        "per_channel": summary,
    }


def run(dat_dir: str = DAT_DIR, xls_path: str = XLS_PATH,
        output_path: str = OUTPUT) -> dict:
    with open(CONFIG) as f:
        thresholds = yaml.safe_load(f)

    if not thresholds.get("meta", {}).get("signed_off"):
        raise RuntimeError(
            "deap/config/thresholds.yaml is not signed off "
            "(meta.signed_off is not true). Consistency check refused."
        )

    tolerance = float(thresholds["consistency_cross_source"]["tolerance"])

    dat_files = sorted(
        os.path.join(dat_dir, fn)
        for fn in os.listdir(dat_dir)
        if fn.endswith(".dat")
    )

    all_data = []
    for path in dat_files:
        pid = os.path.splitext(os.path.basename(path))[0]
        print(f"  consistency: {os.path.basename(path)}", file=sys.stderr)
        d = load_dat(path)
        all_data.append({
            "participant": pid,
            "data": d["data"],
            "labels": d["labels"],
            "data_shape": list(d["data"].shape),
            "labels_shape": list(d["labels"].shape),
        })

    xls_ratings = _load_xls(xls_path)

    structure_result = check_structure(all_data, thresholds)
    cross_source_result = check_cross_source(all_data, xls_ratings, tolerance)
    scale_result = check_scale_descriptive(all_data)

    overall_pass = structure_result["pass"] and cross_source_result["pass"]

    report = {
        "check": "consistency",
        "threshold_source": "deap/config/thresholds.yaml",
        "participant_count": len(all_data),
        "overall_pass": overall_pass,
        "consistency_structure": structure_result,
        "consistency_cross_source": cross_source_result,
        "consistency_scale_descriptive": scale_result,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"  consistency report -> {output_path}", file=sys.stderr)
    return report


if __name__ == "__main__":
    run()
