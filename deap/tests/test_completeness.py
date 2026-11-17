"""
Tests for deap/src/checks/completeness.py using synthetic data.
"""
import io
import os
import pickle
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from deap.src.checks.completeness import check_participant


THRESHOLDS = {
    "completeness": {
        "max_nan_count": 0,
        "max_inf_count": 0,
    }
}

ALLOWED = {
    ("numpy.core.multiarray", "_reconstruct"),
    ("numpy", "ndarray"),
    ("numpy", "dtype"),
}


def _make_dat(data, labels):
    """Write a minimal .dat pickle and return its path in a temp dir."""
    tmpdir = tempfile.mkdtemp()
    path = os.path.join(tmpdir, "s99.dat")
    with open(path, "wb") as f:
        pickle.dump({"data": data, "labels": labels}, f, protocol=4)
    return path


def _clean_data():
    return np.ones((40, 40, 8064), dtype=np.float64)


def _clean_labels():
    return np.ones((40, 4), dtype=np.float64) * 5.0


def test_completeness_clean_passes():
    """Clean data with no NaNs or Infs must pass."""
    path = _make_dat(_clean_data(), _clean_labels())
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is True
    assert result["total_nan"] == 0
    assert result["total_inf"] == 0


def test_completeness_nan_fails():
    """Data with a NaN must fail."""
    data = _clean_data()
    data[0, 0, 0] = np.nan
    path = _make_dat(data, _clean_labels())
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is False
    assert result["total_nan"] >= 1


def test_completeness_inf_fails():
    """Data with an Inf must fail."""
    data = _clean_data()
    data[5, 3, 100] = np.inf
    path = _make_dat(data, _clean_labels())
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is False
    assert result["total_inf"] >= 1


def test_completeness_neg_inf_fails():
    """Data with -Inf must fail."""
    data = _clean_data()
    data[0, 0, 0] = -np.inf
    path = _make_dat(data, _clean_labels())
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is False
    assert result["total_inf"] >= 1


def test_completeness_per_channel_reported():
    """NaN in Fp1 (index 0) must appear in per_channel stats."""
    data = _clean_data()
    data[:, 0, :50] = np.nan  # Fp1 channel, first 50 samples of all trials
    path = _make_dat(data, _clean_labels())
    result = check_participant(path, THRESHOLDS)
    assert result["pass"] is False
    assert result["per_channel"]["Fp1"]["nan_count"] > 0
    assert result["per_channel"]["Temp"]["nan_count"] == 0
