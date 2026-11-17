"""
DEAP fault injection vs-control comparison.

Reads deap/reports/experiments/deap_fault_injection_results.json and the
original .dat files to produce a per-participant, per-fault comparison of
each check's count against the unmodified (control) baseline.

For the label_out_of_range fault, identifies each injected position and
whether it was already out of range in the control, explaining any count
increase below 10.

Output: deap/reports/experiments/deap_fault_injection_vs_control.json

Run from project root:
    .venv\\Scripts\\python.exe deap/src/experiments/fault_injection_vs_control.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_ROOT = os.path.dirname(ROOT)
DAT_DIR = os.path.join(DATA_ROOT, "bronze", "DEAP", "deap-dataset",
                        "data_preprocessed_python")
RESULTS_PATH = os.path.join(ROOT, "reports", "experiments",
                             "deap_fault_injection_results.json")
OUTPUT = os.path.join(ROOT, "reports", "experiments",
                       "deap_fault_injection_vs_control.json")

sys.path.insert(0, DATA_ROOT)
from deap.src.loader import load_dat  # noqa: E402


COUNT_KEYS = {
    "completeness": ["total_nan", "total_inf"],
    "conformance": ["violation_count"],
    "label_plausibility": ["total_out_of_range"],
    "consistency_cross_source": ["mismatches"],
}

SAM_MIN = 1.0
SAM_MAX = 9.0
LABEL_DIMS = ["valence", "arousal", "dominance", "liking"]

# Fault parameters (must match experiments.yaml)
LABEL_FAULT_N_BELOW = 5
LABEL_FAULT_BELOW_VALUE = 0.0
LABEL_FAULT_N_ABOVE = 5
LABEL_FAULT_ABOVE_VALUE = 10.0


def _injected_positions():
    """Return the 10 injected (trial_index, dim_index) pairs for label_out_of_range."""
    positions = []
    for i in range(LABEL_FAULT_N_BELOW):
        positions.append((i, 0))  # trials 0-4, valence
    for i in range(LABEL_FAULT_N_ABOVE):
        positions.append((LABEL_FAULT_N_BELOW + i, 1))  # trials 5-9, arousal
    return positions


def _analyse_label_positions(dat_path):
    """
    For each injected position, check whether the original value was already
    out of [1, 9] range. Returns a list of dicts, one per injected position.
    """
    d = load_dat(dat_path)
    labels = d["labels"]
    results = []
    for trial_idx, dim_idx in _injected_positions():
        original_val = float(labels[trial_idx, dim_idx])
        already_oor = original_val < SAM_MIN or original_val > SAM_MAX
        injected_val = (
            LABEL_FAULT_BELOW_VALUE if dim_idx == 0
            else LABEL_FAULT_ABOVE_VALUE
        )
        injected_oor = injected_val < SAM_MIN or injected_val > SAM_MAX
        results.append({
            "trial_index": trial_idx,
            "dim_index": dim_idx,
            "dim_name": LABEL_DIMS[dim_idx],
            "original_value": round(original_val, 6),
            "original_already_oor": already_oor,
            "injected_value": injected_val,
            "injected_oor": injected_oor,
            "net_new_oor": not already_oor and injected_oor,
        })
    return results


def run(output_path=OUTPUT):
    with open(RESULTS_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    # Index records by (participant, fault_id)
    records_by_key = {}
    for rec in raw["records"]:
        records_by_key[(rec["participant"], rec["fault_id"])] = rec

    participants = sorted({rec["participant"] for rec in raw["records"]})
    fault_ids = [
        f["id"]
        for f in [
            {"id": "control"},
            {"id": "nan_in_eeg"},
            {"id": "label_out_of_range"},
            {"id": "truncated_data"},
        ]
    ]

    comparisons = []

    for pid in participants:
        ctrl = records_by_key.get((pid, "control"), {})
        ctrl_checks = ctrl.get("check_results", {})

        dat_path = os.path.join(DAT_DIR, f"{pid}.dat")
        label_positions = _analyse_label_positions(dat_path)
        net_new_oor = sum(1 for p in label_positions if p["net_new_oor"])

        for fault_id in fault_ids:
            rec = records_by_key.get((pid, fault_id))
            if rec is None:
                continue

            fault_checks = rec.get("check_results", {})
            deltas = {}
            for check_name, keys in COUNT_KEYS.items():
                ctrl_counts = ctrl_checks.get(check_name, {})
                fault_counts = fault_checks.get(check_name, {})
                deltas[check_name] = {
                    k: {
                        "control": ctrl_counts.get(k),
                        "fault": fault_counts.get(k),
                        "delta": (
                            (fault_counts.get(k) - ctrl_counts.get(k))
                            if fault_counts.get(k) is not None
                            and ctrl_counts.get(k) is not None
                            else None
                        ),
                    }
                    for k in keys
                }

            entry = {
                "participant": pid,
                "fault_id": fault_id,
                "count_vs_control": deltas,
            }

            if fault_id == "label_out_of_range":
                expected_lp_delta = net_new_oor
                actual_lp_delta = deltas["label_plausibility"]["total_out_of_range"]["delta"]
                entry["label_positions"] = {
                    "injected_count": len(label_positions),
                    "net_new_oor": net_new_oor,
                    "pre_existing_overwritten": len(label_positions) - net_new_oor,
                    "delta_matches_net_new_oor": actual_lp_delta == expected_lp_delta,
                    "positions": label_positions,
                }

            comparisons.append(entry)

    report = {
        "source": "deap/reports/experiments/deap_fault_injection_results.json",
        "method": (
            "Per-fault counts compared against the unmodified control baseline "
            "for the same participant. For label_out_of_range, each injected "
            "position is examined against the original data to identify whether "
            "it was already out of [1,9] range before injection."
        ),
        "count_metrics": {
            check: keys for check, keys in COUNT_KEYS.items()
        },
        "comparisons": comparisons,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"vs-control report -> {output_path}", file=sys.stderr)
    return report


if __name__ == "__main__":
    run()
