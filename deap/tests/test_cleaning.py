"""
Tests for deap/src/cleaning.py using synthetic data.
XLS loading is exercised via dict injection to avoid requiring xlwt.
"""
import csv
import json
import os
import pickle
import sys

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from deap.src.cleaning import clean_participant


LABEL_DIMS = ["valence", "arousal", "dominance", "liking"]


def _xls_ratings(pid_int: int, values: list) -> dict:
    """
    Build an xls_ratings dict: {pid_int: {exp_id: {dim: float}}}.
    values must be a list of 40 tuples (v, a, d, l).
    """
    return {
        pid_int: {
            i + 1: {
                "valence": float(values[i][0]),
                "arousal": float(values[i][1]),
                "dominance": float(values[i][2]),
                "liking": float(values[i][3]),
            }
            for i in range(40)
        }
    }


def _make_dat(tmpdir: str, pid: str, labels: np.ndarray) -> str:
    data = np.ones((40, 40, 8064), dtype=np.float64)
    path = os.path.join(tmpdir, f"{pid}.dat")
    with open(path, "wb") as f:
        pickle.dump({"data": data, "labels": labels}, f, protocol=4)
    return path


def test_cleaning_no_corrections_when_dat_matches_xls(tmp_path):
    """When dat labels match XLS, no corrections recorded."""
    labels = np.ones((40, 4), dtype=np.float64) * 5.0
    dat_path = _make_dat(str(tmp_path), "s01", labels)
    xls_ratings = _xls_ratings(1, [(5.0, 5.0, 5.0, 5.0)] * 40)
    silver_dir = str(tmp_path / "silver")
    rec = clean_participant(dat_path, xls_ratings, silver_dir)
    assert rec["n_corrections"] == 0
    assert rec["corrections"] == []


def test_cleaning_records_correction_when_dat_differs_from_xls(tmp_path):
    """When dat differs from XLS, correction is recorded."""
    labels = np.ones((40, 4), dtype=np.float64) * 5.0
    labels[0, 0] = 2.0  # trial 0, valence: dat=2, xls=5
    dat_path = _make_dat(str(tmp_path), "s01", labels)
    xls_ratings = _xls_ratings(1, [(5.0, 5.0, 5.0, 5.0)] * 40)
    silver_dir = str(tmp_path / "silver")
    rec = clean_participant(dat_path, xls_ratings, silver_dir)
    assert rec["n_corrections"] == 1
    assert rec["corrections"][0]["dat_value"] == pytest.approx(2.0)
    assert rec["corrections"][0]["xls_value"] == pytest.approx(5.0)
    assert rec["corrections"][0]["dim"] == "valence"


def test_cleaning_silver_csv_uses_xls_values(tmp_path):
    """Silver CSV must contain XLS values where dat differed."""
    labels = np.ones((40, 4), dtype=np.float64) * 5.0
    labels[0, 0] = 2.0  # trial 0, valence: dat=2, xls=7
    dat_path = _make_dat(str(tmp_path), "s01", labels)
    xls_ratings = _xls_ratings(1, [(7.0, 5.0, 5.0, 5.0)] * 40)
    silver_dir = str(tmp_path / "silver")
    clean_participant(dat_path, xls_ratings, silver_dir)

    csv_path = os.path.join(silver_dir, "s01_labels.csv")
    assert os.path.exists(csv_path)
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 40
    assert float(rows[0]["valence"]) == pytest.approx(7.0)


def test_cleaning_silver_csv_has_correct_columns(tmp_path):
    """Silver CSV must have trial_index, experiment_id, and four label dims."""
    labels = np.ones((40, 4), dtype=np.float64) * 5.0
    dat_path = _make_dat(str(tmp_path), "s02", labels)
    xls_ratings = _xls_ratings(2, [(5.0, 5.0, 5.0, 5.0)] * 40)
    silver_dir = str(tmp_path / "silver")
    clean_participant(dat_path, xls_ratings, silver_dir)

    csv_path = os.path.join(silver_dir, "s02_labels.csv")
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
    assert set(fieldnames) == {
        "trial_index", "experiment_id", "valence", "arousal", "dominance", "liking"
    }


def test_cleaning_silver_csv_has_40_rows(tmp_path):
    """Silver CSV must have exactly 40 data rows."""
    labels = np.ones((40, 4), dtype=np.float64) * 5.0
    dat_path = _make_dat(str(tmp_path), "s03", labels)
    xls_ratings = _xls_ratings(3, [(5.0, 5.0, 5.0, 5.0)] * 40)
    silver_dir = str(tmp_path / "silver")
    clean_participant(dat_path, xls_ratings, silver_dir)

    csv_path = os.path.join(silver_dir, "s03_labels.csv")
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert len(rows) == 40


def test_cleaning_all_878_inversions_corrected():
    """Full correction count matches expected 878 (requires pipeline report)."""
    report_path = os.path.join(
        PROJECT_ROOT, "deap", "reports", "deap_cleaning.json"
    )
    if not os.path.exists(report_path):
        pytest.skip("deap_cleaning.json not found; run pipeline first")
    with open(report_path) as f:
        report = json.load(f)
    assert report["total_corrections"] == 878
