"""
Internal validation tests for src/checks/plausibility.py (Task 6).

All inputs are synthetic — no real WESAD data is read.
Tests verify:
  - physiological_implausible classification is applied correctly.
  - device_capacity classification is applied correctly (E4 EDA above max).
  - device_rail classification is applied correctly (ACC, RespiBAN channels).
  - In-bounds values produce zero violations.
  - Determinism: identical output on two consecutive calls.
"""
import json

import pytest

from src.checks.plausibility import _check_e4_signal, check_respiban
from tests.conftest import (
    FAKE_RANGES,
    make_e4_acc_csv,
    make_e4_csv,
    make_respiban_txt,
    neutral_respiban_row,
)

WESAD_CFG = FAKE_RANGES["wesad"]
THRESHOLD = 0.01


# ── E4 EDA: physiological_implausible (below) and device_capacity (above) ─────

class TestEdaClassification:

    def test_eda_in_bounds_no_violation(self, tmp_path):
        """EDA values within [0, 100] µS → 0 violations."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [0.0, 50.0, 100.0], hz=4.0)
        r = _check_e4_signal(f, "EDA", WESAD_CFG, THRESHOLD)
        assert r["n_violations"] == 0
        assert r["physiological_implausible_count"] == 0
        assert r["device_flagged_count"] == 0
        assert r["passes_threshold"] is True

    def test_eda_below_min_physiological_implausible(self, tmp_path):
        """EDA of -1 µS is below physiological minimum → physiological_implausible."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [-1.0, 50.0, 80.0], hz=4.0)
        r = _check_e4_signal(f, "EDA", WESAD_CFG, THRESHOLD)
        assert r["n_violations"] == 1
        assert r["n_below_min"] == 1
        assert r["physiological_implausible_count"] == 1
        assert r["device_flagged_count"] == 0
        # Confirm classification label via BREACH_CLASS
        assert r["breach_class_below_min"] == "physiological_implausible"

    def test_eda_above_max_device_capacity(self, tmp_path):
        """EDA of 101 µS exceeds device capacity → device_capacity (not physiological_implausible)."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [50.0, 101.0, 80.0], hz=4.0)
        r = _check_e4_signal(f, "EDA", WESAD_CFG, THRESHOLD)
        assert r["n_violations"] == 1
        assert r["n_above_max"] == 1
        assert r["physiological_implausible_count"] == 0
        assert r["device_flagged_count"] == 1
        assert r["breach_class_above_max"] == "device_capacity"


# ── E4 TEMP: physiological_implausible on both sides ─────────────────────────

class TestTempClassification:

    def test_temp_in_bounds_no_violation(self, tmp_path):
        """TEMP values within [15, 42] °C → 0 violations."""
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [15.0, 35.0, 42.0], hz=4.0)
        r = _check_e4_signal(f, "skin_temperature", WESAD_CFG, THRESHOLD)
        assert r["n_violations"] == 0
        assert r["physiological_implausible_count"] == 0

    def test_temp_below_min_physiological_implausible(self, tmp_path):
        """TEMP of 10 °C is below physiological minimum → physiological_implausible."""
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [10.0, 36.0, 37.0], hz=4.0)
        r = _check_e4_signal(f, "skin_temperature", WESAD_CFG, THRESHOLD)
        assert r["n_violations"] == 1
        assert r["physiological_implausible_count"] == 1
        assert r["device_flagged_count"] == 0
        assert r["breach_class_below_min"] == "physiological_implausible"

    def test_temp_above_max_physiological_implausible(self, tmp_path):
        """TEMP of 50 °C exceeds physiological maximum → physiological_implausible."""
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [36.0, 50.0, 37.0], hz=4.0)
        r = _check_e4_signal(f, "skin_temperature", WESAD_CFG, THRESHOLD)
        assert r["n_violations"] == 1
        assert r["physiological_implausible_count"] == 1
        assert r["device_flagged_count"] == 0
        assert r["breach_class_above_max"] == "physiological_implausible"


# ── E4 HR: physiological_implausible on both sides ────────────────────────────

class TestHRClassification:

    def test_hr_in_bounds_no_violation(self, tmp_path):
        """HR values within [20, 250] bpm → 0 violations."""
        f = tmp_path / "HR.csv"
        make_e4_csv(f, [60.0, 100.0, 180.0], hz=1.0)
        r = _check_e4_signal(f, "heart_rate", WESAD_CFG, THRESHOLD)
        assert r["n_violations"] == 0
        assert r["physiological_implausible_count"] == 0

    def test_hr_below_min_physiological_implausible(self, tmp_path):
        """HR of 10 bpm is below physiological minimum → physiological_implausible."""
        f = tmp_path / "HR.csv"
        make_e4_csv(f, [10.0, 60.0, 80.0], hz=1.0)
        r = _check_e4_signal(f, "heart_rate", WESAD_CFG, THRESHOLD)
        assert r["n_violations"] == 1
        assert r["physiological_implausible_count"] == 1
        assert r["breach_class_below_min"] == "physiological_implausible"

    def test_hr_above_max_physiological_implausible(self, tmp_path):
        """HR of 300 bpm exceeds physiological maximum → physiological_implausible."""
        f = tmp_path / "HR.csv"
        make_e4_csv(f, [60.0, 300.0, 80.0], hz=1.0)
        r = _check_e4_signal(f, "heart_rate", WESAD_CFG, THRESHOLD)
        assert r["n_violations"] == 1
        assert r["physiological_implausible_count"] == 1
        assert r["breach_class_above_max"] == "physiological_implausible"


# ── E4 ACC: device_rail on both sides ────────────────────────────────────────

class TestACCClassification:

    def test_acc_in_bounds_no_violation(self, tmp_path):
        """ACC stored values within ±128 → 0 violations."""
        f = tmp_path / "ACC.csv"
        make_e4_acc_csv(f, [(50, -50, 0), (10, 20, -30)], hz=32.0)
        r = _check_e4_signal(
            f, "accelerometry_e4", WESAD_CFG, THRESHOLD,
            stored_unit_factor=64.0,
        )
        assert r["n_violations"] == 0
        assert r["physiological_implausible_count"] == 0
        assert r["device_flagged_count"] == 0

    def test_acc_above_max_device_rail(self, tmp_path):
        """ACC x-axis value 200 > 128 (2g rail) → device_rail, not physiological_implausible."""
        f = tmp_path / "ACC.csv"
        make_e4_acc_csv(f, [(200, 0, 0), (10, 0, 0)], hz=32.0)
        r = _check_e4_signal(
            f, "accelerometry_e4", WESAD_CFG, THRESHOLD,
            stored_unit_factor=64.0,
        )
        assert r["n_violations"] == 1
        assert r["physiological_implausible_count"] == 0
        assert r["device_flagged_count"] == 1
        # Verify via per-axis structure for ACC
        assert r["per_axis"]["x"]["breach_class_above_max"] == "device_rail"

    def test_acc_below_min_device_rail(self, tmp_path):
        """ACC y-axis value -200 < -128 → device_rail."""
        f = tmp_path / "ACC.csv"
        make_e4_acc_csv(f, [(0, -200, 0), (0, 0, 0)], hz=32.0)
        r = _check_e4_signal(
            f, "accelerometry_e4", WESAD_CFG, THRESHOLD,
            stored_unit_factor=64.0,
        )
        assert r["n_violations"] == 1
        assert r["physiological_implausible_count"] == 0
        assert r["device_flagged_count"] == 1
        assert r["per_axis"]["y"]["breach_class_below_min"] == "device_rail"


# ── RespiBAN plausibility: device_rail classification ─────────────────────────

class TestRespiBanPlausibility:

    def test_all_in_bounds_no_violation(self, tmp_path):
        """Neutral rows with all channels in-bounds → 0 violations on all signals."""
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(i) for i in range(5)]
        make_respiban_txt(f, rows)
        r = check_respiban(f, WESAD_CFG, THRESHOLD)
        assert r["ECG"]["n_violations"] == 0
        assert r["EMG"]["n_violations"] == 0
        assert r["RESP"]["n_violations"] == 0
        assert r["ACC"]["n_violations"] == 0

    def test_acc_above_bound_device_rail(self, tmp_path):
        """
        CH5 raw=40000 → g=(40000-28000)/(38000-28000)*2-1 = 1.4 > 1.0
        → device_rail (not physiological_implausible).
        """
        f = tmp_path / "S99_respiban.txt"
        rows = [
            # CH5=40000 produces 1.4 g > 1.0 (device_rail bound)
            (0, 0, 32768, 32768, 32768, 32768, 40000, 33000, 33000, 32768),
            neutral_respiban_row(1),
        ]
        make_respiban_txt(f, rows)
        r = check_respiban(f, WESAD_CFG, THRESHOLD)
        assert r["ACC"]["n_violations"] == 1
        assert r["ACC"]["physiological_implausible_count"] == 0
        assert r["ACC"]["device_flagged_count"] == 1
        assert r["ACC"]["per_axis"]["x"]["breach_class_above_max"] == "device_rail"

    def test_acc_below_bound_device_rail(self, tmp_path):
        """
        CH5 raw=25000 → g=(25000-28000)/10000*2-1 = -1.6 < -1.0
        → device_rail.
        """
        f = tmp_path / "S99_respiban.txt"
        rows = [
            (0, 0, 32768, 32768, 32768, 32768, 25000, 33000, 33000, 32768),
            neutral_respiban_row(1),
        ]
        make_respiban_txt(f, rows)
        r = check_respiban(f, WESAD_CFG, THRESHOLD)
        assert r["ACC"]["n_violations"] == 1
        assert r["ACC"]["physiological_implausible_count"] == 0
        assert r["ACC"]["device_flagged_count"] == 1
        assert r["ACC"]["per_axis"]["x"]["breach_class_below_min"] == "device_rail"

    def test_ch2_ch4_excluded(self, tmp_path):
        """RespiBAN CH2 (EDA) and CH4 (TEMP) are always excluded with a reason."""
        f = tmp_path / "S99_respiban.txt"
        make_respiban_txt(f, [neutral_respiban_row(0)])
        r = check_respiban(f, WESAD_CFG, THRESHOLD)
        assert r["EDA_chest"]["excluded"] is True
        assert "reason" in r["EDA_chest"]
        assert r["TEMP_chest"]["excluded"] is True
        assert "reason" in r["TEMP_chest"]

    def test_determinism_plausibility(self, tmp_path):
        """Two consecutive calls on the same file produce identical results."""
        f = tmp_path / "S99_respiban.txt"
        rows = [
            (0, 0, 32768, 32768, 32768, 32768, 40000, 33000, 33000, 32768),
            neutral_respiban_row(1),
        ]
        make_respiban_txt(f, rows)
        r1 = json.dumps(check_respiban(f, WESAD_CFG, THRESHOLD), sort_keys=True)
        r2 = json.dumps(check_respiban(f, WESAD_CFG, THRESHOLD), sort_keys=True)
        assert r1 == r2

    def test_determinism_e4(self, tmp_path):
        """E4 signal check produces identical results on two calls."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [-1.0, 50.0, 101.0], hz=4.0)
        r1 = json.dumps(
            _check_e4_signal(f, "EDA", WESAD_CFG, THRESHOLD), sort_keys=True
        )
        r2 = json.dumps(
            _check_e4_signal(f, "EDA", WESAD_CFG, THRESHOLD), sort_keys=True
        )
        assert r1 == r2
