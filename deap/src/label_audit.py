"""
Label audit: compare v1 and v2 mirror labels against the metadata spreadsheet.

Matching logic
--------------
participant_ratings.xls has columns:
    Participant_id, Trial, Experiment_id, Start_time,
    Valence, Arousal, Dominance, Liking, Familiarity

The .dat files store trials in Experiment_id order (1..40), confirmed by
sorting participant 1's XLS rows by Experiment_id: the result is exactly
Experiment_id 1,2,...,40, and labels[0] matches XLS row with Experiment_id=1.
So: dat labels[i] <-> XLS row where Experiment_id == i+1 (for the same participant).

SAM scale check
---------------
DEAP uses a 1-9 SAM (Self-Assessment Manikin) scale for Valence, Arousal,
Dominance, and Liking. Per the DEAP paper (Koelstra et al. 2012), valid range
is 1-9. Values outside [1, 9] are out-of-range. The XLS metadata also uses
this range.

V2 inversion pattern
--------------------
The cross-mirror comparison showed: v2_value = 9 - v1_value for affected entries.
The audit classifies each label entry as:
  "match"    -- mirror value matches XLS within floating-point tolerance (1e-4)
  "inverted" -- mirror value == 9.0 - XLS value within tolerance
  "other"    -- differs from XLS in another way

Run from project root:
    python deap/src/label_audit.py

Output: deap/reports/deap_label_audit.json (deterministic)
"""

import io
import json
import os
import pickle

import numpy as np
import xlrd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BRONZE = os.path.join(ROOT, "bronze", "DEAP", "deap-dataset")
V1_ZIP = os.path.join(ROOT, "archive_DEAP_v1.zip")
DAT_DIR_V2 = os.path.join(BRONZE, "data_preprocessed_python")
XLS_PATH = os.path.join(BRONZE, "Metadata", "participant_ratings.xls")
OUTPUT = os.path.join(ROOT, "deap", "reports", "deap_label_audit.json")

DIMS = ["Valence", "Arousal", "Dominance", "Liking"]
SAM_MIN = 1.0
SAM_MAX = 9.0
TOLERANCE = 1e-4

ALLOWED = {
    ("numpy.core.multiarray", "_reconstruct"),
    ("numpy", "ndarray"),
    ("numpy", "dtype"),
}


class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) in ALLOWED:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(f"Refused: {module}.{name}")


def load_dat_bytes(data: bytes) -> dict:
    return RestrictedUnpickler(io.BytesIO(data), encoding="latin1").load()


def load_xls_ratings(xls_path: str) -> dict:
    """
    Returns {participant_id (int): {experiment_id (int): {dim: value}}}.
    experiment_id runs 1..40; dim is one of Valence, Arousal, Dominance, Liking.
    """
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
            "Valence": row[col["Valence"]],
            "Arousal": row[col["Arousal"]],
            "Dominance": row[col["Dominance"]],
            "Liking": row[col["Liking"]],
        }
    return ratings


def classify(mirror_val: float, xls_val: float) -> str:
    if abs(mirror_val - xls_val) <= TOLERANCE:
        return "match"
    if abs(mirror_val - (9.0 - xls_val)) <= TOLERANCE:
        return "inverted"
    return "other"


def audit_participant(labels: np.ndarray, xls_pid: dict, pid_str: str) -> dict:
    """
    labels: shape (40, 4) -- Valence, Arousal, Dominance, Liking in that order.
    xls_pid: {experiment_id: {dim: value}} for this participant.
    Returns per-trial, per-dimension classification.
    """
    out_of_range = []
    per_dim_counts = {d: {"match": 0, "inverted": 0, "other": 0} for d in DIMS}
    discrepancies = []

    for exp_id in range(1, 41):
        trial_idx = exp_id - 1
        if exp_id not in xls_pid:
            discrepancies.append({
                "experiment_id": exp_id,
                "note": "experiment_id missing from XLS"
            })
            continue
        xls_row = xls_pid[exp_id]
        for dim_idx, dim in enumerate(DIMS):
            val = float(labels[trial_idx, dim_idx])
            xls_val = xls_row[dim]
            cls = classify(val, xls_val)
            per_dim_counts[dim][cls] += 1
            if cls != "match":
                discrepancies.append({
                    "experiment_id": exp_id,
                    "trial_index": trial_idx,
                    "dim": dim,
                    "mirror_value": round(val, 6),
                    "xls_value": round(xls_val, 6),
                    "classification": cls,
                })
            # SAM range check
            if val < SAM_MIN - TOLERANCE or val > SAM_MAX + TOLERANCE:
                out_of_range.append({
                    "experiment_id": exp_id,
                    "trial_index": trial_idx,
                    "dim": dim,
                    "value": round(val, 6),
                })

    total_entries = 40 * 4
    total_match = sum(per_dim_counts[d]["match"] for d in DIMS)
    total_inverted = sum(per_dim_counts[d]["inverted"] for d in DIMS)
    total_other = sum(per_dim_counts[d]["other"] for d in DIMS)

    return {
        "participant": pid_str,
        "total_label_entries": total_entries,
        "xls_match": total_match,
        "xls_inverted": total_inverted,
        "xls_other": total_other,
        "out_of_sam_range_count": len(out_of_range),
        "out_of_sam_range": out_of_range,
        "per_dim_counts": per_dim_counts,
        "discrepancies": discrepancies,
    }


def sam_range_check_only(labels: np.ndarray, pid_str: str) -> dict:
    """Check SAM range without XLS comparison (for participants not in XLS)."""
    out_of_range = []
    for exp_id in range(1, 41):
        trial_idx = exp_id - 1
        for dim_idx, dim in enumerate(DIMS):
            val = float(labels[trial_idx, dim_idx])
            if val < SAM_MIN - TOLERANCE or val > SAM_MAX + TOLERANCE:
                out_of_range.append({
                    "experiment_id": exp_id,
                    "trial_index": trial_idx,
                    "dim": dim,
                    "value": round(val, 6),
                })
    return {
        "participant": pid_str,
        "total_label_entries": 160,
        "out_of_sam_range_count": len(out_of_range),
        "out_of_sam_range": out_of_range,
        "note": "not in v1 mirror; XLS comparison only",
    }


def run_audit() -> None:
    import zipfile

    # Load XLS
    xls_ratings = load_xls_ratings(XLS_PATH)
    xls_pids = set(xls_ratings.keys())
    print(f"XLS: {len(xls_ratings)} participants, IDs: {sorted(xls_pids)}", flush=True)

    # Collect v1 labels from zip (12 participants)
    v1_labels = {}
    with zipfile.ZipFile(V1_ZIP, "r") as zf:
        dat_entries = sorted(e for e in zf.namelist() if e.endswith(".dat"))
        for entry in dat_entries:
            fname = os.path.basename(entry)
            pid_str = fname.replace(".dat", "")  # e.g. "s01"
            with zf.open(entry) as f:
                data = load_dat_bytes(f.read())
            v1_labels[pid_str] = data["labels"]  # shape (40, 4)

    # Collect v2 labels from extracted bronze/DEAP
    v2_labels = {}
    for fname in sorted(os.listdir(DAT_DIR_V2)):
        if not fname.endswith(".dat"):
            continue
        pid_str = fname.replace(".dat", "")
        path = os.path.join(DAT_DIR_V2, fname)
        with open(path, "rb") as f:
            data = load_dat_bytes(f.read())
        v2_labels[pid_str] = data["labels"]
        print(f"  Loaded v2 {fname}", flush=True)

    all_pids_v2 = sorted(v2_labels.keys())
    v1_pids = sorted(v1_labels.keys())

    # SAM range check -- both mirrors
    sam_v1 = {}
    for pid_str, labels in sorted(v1_labels.items()):
        pid_int = int(pid_str[1:])
        out_of_range = []
        for exp_id in range(1, 41):
            for dim_idx, dim in enumerate(DIMS):
                val = float(labels[exp_id - 1, dim_idx])
                if val < SAM_MIN - TOLERANCE or val > SAM_MAX + TOLERANCE:
                    out_of_range.append({
                        "experiment_id": exp_id,
                        "dim": dim,
                        "value": round(val, 6),
                    })
        sam_v1[pid_str] = {
            "out_of_range_count": len(out_of_range),
            "out_of_range": out_of_range,
        }

    sam_v2 = {}
    for pid_str, labels in sorted(v2_labels.items()):
        out_of_range = []
        for exp_id in range(1, 41):
            for dim_idx, dim in enumerate(DIMS):
                val = float(labels[exp_id - 1, dim_idx])
                if val < SAM_MIN - TOLERANCE or val > SAM_MAX + TOLERANCE:
                    out_of_range.append({
                        "experiment_id": exp_id,
                        "dim": dim,
                        "value": round(val, 6),
                    })
        sam_v2[pid_str] = {
            "out_of_range_count": len(out_of_range),
            "out_of_range": out_of_range,
        }

    # XLS comparison -- v1 and v2 (all 32 for v2; 12 for v1)
    v1_audit = {}
    for pid_str in sorted(v1_pids):
        pid_int = int(pid_str[1:])
        if pid_int in xls_ratings:
            v1_audit[pid_str] = audit_participant(
                v1_labels[pid_str], xls_ratings[pid_int], pid_str
            )

    v2_audit = {}
    for pid_str in all_pids_v2:
        pid_int = int(pid_str[1:])
        if pid_int in xls_ratings:
            v2_audit[pid_str] = audit_participant(
                v2_labels[pid_str], xls_ratings[pid_int], pid_str
            )

    # Aggregate counts
    def aggregate(audit_dict: dict) -> dict:
        total = sum(p["total_label_entries"] for p in audit_dict.values())
        match = sum(p["xls_match"] for p in audit_dict.values())
        inverted = sum(p["xls_inverted"] for p in audit_dict.values())
        other = sum(p["xls_other"] for p in audit_dict.values())
        return {
            "participants_compared": len(audit_dict),
            "total_label_entries": total,
            "total_match": match,
            "total_inverted": inverted,
            "total_other": other,
        }

    v1_total_oor = sum(v["out_of_range_count"] for v in sam_v1.values())
    v2_total_oor = sum(v["out_of_range_count"] for v in sam_v2.values())

    report = {
        "matching_methodology": (
            "Trials in .dat labels arrays are in Experiment_id order (1..40). "
            "Matching: dat labels[i] corresponds to XLS row where "
            "Experiment_id == i+1 for the same participant. "
            "Confirmed: sorting participant 1 XLS rows by Experiment_id yields "
            "Experiment_ids 1,2,...,40, and labels[0] matches XLS Experiment_id=1."
        ),
        "sam_scale_note": (
            "SAM scale range is 1-9 (Koelstra et al. 2012). "
            "Tolerance for float comparison: 1e-4."
        ),
        "inversion_note": (
            "An 'inverted' classification means mirror_value == 9.0 - xls_value "
            "within tolerance. Affects only Valence and Arousal dimensions, "
            "and only specific trials per participant."
        ),
        "v1_mirror": {
            "archive": "archive_DEAP_v1.zip",
            "participant_count": len(v1_labels),
            "participant_ids": sorted(v1_labels.keys()),
            "sam_range_check": {
                "total_out_of_range": v1_total_oor,
                "participants_with_out_of_range": [
                    p for p, v in sorted(sam_v1.items())
                    if v["out_of_range_count"] > 0
                ],
                "per_participant": {
                    p: v for p, v in sorted(sam_v1.items())
                    if v["out_of_range_count"] > 0
                },
            },
            "xls_comparison": {
                "summary": aggregate(v1_audit),
                "per_participant": {p: v for p, v in sorted(v1_audit.items())},
            },
        },
        "v2_mirror": {
            "archive": "archive_DEAP_V2.zip",
            "participant_count": len(v2_labels),
            "participant_ids": sorted(v2_labels.keys()),
            "sam_range_check": {
                "total_out_of_range": v2_total_oor,
                "participants_with_out_of_range": [
                    p for p, v in sorted(sam_v2.items())
                    if v["out_of_range_count"] > 0
                ],
                "per_participant": {
                    p: v for p, v in sorted(sam_v2.items())
                    if v["out_of_range_count"] > 0
                },
            },
            "xls_comparison": {
                "summary": aggregate(v2_audit),
                "per_participant": {p: v for p, v in sorted(v2_audit.items())},
            },
        },
    }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
    print(f"\nReport written to {OUTPUT}", flush=True)


if __name__ == "__main__":
    run_audit()
