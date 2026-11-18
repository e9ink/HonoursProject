"""
DEAP Silver layer: label correction.

Reads participant_ratings.xls as the authoritative label source and writes
one Silver CSV per participant to silver/DEAP/labels/sXX_labels.csv.

Pre-registered rule: deap/config/cleaning.yaml (signed off 2026-11-18).
Sign-off gate: refuses to run if meta.signed_off is not true in cleaning.yaml.

For each participant/trial, the XLS value is written as the Silver label.
Where dat matches XLS, the Silver value is identical to Bronze. Where dat
follows v2 = 9 - v1 (the v2 inversion artefact), the Silver value is v1.

Output: silver/DEAP/labels/sXX_labels.csv (40 rows per participant).
Report: deap/reports/deap_cleaning.json (deterministic, sorted keys).
Never modifies bronze/ data or .dat files.

Run from project root:
    python -c "from deap.src.cleaning import run; run()"
"""

import csv
import json
import os
import sys

import xlrd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_ROOT = os.path.dirname(ROOT)
DAT_DIR = os.path.join(DATA_ROOT, "bronze", "DEAP", "deap-dataset",
                       "data_preprocessed_python")
XLS_PATH = os.path.join(DATA_ROOT, "bronze", "DEAP", "deap-dataset",
                        "Metadata", "participant_ratings.xls")
CLEANING_CONFIG = os.path.join(ROOT, "config", "cleaning.yaml")
THRESHOLDS_CONFIG = os.path.join(ROOT, "config", "thresholds.yaml")
SILVER_DIR = os.path.join(DATA_ROOT, "silver", "DEAP", "labels")
OUTPUT = os.path.join(ROOT, "reports", "deap_cleaning.json")

LABEL_DIMS = ["valence", "arousal", "dominance", "liking"]
XLS_COLS = ["Valence", "Arousal", "Dominance", "Liking"]

sys.path.insert(0, DATA_ROOT)
from deap.src.loader import load_dat  # noqa: E402


def _load_xls(xls_path: str) -> dict:
    """Return {pid_int: {exp_id: {dim: float}}}."""
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
            dim: float(row[col[xcol]])
            for dim, xcol in zip(LABEL_DIMS, XLS_COLS)
        }
    return ratings


def clean_participant(dat_path: str, xls_ratings: dict,
                      silver_dir: str) -> dict:
    """Write Silver label CSV for one participant; return correction record."""
    pid_str = os.path.splitext(os.path.basename(dat_path))[0]  # e.g. "s01"
    pid_int = int(pid_str[1:])

    d = load_dat(dat_path)
    dat_labels = d["labels"]  # (40, 4)

    xls_pid = xls_ratings.get(pid_int, {})

    silver_rows = []
    corrections = []
    n_corrections = 0

    for trial_idx in range(dat_labels.shape[0]):
        exp_id = trial_idx + 1
        xls_row = xls_pid.get(exp_id)

        row = {"trial_index": trial_idx, "experiment_id": exp_id}
        for dim_idx, dim in enumerate(LABEL_DIMS):
            dat_val = float(dat_labels[trial_idx, dim_idx])
            if xls_row is not None:
                xls_val = xls_row[dim]
                if abs(dat_val - xls_val) > 1e-9:
                    n_corrections += 1
                    corrections.append({
                        "trial_index": trial_idx,
                        "experiment_id": exp_id,
                        "dim": dim,
                        "dat_value": round(dat_val, 6),
                        "xls_value": round(xls_val, 6),
                    })
                row[dim] = round(xls_val, 6)
            else:
                row[dim] = round(dat_val, 6)
        silver_rows.append(row)

    os.makedirs(silver_dir, exist_ok=True)
    csv_path = os.path.join(silver_dir, f"{pid_str}_labels.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["trial_index", "experiment_id"] + LABEL_DIMS
        )
        writer.writeheader()
        writer.writerows(silver_rows)

    return {
        "participant": pid_str,
        "silver_path": os.path.relpath(csv_path, DATA_ROOT).replace("\\", "/"),
        "n_trials": dat_labels.shape[0],
        "n_corrections": n_corrections,
        "corrections": corrections,
    }


def run(dat_dir: str = DAT_DIR, xls_path: str = XLS_PATH,
        silver_dir: str = SILVER_DIR, output_path: str = OUTPUT) -> dict:
    with open(CLEANING_CONFIG) as f:
        cleaning_cfg = yaml.safe_load(f)

    if not cleaning_cfg.get("meta", {}).get("signed_off"):
        raise RuntimeError(
            "deap/config/cleaning.yaml is not signed off "
            "(meta.signed_off is not true). DEAP cleaning refused."
        )

    xls_ratings = _load_xls(xls_path)

    dat_files = sorted(
        os.path.join(dat_dir, fn)
        for fn in os.listdir(dat_dir)
        if fn.endswith(".dat")
    )

    participant_records = []
    for path in dat_files:
        pid = os.path.splitext(os.path.basename(path))[0]
        print(f"  cleaning: {pid}", file=sys.stderr)
        rec = clean_participant(path, xls_ratings, silver_dir)
        participant_records.append(rec)

    total_corrections = sum(r["n_corrections"] for r in participant_records)
    n_corrected = sum(1 for r in participant_records if r["n_corrections"] > 0)

    report = {
        "check": "cleaning",
        "action": "replace_inverted_labels_with_xls",
        "authoritative_source": "participant_ratings.xls",
        "cleaning_config": "deap/config/cleaning.yaml",
        "silver_dir": os.path.relpath(silver_dir, DATA_ROOT).replace("\\", "/"),
        "participant_count": len(participant_records),
        "n_participants_with_corrections": n_corrected,
        "total_corrections": total_corrections,
        "participants": {r["participant"]: r for r in participant_records},
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"  cleaning report -> {output_path}", file=sys.stderr)
    print(f"      total_corrections={total_corrections}", file=sys.stderr)
    return report


if __name__ == "__main__":
    run()
