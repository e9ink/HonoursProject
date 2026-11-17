"""
Bronze profiling for WESAD dataset.

Reads raw data from bronze/ in read-only mode.
Never writes to, moves, or modifies anything in bronze/.
Output: reports/wesad_baseline.json  (the 'before' snapshot).
Deterministic: same input always produces identical output.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent  # wesad/
DATA_ROOT = ROOT.parent                        # project root; bronze/silver/gold live here
BRONZE_WESAD = DATA_ROOT / "bronze" / "WESAD"
REPORTS = ROOT / "reports"

# Fixed-rate E4 wristband modalities (IBI is event-based and handled separately).
E4_FIXED_MODALITIES = ["ACC", "BVP", "EDA", "HR", "TEMP"]

# RespiBAN chest sensor: column name → signal label.
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


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _find_nan_runs(bool_series: "pd.Series[bool]", hz: float) -> list:
    """Return gap-location dicts for runs of True (NaN) in bool_series."""
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
# E4 wristband profiling
# ---------------------------------------------------------------------------

def profile_e4_fixed(csv_path: Path) -> dict:
    """
    Profile one fixed-rate E4 CSV (ACC, BVP, EDA, HR, TEMP).

    Format: row 0 = start Unix timestamp; row 1 = sample rate (Hz);
    rows 2+ = data values (ACC has 3 columns; others have 1).
    """
    # Read everything as strings to avoid type inference on mixed-length rows.
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
    missingness_rate = round(n_nan / total_cells, 6) if total_cells > 0 else None
    implied_duration_s = round(n_samples / declared_hz, 4) if declared_hz > 0 else None

    # NaN gaps: any row with at least one NaN cell counts as a gap row.
    row_has_nan = data.isnull().any(axis=1)
    nan_gap_locations = _find_nan_runs(row_has_nan, declared_hz)

    return {
        "start_time_unix": start_time,
        "declared_hz": declared_hz,
        "n_samples": n_samples,
        "n_columns": n_cols,
        "implied_duration_seconds": implied_duration_s,
        "n_nan": n_nan,
        "missingness_rate": missingness_rate,
        # E4 CSVs carry no per-sample timestamps, so the actual inter-sample
        # interval cannot be verified from this file alone.
        "sampling_rate_note": (
            "E4 CSV format provides no per-sample timestamps; "
            "actual sampling rate cannot be independently verified. "
            "Declared rate reported."
        ),
        "nan_gap_count": len(nan_gap_locations),
        "nan_gap_locations": nan_gap_locations,
    }


def profile_e4_ibi(csv_path: Path) -> dict:
    """
    Profile the IBI CSV (event-based inter-beat intervals; no fixed rate).

    Format: row 0 = 'start_timestamp, IBI' (label, not a rate);
    rows 1+ = (time_offset_seconds, ibi_duration_seconds).
    """
    raw = pd.read_csv(csv_path, header=None, dtype=str)
    start_time = float(raw.iloc[0, 0].strip())
    data = (
        raw.iloc[1:]
        .apply(lambda col: pd.to_numeric(col, errors="coerce"))
        .reset_index(drop=True)
    )
    n_events = len(data)
    n_nan = int(data.isnull().sum().sum())
    return {
        "start_time_unix": start_time,
        "note": "Event-based (inter-beat intervals). No fixed sample rate.",
        "n_events": n_events,
        "n_nan": n_nan,
    }


# ---------------------------------------------------------------------------
# RespiBAN chest sensor profiling
# ---------------------------------------------------------------------------

def profile_chest(txt_path: Path) -> dict:
    """
    Profile one RespiBAN chest text file.

    Format: 3-line header (two '#' comment lines + '# EndOfHeader'), then
    tab-separated data with a trailing tab (11 tokens per row; use first 10).
    Columns: nSeq, DI, CH1..CH8.  Declared rate: 700 Hz.
    Gaps are detected via non-consecutive nSeq values.
    """
    # Extract JSON metadata from the second header line.
    with open(txt_path, "r", encoding="utf-8", errors="replace") as fh:
        fh.readline()              # "# OpenSignals Text File Format"
        meta_line = fh.readline()  # "# {JSON...}"

    json_str = meta_line.lstrip("# ").strip()
    meta = json.loads(json_str)
    device_key = next(iter(meta))
    device_info = meta[device_key]
    declared_hz = int(device_info["sampling rate"])
    sensors_in_header = device_info.get("sensor", [])

    # Load data; trailing tab produces an 11th empty column — discard it.
    data = pd.read_csv(
        txt_path,
        sep="\t",
        skiprows=3,
        header=None,
        usecols=range(10),
        dtype={0: int},      # nSeq must be int for gap detection
    )
    data.columns = ["nSeq", "DI", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"]

    n_samples = len(data)
    seq = data["nSeq"]
    nseq_start = int(seq.iloc[0])
    nseq_end = int(seq.iloc[-1])
    expected_n = nseq_end - nseq_start + 1

    # Sequence gaps: diff != 1 means one or more samples were dropped.
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
    seq_missingness = round(total_dropped / expected_n, 6) if expected_n > 0 else 0.0

    # Per-channel NaN rate (NaN in data cells, separate from sequence gaps).
    per_channel: dict = {}
    for ch, signal in sorted(CHEST_CHANNEL_MAP.items()):
        col = data[ch]
        n_nan = int(col.isnull().sum())
        per_channel[signal] = {
            "column": ch,
            "n_nan": n_nan,
            "nan_rate": round(n_nan / n_samples, 6) if n_samples > 0 else None,
        }

    return {
        "declared_hz": declared_hz,
        "sensors_in_header": sensors_in_header,
        "n_samples": n_samples,
        "nseq_start": nseq_start,
        "nseq_end": nseq_end,
        "expected_n_from_nseq": expected_n,
        "total_dropped_samples_in_gaps": total_dropped,
        "sequence_gap_missingness_rate": seq_missingness,
        "implied_duration_seconds": round(expected_n / declared_hz, 4),
        "n_sequence_gaps": len(sequence_gaps),
        "sequence_gap_locations": sequence_gaps,
        "per_channel": per_channel,
    }


# ---------------------------------------------------------------------------
# Per-participant coordinator
# ---------------------------------------------------------------------------

def profile_participant(participant_dir: Path) -> dict:
    """Build a structural profile dict (sample counts, frequencies, start timestamps) for one participant."""
    pid = participant_dir.name
    e4_dir = participant_dir / f"{pid}_E4_Data"

    e4_profile: dict = {}
    for modality in sorted(E4_FIXED_MODALITIES):
        csv_path = e4_dir / f"{modality}.csv"
        e4_profile[modality] = (
            profile_e4_fixed(csv_path)
            if csv_path.exists()
            else {"error": "file_not_found"}
        )

    ibi_path = e4_dir / "IBI.csv"
    e4_profile["IBI"] = (
        profile_e4_ibi(ibi_path)
        if ibi_path.exists()
        else {"error": "file_not_found"}
    )

    chest_path = participant_dir / f"{pid}_respiban.txt"
    chest_profile = (
        profile_chest(chest_path)
        if chest_path.exists()
        else {"error": "file_not_found"}
    )

    return {"chest": chest_profile, "e4": e4_profile}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Profile all participants and write reports/wesad_baseline.json."""
    REPORTS.mkdir(exist_ok=True)

    participant_dirs = sorted(
        (d for d in BRONZE_WESAD.iterdir() if d.is_dir()),
        key=lambda p: p.name,
    )

    participants: dict = {}
    for pdir in participant_dirs:
        print(f"  Profiling {pdir.name} ...")
        participants[pdir.name] = profile_participant(pdir)

    report = {
        "dataset": "WESAD",
        "bronze_path": str(BRONZE_WESAD),
        "n_participants": len(participants),
        "participant_ids": sorted(participants.keys()),
        "participants": participants,
    }

    output_path = REPORTS / "wesad_baseline.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    print(f"\nBaseline report written to: {output_path}")


if __name__ == "__main__":
    main()
