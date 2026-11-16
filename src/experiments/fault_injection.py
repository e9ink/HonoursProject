"""
Fault injection harness for WESAD CCP check validation.

Pre-registered design: config/experiments.yaml
Results (when run): reports/experiments/fault_injection_results.json

This module MUST NOT be executed as part of stage A (pre-registration).
Run it only after the design commit has been reviewed.

Constraint: no check module is modified. The harness calls existing check
functions on copies of participant data in experiments/scratch/.

Injection state: each participant's scratch directory uses Silver TEMP
(warm-up indices 0-3 already replaced with NaN) plus Bronze for all other
signals, matching the state that src/checks/post_cleaning.py operates on.
Documented intentional removals (from reports/wesad_cleaning.json) are
excluded from the completeness missingness rate.

Timeliness note: src/alignment._align_participant() hardcodes
BRONZE = Path("bronze/WESAD") and cannot be redirected to a scratch
directory. The harness uses _e4_modality_info, _respiban_info, and
_measure_overlap_offsets from src/alignment.py directly -- all three
accept path arguments. No check code is modified.
"""

import json
import os
import shutil
import stat
import tempfile
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
# Scratch directories live in the system temp folder, not the project tree,
# to avoid OneDrive sync locking and to keep participant data copies off
# cloud storage. Both are defined here so callers never hardcode paths.
_SCRATCH_BASE = Path(tempfile.gettempdir()) / "wesad_fault_injection"
SCRATCH_DIR = _SCRATCH_BASE / "clean"
SCRATCH_DIRTY = _SCRATCH_BASE / "dirty"
BRONZE_WESAD = ROOT / "bronze" / "WESAD"
SILVER_WESAD = ROOT / "silver" / "WESAD"
CLEANING_REPORT = ROOT / "reports" / "wesad_cleaning.json"
RESULTS_DIR = ROOT / "reports" / "experiments"
RESULTS_PATH = RESULTS_DIR / "fault_injection_results.json"
EXPERIMENTS_CONFIG = ROOT / "config" / "experiments.yaml"

# RespiBAN column order used throughout (from check modules)
_RESPIBAN_COLS = ["nSeq", "DI", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"]

# E4 TEMP warm-up positions (indices 0-3) are already NaN in Silver TEMP.
# Injecting faults at these positions would overwrite known-clean NaN values.
_TEMP_EXCLUDE = frozenset({0, 1, 2, 3})


# ---------------------------------------------------------------------------
# Seed derivation
# ---------------------------------------------------------------------------

_PARTICIPANTS_ORDER = ["S2", "S8", "S15"]
_FAULT_TYPES_ORDER = [
    "completeness_scattered_nan",
    "completeness_contiguous_dropout",
    "conformance_non_numeric",
    "conformance_sampling_rate_fault",
    "plausibility_physiological_impossible",
    "timeliness_start_shift",
]
_BASE_SEED = 12345


def _seed(pid: str, fault_type: str, severity_idx: int) -> int:
    """Derive a deterministic seed from participant, fault type, and severity index."""
    pid_idx = _PARTICIPANTS_ORDER.index(pid)
    ft_idx = _FAULT_TYPES_ORDER.index(fault_type)
    return _BASE_SEED + pid_idx * 1000 + ft_idx * 100 + severity_idx * 10


def _load_intentional_removals(pid: str) -> dict:
    """Return intentional NaN removal indices from the cleaning report as {mod: [indices]}."""
    with open(CLEANING_REPORT, encoding="utf-8") as fh:
        cleaning = json.load(fh)
    indices = cleaning["participants"][pid]["cleaning"]["indices_replaced"]
    return {"TEMP": indices}


# ---------------------------------------------------------------------------
# File copying and deletion
# ---------------------------------------------------------------------------

def _rmtree(path: Path) -> None:
    """Remove a directory tree, force-clearing read-only flags on Windows."""
    def _on_error(func, fpath, exc_info):
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except Exception:
            pass
    shutil.rmtree(path, onerror=_on_error)


def _copy_participant_to_scratch(pid: str) -> Path:
    """
    Copy one participant's files to a fresh scratch directory.
    Bronze files are used for all signals except E4 TEMP, which is taken from
    Silver (warm-up indices 0-3 already NaN), matching the state that
    src/checks/post_cleaning.py operates on.
    Returns the scratch participant directory path.
    """
    src = BRONZE_WESAD / pid
    dst = SCRATCH_DIR / pid
    if dst.exists():
        _rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("*.pkl"))
    silver_temp = SILVER_WESAD / pid / f"{pid}_E4_Data" / "TEMP.csv"
    scratch_temp = dst / f"{pid}_E4_Data" / "TEMP.csv"
    shutil.copy2(silver_temp, scratch_temp)
    return dst


def _copy_to_dirty_scratch(pid: str) -> Path:
    """
    Copy one participant's files to a fresh injection (dirty) scratch directory.
    Uses SCRATCH_DIRTY / pid so it never collides with the clean reference copy
    at SCRATCH_DIR / pid.  Both are named by pid so participant_dir.name is
    correct for check functions that derive pid from the directory name.
    Returns the dirty scratch path.
    """
    src = BRONZE_WESAD / pid
    dst = SCRATCH_DIRTY / pid
    if dst.exists():
        _rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("*.pkl"))
    silver_temp = SILVER_WESAD / pid / f"{pid}_E4_Data" / "TEMP.csv"
    scratch_temp = dst / f"{pid}_E4_Data" / "TEMP.csv"
    shutil.copy2(silver_temp, scratch_temp)
    return dst


def _count_rb_rows(txt_path: Path) -> int:
    """Count RespiBAN data rows without parsing tab-delimited content."""
    count = 0
    with open(txt_path, "rb") as fh:
        fh.readline(); fh.readline(); fh.readline()
        for line in fh:
            if line.strip():
                count += 1
    return count


def _copy_e4_to_dirty_scratch(pid: str) -> Path:
    """
    Copy only the E4_Data directory to dirty scratch.
    Use for E4-only faults to avoid copying the 250 MB RespiBAN file.
    """
    dst = SCRATCH_DIRTY / pid
    if dst.exists():
        _rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        BRONZE_WESAD / pid / f"{pid}_E4_Data",
        dst / f"{pid}_E4_Data",
        ignore=shutil.ignore_patterns("*.pkl"),
    )
    silver_temp = SILVER_WESAD / pid / f"{pid}_E4_Data" / "TEMP.csv"
    shutil.copy2(silver_temp, dst / f"{pid}_E4_Data" / "TEMP.csv")
    return dst


def _copy_rb_to_dirty_scratch(pid: str) -> Path:
    """
    Copy only the RespiBAN .txt file to dirty scratch.
    Use for RespiBAN-only faults to avoid copying E4 data unnecessarily.
    """
    dst = SCRATCH_DIRTY / pid
    if dst.exists():
        _rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        BRONZE_WESAD / pid / f"{pid}_respiban.txt",
        dst / f"{pid}_respiban.txt",
    )
    return dst


# ---------------------------------------------------------------------------
# E4 injection helpers
# ---------------------------------------------------------------------------

def _n_faults(n_samples: int, severity: float) -> int:
    return max(1, int(n_samples * severity))


def _e4_sample_count(csv_path: Path) -> int:
    """Number of data rows (rows 2+) in an E4 fixed-rate CSV."""
    lines = [l for l in csv_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return max(0, len(lines) - 2)


def _read_e4_lines(csv_path: Path):
    """Return (header_lines, data_lines) from an E4 CSV."""
    all_lines = csv_path.read_text(encoding="utf-8").splitlines()
    return all_lines[:2], all_lines[2:]


def _write_e4_lines(csv_path: Path, header: list, data: list) -> None:
    csv_path.write_text("\n".join(header + data), encoding="utf-8")


def _n_cols(line: str) -> int:
    return len(line.split(","))


def inject_e4_nan_scattered(
    csv_path: Path,
    n_faults: int,
    rng: np.random.Generator,
    exclude_indices: frozenset = frozenset(),
) -> list:
    """
    Inject n_faults scattered NaN values into an E4 fixed-rate CSV.
    Positions are chosen uniformly at random, excluding exclude_indices.
    Returns sorted list of injected row indices (0-indexed into data rows).
    """
    header, data = _read_e4_lines(csv_path)
    n_data = len(data)
    available = np.array([i for i in range(n_data) if i not in exclude_indices])
    if len(available) < n_faults:
        raise ValueError(
            f"Cannot inject {n_faults} faults into {n_data}-row file "
            f"with {len(exclude_indices)} excluded positions."
        )
    chosen = sorted(rng.choice(available, size=n_faults, replace=False).tolist())
    for idx in chosen:
        nc = _n_cols(data[idx])
        data[idx] = ",".join(["nan"] * nc)
    _write_e4_lines(csv_path, header, data)
    return chosen


def inject_e4_nan_contiguous(
    csv_path: Path,
    n_faults: int,
    rng: np.random.Generator,
    exclude_indices: frozenset = frozenset(),
) -> list:
    """
    Inject a single contiguous block of n_faults NaN values into an E4 CSV.
    Block start is chosen uniformly at random from valid positions.
    Returns sorted list of injected row indices.
    """
    header, data = _read_e4_lines(csv_path)
    n_data = len(data)
    if n_faults > n_data:
        raise ValueError(f"Cannot inject {n_faults} contiguous faults into {n_data}-row file.")

    max_start = n_data - n_faults
    candidates = list(range(max_start + 1))
    rng.shuffle(candidates)

    start = None
    for c in candidates:
        block = set(range(c, c + n_faults))
        if not (block & exclude_indices):
            start = c
            break

    if start is None:
        raise ValueError(
            f"Cannot place {n_faults} contiguous faults avoiding exclusions."
        )

    chosen = list(range(start, start + n_faults))
    for idx in chosen:
        nc = _n_cols(data[idx])
        data[idx] = ",".join(["nan"] * nc)
    _write_e4_lines(csv_path, header, data)
    return chosen


def inject_e4_non_numeric(
    csv_path: Path,
    n_faults: int,
    rng: np.random.Generator,
    exclude_indices: frozenset = frozenset(),
) -> list:
    """
    Inject n_faults non-parseable "FAULT" strings into an E4 CSV data rows.
    Returns sorted list of injected row indices.
    """
    header, data = _read_e4_lines(csv_path)
    n_data = len(data)
    available = np.array([i for i in range(n_data) if i not in exclude_indices])
    if len(available) < n_faults:
        raise ValueError(
            f"Cannot inject {n_faults} non-numeric faults into {n_data}-row file."
        )
    chosen = sorted(rng.choice(available, size=n_faults, replace=False).tolist())
    for idx in chosen:
        nc = _n_cols(data[idx])
        data[idx] = ",".join(["FAULT"] * nc)
    _write_e4_lines(csv_path, header, data)
    return chosen


def inject_e4_value(
    csv_path: Path,
    fault_value: float,
    n_faults: int,
    rng: np.random.Generator,
    exclude_indices: frozenset = frozenset(),
) -> list:
    """
    Inject fault_value into n_faults rows of an E4 CSV.
    Returns sorted list of injected row indices.
    """
    header, data = _read_e4_lines(csv_path)
    n_data = len(data)
    available = np.array([i for i in range(n_data) if i not in exclude_indices])
    if len(available) < n_faults:
        raise ValueError(
            f"Cannot inject {n_faults} value faults into {n_data}-row file."
        )
    chosen = sorted(rng.choice(available, size=n_faults, replace=False).tolist())
    for idx in chosen:
        nc = _n_cols(data[idx])
        data[idx] = ",".join([str(fault_value)] * nc)
    _write_e4_lines(csv_path, header, data)
    return chosen


def shift_e4_start_time(csv_path: Path, offset_s: float) -> None:
    """
    Add offset_s to the Unix start timestamp in row 0 of an E4 CSV.
    Row 0 may be single-valued ("1000.0") or padded ("1000.0,,") for ACC.
    """
    all_lines = csv_path.read_text(encoding="utf-8").splitlines()
    parts = all_lines[0].split(",")
    parts[0] = repr(float(parts[0]) + offset_s)
    all_lines[0] = ",".join(parts)
    csv_path.write_text("\n".join(all_lines), encoding="utf-8")


def inject_e4_sampling_rate(csv_path: Path, new_hz: float) -> float:
    """
    Replace the declared sampling rate in row 1 of an E4 CSV header.
    Row 1 contains a single number (e.g. "4.0") or padded form ("4.0,,").
    Returns the original declared rate.
    """
    all_lines = csv_path.read_text(encoding="utf-8").splitlines()
    parts = all_lines[1].split(",")
    original_hz = float(parts[0])
    parts[0] = str(float(new_hz))
    all_lines[1] = ",".join(parts)
    csv_path.write_text("\n".join(all_lines), encoding="utf-8")
    return original_hz


# ---------------------------------------------------------------------------
# RespiBAN injection helpers
# ---------------------------------------------------------------------------

def _read_respiban(txt_path: Path):
    """
    Return (header_lines, data_rows).
    header_lines: list of 3 strings (each ending with newline).
    data_rows: list of lists of 10 strings (trailing tabs stripped).
    """
    with open(txt_path, "r", encoding="utf-8") as fh:
        header = [fh.readline(), fh.readline(), fh.readline()]
        rows = []
        for line in fh:
            stripped = line.rstrip("\n").rstrip("\r")
            if not stripped.strip():
                continue
            parts = [p for p in stripped.split("\t") if p != ""][:10]
            while len(parts) < 10:
                parts.append("0")
            rows.append(parts)
    return header, rows


def _write_respiban(txt_path: Path, header: list, rows: list) -> None:
    with open(txt_path, "w", encoding="utf-8") as fh:
        fh.writelines(header)
        for row in rows:
            fh.write("\t".join(row[:10]) + "\t\n")


def inject_respiban_sequence_gaps(
    txt_path: Path,
    n_gaps: int,
    rng: np.random.Generator,
) -> list:
    """
    Drop n_gaps rows from a RespiBAN file to create nSeq sequence gaps.
    Each dropped row creates one gap of size 1 in the nSeq counter.
    Rows at index 0 and n-1 are excluded to avoid edge effects.
    Returns sorted list of dropped nSeq integer values.
    """
    header, rows = _read_respiban(txt_path)
    n_rows = len(rows)
    if n_gaps >= n_rows - 2:
        raise ValueError(
            f"Cannot drop {n_gaps} rows from {n_rows}-row RespiBAN file."
        )
    available = np.array(range(1, n_rows - 1))
    chosen_idx = sorted(rng.choice(available, size=n_gaps, replace=False).tolist())
    dropped_nseq = [int(rows[i][0]) for i in chosen_idx]
    kept = [row for i, row in enumerate(rows) if i not in set(chosen_idx)]
    _write_respiban(txt_path, header, kept)
    return sorted(dropped_nseq)


def inject_respiban_non_numeric(
    txt_path: Path,
    channel: str,
    n_faults: int,
    rng: np.random.Generator,
) -> list:
    """
    Inject "FAULT" into the specified channel column at n_faults randomly
    chosen rows. channel must be one of the RESPIBAN_COLS names (e.g. "CH1").
    Returns sorted list of injected row indices.
    """
    header, rows = _read_respiban(txt_path)
    col_idx = _RESPIBAN_COLS.index(channel)
    available = np.array(range(len(rows)))
    chosen = sorted(rng.choice(available, size=n_faults, replace=False).tolist())
    for idx in chosen:
        rows[idx][col_idx] = "FAULT"
    _write_respiban(txt_path, header, rows)
    return chosen


def inject_respiban_value(
    txt_path: Path,
    channel: str,
    fault_value: int,
    n_faults: int,
    rng: np.random.Generator,
) -> list:
    """
    Inject fault_value (an integer ADC value) into the specified channel
    column at n_faults randomly chosen rows.
    Returns sorted list of injected row indices.
    """
    header, rows = _read_respiban(txt_path)
    col_idx = _RESPIBAN_COLS.index(channel)
    available = np.array(range(len(rows)))
    chosen = sorted(rng.choice(available, size=n_faults, replace=False).tolist())
    for idx in chosen:
        rows[idx][col_idx] = str(fault_value)
    _write_respiban(txt_path, header, rows)
    return chosen


# ---------------------------------------------------------------------------
# Fast binary RespiBAN injection -- avoids full parse of 4.4 M row Python lists
# ---------------------------------------------------------------------------

def _inject_rb_gaps_bytes(
    txt_path: Path,
    n_gaps: int,
    rng: np.random.Generator,
) -> list:
    """
    Drop n_gaps rows from a RespiBAN file by streaming binary lines.
    Semantics identical to inject_respiban_sequence_gaps.
    Returns sorted list of dropped nSeq integer values.
    """
    with open(txt_path, "rb") as fh:
        header = [fh.readline(), fh.readline(), fh.readline()]
        lines = [ln for ln in fh if ln.strip()]

    n_rows = len(lines)
    if n_gaps >= n_rows - 2:
        raise ValueError(f"Cannot drop {n_gaps} rows from {n_rows}-row RespiBAN file.")

    available = np.array(range(1, n_rows - 1))
    chosen_idx = sorted(rng.choice(available, size=n_gaps, replace=False).tolist())
    chosen_set = set(chosen_idx)
    dropped_nseq = [int(lines[i].split(b"\t", 1)[0]) for i in chosen_idx]

    with open(txt_path, "wb") as fh:
        fh.writelines(header)
        for i, ln in enumerate(lines):
            if i not in chosen_set:
                fh.write(ln)

    return sorted(dropped_nseq)


def _inject_rb_contiguous_bytes(
    txt_path: Path,
    n_drop: int,
    rng: np.random.Generator,
) -> list:
    """
    Drop a contiguous block of n_drop rows from a RespiBAN file.
    Semantics identical to the in-line contiguous logic in _run_completeness_experiments.
    Returns sorted list of dropped nSeq integer values.
    """
    with open(txt_path, "rb") as fh:
        header = [fh.readline(), fh.readline(), fh.readline()]
        lines = [ln for ln in fh if ln.strip()]

    n_rows = len(lines)
    max_start = n_rows - n_drop - 1
    start_row = int(rng.integers(1, max(2, max_start)))
    injected_rb = list(range(start_row, start_row + n_drop))
    injected_set = set(injected_rb)
    dropped_nseq = [int(lines[i].split(b"\t", 1)[0]) for i in injected_rb]

    with open(txt_path, "wb") as fh:
        fh.writelines(header)
        for i, ln in enumerate(lines):
            if i not in injected_set:
                fh.write(ln)

    return sorted(dropped_nseq)


def _inject_rb_non_numeric_bytes(
    txt_path: Path,
    channel: str,
    n_faults: int,
    rng: np.random.Generator,
) -> list:
    """
    Inject b'FAULT' into the specified channel column at n_faults random rows.
    Semantics identical to inject_respiban_non_numeric.
    Returns sorted list of injected row indices.
    """
    col_idx = _RESPIBAN_COLS.index(channel)
    with open(txt_path, "rb") as fh:
        header = [fh.readline(), fh.readline(), fh.readline()]
        lines = [ln for ln in fh if ln.strip()]

    n_rows = len(lines)
    available = np.array(range(n_rows))
    chosen = sorted(rng.choice(available, size=n_faults, replace=False).tolist())

    for idx in chosen:
        parts = lines[idx].rstrip(b"\n").rstrip(b"\r").split(b"\t")
        while len(parts) <= col_idx:
            parts.append(b"0")
        parts[col_idx] = b"FAULT"
        lines[idx] = b"\t".join(parts[:10]) + b"\t\n"

    with open(txt_path, "wb") as fh:
        fh.writelines(header)
        fh.writelines(lines)

    return chosen


def _inject_rb_value_bytes(
    txt_path: Path,
    channel: str,
    fault_value: int,
    n_faults: int,
    rng: np.random.Generator,
) -> list:
    """
    Inject fault_value into the specified channel column at n_faults random rows.
    Semantics identical to inject_respiban_value.
    Returns sorted list of injected row indices.
    """
    col_idx = _RESPIBAN_COLS.index(channel)
    fault_bytes = str(fault_value).encode()
    with open(txt_path, "rb") as fh:
        header = [fh.readline(), fh.readline(), fh.readline()]
        lines = [ln for ln in fh if ln.strip()]

    n_rows = len(lines)
    available = np.array(range(n_rows))
    chosen = sorted(rng.choice(available, size=n_faults, replace=False).tolist())

    for idx in chosen:
        parts = lines[idx].rstrip(b"\n").rstrip(b"\r").split(b"\t")
        while len(parts) <= col_idx:
            parts.append(b"0")
        parts[col_idx] = fault_bytes
        lines[idx] = b"\t".join(parts[:10]) + b"\t\n"

    with open(txt_path, "wb") as fh:
        fh.writelines(header)
        fh.writelines(lines)

    return chosen


# ---------------------------------------------------------------------------
# Check runners on scratch paths
# ---------------------------------------------------------------------------

def _run_completeness(
    scratch_pid_dir: Path,
    pid: str,
    threshold: float,
    intentional_by_mod: "dict | None" = None,
) -> dict:
    from src.checks.completeness import check_e4, check_chest
    e4 = check_e4(scratch_pid_dir, threshold, intentional_removals_by_mod=intentional_by_mod)
    rb_path = scratch_pid_dir / f"{pid}_respiban.txt"
    chest = check_chest(rb_path, threshold) if rb_path.exists() else {}
    return {"e4": e4, "chest": chest}


def _run_conformance(scratch_pid_dir: Path, ranges: dict) -> dict:
    from src.checks.conformance import check_participant
    return check_participant(scratch_pid_dir, ranges)


def _run_plausibility(scratch_pid_dir: Path, wesad_cfg: dict, threshold: float) -> dict:
    """Run plausibility checks on a scratch participant directory for one fault scenario."""
    from src.checks.plausibility import check_e4, check_respiban
    pid = scratch_pid_dir.name
    e4 = check_e4(scratch_pid_dir, wesad_cfg, threshold)
    rb_path = scratch_pid_dir / f"{pid}_respiban.txt"
    chest = check_respiban(rb_path, wesad_cfg, threshold) if rb_path.exists() else {}
    return {"e4": e4, "chest": chest}


def _run_alignment(scratch_pid_dir: Path, pid: str, threshold_s: float) -> dict:
    """
    Measure alignment on scratch files using src/alignment sub-functions.
    _align_participant() cannot be used because it hardcodes BRONZE; the
    sub-functions _e4_modality_info, _respiban_info, _measure_overlap_offsets
    all accept path arguments and are called unchanged here.
    """
    from src.alignment import (
        _e4_modality_info,
        _respiban_info,
        _measure_overlap_offsets,
        _E4_REF_PRIORITY,
        E4_FIXED,
    )

    e4_dir = scratch_pid_dir / f"{pid}_E4_Data"
    e4_mods = {}
    for name in E4_FIXED:
        p = e4_dir / f"{name}.csv"
        if p.exists():
            e4_mods[name] = _e4_modality_info(p)

    non_hr = {k: v for k, v in e4_mods.items() if k != "HR"}
    e4_start = min(v["start_unix"] for v in non_hr.values())
    e4_end = max(v["end_unix"] for v in e4_mods.values())

    rb = _respiban_info(scratch_pid_dir, pid)
    overlap_start = max(e4_start, rb["start_unix"])
    overlap_end = min(e4_end, rb["end_unix"])
    overlap_dur = round(max(0.0, overlap_end - overlap_start), 3)

    ref_mod = next((m for m in _E4_REF_PRIORITY if m in non_hr), list(non_hr)[0])
    ref_hz = e4_mods[ref_mod]["hz"]

    within = _measure_overlap_offsets(
        e4_earliest_start=e4_start,
        e4_ref_mod=ref_mod,
        e4_ref_hz=ref_hz,
        rb_start=rb["start_unix"],
        rb_hz=rb["hz"],
        overlap_start=overlap_start,
        overlap_duration=overlap_dur,
    )

    return {
        "offset_before_s": round(rb["start_unix"] - e4_start, 3),
        "offset_after_s": within["max_abs_offset_s"],
        "within_overlap_offsets": within,
        "passes_threshold": within["max_abs_offset_s"] <= threshold_s,
    }


def _run_completeness_e4(
    scratch_pid_dir: Path,
    pid: str,
    threshold: float,
    intentional_by_mod: "dict | None" = None,
) -> dict:
    """Run completeness check on E4 data only."""
    from src.checks.completeness import check_e4
    e4 = check_e4(scratch_pid_dir, threshold, intentional_removals_by_mod=intentional_by_mod)
    return {"e4": e4, "chest": {}}


def _run_completeness_chest(
    scratch_pid_dir: Path,
    pid: str,
    threshold: float,
) -> dict:
    """Run completeness check on RespiBAN chest data only."""
    from src.checks.completeness import check_chest
    rb_path = scratch_pid_dir / f"{pid}_respiban.txt"
    chest = check_chest(rb_path, threshold) if rb_path.exists() else {}
    return {"e4": {}, "chest": chest}


def _run_conformance_e4(scratch_pid_dir: Path, ranges: dict) -> dict:
    """Run conformance check on E4 data only."""
    from src.checks.conformance import check_e4
    e4 = check_e4(scratch_pid_dir, ranges)
    return {"e4": e4, "chest": {}}


def _run_conformance_rb(scratch_pid_dir: Path, pid: str) -> dict:
    """Run conformance check on RespiBAN chest data only."""
    from src.checks.conformance import check_respiban
    rb_path = scratch_pid_dir / f"{pid}_respiban.txt"
    chest = check_respiban(rb_path) if rb_path.exists() else {}
    return {"e4": {}, "chest": chest}


def _run_plausibility_e4(
    scratch_pid_dir: Path,
    wesad_cfg: dict,
    threshold: float,
) -> dict:
    """Run plausibility check on E4 data only."""
    from src.checks.plausibility import check_e4
    e4 = check_e4(scratch_pid_dir, wesad_cfg, threshold)
    return {"e4": e4, "chest": {}}


def _run_plausibility_chest(
    scratch_pid_dir: Path,
    pid: str,
    wesad_cfg: dict,
    threshold: float,
) -> dict:
    """Run plausibility check on RespiBAN chest data only."""
    from src.checks.plausibility import check_respiban
    rb_path = scratch_pid_dir / f"{pid}_respiban.txt"
    chest = check_respiban(rb_path, wesad_cfg, threshold) if rb_path.exists() else {}
    return {"e4": {}, "chest": chest}


# ---------------------------------------------------------------------------
# Detection metrics helpers
# ---------------------------------------------------------------------------

def _completeness_nan_count(result: dict, modality: str) -> int:
    return result["e4"].get(modality, {}).get("n_nan", 0)


def _completeness_passes(result: dict, modality: str) -> bool:
    return result["e4"].get(modality, {}).get("passes_threshold", True)


def _completeness_chest_dropped(result: dict) -> int:
    return result.get("chest", {}).get("total_dropped_samples_in_gaps", 0)


def _completeness_chest_passes(result: dict) -> bool:
    return result.get("chest", {}).get("sequence_gap_passes_threshold", True)


def _conformance_non_numeric(result: dict, modality: str) -> int:
    return result["e4"].get(modality, {}).get("non_numeric", {}).get("n_non_numeric", 0)


def _conformance_range_violations(result: dict, modality: str) -> int:
    return result["e4"].get(modality, {}).get("range", {}).get("n_violations", 0)


def _conformance_chest_non_numeric(result: dict, ch: str) -> int:
    return result.get("chest", {}).get("per_channel_range", {}).get(ch, {}).get("n_non_numeric", 0)


def _conformance_chest_range_violations(result: dict, ch: str) -> int:
    return result.get("chest", {}).get("per_channel_range", {}).get(ch, {}).get("n_violations", 0)


def _plausibility_violations(result: dict, modality: str) -> int:
    findings = result["e4"].get(modality, {})
    if findings.get("excluded"):
        return 0
    return findings.get("n_violations", 0)


def _plausibility_passes(result: dict, modality: str) -> bool:
    findings = result["e4"].get(modality, {})
    if findings.get("excluded"):
        return True
    return findings.get("passes_threshold", True)


# ---------------------------------------------------------------------------
# Main experiment runners
# ---------------------------------------------------------------------------

def _run_completeness_experiments(
    records: list,
    participants: list,
    severities: list,
    thresholds_cfg: dict,
) -> None:
    threshold = float(thresholds_cfg["completeness"]["max_missingness_rate"])
    ft_nan = "completeness_scattered_nan"
    ft_drop = "completeness_contiguous_dropout"

    e4_targets = {
        "TEMP": (_TEMP_EXCLUDE, "E4_TEMP"),
        "EDA":  (frozenset(),   "E4_EDA"),
        "HR":   (frozenset(),   "E4_HR"),
    }

    for pid in participants:
        print(f"  completeness: {pid}")
        scratch = _copy_participant_to_scratch(pid)
        e4_dir = scratch / f"{pid}_E4_Data"
        rb_path = scratch / f"{pid}_respiban.txt"
        intentional = _load_intentional_removals(pid)

        # Count RespiBAN rows once per participant (fast binary scan).
        n_rb = _count_rb_rows(rb_path)

        # Compute clean references once per participant -- reused across all
        # (ft, sev) combinations.
        clean_e4 = _run_completeness_e4(scratch, pid, threshold, intentional)
        clean_chest = _run_completeness_chest(scratch, pid, threshold)

        for ft, is_contiguous in [(ft_nan, False), (ft_drop, True)]:
            for sev_idx, sev in enumerate(severities):
                nf_rb = _n_faults(n_rb, sev)

                # ---- E4 signals ----
                for mod, (excl, sig_label) in e4_targets.items():
                    csv = e4_dir / f"{mod}.csv"
                    n = _e4_sample_count(csv)
                    nf = _n_faults(n, sev)

                    clean_nan = _completeness_nan_count(clean_e4, mod)
                    clean_passes = _completeness_passes(clean_e4, mod)

                    scratch2 = _copy_e4_to_dirty_scratch(pid)
                    csv2 = scratch2 / f"{pid}_E4_Data" / f"{mod}.csv"
                    rng2 = np.random.default_rng(_seed(pid, ft, sev_idx))

                    if is_contiguous:
                        injected = inject_e4_nan_contiguous(csv2, nf, rng2, excl)
                    else:
                        injected = inject_e4_nan_scattered(csv2, nf, rng2, excl)

                    dirty_result = _run_completeness_e4(scratch2, pid, threshold, intentional)
                    dirty_nan = _completeness_nan_count(dirty_result, mod)
                    dirty_passes = _completeness_passes(dirty_result, mod)
                    _rmtree(scratch2)
                    del dirty_result

                    new_nan = dirty_nan - clean_nan
                    records.append({
                        "dimension": "completeness",
                        "fault_type": ft,
                        "signal": sig_label,
                        "participant": pid,
                        "severity": sev,
                        "n_injected": len(injected),
                        "n_detected": new_nan,
                        "detection_rate": new_nan / len(injected) if injected else None,
                        "false_positive_count": max(0, new_nan - len(injected)),
                        "verdict_before_passes": clean_passes,
                        "verdict_after_passes": dirty_passes,
                        "verdict_flip": clean_passes and not dirty_passes,
                    })

                # ---- RespiBAN ECG (sequence gaps) ----
                clean_drops = _completeness_chest_dropped(clean_chest)
                clean_passes_rb = _completeness_chest_passes(clean_chest)

                scratch3 = _copy_rb_to_dirty_scratch(pid)
                rb_path3 = scratch3 / f"{pid}_respiban.txt"
                rng_rb3 = np.random.default_rng(_seed(pid, ft, sev_idx) + 5)

                if is_contiguous:
                    dropped_nseq = _inject_rb_contiguous_bytes(rb_path3, nf_rb, rng_rb3)
                else:
                    dropped_nseq = _inject_rb_gaps_bytes(rb_path3, nf_rb, rng_rb3)

                dirty_result3 = _run_completeness_chest(scratch3, pid, threshold)
                dirty_drops = _completeness_chest_dropped(dirty_result3)
                dirty_passes_rb = _completeness_chest_passes(dirty_result3)
                _rmtree(scratch3)
                del dirty_result3

                new_drops = dirty_drops - clean_drops
                records.append({
                    "dimension": "completeness",
                    "fault_type": ft,
                    "signal": "RespiBAN_ECG",
                    "participant": pid,
                    "severity": sev,
                    "n_injected": len(dropped_nseq),
                    "n_detected": new_drops,
                    "detection_rate": new_drops / len(dropped_nseq) if dropped_nseq else None,
                    "false_positive_count": max(0, new_drops - len(dropped_nseq)),
                    "verdict_before_passes": clean_passes_rb,
                    "verdict_after_passes": dirty_passes_rb,
                    "verdict_flip": clean_passes_rb and not dirty_passes_rb,
                    "note": "RespiBAN completeness measured via nSeq gaps; affects all channels.",
                })

        del clean_e4, clean_chest
        _rmtree(scratch)


def _run_conformance_experiments(
    records: list,
    participants: list,
    severities: list,
    ranges_cfg: dict,
) -> None:
    ft_nn = "conformance_non_numeric"
    ft_sr = "conformance_sampling_rate_fault"

    e4_targets_excl = {"TEMP": _TEMP_EXCLUDE, "EDA": frozenset(), "HR": frozenset()}
    sig_labels = {"TEMP": "E4_TEMP", "EDA": "E4_EDA", "HR": "E4_HR"}

    for pid in participants:
        print(f"  conformance: {pid}")
        scratch = _copy_participant_to_scratch(pid)
        e4_dir = scratch / f"{pid}_E4_Data"
        rb_path = scratch / f"{pid}_respiban.txt"

        # Count RespiBAN rows once per participant (fast binary scan).
        n_rb = _count_rb_rows(rb_path)

        # Compute clean references once per participant -- reused across all severities.
        clean_e4 = _run_conformance_e4(scratch, ranges_cfg)
        clean_rb = _run_conformance_rb(scratch, pid)

        for sev_idx, sev in enumerate(severities):
            nf_rb = _n_faults(n_rb, sev)

            # ---- E4 non-numeric ----
            for mod, excl in e4_targets_excl.items():
                csv = e4_dir / f"{mod}.csv"
                n = _e4_sample_count(csv)
                nf = _n_faults(n, sev)

                clean_nn = _conformance_non_numeric(clean_e4, mod)

                scratch2 = _copy_e4_to_dirty_scratch(pid)
                csv2 = scratch2 / f"{pid}_E4_Data" / f"{mod}.csv"
                rng = np.random.default_rng(_seed(pid, ft_nn, sev_idx))
                injected = inject_e4_non_numeric(csv2, nf, rng, excl)

                dirty = _run_conformance_e4(scratch2, ranges_cfg)
                dirty_nn = _conformance_non_numeric(dirty, mod)
                verdict_flip = not dirty.get("e4", {}).get(mod, {}).get(
                    "non_numeric", {}
                ).get("ok", True)
                _rmtree(scratch2)
                del dirty

                new_nn = dirty_nn - clean_nn
                records.append({
                    "dimension": "conformance",
                    "fault_type": ft_nn,
                    "signal": sig_labels[mod],
                    "participant": pid,
                    "severity": sev,
                    "n_injected": len(injected),
                    "n_detected": new_nn,
                    "detection_rate": new_nn / len(injected) if injected else None,
                    "false_positive_count": max(0, new_nn - len(injected)),
                    "verdict_flip": verdict_flip,
                })

            # ---- RespiBAN ECG non-numeric ----
            clean_rb_nn = _conformance_chest_non_numeric(clean_rb, "CH1")

            scratch3 = _copy_rb_to_dirty_scratch(pid)
            rb3 = scratch3 / f"{pid}_respiban.txt"
            rng_rb = np.random.default_rng(_seed(pid, ft_nn, sev_idx) + 5)
            inj_rb = _inject_rb_non_numeric_bytes(rb3, "CH1", nf_rb, rng_rb)

            dirty_rb = _run_conformance_rb(scratch3, pid)
            dirty_rb_nn = _conformance_chest_non_numeric(dirty_rb, "CH1")
            rb_verdict_flip = not dirty_rb.get("chest", {}).get(
                "range_summary", {}
            ).get("ok", True)
            _rmtree(scratch3)
            del dirty_rb

            records.append({
                "dimension": "conformance",
                "fault_type": ft_nn,
                "signal": "RespiBAN_ECG",
                "participant": pid,
                "severity": sev,
                "n_injected": len(inj_rb),
                "n_detected": dirty_rb_nn - clean_rb_nn,
                "detection_rate": (
                    (dirty_rb_nn - clean_rb_nn) / len(inj_rb) if inj_rb else None
                ),
                "false_positive_count": max(0, dirty_rb_nn - clean_rb_nn - len(inj_rb)),
                "verdict_flip": rb_verdict_flip,
            })

            # ---- RespiBAN ECG out-of-range (ADC = 70000) ----
            clean_rb2_viol = _conformance_chest_range_violations(clean_rb, "CH1")

            scratch5 = _copy_rb_to_dirty_scratch(pid)
            rb5 = scratch5 / f"{pid}_respiban.txt"
            rng5 = np.random.default_rng(_seed(pid, ft_sr, sev_idx) + 5)
            inj5 = _inject_rb_value_bytes(rb5, "CH1", 70000, nf_rb, rng5)

            dirty_rb2 = _run_conformance_rb(scratch5, pid)
            dirty_rb2_viol = _conformance_chest_range_violations(dirty_rb2, "CH1")
            rb2_verdict_flip = not dirty_rb2.get("chest", {}).get(
                "range_summary", {}
            ).get("ok", True)
            del dirty_rb2

            # Cross-check: plausibility on the same corrupted RespiBAN
            dirty_rb2_pls = _run_plausibility_chest(scratch5, pid, ranges_cfg["wesad"], 0.01)
            ecg_pls = dirty_rb2_pls.get("chest", {}).get("ECG", {})
            pls_viol_rb = ecg_pls.get("n_violations", 0)
            _rmtree(scratch5)
            del dirty_rb2_pls

            records.append({
                "dimension": "conformance",
                "fault_type": "conformance_out_of_device_range",
                "signal": "RespiBAN_ECG",
                "participant": pid,
                "severity": sev,
                "fault_value": 70000,
                "n_injected": len(inj5),
                "n_detected_conformance": dirty_rb2_viol - clean_rb2_viol,
                "detection_rate": (
                    (dirty_rb2_viol - clean_rb2_viol) / len(inj5) if inj5 else None
                ),
                "false_positive_count": max(0, dirty_rb2_viol - clean_rb2_viol - len(inj5)),
                "cross_check_plausibility_detections": pls_viol_rb,
                "verdict_flip": rb2_verdict_flip,
            })

        # ---- E4 EDA sampling-rate fault (file-level, no severity loop) ----
        clean_sr_ok = (
            clean_e4.get("e4", {}).get("EDA", {}).get("sampling_rate", {}).get("ok", True)
        )

        scratch_sr = _copy_e4_to_dirty_scratch(pid)
        eda_csv_sr = scratch_sr / f"{pid}_E4_Data" / "EDA.csv"
        original_hz = inject_e4_sampling_rate(eda_csv_sr, 8.0)
        dirty_sr = _run_conformance_e4(scratch_sr, ranges_cfg)
        dirty_sr_ok = (
            dirty_sr.get("e4", {}).get("EDA", {}).get("sampling_rate", {}).get("ok", True)
        )
        _rmtree(scratch_sr)
        del dirty_sr

        records.append({
            "dimension": "conformance",
            "fault_type": ft_sr,
            "signal": "E4_EDA",
            "participant": pid,
            "severity": None,
            "original_hz": original_hz,
            "injected_hz": 8.0,
            "baseline_sampling_rate_ok": clean_sr_ok,
            "detected": not dirty_sr_ok,
            "verdict_flip": clean_sr_ok and not dirty_sr_ok,
        })

        del clean_e4, clean_rb
        _rmtree(scratch)


def _run_plausibility_experiments(
    records: list,
    participants: list,
    severities: list,
    wesad_cfg: dict,
    full_ranges_cfg: dict,
    pls_threshold: float,
) -> None:
    ft = "plausibility_physiological_impossible"
    targets = {
        "TEMP": (50.0,  _TEMP_EXCLUDE, "E4_TEMP"),
        "HR":   (300.0, frozenset(),   "E4_HR"),
        "EDA":  (-1.0,  frozenset(),   "E4_EDA"),
    }

    for pid in participants:
        print(f"  plausibility: {pid}")
        scratch = _copy_participant_to_scratch(pid)
        e4_dir = scratch / f"{pid}_E4_Data"

        # Compute clean E4 references once per participant -- reused across all
        # severities.  RespiBAN is not needed: all plausibility faults target E4.
        clean_pls = _run_plausibility_e4(scratch, wesad_cfg, pls_threshold)
        clean_conf = _run_conformance_e4(scratch, full_ranges_cfg)

        for sev_idx, sev in enumerate(severities):
            for mod, (fault_val, excl, sig_label) in targets.items():
                csv = e4_dir / f"{mod}.csv"
                n = _e4_sample_count(csv)
                nf = _n_faults(n, sev)

                clean_viol = _plausibility_violations(clean_pls, mod)
                clean_passes = _plausibility_passes(clean_pls, mod)
                clean_conf_viol = _conformance_range_violations(clean_conf, mod)

                scratch2 = _copy_e4_to_dirty_scratch(pid)
                csv2 = scratch2 / f"{pid}_E4_Data" / f"{mod}.csv"
                rng = np.random.default_rng(_seed(pid, ft, sev_idx))
                injected = inject_e4_value(csv2, fault_val, nf, rng, excl)

                dirty_pls = _run_plausibility_e4(scratch2, wesad_cfg, pls_threshold)
                dirty_viol = _plausibility_violations(dirty_pls, mod)
                dirty_passes = _plausibility_passes(dirty_pls, mod)
                del dirty_pls

                dirty_conf = _run_conformance_e4(scratch2, full_ranges_cfg)
                dirty_conf_viol = _conformance_range_violations(dirty_conf, mod)
                _rmtree(scratch2)
                del dirty_conf

                new_viol = dirty_viol - clean_viol
                records.append({
                    "dimension": "plausibility",
                    "fault_type": ft,
                    "signal": sig_label,
                    "participant": pid,
                    "severity": sev,
                    "fault_value": fault_val,
                    "n_injected": len(injected),
                    "n_detected": new_viol,
                    "detection_rate": new_viol / len(injected) if injected else None,
                    "false_positive_count": max(0, new_viol - len(injected)),
                    "cross_check_conformance_detections": (
                        dirty_conf_viol - clean_conf_viol
                    ),
                    "verdict_before_passes": clean_passes,
                    "verdict_after_passes": dirty_passes,
                    "verdict_flip": clean_passes and not dirty_passes,
                })

        del clean_pls, clean_conf
        _rmtree(scratch)


def _run_timeliness_experiments(
    records: list,
    participants: list,
    offsets_s: list,
    timeliness_threshold: float,
) -> None:
    ft = "timeliness_start_shift"

    for pid in participants:
        print(f"  timeliness: {pid}")
        scratch = _copy_participant_to_scratch(pid)

        # Baseline alignment on unmodified scratch copy
        baseline = _run_alignment(scratch, pid, timeliness_threshold)
        baseline_residual = baseline["offset_after_s"]
        baseline_passes = baseline["passes_threshold"]

        for offset in offsets_s:
            scratch2 = _copy_to_dirty_scratch(pid)
            eda_csv = scratch2 / f"{pid}_E4_Data" / "EDA.csv"
            shift_e4_start_time(eda_csv, offset)

            dirty = _run_alignment(scratch2, pid, timeliness_threshold)
            _rmtree(scratch2)

            records.append({
                "dimension": "timeliness",
                "fault_type": ft,
                "signal": "E4_EDA",
                "participant": pid,
                "offset_injected_s": offset,
                "baseline_residual_s": baseline_residual,
                "dirty_residual_s": dirty["offset_after_s"],
                "residual_change_s": round(dirty["offset_after_s"] - baseline_residual, 6),
                "baseline_passes": baseline_passes,
                "dirty_passes": dirty["passes_threshold"],
                "detected": dirty["offset_after_s"] > timeliness_threshold,
                "note": (
                    "Detector uses each sensor's own timestamps; shifting E4 EDA "
                    "start time shifts the overlap window, not the measured residual. "
                    "Expected residual change: ~0 (bounded by quantization noise)."
                ),
            })

        _rmtree(scratch)


# ---------------------------------------------------------------------------
# Control condition (severity zero)
# ---------------------------------------------------------------------------

def _run_control_experiments(
    records: list,
    participants: list,
    thresholds_cfg: dict,
    ranges_cfg: dict,
) -> None:
    """
    Control condition: no faults injected. Pre-registered expectation: every
    check returns zero flags and a passing verdict for every signal.
    """
    comp_threshold = float(thresholds_cfg["completeness"]["max_missingness_rate"])
    pls_threshold = float(thresholds_cfg["validity"]["max_plausibility_failure_rate"])
    tl_threshold = float(thresholds_cfg["timeliness"]["max_cross_modal_offset_seconds"])
    wesad_cfg = ranges_cfg["wesad"]

    for pid in participants:
        scratch = _copy_participant_to_scratch(pid)
        intentional = _load_intentional_removals(pid)

        comp = _run_completeness(scratch, pid, comp_threshold, intentional)
        conf = _run_conformance(scratch, ranges_cfg)
        plaus = _run_plausibility(scratch, wesad_cfg, pls_threshold)
        align = _run_alignment(scratch, pid, tl_threshold)
        _rmtree(scratch)

        comp_e4_flags = {
            mod: not v.get("passes_threshold", True)
            for mod, v in comp["e4"].items()
        }
        comp_chest_flag = not comp.get("chest", {}).get("sequence_gap_passes_threshold", True)

        conf_e4_flags = {
            mod: (
                not m.get("sampling_rate", {}).get("ok", True)
                or not m.get("range", {}).get("ok", True)
                or not m.get("non_numeric", {}).get("ok", True)
            )
            for mod, m in conf.get("e4", {}).items()
            if m.get("format", {}).get("ok", True)
        }
        conf_chest_flag = not conf.get("chest", {}).get("range_summary", {}).get("ok", True)

        plaus_e4_flags = {
            mod: not v.get("passes_threshold", True)
            for mod, v in plaus["e4"].items()
            if not v.get("excluded") and not v.get("error")
        }
        plaus_chest_flag = any(
            not sig.get("passes_threshold", True)
            for sig in plaus.get("chest", {}).values()
            if isinstance(sig, dict) and not sig.get("excluded")
        )

        any_flag = (
            any(comp_e4_flags.values()) or comp_chest_flag
            or any(conf_e4_flags.values()) or conf_chest_flag
            or any(plaus_e4_flags.values()) or plaus_chest_flag
            or not align["passes_threshold"]
        )

        records.append({
            "dimension": "control",
            "fault_type": "control_no_injection",
            "participant": pid,
            "severity": 0,
            "n_injected": 0,
            "completeness_e4_flags": comp_e4_flags,
            "completeness_chest_flag": comp_chest_flag,
            "conformance_e4_flags": conf_e4_flags,
            "conformance_chest_flag": conf_chest_flag,
            "plausibility_e4_flags": plaus_e4_flags,
            "plausibility_chest_flag": plaus_chest_flag,
            "timeliness_passes": align["passes_threshold"],
            "any_flag": any_flag,
            "pre_registered_expectation": "any_flag == false",
        })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_all_experiments() -> None:
    """
    Execute all pre-registered fault injection experiments.
    Requires bronze/WESAD/{S2,S8,S15} to be present.
    Writes results to reports/experiments/fault_injection_results.json.

    DO NOT call this function as part of stage A (pre-registration).
    """
    for pid in _PARTICIPANTS_ORDER:
        if not (BRONZE_WESAD / pid).exists():
            raise RuntimeError(
                f"Bronze data missing: {BRONZE_WESAD / pid}. "
                "Fault injection experiments require bronze data on disk."
            )

    with open(EXPERIMENTS_CONFIG, encoding="utf-8") as fh:
        exp_cfg = yaml.safe_load(fh)
    with open(ROOT / "config" / "physiological_ranges.yaml", encoding="utf-8") as fh:
        ranges_cfg = yaml.safe_load(fh)
    with open(ROOT / "config" / "thresholds.yaml", encoding="utf-8") as fh:
        thresholds_cfg = yaml.safe_load(fh)

    participants = exp_cfg["participants"]["fixed"]
    severities = exp_cfg["severities"]["sample_level_fractions"]
    offsets = exp_cfg["fault_types"]["timeliness_start_shift"]["offsets_seconds"]
    wesad_cfg = ranges_cfg["wesad"]
    pls_threshold = float(thresholds_cfg["validity"]["max_plausibility_failure_rate"])
    tl_threshold = float(thresholds_cfg["timeliness"]["max_cross_modal_offset_seconds"])

    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    SCRATCH_DIRTY.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Scratch base: {_SCRATCH_BASE}")

    records: list = []

    print("Running control condition ...")
    _run_control_experiments(records, participants, thresholds_cfg, ranges_cfg)
    print(f"  control done ({len(records)} records so far)")

    print("Running completeness experiments ...")
    _run_completeness_experiments(records, participants, severities, thresholds_cfg)
    print(f"  completeness done ({len(records)} records so far)")

    print("Running conformance experiments ...")
    _run_conformance_experiments(records, participants, severities, ranges_cfg)
    print(f"  conformance done ({len(records)} records so far)")

    print("Running plausibility experiments ...")
    _run_plausibility_experiments(
        records, participants, severities, wesad_cfg, ranges_cfg, pls_threshold
    )
    print(f"  plausibility done ({len(records)} records so far)")

    print("Running timeliness experiments ...")
    _run_timeliness_experiments(records, participants, offsets, tl_threshold)
    print(f"  timeliness done ({len(records)} records so far)")

    output = {
        "experiment": "fault_injection",
        "dataset": "WESAD",
        "design_config": "config/experiments.yaml",
        "participants": participants,
        "n_records": len(records),
        "records": records,
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2, sort_keys=True)

    print(f"Results written to: {RESULTS_PATH}")
    print(f"Total records: {len(records)}")


if __name__ == "__main__":
    run_all_experiments()
