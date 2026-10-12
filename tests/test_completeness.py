"""
Internal validation tests for src/checks/completeness.py (Task 6).

All inputs are synthetic — no real WESAD data is read.
Planted faults are explicit so failures have unambiguous meaning.
"""
import json
from pathlib import Path

import pytest

from src.checks.completeness import _check_e4_fixed, _check_e4_ibi, check_chest, _find_nan_runs
from tests.conftest import make_e4_csv, make_respiban_txt, neutral_respiban_row

THRESHOLD = 0.0


# ── E4 fixed-rate completeness ────────────────────────────────────────────────

class TestE4FixedCompleteness:

    def test_clean_data_no_missingness(self, tmp_path):
        """Clean values → missingness_rate=0.0 and passes threshold."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [1.0, 2.0, 3.0, 4.0, 5.0])
        result = _check_e4_fixed(f, THRESHOLD)
        assert result["n_nan"] == 0
        assert result["missingness_rate"] == 0.0
        assert result["passes_threshold"] is True

    def test_injected_nan_raises_missingness(self, tmp_path):
        """Two NaN values in 5 samples → rate = 0.4, fails threshold=0.0."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [1.0, "nan", 3.0, "nan", 5.0])
        result = _check_e4_fixed(f, THRESHOLD)
        assert result["n_nan"] == 2
        assert result["missingness_rate"] == pytest.approx(0.4)
        assert result["passes_threshold"] is False

    def test_missingness_rate_formula(self, tmp_path):
        """Rate = n_nan / (n_samples × n_columns). Single column, 1 NaN in 10."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [1.0] * 9 + ["nan"])
        result = _check_e4_fixed(f, THRESHOLD)
        assert result["n_nan"] == 1
        assert result["missingness_rate"] == pytest.approx(0.1)

    def test_lenient_threshold_passes(self, tmp_path):
        """A 0.5 threshold allows a 0.2 missingness rate."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [1.0, "nan", 3.0, 4.0, 5.0])
        result = _check_e4_fixed(f, 0.5)
        assert result["passes_threshold"] is True

    def test_gap_location_reported(self, tmp_path):
        """A run of NaN rows is reported as a gap with start/end indices."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, ["nan", "nan", 3.0, 4.0, 5.0], hz=4.0)
        result = _check_e4_fixed(f, THRESHOLD)
        assert result["nan_gap_count"] == 1
        gap = result["nan_gap_locations"][0]
        assert gap["start_sample"] == 0
        assert gap["n_samples"] == 2
        assert gap["start_seconds"] == pytest.approx(0.0)

    def test_determinism(self, tmp_path):
        """Identical output on two consecutive calls with the same file."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [1.0, "nan", 3.0])
        r1 = json.dumps(_check_e4_fixed(f, THRESHOLD), sort_keys=True)
        r2 = json.dumps(_check_e4_fixed(f, THRESHOLD), sort_keys=True)
        assert r1 == r2


# ── IBI (event-based) completeness ───────────────────────────────────────────

class TestIBICompleteness:

    def _write_ibi_csv(self, path: Path, events):
        """IBI CSV: row 0 = 'start_timestamp, IBI', rows 1+ = (offset, duration)."""
        lines = ["1000.0, IBI"] + [f"{e[0]},{e[1]}" for e in events]
        path.write_text("\n".join(lines), encoding="utf-8")

    def test_ibi_reports_event_count(self, tmp_path):
        """IBI returns n_events and n_nan; no missingness_rate (undefined)."""
        f = tmp_path / "IBI.csv"
        self._write_ibi_csv(f, [(0.5, 0.82), (1.3, 0.79), (2.1, 0.81)])
        result = _check_e4_ibi(f)
        assert result["n_events"] == 3
        assert result["n_nan"] == 0
        assert "missingness_rate" not in result
        assert result["threshold_applied"] is False

    def test_ibi_nan_cell_counted(self, tmp_path):
        """A non-numeric IBI value becomes NaN and is counted."""
        f = tmp_path / "IBI.csv"
        self._write_ibi_csv(f, [(0.5, 0.82), (1.3, "bad")])
        result = _check_e4_ibi(f)
        assert result["n_nan"] == 1


# ── RespiBAN chest completeness ───────────────────────────────────────────────

class TestChestCompleteness:

    def _clean_rows(self, n: int, start: int = 0):
        return [neutral_respiban_row(start + i) for i in range(n)]

    def test_clean_data_no_gaps(self, tmp_path):
        """Sequential nSeq → 0 dropped samples, 0 sequence gaps."""
        f = tmp_path / "S99_respiban.txt"
        make_respiban_txt(f, self._clean_rows(10))
        result = check_chest(f, THRESHOLD)
        assert result["total_dropped_samples_in_gaps"] == 0
        assert result["n_sequence_gaps"] == 0
        assert result["sequence_gap_missingness_rate"] == 0.0
        assert result["sequence_gap_passes_threshold"] is True

    def test_injected_nseq_gap_flagged(self, tmp_path):
        """nSeq jumps from 2 → 5 (dropping samples 3 and 4): gap detected."""
        f = tmp_path / "S99_respiban.txt"
        rows = [
            neutral_respiban_row(0),
            neutral_respiban_row(1),
            neutral_respiban_row(2),
            neutral_respiban_row(5),   # gap: skips 3 and 4
            neutral_respiban_row(6),
        ]
        make_respiban_txt(f, rows)
        result = check_chest(f, THRESHOLD)
        assert result["total_dropped_samples_in_gaps"] == 2
        assert result["n_sequence_gaps"] == 1
        assert result["sequence_gap_missingness_rate"] > 0.0
        assert result["sequence_gap_passes_threshold"] is False

    def test_gap_location_recorded(self, tmp_path):
        """The gap location dict records the row index and nSeq values."""
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(0), neutral_respiban_row(1),
                neutral_respiban_row(4)]  # gap: skips 2 and 3
        make_respiban_txt(f, rows)
        result = check_chest(f, THRESHOLD)
        gap = result["sequence_gap_locations"][0]
        assert gap["prev_nseq"] == 1
        assert gap["next_nseq"] == 4
        assert gap["dropped_samples"] == 2

    def test_per_channel_nan_flagged(self, tmp_path):
        """An empty tab-separated field in a channel column is read as NaN."""
        rows = [
            (0, 0, "", 32768, 32768, 32768, 33000, 33000, 33000, 32768),
            (1, 0, 32768, 32768, 32768, 32768, 33000, 33000, 33000, 32768),
        ]
        f = tmp_path / "S99_respiban.txt"
        make_respiban_txt(f, rows)
        result = check_chest(f, THRESHOLD)
        # ECG (CH1) should have 1 NaN
        assert result["per_channel"]["ECG"]["n_nan"] == 1
        assert result["per_channel"]["ECG"]["nan_rate"] == pytest.approx(0.5)

    def test_determinism(self, tmp_path):
        """Identical output on two calls with the same file."""
        f = tmp_path / "S99_respiban.txt"
        rows = self._clean_rows(5)
        make_respiban_txt(f, rows)
        r1 = json.dumps(check_chest(f, THRESHOLD), sort_keys=True)
        r2 = json.dumps(check_chest(f, THRESHOLD), sort_keys=True)
        assert r1 == r2


# ── Intentional-removal handling ─────────────────────────────────────────────

class TestIntentionalRemovals:
    """
    Validates the intentional_removal_indices parameter added in the
    'exclude documented intentional removals from missingness' change.
    All inputs are synthetic; no real WESAD data is read.
    """

    def test_documented_nan_excluded_from_rate(self, tmp_path):
        """
        A NaN at a documented removal index is excluded from missingness_rate
        and counted in intentional_removals.

        File: 5 samples, index 0 is NaN (documented removal).
        Without exclusion: n_nan=1, rate=0.2.
        With exclusion: n_unintentional_nan=0, rate=0.0, passes threshold=0.0.
        """
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, ["nan", 2.0, 3.0, 4.0, 5.0])
        result = _check_e4_fixed(f, THRESHOLD, intentional_removal_indices=[0])

        assert result["n_nan"] == 1                          # total NaN (unchanged)
        assert result["n_intentional_nan"] == 1              # excluded from rate
        assert result["n_unintentional_nan"] == 0            # contributes to rate
        assert result["missingness_rate"] == 0.0             # rate based on unintentional only
        assert result["passes_threshold"] is True
        ri = result["intentional_removals"]
        assert ri["count"] == 1
        assert ri["indices"] == [0]

    def test_undocumented_nan_still_counts_as_missing(self, tmp_path):
        """
        A NaN at an undocumented index in the same file is still counted as
        missing, so missingness_rate is non-zero and the file fails the threshold.

        File: 5 samples.  Index 0 is a documented removal (NaN); index 2 is
        an undocumented NaN (unexpected missingness).
        Expected: n_intentional_nan=1, n_unintentional_nan=1, rate=0.2.
        """
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, ["nan", 2.0, "nan", 4.0, 5.0])
        result = _check_e4_fixed(f, THRESHOLD, intentional_removal_indices=[0])

        assert result["n_nan"] == 2
        assert result["n_intentional_nan"] == 1
        assert result["n_unintentional_nan"] == 1
        assert result["missingness_rate"] == pytest.approx(0.2)
        assert result["passes_threshold"] is False

    def test_documented_index_not_nan_not_subtracted(self, tmp_path):
        """
        A documented removal index whose value is NOT NaN does not reduce
        n_intentional_nan — no negative or understated count.

        File: 5 clean samples (no NaN).  Index 0 is listed as a removal index
        but the value is a normal float.  The file has no NaN, so both
        n_intentional_nan and n_unintentional_nan should be 0.
        """
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [1.0, 2.0, 3.0, 4.0, 5.0])
        result = _check_e4_fixed(f, THRESHOLD, intentional_removal_indices=[0])

        assert result["n_nan"] == 0
        assert result.get("n_intentional_nan", 0) == 0
        assert result.get("n_unintentional_nan", 0) == 0
        assert result["missingness_rate"] == 0.0
        assert result["passes_threshold"] is True
        # intentional_removals block should not appear when count is 0
        assert "intentional_removals" not in result

    def test_no_removal_list_reproduces_original_behaviour(self, tmp_path):
        """
        Calling with no removal list (default None) produces the same result
        as the original function: n_nan==1, rate==0.2, passes_threshold=False.
        The new fields n_intentional_nan / n_unintentional_nan must not appear.
        """
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [1.0, "nan", 3.0, 4.0, 5.0])
        result = _check_e4_fixed(f, THRESHOLD)

        assert result["n_nan"] == 1
        assert result["missingness_rate"] == pytest.approx(0.2)
        assert result["passes_threshold"] is False
        assert "n_intentional_nan" not in result
        assert "n_unintentional_nan" not in result
        assert "intentional_removals" not in result
