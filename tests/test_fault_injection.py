"""
Unit tests for src/experiments/fault_injection.py injector functions.

All inputs are synthetic -- no real WESAD data is read.
Tests confirm that each injector:
  - places exactly the requested number of faults, and
  - places them only at the positions recorded in the returned index list.
"""

import pandas as pd
import numpy as np
import pytest

from src.experiments.fault_injection import (
    inject_e4_nan_scattered,
    inject_e4_nan_contiguous,
    inject_e4_non_numeric,
    inject_e4_value,
    inject_respiban_sequence_gaps,
    inject_respiban_non_numeric,
    inject_respiban_value,
    shift_e4_start_time,
)
from tests.conftest import make_e4_csv, make_respiban_txt, neutral_respiban_row


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_e4_data(csv_path) -> pd.DataFrame:
    """Read an E4 CSV and return data rows (rows 2+) as a DataFrame."""
    raw = pd.read_csv(csv_path, header=None, dtype=str)
    return (
        raw.iloc[2:]
        .apply(lambda col: pd.to_numeric(col, errors="coerce"))
        .reset_index(drop=True)
    )


def _read_e4_raw_data(csv_path) -> list:
    """Return raw string lines for data rows (rows 2+) of an E4 CSV."""
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    return lines[2:]


def _read_respiban_data(txt_path) -> pd.DataFrame:
    data = pd.read_csv(txt_path, sep="\t", skiprows=3, header=None, usecols=range(10))
    data.columns = ["nSeq", "DI", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"]
    return data


# ---------------------------------------------------------------------------
# E4 scattered NaN injector
# ---------------------------------------------------------------------------

class TestInjectE4NanScattered:

    def test_exact_count(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 100)
        rng = np.random.default_rng(42)
        injected = inject_e4_nan_scattered(f, 7, rng, frozenset())
        assert len(injected) == 7

    def test_positions_are_nan_in_file(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 100)
        rng = np.random.default_rng(42)
        injected = inject_e4_nan_scattered(f, 5, rng, frozenset())
        data = _read_e4_data(f)
        for idx in injected:
            assert pd.isna(data.iloc[idx, 0]), f"Expected NaN at index {idx}"

    def test_non_injected_positions_unchanged(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 50)
        rng = np.random.default_rng(99)
        injected = inject_e4_nan_scattered(f, 3, rng, frozenset())
        data = _read_e4_data(f)
        non_injected = [i for i in range(50) if i not in injected]
        for idx in non_injected:
            assert not pd.isna(data.iloc[idx, 0]), (
                f"Unexpected NaN at non-injected index {idx}"
            )

    def test_exclude_indices_respected(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 50)
        exclude = frozenset({0, 1, 2, 3})
        rng = np.random.default_rng(7)
        injected = inject_e4_nan_scattered(f, 10, rng, exclude)
        assert not (set(injected) & exclude), (
            "Injector placed a fault at an excluded index"
        )

    def test_positions_sorted(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 100)
        rng = np.random.default_rng(42)
        injected = inject_e4_nan_scattered(f, 10, rng, frozenset())
        assert injected == sorted(injected)

    def test_total_nan_matches_injected_count(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 80)
        rng = np.random.default_rng(1)
        injected = inject_e4_nan_scattered(f, 6, rng, frozenset())
        data = _read_e4_data(f)
        total_nan = int(data.isnull().sum().sum())
        assert total_nan == len(injected)

    def test_multi_column_nan(self, tmp_path):
        """ACC CSV (3 columns): all columns in an injected row become NaN."""
        from tests.conftest import make_e4_acc_csv
        f = tmp_path / "ACC.csv"
        make_e4_acc_csv(f, [(0, 0, 0)] * 50)
        rng = np.random.default_rng(5)
        injected = inject_e4_nan_scattered(f, 2, rng, frozenset())
        raw = pd.read_csv(f, header=None, dtype=str)
        data = raw.iloc[2:].reset_index(drop=True).apply(
            lambda col: pd.to_numeric(col, errors="coerce")
        )
        for idx in injected:
            assert data.iloc[idx].isnull().all(), (
                f"Expected all columns NaN at ACC row {idx}"
            )


# ---------------------------------------------------------------------------
# E4 contiguous NaN injector
# ---------------------------------------------------------------------------

class TestInjectE4NanContiguous:

    def test_exact_count(self, tmp_path):
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [50.0] * 100)
        rng = np.random.default_rng(42)
        injected = inject_e4_nan_contiguous(f, 8, rng, frozenset())
        assert len(injected) == 8

    def test_positions_are_consecutive(self, tmp_path):
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [50.0] * 100)
        rng = np.random.default_rng(42)
        injected = inject_e4_nan_contiguous(f, 8, rng, frozenset())
        assert injected == list(range(min(injected), max(injected) + 1)), (
            "Contiguous injection positions must be consecutive"
        )

    def test_positions_are_nan_in_file(self, tmp_path):
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [50.0] * 60)
        rng = np.random.default_rng(13)
        injected = inject_e4_nan_contiguous(f, 5, rng, frozenset())
        data = _read_e4_data(f)
        for idx in injected:
            assert pd.isna(data.iloc[idx, 0])

    def test_exclude_indices_respected(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 100)
        exclude = frozenset({0, 1, 2, 3})
        rng = np.random.default_rng(88)
        injected = inject_e4_nan_contiguous(f, 5, rng, exclude)
        assert not (set(injected) & exclude)


# ---------------------------------------------------------------------------
# E4 non-numeric injector
# ---------------------------------------------------------------------------

class TestInjectE4NonNumeric:

    def test_exact_count(self, tmp_path):
        f = tmp_path / "HR.csv"
        make_e4_csv(f, [75.0] * 50, hz=1.0)
        rng = np.random.default_rng(42)
        injected = inject_e4_non_numeric(f, 4, rng, frozenset())
        assert len(injected) == 4

    def test_injected_positions_are_fault_string(self, tmp_path):
        f = tmp_path / "HR.csv"
        make_e4_csv(f, [75.0] * 50, hz=1.0)
        rng = np.random.default_rng(42)
        injected = inject_e4_non_numeric(f, 4, rng, frozenset())
        raw_lines = _read_e4_raw_data(f)
        for idx in injected:
            assert raw_lines[idx].strip() == "FAULT", (
                f"Expected 'FAULT' at row {idx}, got '{raw_lines[idx]}'"
            )

    def test_non_injected_positions_parseable(self, tmp_path):
        f = tmp_path / "HR.csv"
        make_e4_csv(f, [75.0] * 50, hz=1.0)
        rng = np.random.default_rng(42)
        injected = inject_e4_non_numeric(f, 4, rng, frozenset())
        data = _read_e4_data(f)
        for i in range(50):
            if i not in injected:
                assert not pd.isna(data.iloc[i, 0]), (
                    f"Unexpected non-numeric at row {i}"
                )

    def test_exclude_respected(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 50)
        exclude = frozenset({0, 1, 2, 3})
        rng = np.random.default_rng(42)
        injected = inject_e4_non_numeric(f, 5, rng, exclude)
        assert not (set(injected) & exclude)


# ---------------------------------------------------------------------------
# E4 value injector
# ---------------------------------------------------------------------------

class TestInjectE4Value:

    def test_exact_count(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 50)
        rng = np.random.default_rng(7)
        injected = inject_e4_value(f, 50.0, 5, rng, frozenset())
        assert len(injected) == 5

    def test_injected_positions_have_fault_value(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 50)
        rng = np.random.default_rng(7)
        injected = inject_e4_value(f, 50.0, 5, rng, frozenset())
        data = _read_e4_data(f)
        for idx in injected:
            assert data.iloc[idx, 0] == pytest.approx(50.0)

    def test_non_injected_positions_unchanged(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 50)
        rng = np.random.default_rng(7)
        injected = inject_e4_value(f, 50.0, 5, rng, frozenset())
        data = _read_e4_data(f)
        for i in range(50):
            if i not in injected:
                assert data.iloc[i, 0] == pytest.approx(30.0)

    def test_exclude_respected(self, tmp_path):
        f = tmp_path / "TEMP.csv"
        make_e4_csv(f, [30.0] * 50)
        exclude = frozenset({0, 1, 2, 3})
        rng = np.random.default_rng(7)
        injected = inject_e4_value(f, 50.0, 5, rng, exclude)
        assert not (set(injected) & exclude)

    def test_negative_fault_value(self, tmp_path):
        """EDA plausibility fault: negative value."""
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [5.0] * 40)
        rng = np.random.default_rng(3)
        injected = inject_e4_value(f, -1.0, 3, rng, frozenset())
        data = _read_e4_data(f)
        for idx in injected:
            assert data.iloc[idx, 0] == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# E4 start time shift
# ---------------------------------------------------------------------------

class TestShiftE4StartTime:

    def test_start_time_shifted(self, tmp_path):
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [5.0] * 10, start_time=1000.0)
        shift_e4_start_time(f, 60.0)
        lines = f.read_text(encoding="utf-8").splitlines()
        new_time = float(lines[0].split(",")[0])
        assert new_time == pytest.approx(1060.0)

    def test_data_rows_unchanged(self, tmp_path):
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [5.0, 6.0, 7.0], start_time=1000.0)
        shift_e4_start_time(f, 10.0)
        data = _read_e4_data(f)
        assert list(data.iloc[:, 0]) == pytest.approx([5.0, 6.0, 7.0])

    def test_hz_row_unchanged(self, tmp_path):
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [5.0] * 5, hz=4.0, start_time=1000.0)
        shift_e4_start_time(f, 2.0)
        lines = f.read_text(encoding="utf-8").splitlines()
        hz = float(lines[1].split(",")[0])
        assert hz == pytest.approx(4.0)

    def test_negative_offset(self, tmp_path):
        f = tmp_path / "EDA.csv"
        make_e4_csv(f, [5.0] * 5, start_time=1000.0)
        shift_e4_start_time(f, -30.0)
        lines = f.read_text(encoding="utf-8").splitlines()
        assert float(lines[0].split(",")[0]) == pytest.approx(970.0)


# ---------------------------------------------------------------------------
# RespiBAN sequence gap injector
# ---------------------------------------------------------------------------

class TestInjectRespiBanSequenceGaps:

    def test_exact_gap_count(self, tmp_path):
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(i) for i in range(100)]
        make_respiban_txt(f, rows)
        rng = np.random.default_rng(42)
        dropped = inject_respiban_sequence_gaps(f, 5, rng)
        assert len(dropped) == 5

    def test_gaps_present_in_file(self, tmp_path):
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(i) for i in range(100)]
        make_respiban_txt(f, rows)
        rng = np.random.default_rng(42)
        inject_respiban_sequence_gaps(f, 5, rng)
        data = _read_respiban_data(f)
        seq = data["nSeq"].tolist()
        diffs = [seq[i + 1] - seq[i] for i in range(len(seq) - 1)]
        actual_gaps = sum(1 for d in diffs if d > 1)
        assert actual_gaps == 5

    def test_dropped_nseq_values_returned(self, tmp_path):
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(i) for i in range(80)]
        make_respiban_txt(f, rows)
        rng = np.random.default_rng(11)
        dropped = inject_respiban_sequence_gaps(f, 3, rng)
        data = _read_respiban_data(f)
        remaining_nseq = set(data["nSeq"].tolist())
        for ns in dropped:
            assert ns not in remaining_nseq, f"nSeq {ns} should have been dropped"

    def test_row_count_decreases_by_n_gaps(self, tmp_path):
        f = tmp_path / "S99_respiban.txt"
        n = 60
        rows = [neutral_respiban_row(i) for i in range(n)]
        make_respiban_txt(f, rows)
        rng = np.random.default_rng(99)
        inject_respiban_sequence_gaps(f, 4, rng)
        data = _read_respiban_data(f)
        assert len(data) == n - 4


# ---------------------------------------------------------------------------
# RespiBAN non-numeric injector
# ---------------------------------------------------------------------------

class TestInjectRespiBanNonNumeric:

    def test_exact_count(self, tmp_path):
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(i) for i in range(80)]
        make_respiban_txt(f, rows)
        rng = np.random.default_rng(42)
        injected = inject_respiban_non_numeric(f, "CH1", 6, rng)
        assert len(injected) == 6

    def test_injected_positions_non_parseable(self, tmp_path):
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(i) for i in range(80)]
        make_respiban_txt(f, rows)
        rng = np.random.default_rng(42)
        injected = inject_respiban_non_numeric(f, "CH1", 6, rng)
        data = pd.read_csv(f, sep="\t", skiprows=3, header=None, usecols=range(10), dtype=str)
        data.columns = ["nSeq", "DI", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"]
        for idx in injected:
            assert data.iloc[idx]["CH1"].strip() == "FAULT"

    def test_other_columns_unchanged(self, tmp_path):
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(i) for i in range(40)]
        make_respiban_txt(f, rows)
        rng = np.random.default_rng(7)
        injected = inject_respiban_non_numeric(f, "CH1", 3, rng)
        data = pd.read_csv(f, sep="\t", skiprows=3, header=None, usecols=range(10))
        data.columns = ["nSeq", "DI", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"]
        for idx in injected:
            assert data.iloc[idx]["CH2"] == 32768


# ---------------------------------------------------------------------------
# RespiBAN value injector
# ---------------------------------------------------------------------------

class TestInjectRespiBanValue:

    def test_exact_count(self, tmp_path):
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(i) for i in range(60)]
        make_respiban_txt(f, rows)
        rng = np.random.default_rng(5)
        injected = inject_respiban_value(f, "CH1", 70000, 4, rng)
        assert len(injected) == 4

    def test_fault_value_at_injected_positions(self, tmp_path):
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(i) for i in range(60)]
        make_respiban_txt(f, rows)
        rng = np.random.default_rng(5)
        injected = inject_respiban_value(f, "CH1", 70000, 4, rng)
        data = _read_respiban_data(f)
        for idx in injected:
            assert data.iloc[idx]["CH1"] == 70000

    def test_non_injected_positions_unchanged(self, tmp_path):
        f = tmp_path / "S99_respiban.txt"
        rows = [neutral_respiban_row(i) for i in range(40)]
        make_respiban_txt(f, rows)
        rng = np.random.default_rng(5)
        injected = inject_respiban_value(f, "CH1", 70000, 3, rng)
        data = _read_respiban_data(f)
        for i in range(40):
            if i not in injected:
                assert data.iloc[i]["CH1"] == 32768


# ---------------------------------------------------------------------------
# Determinism: same seed produces same injected positions
# ---------------------------------------------------------------------------

class TestDeterminism:

    def test_same_seed_same_positions_e4(self, tmp_path):
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        make_e4_csv(f1, [30.0] * 100)
        make_e4_csv(f2, [30.0] * 100)
        inj1 = inject_e4_nan_scattered(f1, 5, np.random.default_rng(42), frozenset())
        inj2 = inject_e4_nan_scattered(f2, 5, np.random.default_rng(42), frozenset())
        assert inj1 == inj2

    def test_different_seeds_different_positions_e4(self, tmp_path):
        f1 = tmp_path / "a.csv"
        f2 = tmp_path / "b.csv"
        make_e4_csv(f1, [30.0] * 100)
        make_e4_csv(f2, [30.0] * 100)
        inj1 = inject_e4_nan_scattered(f1, 5, np.random.default_rng(42), frozenset())
        inj2 = inject_e4_nan_scattered(f2, 5, np.random.default_rng(99), frozenset())
        assert inj1 != inj2

    def test_same_seed_same_positions_respiban(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        rows = [neutral_respiban_row(i) for i in range(80)]
        make_respiban_txt(f1, rows)
        make_respiban_txt(f2, rows)
        d1 = inject_respiban_sequence_gaps(f1, 4, np.random.default_rng(1))
        d2 = inject_respiban_sequence_gaps(f2, 4, np.random.default_rng(1))
        assert d1 == d2
