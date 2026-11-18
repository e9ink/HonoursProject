"""
Tests for deap/src/checks/post_cleaning.py using synthetic Silver label CSVs.
"""
import csv
import json
import os
import sys
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from deap.src.checks.post_cleaning import check_participant


THRESHOLDS = {
    "meta": {"signed_off": True},
    "label_plausibility": {
        "min_label_value": 1.0,
        "max_label_value": 9.0,
        "max_out_of_range": 0,
    },
    "consistency_cross_source": {
        "tolerance": 1e-4,
        "max_mismatches": 0,
    },
}


def _xls_pid(values: list) -> dict:
    """Return {exp_id: {dim: float}} for 40 trials. values = list of (v,a,d,l)."""
    return {
        i + 1: {
            "valence": float(values[i][0]),
            "arousal": float(values[i][1]),
            "dominance": float(values[i][2]),
            "liking": float(values[i][3]),
        }
        for i in range(40)
    }


def _write_silver_csv(path: str, rows: list) -> None:
    """Write a Silver label CSV. rows = list of (v,a,d,l) for 40 trials."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["trial_index", "experiment_id", "valence", "arousal",
                           "dominance", "liking"]
        )
        writer.writeheader()
        for i, (v, a, d, l) in enumerate(rows):
            writer.writerow({
                "trial_index": i, "experiment_id": i + 1,
                "valence": v, "arousal": a, "dominance": d, "liking": l,
            })


def test_post_cleaning_clean_passes(tmp_path):
    """Clean Silver labels matching XLS must pass both checks."""
    csv_path = str(tmp_path / "s01_labels.csv")
    vals = [(5.0, 5.0, 5.0, 5.0)] * 40
    _write_silver_csv(csv_path, vals)
    xls_pid = _xls_pid(vals)
    result = check_participant("s01", csv_path, xls_pid, THRESHOLDS)
    assert result["pass"] is True
    assert result["label_plausibility"]["total_out_of_range"] == 0
    assert result["cross_source"]["total_mismatches"] == 0


def test_post_cleaning_oor_detected(tmp_path):
    """Labels below 1 (inversion artefact residue) must be flagged."""
    vals = [(5.0, 5.0, 5.0, 5.0)] * 40
    vals[0] = (0.5, 5.0, 5.0, 5.0)  # valence below SAM min
    csv_path = str(tmp_path / "s01_labels.csv")
    _write_silver_csv(csv_path, vals)
    xls_pid = _xls_pid([(5.0, 5.0, 5.0, 5.0)] * 40)
    result = check_participant("s01", csv_path, xls_pid, THRESHOLDS)
    assert result["label_plausibility"]["total_out_of_range"] >= 1
    assert result["label_plausibility"]["pass"] is False


def test_post_cleaning_cross_source_mismatch_detected(tmp_path):
    """Silver value differing from XLS by more than tolerance must be flagged."""
    vals = [(5.0, 5.0, 5.0, 5.0)] * 40
    csv_path = str(tmp_path / "s01_labels.csv")
    _write_silver_csv(csv_path, vals)
    xls_rows = [(5.0, 5.0, 5.0, 5.0)] * 40
    xls_rows[3] = (7.0, 5.0, 5.0, 5.0)  # trial 3 valence mismatch
    xls_pid = _xls_pid(xls_rows)
    result = check_participant("s01", csv_path, xls_pid, THRESHOLDS)
    assert result["cross_source"]["total_mismatches"] >= 1
    assert result["cross_source"]["pass"] is False


def test_post_cleaning_silver_derived_from_xls_passes(tmp_path):
    """Silver CSV values taken directly from XLS must have zero mismatches."""
    vals = [(float(i % 9 + 1), 5.0, 4.0, 6.0) for i in range(40)]
    csv_path = str(tmp_path / "s01_labels.csv")
    _write_silver_csv(csv_path, vals)
    xls_pid = _xls_pid(vals)
    result = check_participant("s01", csv_path, xls_pid, THRESHOLDS)
    assert result["pass"] is True


def test_post_cleaning_full_pipeline_result():
    """Full pipeline post-cleaning report must show 0 OOR and 0 mismatches."""
    report_path = os.path.join(
        PROJECT_ROOT, "deap", "reports", "deap_post_cleaning.json"
    )
    if not os.path.exists(report_path):
        pytest.skip("deap_post_cleaning.json not found; run pipeline first")
    with open(report_path) as f:
        report = json.load(f)
    assert report["total_label_plausibility_oor"] == 0
    assert report["total_cross_source_mismatches"] == 0
    assert report["overall_pass"] is True
