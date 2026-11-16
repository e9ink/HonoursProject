"""
Silver-layer completeness check for WESAD dataset (Task 4).

Measures missingness per modality and per participant using the same
definitions as Task 2 Bronze profiling (src/profiling.py), so that
findings are directly comparable with the baseline report.

Missingness definitions (unchanged from Task 2):
  E4 fixed-rate (ACC, BVP, EDA, HR, TEMP):
    missingness_rate = n_nan / (n_samples × n_columns)
    NaN-gap locations reported separately (contiguous rows with any NaN cell).

  IBI (event-based):
    No missingness rate defined — no fixed expected-sample-count baseline.
    n_events and n_nan are reported for reference only.
    IBI is NOT compared against the threshold.

  RespiBAN chest:
    sequence_gap_missingness_rate = total_dropped_samples / expected_n_from_nseq
      (primary measure; dropped samples inferred from non-consecutive nSeq)
    per_channel_nan_rate = n_nan / n_actual_rows  (per signal, secondary)

Threshold:
  max_missingness_rate is read from config/thresholds.yaml.
  Applies to: E4 fixed-rate missingness_rate and RespiBAN sequence-gap rate
  and per-channel NaN rate, assessed both per-modality and dataset-wide.
  IBI is excluded from threshold comparison.

Cross-check:
  After measuring, key metrics are compared against reports/wesad_baseline.json
  (Task 2 output). If any E4 missingness_rate or RespiBAN sequence-gap rate
  differs, execution stops with a clear error. A mismatch means one of the two
  measurements is wrong and must be investigated before continuing.

Output: reports/wesad_completeness.json
Deterministic: same input always produces identical output.
Never writes to, moves, or modifies anything in bronze/.
"""

import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_WESAD = ROOT / "bronze" / "WESAD"
REPORTS = ROOT / "reports"
CONFIG_DIR = ROOT / "config"

E4_FIXED_MODALITIES = ["ACC", "BVP", "EDA", "HR", "TEMP"]

CHEST_CHANNEL_MAP = {
    "CH1": "ECG",
    "CH2": "EDA",
    "CH3": "EMG",
    "CH4": "TEMP",
    "CH5": "ACC_x",
    "CH6": "ACC_y",
    "CH7": "ACC_z",
    "CH8": "RESP",
}

RESPIBAN_COLS = ["nSeq", "DI", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"]


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_threshold() -> float:
    path = CONFIG_DIR / "thresholds.yaml"
    with open(path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return float(cfg["completeness"]["max_missingness_rate"])


# ---------------------------------------------------------------------------
# Shared helper: NaN-run location finder (identical to profiling.py)
# ---------------------------------------------------------------------------

def _find_nan_runs(bool_series: "pd.Series[bool]", hz: float) -> list:
    """Return list of contiguous NaN run dicts with start index, length, and duration."""
    runs = []
    arr = bool_series.to_numpy()
    n = len(arr)
    in_run = False
    start = 0
    for i, v in enumerate(arr):
        if v and not in_run:
            in_run = True
            start = i
        elif not v and in_run:
            in_run = False
            runs.append({
                "start_sample": start,
                "end_sample": i - 1,
                "n_samples": i - start,
                "start_seconds": round(start / hz, 4),
                "end_seconds": round((i - 1) / hz, 4),
            })
    if in_run:
        runs.append({
            "start_sample": start,
            "end_sample": n - 1,
            "n_samples": n - start,
            "start_seconds": round(start / hz, 4),
            "end_seconds": round((n - 1) / hz, 4),
        })
    return runs


# ---------------------------------------------------------------------------
# E4 wristband completeness
# ---------------------------------------------------------------------------

def _check_e4_fixed(
    csv_path: Path,
    threshold: float,
    intentional_removal_indices: "list[int] | None" = None,
) -> dict:
    """
    Measure E4 fixed-rate missingness.
    Formula: missingness_rate = n_unintentional_nan / (n_samples × n_columns).

    intentional_removal_indices: sample indices that were deliberately set to NaN
    during the cleaning stage (from reports/wesad_cleaning.json).  These are
    EXCLUDED from missingness_rate and reported separately as intentional_removals.
    Defaults to None (no intentional removals — original Bronze behaviour).
    """
    raw = pd.read_csv(csv_path, header=None, dtype=str)
    start_time = float(raw.iloc[0, 0].strip())
    declared_hz = float(raw.iloc[1, 0].strip())

    data = (
        raw.iloc[2:]
        .apply(lambda col: pd.to_numeric(col, errors="coerce"))
        .reset_index(drop=True)
    )

    n_samples = len(data)
    n_cols = data.shape[1]
    n_nan = int(data.isnull().sum().sum())
    total_cells = n_samples * n_cols

    # Count intentional removals that are actually NaN in this file (0 for Bronze,
    # equals the cleaning count for Silver TEMP).
    n_intentional_nan = 0
    intentional_removals_info: "dict | None" = None
    if intentional_removal_indices:
        for idx in intentional_removal_indices:
            if idx < len(data) and data.iloc[idx].isnull().any():
                n_intentional_nan += 1
        if n_intentional_nan > 0:
            intentional_removals_info = {
                "count": n_intentional_nan,
                "indices": sorted(intentional_removal_indices),
                "note": (
                    "Samples intentionally removed during cleaning; excluded from "
                    "missingness_rate. Source: reports/wesad_cleaning.json."
                ),
            }

    n_unintentional_nan = n_nan - n_intentional_nan
    missingness_rate = (
        round(n_unintentional_nan / total_cells, 6) if total_cells > 0 else None
    )

    # Gap detection uses only unintentional NaN rows.
    if intentional_removal_indices:
        import pandas as _pd
        intentional_mask = _pd.Series(False, index=range(len(data)))
        for idx in intentional_removal_indices:
            if idx < len(data):
                intentional_mask.iloc[idx] = True
        row_has_nan = data.isnull().any(axis=1) & ~intentional_mask
    else:
        row_has_nan = data.isnull().any(axis=1)
    nan_gap_locations = _find_nan_runs(row_has_nan, declared_hz)

    passes = (missingness_rate is not None) and (missingness_rate <= threshold)
    result = {
        "start_time_unix": start_time,
        "declared_hz": declared_hz,
        "n_samples": n_samples,
        "n_columns": n_cols,
        "total_cells": total_cells,
        "n_nan": n_nan,
        "missingness_rate": missingness_rate,
        "nan_gap_count": len(nan_gap_locations),
        "nan_gap_locations": nan_gap_locations,
        "threshold": threshold,
        "passes_threshold": passes,
    }
    if intentional_removals_info:
        result["n_intentional_nan"] = n_intentional_nan
        result["n_unintentional_nan"] = n_unintentional_nan
        result["intentional_removals"] = intentional_removals_info
    return result


def _check_e4_ibi(csv_path: Path) -> dict:
    """
    IBI is event-based: no fixed expected-sample-count, no missingness rate.
    Reports n_events and n_nan for reference only; not compared to threshold.
    Consistent with Task 2 treatment in profile_e4_ibi.
    """
    raw = pd.read_csv(csv_path, header=None, dtype=str)
    start_time = float(raw.iloc[0, 0].strip())
    data = (
        raw.iloc[1:]
        .apply(lambda col: pd.to_numeric(col, errors="coerce"))
        .reset_index(drop=True)
    )
    return {
        "start_time_unix": start_time,
        "note": (
            "Event-based (inter-beat intervals). No fixed sample rate; "
            "missingness rate is undefined and not compared against threshold."
        ),
        "n_events": len(data),
        "n_nan": int(data.isnull().sum().sum()),
        "threshold_applied": False,
    }


def check_e4(
    participant_dir: Path,
    threshold: float,
    e4_path_overrides: "dict[str, Path] | None" = None,
    intentional_removals_by_mod: "dict[str, list[int]] | None" = None,
) -> dict:
    """
    e4_path_overrides: optional dict {modality: Path} — use Silver path for that
    modality instead of the default bronze path (post-cleaning checks only).
    intentional_removals_by_mod: optional dict {modality: [indices]} — indices
    to exclude from missingness_rate (post-cleaning checks only).
    """
    pid = participant_dir.name
    e4_dir = participant_dir / f"{pid}_E4_Data"
    result: dict = {}

    for modality in sorted(E4_FIXED_MODALITIES):
        csv_path = (
            (e4_path_overrides or {}).get(modality)
            or e4_dir / f"{modality}.csv"
        )
        if not csv_path.exists():
            result[modality] = {"error": "file_not_found", "passes_threshold": False}
            continue
        removal_indices = (intentional_removals_by_mod or {}).get(modality)
        result[modality] = _check_e4_fixed(csv_path, threshold, removal_indices)

    ibi_path = e4_dir / "IBI.csv"
    result["IBI"] = (
        _check_e4_ibi(ibi_path)
        if ibi_path.exists()
        else {"error": "file_not_found", "threshold_applied": False}
    )
    return result


# ---------------------------------------------------------------------------
# RespiBAN chest completeness
# ---------------------------------------------------------------------------

def check_chest(txt_path: Path, threshold: float) -> dict:
    """
    Measure RespiBAN missingness.
    Primary: sequence_gap_missingness_rate = total_dropped / expected_n_from_nseq.
    Secondary: per-channel NaN rate = n_nan / n_actual_rows.
    Both formulas are identical to profile_chest in profiling.py.
    """
    with open(txt_path, "r", encoding="utf-8", errors="replace") as fh:
        fh.readline()
        meta_line = fh.readline()

    json_str = meta_line.lstrip("# ").strip()
    meta = json.loads(json_str)
    device_key = next(iter(meta))
    device_info = meta[device_key]
    declared_hz = int(device_info["sampling rate"])

    data = pd.read_csv(
        txt_path,
        sep="\t",
        skiprows=3,
        header=None,
        usecols=range(10),
        dtype={0: int},
    )
    data.columns = RESPIBAN_COLS

    n_samples = len(data)
    seq = data["nSeq"]
    nseq_start = int(seq.iloc[0])
    nseq_end = int(seq.iloc[-1])
    expected_n = nseq_end - nseq_start + 1

    diffs = seq.diff().iloc[1:]
    gap_rows = diffs[diffs != 1]
    sequence_gaps = []
    for row_idx in sorted(gap_rows.index):
        prev_seq = int(seq.iloc[row_idx - 1])
        curr_seq = int(seq.iloc[row_idx])
        dropped = curr_seq - prev_seq - 1
        sequence_gaps.append({
            "at_row": int(row_idx),
            "prev_nseq": prev_seq,
            "next_nseq": curr_seq,
            "dropped_samples": int(dropped),
            "approx_start_seconds": round(prev_seq / declared_hz, 4),
        })

    total_dropped = int(sum(g["dropped_samples"] for g in sequence_gaps))
    seq_rate = round(total_dropped / expected_n, 6) if expected_n > 0 else 0.0

    per_channel: dict = {}
    for ch, signal in sorted(CHEST_CHANNEL_MAP.items()):
        col = data[ch]
        n_nan = int(col.isnull().sum())
        nan_rate = round(n_nan / n_samples, 6) if n_samples > 0 else None
        per_channel[signal] = {
            "column": ch,
            "n_nan": n_nan,
            "nan_rate": nan_rate,
            "passes_threshold": (nan_rate is not None) and (nan_rate <= threshold),
        }

    seq_passes = seq_rate <= threshold
    return {
        "declared_hz": declared_hz,
        "n_samples": n_samples,
        "nseq_start": nseq_start,
        "nseq_end": nseq_end,
        "expected_n_from_nseq": expected_n,
        "total_dropped_samples_in_gaps": total_dropped,
        "sequence_gap_missingness_rate": seq_rate,
        "n_sequence_gaps": len(sequence_gaps),
        "sequence_gap_locations": sequence_gaps,
        "sequence_gap_passes_threshold": seq_passes,
        "threshold": threshold,
        "per_channel": per_channel,
    }


# ---------------------------------------------------------------------------
# Cross-check against Task 2 baseline report
# ---------------------------------------------------------------------------

def _cross_check_baseline(participants: dict) -> None:
    """
    Compare key missingness metrics against the Task 2 baseline report.
    Raises RuntimeError if any value differs, because a mismatch means one
    of the two measurements is wrong and must be investigated.
    """
    baseline_path = REPORTS / "wesad_baseline.json"
    if not baseline_path.exists():
        print("  WARNING: wesad_baseline.json not found; cross-check skipped.")
        return

    with open(baseline_path, "r", encoding="utf-8") as fh:
        baseline = json.load(fh)

    mismatches: list[str] = []

    for pid in sorted(participants.keys()):
        p = participants[pid]
        b = baseline["participants"].get(pid)
        if b is None:
            mismatches.append(f"{pid}: participant missing from baseline report")
            continue

        # E4 fixed-rate missingness_rate
        for mod in sorted(E4_FIXED_MODALITIES):
            measured = p["e4"].get(mod, {}).get("missingness_rate")
            b_rate = b["e4"].get(mod, {}).get("missingness_rate")
            if measured != b_rate:
                mismatches.append(
                    f"{pid}/E4/{mod}: measured={measured}, baseline={b_rate}"
                )

        # RespiBAN sequence-gap rate
        measured_seq = p["chest"].get("sequence_gap_missingness_rate")
        b_seq = b["chest"].get("sequence_gap_missingness_rate")
        if measured_seq != b_seq:
            mismatches.append(
                f"{pid}/chest/sequence_gap: measured={measured_seq}, baseline={b_seq}"
            )

    if mismatches:
        raise RuntimeError(
            "Completeness check DOES NOT MATCH Task 2 baseline. "
            "One of the two measurements is wrong — investigate before continuing.\n"
            + "\n".join(f"  MISMATCH: {m}" for m in mismatches)
        )

    print("  Cross-check passed: all metrics match Task 2 baseline.")


# ---------------------------------------------------------------------------
# Aggregate summary
# ---------------------------------------------------------------------------

def _summarise(participants: dict, threshold: float) -> dict:
    """Aggregate per-participant completeness results into a dataset-level summary."""
    e4_total_nan = 0
    e4_intentional_nan = 0
    e4_total_cells = 0
    chest_total_dropped = 0
    chest_total_expected = 0
    chest_total_nan = 0
    chest_total_actual_samples_per_channel = 0

    per_participant_pass: dict[str, bool] = {}

    for pid, p in sorted(participants.items()):
        pid_passes = True

        for mod in sorted(E4_FIXED_MODALITIES):
            m = p["e4"].get(mod, {})
            e4_total_nan += m.get("n_nan", 0)
            e4_intentional_nan += m.get("n_intentional_nan", 0)
            e4_total_cells += m.get("total_cells", 0)
            if not m.get("passes_threshold", True):
                pid_passes = False

        chest = p["chest"]
        chest_total_dropped += chest.get("total_dropped_samples_in_gaps", 0)
        chest_total_expected += chest.get("expected_n_from_nseq", 0)
        if not chest.get("sequence_gap_passes_threshold", True):
            pid_passes = False

        n_act = chest.get("n_samples", 0)
        for ch_info in chest.get("per_channel", {}).values():
            chest_total_nan += ch_info.get("n_nan", 0)
            chest_total_actual_samples_per_channel += n_act
            if not ch_info.get("passes_threshold", True):
                pid_passes = False

        per_participant_pass[pid] = pid_passes

    # Missingness rate is based on unintentional NaN only (intentional removals
    # are documented in reports/wesad_cleaning.json and excluded from this metric).
    e4_unintentional_nan = e4_total_nan - e4_intentional_nan
    e4_overall = (
        round(e4_unintentional_nan / e4_total_cells, 8) if e4_total_cells > 0 else 0.0
    )
    chest_seq_overall = (
        round(chest_total_dropped / chest_total_expected, 8)
        if chest_total_expected > 0
        else 0.0
    )
    chest_nan_overall = (
        round(chest_total_nan / chest_total_actual_samples_per_channel, 8)
        if chest_total_actual_samples_per_channel > 0
        else 0.0
    )

    dataset_passes = (
        e4_overall <= threshold
        and chest_seq_overall <= threshold
        and chest_nan_overall <= threshold
        and all(per_participant_pass.values())
    )

    summary: dict = {
        "threshold_max_missingness_rate": threshold,
        "e4_overall_missingness_rate": e4_overall,
        "e4_total_nan_cells": e4_total_nan,
        "e4_total_cells_checked": e4_total_cells,
        "chest_sequence_gap_rate": chest_seq_overall,
        "chest_total_dropped_samples": chest_total_dropped,
        "chest_total_expected_samples": chest_total_expected,
        "chest_nan_rate": chest_nan_overall,
        "chest_total_nan_cells": chest_total_nan,
        "per_participant_passes": per_participant_pass,
        "dataset_passes_threshold": dataset_passes,
        "note_ibi": (
            "IBI is event-based; no missingness rate is defined for it and it "
            "is excluded from the threshold comparison. See per-participant "
            "e4.IBI entries for event and NaN counts."
        ),
    }
    if e4_intentional_nan > 0:
        summary["e4_intentional_removals"] = e4_intentional_nan
        summary["e4_unintentional_nan_cells"] = e4_unintentional_nan
        summary["intentional_removals_note"] = (
            "e4_overall_missingness_rate is based on unintentional NaN only. "
            f"{e4_intentional_nan} samples were intentionally removed during "
            "cleaning (documented in reports/wesad_cleaning.json) and are "
            "excluded from the missingness rate."
        )
    return summary


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run completeness check for all participants and write reports/wesad_completeness.json."""
    threshold = _load_threshold()
    print(f"  Threshold: max_missingness_rate = {threshold}")

    REPORTS.mkdir(exist_ok=True)

    participant_dirs = sorted(
        (d for d in BRONZE_WESAD.iterdir() if d.is_dir()),
        key=lambda p: p.name,
    )

    participants: dict = {}
    for pdir in participant_dirs:
        print(f"  Checking {pdir.name} ...")
        pid = pdir.name
        e4 = check_e4(pdir, threshold)
        chest_path = pdir / f"{pid}_respiban.txt"
        chest = (
            check_chest(chest_path, threshold)
            if chest_path.exists()
            else {"error": "file_not_found", "sequence_gap_passes_threshold": False}
        )
        participants[pid] = {"chest": chest, "e4": e4}

    print("  Running cross-check against Task 2 baseline ...")
    _cross_check_baseline(participants)

    summary = _summarise(participants, threshold)

    report = {
        "dataset": "WESAD",
        "check": "completeness",
        "config_thresholds_date_locked": "2026-09-09",
        "n_participants": len(participants),
        "participant_ids": sorted(participants.keys()),
        "participants": participants,
        "summary": summary,
    }

    output_path = REPORTS / "wesad_completeness.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    print(f"\nCompleteness report written to: {output_path}")
    print(f"E4 overall missingness rate    : {summary['e4_overall_missingness_rate']}")
    print(f"Chest sequence-gap rate        : {summary['chest_sequence_gap_rate']}")
    print(f"Chest per-channel NaN rate     : {summary['chest_nan_rate']}")
    print(f"Dataset passes threshold       : {summary['dataset_passes_threshold']}")


if __name__ == "__main__":
    main()
