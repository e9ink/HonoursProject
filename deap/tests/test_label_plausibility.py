"""
Tests for deap/src/checks/label_plausibility.py using synthetic data.
"""
import os
import pickle
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from deap.src.checks.label_plausibility import check_participant

THRESHOLDS = {
    "label_plausibility": {
        "min_label_value": 1.0,
        "max_label_value": 9.0,
        "max_out_of_range": 0,
    }
}


def _make_dat(data, labels):
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "s99.dat")
    with open(path, "wb") as f:
        pickle.dump({"data": data, "labels": labels}, f, protocol=4)
    return path


def _clean_data():
    return np.ones((40, 40, 8064), dtype=np.float64)


def test_label_plausibility_valid_passes():
    """Labels all in [1, 9] must pass."""
    labels = np.full((40, 4), 5.0, dtype=np.float64)
    path = _make_dat(_clean_data(), labels)
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is True
    assert result["total_out_of_range"] == 0


def test_label_plausibility_boundary_values_pass():
    """Labels exactly at 1.0 and 9.0 must pass."""
    labels = np.full((40, 4), 5.0, dtype=np.float64)
    labels[0, 0] = 1.0
    labels[0, 1] = 9.0
    path = _make_dat(_clean_data(), labels)
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is True


def test_label_plausibility_zero_fails():
    """Label value of 0.0 must fail (below SAM minimum of 1)."""
    labels = np.full((40, 4), 5.0, dtype=np.float64)
    labels[0, 0] = 0.0
    path = _make_dat(_clean_data(), labels)
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is False
    assert result["total_out_of_range"] >= 1
    assert result["violations"][0]["dim"] == "valence"
    assert result["violations"][0]["value"] == 0.0


def test_label_plausibility_above_max_fails():
    """Label value of 10.0 must fail (above SAM maximum of 9)."""
    labels = np.full((40, 4), 5.0, dtype=np.float64)
    labels[5, 1] = 10.0
    path = _make_dat(_clean_data(), labels)
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is False
    assert result["total_out_of_range"] >= 1
    assert result["violations"][0]["dim"] == "arousal"


def test_label_plausibility_multiple_violations():
    """Multiple out-of-range labels all counted."""
    labels = np.full((40, 4), 5.0, dtype=np.float64)
    labels[0, 0] = 0.0   # valence=0
    labels[1, 1] = 10.0  # arousal=10
    labels[2, 2] = -1.0  # dominance=-1
    path = _make_dat(_clean_data(), labels)
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is False
    assert result["total_out_of_range"] == 3
