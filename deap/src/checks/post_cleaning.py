"""
Post-cleaning checks for DEAP dataset.

Runs label_plausibility and cross-source consistency checks on the Silver
label CSVs (silver/DEAP/labels/sXX_labels.csv) to verify the cleaning
resolved all label issues.

Expected results:
  label_plausibility: 0 out-of-range values (XLS source is in [1,9])
  cross_source: 0 mismatches (Silver = XLS by construction)

Output: deap/reports/deap_post_cleaning.json (deterministic, sorted keys).
Never modifies bronze/ data.

Run from project root:
    python -c "from deap.src.checks.post_cleaning import run; run()"
"""

import csv
import json
import os
import sys

import xlrd
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_ROOT = os.path.dirname(ROOT)
SILVER_DIR = os.path.join(DATA_ROOT, "silver", "DEAP", "labels")
XLS_PATH = os.path.join(DATA_ROOT, "bronze", "DEAP", "deap-dataset",
                        "Metadata", "participant_ratings.xls")
CONFIG = os.path.join(ROOT, "config", "thresholds.yaml")
OUTPUT = os.path.join(ROOT, "reports", "deap_post_cleaning.json")

LABEL_DIMS = ["valence", "arousal", "dominance", "liking"]
XLS_COLS = ["Valence", "Arousal", "Dominance", "Liking"]


def _load_xls(xls_path: str) -> dict:
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


def _load_silver_csv(csv_path: str) -> list:
    """Return list of row dicts from a Silver label CSV."""
    rows = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({k: float(v) for k, v in row.items()})
    return rows


def check_participant(pid_str: str, silver_csv: str,
                      xls_pid: dict, thresholds: dict) -> dict:
    rows = _load_silver_csv(silver_csv)
    cfg_lp = thresholds["label_plausibility"]
    lo = float(cfg_lp["min_label_value"])
    hi = float(cfg_lp["max_label_value"])
    tol = 1e-9
    tol_xls = float(thresholds["consistency_cross_source"]["tolerance"])

    oor_violations = []
    cross_mismatches = []

    for row in rows:
        trial_idx = int(row["trial_index"])
        exp_id = int(row["experiment_id"])
        for dim in LABEL_DIMS:
            val = row[dim]
            if val < lo - tol or val > hi + tol:
                oor_violations.append({
                    "trial_index": trial_idx,
                    "experiment_id": exp_id,
                    "dim": dim,
                    "value": round(val, 6),
                })
            if xls_pid and exp_id in xls_pid:
                xls_val = xls_pid[exp_id][dim]
                if abs(val - xls_val) > tol_xls:
                    cross_mismatches.append({
                        "trial_index": trial_idx,
                        "experiment_id": exp_id,
                        "dim": dim,
                        "silver_value": round(val, 6),
                        "xls_value": round(xls_val, 6),
                        "difference": round(abs(val - xls_val), 6),
                    })

    lp_pass = len(oor_violations) <= cfg_lp["max_out_of_range"]
    cs_pass = len(cross_mismatches) == 0

    return {
        "participant": pid_str,
        "label_plausibility": {
            "total_out_of_range": len(oor_violations),
            "threshold": cfg_lp["max_out_of_range"],
            "pass": lp_pass,
            "violations": oor_violations,
        },
        "cross_source": {
            "total_mismatches": len(cross_mismatches),
            "threshold": thresholds["consistency_cross_source"]["max_mismatches"],
            "pass": cs_pass,
            "mismatches": cross_mismatches,
        },
        "pass": lp_pass and cs_pass,
    }


def run(silver_dir: str = SILVER_DIR, xls_path: str = XLS_PATH,
        output_path: str = OUTPUT) -> dict:
    with open(CONFIG) as f:
        thresholds = yaml.safe_load(f)

    if not thresholds.get("meta", {}).get("signed_off"):
        raise RuntimeError(
            "deap/config/thresholds.yaml is not signed off "
            "(meta.signed_off is not true). Post-cleaning check refused."
        )

    if not os.path.isdir(silver_dir):
        raise RuntimeError(
            f"Silver label directory not found: {silver_dir}. "
            "Run deap/src/cleaning.py first."
        )

    xls_ratings = _load_xls(xls_path)

    csv_files = sorted(
        f for f in os.listdir(silver_dir) if f.endswith("_labels.csv")
    )

    results = []
    for fname in csv_files:
        pid_str = fname.replace("_labels.csv", "")
        pid_int = int(pid_str[1:])
        csv_path = os.path.join(silver_dir, fname)
        print(f"  post_cleaning: {pid_str}", file=sys.stderr)
        rec = check_participant(pid_str, csv_path,
                                xls_ratings.get(pid_int, {}), thresholds)
        results.append(rec)

    overall_pass = all(r["pass"] for r in results)
    total_oor = sum(r["label_plausibility"]["total_out_of_range"] for r in results)
    total_mismatch = sum(r["cross_source"]["total_mismatches"] for r in results)

    report = {
        "check": "post_cleaning",
        "source": "silver/DEAP/labels/",
        "threshold_source": "deap/config/thresholds.yaml",
        "participant_count": len(results),
        "overall_pass": overall_pass,
        "total_label_plausibility_oor": total_oor,
        "total_cross_source_mismatches": total_mismatch,
        "participants": {r["participant"]: r for r in results},
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"  post_cleaning report -> {output_path}", file=sys.stderr)
    return report


if __name__ == "__main__":
    run()
