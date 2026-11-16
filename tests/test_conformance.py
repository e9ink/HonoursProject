"""
Internal validation tests for src/checks/conformance.py (Task 6).

All inputs are synthetic — no real WESAD data is read.
"""
import json


from src.checks.conformance import _check_e4_modality, check_respiban
from tests.conftest import (
    FAKE_RANGES,
    make_e4_acc_csv,
    make_e4_csv,
    make_respiban_txt,
    neutral_respiban_row,
)


# ── E4 sampling-rate conformance ──────────────────────────────────────────────

class TestE4SamplingRate:

    def test_correct_hz_ok(self, tmp_path):
        """EDA declared at 4.0 Hz (expected) → sampling_rate ok=True."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [50.0, 51.0, 52.0], hz=4.0)
        result = _check_e4_modality(f, "EDA", FAKE_RANGES)
        assert result["sampling_rate"]["ok"] is True
        assert result["sampling_rate"]["declared_hz"] == 4.0

    def test_wrong_hz_flagged(self, tmp_path):
        """EDA declared at 8.0 Hz (expected 4.0) → sampling_rate ok=False."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [50.0, 51.0, 52.0], hz=8.0)
        result = _check_e4_modality(f, "EDA", FAKE_RANGES)
        assert result["sampling_rate"]["ok"] is False
        assert "violation" in result["sampling_rate"]

    def test_sampling_note_always_present(self, tmp_path):
        """The E4 no-per-sample-timestamps note is always in the output."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [50.0], hz=4.0)
        result = _check_e4_modality(f, "EDA", FAKE_RANGES)
        assert "note" in result["sampling_rate"]


# ── E4 range conformance ──────────────────────────────────────────────────────

class TestE4Range:

    def test_eda_in_range_no_violation(self, tmp_path):
        """EDA values within [0, 100] µS → no range violation."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [0.0, 50.0, 100.0], hz=4.0)
        result = _check_e4_modality(f, "EDA", FAKE_RANGES)
        assert result["range"]["n_violations"] == 0
        assert result["range"]["ok"] is True

    def test_eda_below_min_flagged(self, tmp_path):
        """EDA value of -1 µS (below 0) → 1 violation."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [-1.0, 50.0, 80.0], hz=4.0)
        result = _check_e4_modality(f, "EDA", FAKE_RANGES)
        assert result["range"]["n_violations"] == 1
        assert result["range"]["n_below_min"] == 1
        assert result["range"]["ok"] is False

    def test_eda_above_max_flagged(self, tmp_path):
        """EDA value of 101 µS (above 100) → 1 violation."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [50.0, 101.0, 80.0], hz=4.0)
        result = _check_e4_modality(f, "EDA", FAKE_RANGES)
        assert result["range"]["n_violations"] == 1
        assert result["range"]["n_above_max"] == 1

    def test_acc_in_range_no_violation(self, tmp_path):
        """ACC values within ±128 stored units (±2 g) → no violation."""
        f = tmp_path / "ACC.csv"
        # 50, -50, 0 are all within [-128, 128]
        make_e4_acc_csv(f, [(50, -50, 0), (10, 20, -30)], hz=32.0)
        result = _check_e4_modality(f, "ACC", FAKE_RANGES)
        assert result["range"]["n_violations"] == 0
        assert result["range"]["ok"] is True

    def test_acc_exceeds_rail_flagged(self, tmp_path):
        """ACC value of 200 (stored units) > 128 (2g rail) → violation."""
        f = tmp_path / "ACC.csv"
        # Row 0: 200 on x-axis exceeds ±128 stored-unit limit
        make_e4_acc_csv(f, [(200, 0, 0), (10, 0, 0)], hz=32.0)
        result = _check_e4_modality(f, "ACC", FAKE_RANGES)
        assert result["range"]["n_violations"] == 1
        assert result["range"]["n_above_max"] == 1

    def test_bvp_range_not_checked(self, tmp_path):
        """BVP has no documented range → range entry marks checked=False."""
        f = tmp_path / "BVP.csv"
        make_e4_csv(f, [500.0, -800.0, 1200.0], hz=64.0)
        result = _check_e4_modality(f, "BVP", FAKE_RANGES)
        assert result["range"]["checked"] is False

    def test_determinism_e4(self, tmp_path):
        """Two calls on the same EDA file produce identical results."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [-1.0, 50.0, 101.0], hz=4.0)
        r1 = json.dumps(_check_e4_modality(f, "EDA", FAKE_RANGES), sort_keys=True)
        r2 = json.dumps(_check_e4_modality(f, "EDA", FAKE_RANGES), sort_keys=True)
        assert r1 == r2


# ── RespiBAN conformance ──────────────────────────────────────────────────────

class TestRespiBAN:

    def test_correct_hz_ok(self, tmp_path):
        """Declared 700 Hz matches expected → sampling_rate ok=True."""
        f = tmp_path / "S99_respiban.txt"
        make_respiban_txt(f, [neutral_respiban_row(0)], hz=700)
        result = check_respiban(f)
        assert result["sampling_rate"]["ok"] is True

    def test_wrong_hz_flagged(self, tmp_path):
        """Declared 500 Hz (expected 700) → sampling_rate ok=False."""
        f = tmp_path / "S99_respiban.txt"
        make_respiban_txt(f, [neutral_respiban_row(0)], hz=500)
        result = check_respiban(f)
        assert result["sampling_rate"]["ok"] is False
        assert "violation" in result["sampling_rate"]

    def test_adc_in_range_no_violation(self, tmp_path):
        """All channel values in [0, 65535] → no ADC range violations."""
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(i) for i in range(5)]
        make_respiban_txt(f, rows)
        result = check_respiban(f)
        assert result["range_summary"]["total_violations"] == 0
        assert result["range_summary"]["ok"] is True

    def test_adc_above_max_flagged(self, tmp_path):
        """CH1 value 70000 > 65535 (ADC ceiling) → violation on ECG channel."""
        f = tmp_path / "S99_respiban.txt"
        rows = [
            (0, 0, 70000, 32768, 32768, 32768, 33000, 33000, 33000, 32768),
            neutral_respiban_row(1),
        ]
        make_respiban_txt(f, rows)
        result = check_respiban(f)
        assert result["per_channel_range"]["CH1"]["n_violations"] == 1
        assert result["per_channel_range"]["CH1"]["n_above_max"] == 1
        assert result["range_summary"]["total_violations"] == 1

    def test_adc_below_min_flagged(self, tmp_path):
        """Negative ADC value (-1) is below 0 → violation."""
        f = tmp_path / "S99_respiban.txt"
        rows = [
            (0, 0, 32768, 32768, -1, 32768, 33000, 33000, 33000, 32768),
            neutral_respiban_row(1),
        ]
        make_respiban_txt(f, rows)
        result = check_respiban(f)
        assert result["per_channel_range"]["CH3"]["n_violations"] == 1
        assert result["per_channel_range"]["CH3"]["n_below_min"] == 1

    def test_determinism_chest(self, tmp_path):
        """Two calls on the same RespiBAN file produce identical results."""
        f = tmp_path / "S99_respiban.txt"
        rows = [
            (0, 0, 70000, 32768, 32768, 32768, 33000, 33000, 33000, 32768),
            neutral_respiban_row(1),
        ]
        make_respiban_txt(f, rows)
        r1 = json.dumps(check_respiban(f), sort_keys=True)
        r2 = json.dumps(check_respiban(f), sort_keys=True)
        assert r1 == r2


# ── Non-numeric conformance violations ───────────────────────────────────────

class TestNonNumericConformance:
    """
    Non-numeric values in numeric channels are a conformance violation.
    Empty/null cells remain completeness's concern and must NOT be reclassified.
    """

    # ── E4 path ──

    def test_e4_non_numeric_caught(self, tmp_path):
        """'bad' string in EDA channel → n_non_numeric=1, ok=False."""
        f = tmp_path / "EDA.csv"
        # make_e4_csv writes values via str(); "bad" becomes the literal string "bad"
        make_e4_csv(f, ["bad", 50.0, 80.0], hz=4.0)
        result = _check_e4_modality(f, "EDA", FAKE_RANGES)
        assert result["non_numeric"]["n_non_numeric"] == 1
        assert result["non_numeric"]["ok"] is False

    def test_e4_valid_data_no_non_numeric(self, tmp_path):
        """All-numeric EDA values → n_non_numeric=0, ok=True."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [0.0, 50.0, 100.0], hz=4.0)
        result = _check_e4_modality(f, "EDA", FAKE_RANGES)
        assert result["non_numeric"]["n_non_numeric"] == 0
        assert result["non_numeric"]["ok"] is True

    def test_e4_empty_cell_not_non_numeric(self, tmp_path):
        """
        A genuinely empty cell (empty string → NaN on read) is not a
        non-numeric violation; it is completeness's concern.
        """
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, ["", 50.0, 80.0], hz=4.0)
        result = _check_e4_modality(f, "EDA", FAKE_RANGES)
        # Empty cell must NOT be counted as a non-numeric conformance violation.
        assert result["non_numeric"]["n_non_numeric"] == 0

    def test_e4_non_numeric_does_not_count_as_range_violation(self, tmp_path):
        """'bad' contributes to non_numeric, not to n_violations in range."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, ["bad", 50.0, 80.0], hz=4.0)
        result = _check_e4_modality(f, "EDA", FAKE_RANGES)
        assert result["range"]["n_violations"] == 0
        assert result["non_numeric"]["n_non_numeric"] == 1

    # ── RespiBAN path ──

    def test_respiban_non_numeric_caught(self, tmp_path):
        """'bad' string in CH1 (ECG) → per_channel n_non_numeric=1, summary total=1."""
        f = tmp_path / "S99_respiban.txt"
        rows = [
            # CH1 (ECG) value is "bad"; all other channels in-bounds
            (0, 0, "bad", 32768, 32768, 32768, 33000, 33000, 33000, 32768),
            neutral_respiban_row(1),
        ]
        make_respiban_txt(f, rows)
        result = check_respiban(f)
        assert result["per_channel_range"]["CH1"]["n_non_numeric"] == 1
        assert result["per_channel_range"]["CH1"]["ok"] is False
        assert result["range_summary"]["total_non_numeric"] == 1
        assert result["range_summary"]["ok"] is False

    def test_respiban_valid_data_no_non_numeric(self, tmp_path):
        """All-numeric RespiBAN rows → total_non_numeric=0."""
        f = tmp_path / "S99_respiban.txt"
        make_respiban_txt(f, [neutral_respiban_row(i) for i in range(3)])
        result = check_respiban(f)
        assert result["range_summary"]["total_non_numeric"] == 0
        assert result["range_summary"]["ok"] is True

    def test_respiban_empty_cell_not_non_numeric(self, tmp_path):
        """
        An empty field (tab-separated gap → NaN on read) must not be counted
        as a non-numeric conformance violation.
        """
        f = tmp_path / "S99_respiban.txt"
        rows = [
            # CH1 is empty — genuinely missing, not malformed
            (0, 0, "", 32768, 32768, 32768, 33000, 33000, 33000, 32768),
            neutral_respiban_row(1),
        ]
        make_respiban_txt(f, rows)
        result = check_respiban(f)
        assert result["per_channel_range"]["CH1"]["n_non_numeric"] == 0

    def test_respiban_non_numeric_separate_from_range_violation(self, tmp_path):
        """'bad' contributes to n_non_numeric, not to n_violations in range."""
        f = tmp_path / "S99_respiban.txt"
        rows = [
            (0, 0, "bad", 32768, 32768, 32768, 33000, 33000, 33000, 32768),
            neutral_respiban_row(1),
        ]
        make_respiban_txt(f, rows)
        result = check_respiban(f)
        assert result["per_channel_range"]["CH1"]["n_violations"] == 0
        assert result["per_channel_range"]["CH1"]["n_non_numeric"] == 1
