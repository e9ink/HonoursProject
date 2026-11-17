"""
Tests for deap/src/checks/consistency.py using synthetic data.
"""
import os
import pickle
import sys
import tempfile

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from deap.src.checks.consistency import check_structure, check_cross_source

THRESHOLDS = {
    "conformance": {
        "expected_data_shape": [40, 40, 8064],
        "expected_labels_shape": [40, 4],
        "expected_dtype": "float64",
        "max_violations": 0,
    },
    "consistency_structure": {
        "max_mismatches": 0,
    },
    "consistency_cross_source": {
        "tolerance": 1.0e-4,
        "max_mismatches": 0,
    },
}


def _make_participant(pid, data_shape=(40, 40, 8064), labels_shape=(40, 4),
                       label_value=5.0):
    data = np.ones(data_shape, dtype=np.float64)
    labels = np.full(labels_shape, label_value, dtype=np.float64)
    return {
        "participant": pid,
        "data": data,
        "labels": labels,
        "data_shape": list(data.shape),
        "labels_shape": list(labels.shape),
    }


def test_structure_all_matching_passes():
    """All participants with correct shapes must pass."""
    participants = [_make_participant(f"s{i:02d}") for i in range(1, 4)]
    result = check_structure(participants, THRESHOLDS)
    assert result["pass"] is True
    assert result["total_mismatches"] == 0


def test_structure_one_wrong_data_shape_fails():
    """One participant with wrong data shape must cause failure."""
    participants = [
        _make_participant("s01"),
        _make_participant("s02", data_shape=(40, 40, 8000)),
    ]
    result = check_structure(participants, THRESHOLDS)
    assert result["pass"] is False
    assert result["total_mismatches"] >= 1
    assert any(m["participant"] == "s02" for m in result["mismatches"])


def test_structure_one_wrong_labels_shape_fails():
    """One participant with wrong labels shape must cause failure."""
    participants = [
        _make_participant("s01"),
        _make_participant("s02", labels_shape=(40, 5)),
    ]
    result = check_structure(participants, THRESHOLDS)
    assert result["pass"] is False
    assert any(m["field"] == "labels_shape" for m in result["mismatches"])


def test_cross_source_matching_passes():
    """Labels identical to XLS must pass cross-source check."""
    participants = [_make_participant("s01")]
    # Build a fake XLS ratings dict matching the labels
    xls_ratings = {
        1: {
            exp_id: {"valence": 5.0, "arousal": 5.0, "dominance": 5.0, "liking": 5.0}
            for exp_id in range(1, 41)
        }
    }
    result = check_cross_source(participants, xls_ratings, tolerance=1e-4)
    assert result["pass"] is True
    assert result["total_mismatches"] == 0


def test_cross_source_mismatch_fails():
    """Labels differing from XLS by more than tolerance must fail."""
    participants = [_make_participant("s01", label_value=5.0)]
    xls_ratings = {
        1: {
            exp_id: {"valence": 9.0, "arousal": 5.0, "dominance": 5.0, "liking": 5.0}
            for exp_id in range(1, 41)
        }
    }
    result = check_cross_source(participants, xls_ratings, tolerance=1e-4)
    assert result["pass"] is False
    assert result["total_mismatches"] == 40  # 40 trials, valence wrong each time


def test_cross_source_within_tolerance_passes():
    """Labels differing from XLS by less than tolerance must pass."""
    participants = [_make_participant("s01", label_value=5.0)]
    xls_ratings = {
        1: {
            exp_id: {"valence": 5.00005, "arousal": 5.0, "dominance": 5.0, "liking": 5.0}
            for exp_id in range(1, 41)
        }
    }
    result = check_cross_source(participants, xls_ratings, tolerance=1e-4)
    assert result["pass"] is True


def test_cross_source_missing_pid_skipped():
    """Participant not in XLS ratings is silently skipped."""
    participants = [_make_participant("s99")]
    xls_ratings = {}
    result = check_cross_source(participants, xls_ratings, tolerance=1e-4)
    assert result["pass"] is True
    assert result["total_entries_compared"] == 0
