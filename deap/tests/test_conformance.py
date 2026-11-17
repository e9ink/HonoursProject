"""
Tests for deap/src/checks/conformance.py using synthetic data.
"""
import os
import pickle
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from deap.src.checks.conformance import check_participant

THRESHOLDS = {
    "conformance": {
        "expected_data_shape": [40, 40, 8064],
        "expected_labels_shape": [40, 4],
        "expected_dtype": "float64",
        "max_violations": 0,
    }
}


def _make_dat(data, labels):
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "s99.dat")
    with open(path, "wb") as f:
        pickle.dump({"data": data, "labels": labels}, f, protocol=4)
    return path


def test_conformance_correct_shape_passes():
    """Standard (40,40,8064) data and (40,4) labels must pass."""
    data = np.ones((40, 40, 8064), dtype=np.float64)
    labels = np.ones((40, 4), dtype=np.float64)
    path = _make_dat(data, labels)
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is True
    assert result["violation_count"] == 0


def test_conformance_wrong_data_shape_fails():
    """Truncated data array must fail."""
    data = np.ones((40, 40, 8000), dtype=np.float64)  # wrong time dim
    labels = np.ones((40, 4), dtype=np.float64)
    path = _make_dat(data, labels)
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is False
    assert result["violation_count"] >= 1
    assert any(v["field"] == "data_shape" for v in result["violations"])


def test_conformance_wrong_labels_shape_fails():
    """Wrong labels shape must fail."""
    data = np.ones((40, 40, 8064), dtype=np.float64)
    labels = np.ones((40, 5), dtype=np.float64)  # 5 dims instead of 4
    path = _make_dat(data, labels)
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is False
    assert any(v["field"] == "labels_shape" for v in result["violations"])


def test_conformance_wrong_dtype_fails():
    """float32 dtype must fail."""
    data = np.ones((40, 40, 8064), dtype=np.float32)
    labels = np.ones((40, 4), dtype=np.float32)
    path = _make_dat(data, labels)
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is False
    assert any(v["field"] == "data_dtype" for v in result["violations"])


def test_conformance_multiple_violations():
    """Wrong shape and wrong dtype both reported."""
    data = np.ones((40, 40, 1000), dtype=np.float32)
    labels = np.ones((40, 4), dtype=np.float64)
    path = _make_dat(data, labels)
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is False
    assert result["violation_count"] >= 2
