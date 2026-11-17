"""
DEAP fault injection runner.

Reads deap/config/experiments.yaml, applies faults to in-memory copies of
participant data, writes scratch files to the system temp directory, runs
all checks on the scratch files, records results, and deletes scratch files.

No bronze/ data is modified.

Output: deap/reports/experiments/deap_fault_injection_results.json (deterministic).

Run from project root:
    python -c "from deap.src.experiments.fault_injection import run; run()"
"""

import io
import json
import os
import pickle
import sys
import tempfile

import numpy as np
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_ROOT = os.path.dirname(ROOT)
DAT_DIR = os.path.join(DATA_ROOT, "bronze", "DEAP", "deap-dataset",
                        "data_preprocessed_python")
XLS_PATH = os.path.join(DATA_ROOT, "bronze", "DEAP", "deap-dataset",
                         "Metadata", "participant_ratings.xls")
EXPERIMENTS_CONFIG = os.path.join(ROOT, "config", "experiments.yaml")
THRESHOLDS_CONFIG = os.path.join(ROOT, "config", "thresholds.yaml")
OUTPUT = os.path.join(ROOT, "reports", "experiments",
                       "deap_fault_injection_results.json")

sys.path.insert(0, DATA_ROOT)
from deap.src.loader import load_dat, load_dat_bytes  # noqa: E402
from deap.src.checks.completeness import check_participant as check_completeness  # noqa: E402
from deap.src.checks.conformance import check_participant as check_conformance  # noqa: E402
from deap.src.checks.label_plausibility import check_participant as check_label_plausibility  # noqa: E402


def _save_scratch(data_dict: dict, scratch_path: str) -> None:
    """Save a modified data dict as a pickle file."""
    with open(scratch_path, "wb") as f:
        pickle.dump(data_dict, f, protocol=4)


def _apply_fault(fault: dict, data_dict: dict) -> dict:
    """Return a new dict with the fault applied. Original is not modified."""
    import copy
    d = {"data": data_dict["data"].copy(), "labels": data_dict["labels"].copy()}

    fault_type = fault["fault_type"]

    if fault_type == "none":
        pass

    elif fault_type == "completeness_nan":
        ch_idx = int(fault["channel_index"])
        rng = np.random.default_rng(seed=42)
        total_samples = d["data"].shape[0] * d["data"].shape[2]
        n_nan = int(total_samples * float(fault["fraction"]))
        # Scatter NaNs across all trials for the channel
        flat = d["data"][:, ch_idx, :].copy().ravel()
        indices = rng.choice(len(flat), size=n_nan, replace=False)
        flat[indices] = np.nan
        d["data"][:, ch_idx, :] = flat.reshape(
            d["data"].shape[0], d["data"].shape[2]
        )

    elif fault_type == "label_plausibility_violation":
        n_below = int(fault["n_below"])
        n_above = int(fault["n_above"])
        below_val = float(fault["below_value"])
        above_val = float(fault["above_value"])
        # First n_below trials: valence set to below_value
        for i in range(n_below):
            d["labels"][i, 0] = below_val
        # Next n_above trials: arousal set to above_value
        for i in range(n_above):
            d["labels"][n_below + i, 1] = above_val

    elif fault_type == "conformance_shape_violation":
        truncated_shape = tuple(fault["truncated_shape"])
        # Truncate the time dimension
        d["data"] = d["data"][:, :, :truncated_shape[2]]

    else:
        raise ValueError(f"Unknown fault_type: {fault_type}")

    return d


def _run_checks_on_scratch(scratch_path: str, thresholds: dict,
                             xls_path: str) -> dict:
    """Run completeness, conformance, label_plausibility on scratch file."""
    results = {}

    # Completeness
    r = check_completeness(scratch_path, thresholds)
    results["completeness"] = {"pass": r["pass"], "total_nan": r["total_nan"],
                                "total_inf": r["total_inf"]}

    # Conformance
    r = check_conformance(scratch_path, thresholds)
    results["conformance"] = {"pass": r["pass"],
                               "violation_count": r["violation_count"]}

    # Label plausibility
    r = check_label_plausibility(scratch_path, thresholds)
    results["label_plausibility"] = {"pass": r["pass"],
                                      "total_out_of_range": r["total_out_of_range"]}

    # Consistency structure (single-participant check: just shape)
    d = load_dat(scratch_path)
    expected_data_shape = tuple(thresholds["conformance"]["expected_data_shape"])
    expected_labels_shape = tuple(thresholds["conformance"]["expected_labels_shape"])
    shape_ok = (
        tuple(d["data"].shape) == expected_data_shape
        and tuple(d["labels"].shape) == expected_labels_shape
    )
    results["consistency_structure"] = {"pass": shape_ok}

    # Consistency cross_source (compare labels vs XLS for this participant)
    import xlrd
    pid_str = os.path.splitext(os.path.basename(scratch_path))[0]
    # scratch file is named like "s01_fault.dat"; extract original pid
    pid_base = pid_str.split("_")[0]
    pid_int = int(pid_base[1:])

    tol = float(thresholds["consistency_cross_source"]["tolerance"])
    wb = xlrd.open_workbook(xls_path)
    sh = wb.sheet_by_index(0)
    header = sh.row_values(0)
    col_map = {h: i for i, h in enumerate(header)}
    xls_pid = {}
    for row_idx in range(1, sh.nrows):
        row = sh.row_values(row_idx)
        if int(row[col_map["Participant_id"]]) == pid_int:
            exp_id = int(row[col_map["Experiment_id"]])
            xls_pid[exp_id] = {
                "valence": row[col_map["Valence"]],
                "arousal": row[col_map["Arousal"]],
                "dominance": row[col_map["Dominance"]],
                "liking": row[col_map["Liking"]],
            }

    label_dims = ["valence", "arousal", "dominance", "liking"]
    xsrc_mismatches = 0
    labels = d["labels"]
    for exp_id in range(1, 41):
        if exp_id not in xls_pid:
            continue
        for dim_idx, dim in enumerate(label_dims):
            dat_val = float(labels[exp_id - 1, dim_idx])
            xls_val = float(xls_pid[exp_id][dim])
            if abs(dat_val - xls_val) > tol:
                xsrc_mismatches += 1
    results["consistency_cross_source"] = {
        "pass": xsrc_mismatches == 0,
        "mismatches": xsrc_mismatches,
    }

    return results


def run(output_path: str = OUTPUT) -> dict:
    with open(EXPERIMENTS_CONFIG) as f:
        exp_config = yaml.safe_load(f)
    with open(THRESHOLDS_CONFIG) as f:
        thresholds = yaml.safe_load(f)

    participants = exp_config["participants"]
    faults = exp_config["faults"]

    records = []

    with tempfile.TemporaryDirectory() as scratch_dir:
        for pid in sorted(participants):
            dat_path = os.path.join(DAT_DIR, f"{pid}.dat")
            original = load_dat(dat_path)
            print(f"  fault injection: {pid}", file=sys.stderr)

            for fault in faults:
                fault_id = fault["id"]
                print(f"    fault: {fault_id}", file=sys.stderr)

                scratch_path = os.path.join(scratch_dir, f"{pid}_{fault_id}.dat")
                modified = _apply_fault(fault, original)
                _save_scratch(modified, scratch_path)

                check_results = _run_checks_on_scratch(
                    scratch_path, thresholds, XLS_PATH
                )

                expected = fault.get("expected_outcomes", {})
                verdict_matches = {}
                for check_name, exp_outcome in expected.items():
                    if check_name == "overall":
                        actual = all(
                            v.get("pass", True)
                            for k, v in check_results.items()
                        )
                        expected_bool = exp_outcome == "pass"
                        verdict_matches["overall"] = actual == expected_bool
                    elif check_name in check_results:
                        actual_pass = check_results[check_name].get("pass", True)
                        expected_pass = exp_outcome == "pass"
                        verdict_matches[check_name] = actual_pass == expected_pass

                all_match = all(verdict_matches.values())

                records.append({
                    "participant": pid,
                    "fault_id": fault_id,
                    "fault_type": fault["fault_type"],
                    "check_results": check_results,
                    "expected_outcomes": expected,
                    "verdict_matches": verdict_matches,
                    "all_expected_met": all_match,
                })

    overall_success = all(r["all_expected_met"] for r in records)

    report = {
        "experiment": "deap_fault_injection",
        "config_source": "deap/config/experiments.yaml",
        "participant_count": len(participants),
        "fault_count": len(faults),
        "total_records": len(records),
        "all_expected_outcomes_met": overall_success,
        "records": records,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"  fault injection report -> {output_path}", file=sys.stderr)
    return report


if __name__ == "__main__":
    run()
