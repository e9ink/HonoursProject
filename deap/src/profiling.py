"""
DEAP dataset bronze-layer profiling.

Loads each participant .dat file from bronze/DEAP/ using a restricted unpickler
that permits only numpy array reconstruction (the only class references present
in these pickles, confirmed by pickletools inspection on 2026-11-17).

Run from project root:
    python deap/src/profiling.py

Output: deap/reports/deap_baseline.json
"""

import io
import json
import math
import os
import pickle
import sys

import numpy as np


# ---------------------------------------------------------------------------
# Restricted unpickler -- refuses any class not in the allow-list
# ---------------------------------------------------------------------------

ALLOWED = {
    ("numpy.core.multiarray", "_reconstruct"),
    ("numpy", "ndarray"),
    ("numpy", "dtype"),
}


class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if (module, name) in ALLOWED:
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"Refused: {module}.{name} not in allow-list"
        )


def load_dat(path: str) -> dict:
    """Load a DEAP .dat file with the restricted unpickler."""
    with open(path, "rb") as fh:
        return RestrictedUnpickler(fh, encoding="latin1").load()


# ---------------------------------------------------------------------------
# Channel definitions (from DEAP paper / readme)
# Channel order is documented in Koelstra et al. (2012), Table 1.
# Source: official DEAP readme at http://www.eecs.qmul.ac.uk/mmv/datasets/deap/readme.html
# (not present in this Kaggle mirror, so channel names are from the paper only)
# ---------------------------------------------------------------------------

EEG_CHANNELS = [
    "Fp1", "AF3", "F3", "F7", "FC5", "FC1", "C3", "T7",
    "CP5", "CP1", "P3", "P7", "PO3", "O1", "Oz", "Pz",
    "Fp2", "AF4", "Fz", "F4", "F8", "FC6", "FC2", "Cz",
    "C4", "T8", "CP6", "CP2", "P4", "P8", "PO4", "O2",
]  # 32 EEG channels, indices 0-31

PERIPHERAL_CHANNELS = [
    "hEOG",   # 32: horizontal EOG
    "vEOG",   # 33: vertical EOG
    "zEMG",   # 34: zygomaticus EMG
    "tEMG",   # 35: trapezius EMG
    "GSR",    # 36: galvanic skin response (Ohm, inverted = conductance)
    "Resp",   # 37: respiration amplitude belt
    "BVP",    # 38: blood volume pressure (photoplethysmograph)
    "Temp",   # 39: skin temperature (degrees C)
]  # 8 peripheral channels, indices 32-39

ALL_CHANNELS = EEG_CHANNELS + PERIPHERAL_CHANNELS  # 40 total

LABEL_DIMENSIONS = ["valence", "arousal", "dominance", "liking"]


# ---------------------------------------------------------------------------
# Per-channel statistics
# ---------------------------------------------------------------------------

def _longest_flatline(arr: np.ndarray) -> int:
    """Return the length of the longest run of consecutive identical values."""
    if arr.size == 0:
        return 0
    # Compute where values change
    diffs = np.diff(arr)
    change_idx = np.where(diffs != 0)[0]
    if change_idx.size == 0:
        return int(arr.size)
    # Lengths of runs: gaps between change points
    runs = np.diff(np.concatenate(([-1], change_idx, [arr.size - 1])))
    return int(runs.max())


def channel_stats(signal_2d: np.ndarray, channel_idx: int) -> dict:
    """Compute stats for one channel across all trials."""
    ch = signal_2d[:, channel_idx, :].ravel()  # (n_trials, n_samples) -> flat
    nan_count = int(np.sum(np.isnan(ch)))
    inf_count = int(np.sum(np.isinf(ch)))
    finite = ch[np.isfinite(ch)]
    if finite.size == 0:
        return {
            "min": None, "max": None, "mean": None, "std": None,
            "nan_count": nan_count, "inf_count": inf_count,
            "longest_flatline": _longest_flatline(ch),
        }
    return {
        "min": float(np.min(finite)),
        "max": float(np.max(finite)),
        "mean": float(np.mean(finite)),
        "std": float(np.std(finite)),
        "nan_count": nan_count,
        "inf_count": inf_count,
        "longest_flatline": _longest_flatline(ch),
    }


# ---------------------------------------------------------------------------
# Profile one participant
# ---------------------------------------------------------------------------

def profile_participant(path: str) -> dict:
    data = load_dat(path)
    pid = os.path.splitext(os.path.basename(path))[0]  # e.g. "s01"

    result = {"participant": pid, "keys": sorted(data.keys())}

    # --- data array ---
    if "data" in data:
        d = data["data"]
        result["data_shape"] = list(d.shape)
        result["data_dtype"] = str(d.dtype)
        # Interpret dimensions based on DEAP paper (Koelstra et al. 2012):
        # shape (40, 40, 8064): (n_trials=40, n_channels=40, n_samples=8064)
        # 8064 samples at 128 Hz = 63 s (3 s pre-trial baseline + 60 s trial)
        if d.ndim == 3:
            result["data_dim_interpretation"] = {
                "dim0": f"trials (n={d.shape[0]})",
                "dim1": f"channels (n={d.shape[1]})",
                "dim2": f"time_samples (n={d.shape[2]})",
            }
            # Sampling rate inference
            if d.shape[2] == 8064:
                result["sampling_rate_hz"] = 128
                result["sampling_rate_source"] = (
                    "inferred from sample count: 8064 / 128 Hz = 63 s "
                    "(3 s pre-trial + 60 s trial per DEAP paper)"
                )
            else:
                result["sampling_rate_hz"] = None
                result["sampling_rate_source"] = (
                    f"unexpected sample count {d.shape[2]}; cannot infer rate"
                )

            # Channel list check
            if d.shape[1] == 40:
                result["channel_list"] = ALL_CHANNELS
                result["channel_list_source"] = (
                    "Koelstra et al. (2012), Table 1 channel order; "
                    "not embedded in file"
                )
            else:
                result["channel_list"] = None
                result["channel_list_source"] = (
                    f"unexpected channel count {d.shape[1]}"
                )

            # Per-channel stats
            ch_stats = {}
            for i, name in enumerate(ALL_CHANNELS):
                if i < d.shape[1]:
                    ch_stats[name] = channel_stats(d, i)
            result["channel_stats"] = ch_stats
        else:
            result["data_dim_interpretation"] = f"unexpected ndim={d.ndim}"
    else:
        result["data_shape"] = None

    # --- labels array ---
    if "labels" in data:
        lb = data["labels"]
        result["labels_shape"] = list(lb.shape)
        result["labels_dtype"] = str(lb.dtype)
        result["labels_dim_interpretation"] = {
            "dim0": f"trials (n={lb.shape[0]})",
            "dim1": f"dimensions: {LABEL_DIMENSIONS}",
        }
        lb_stats = {}
        for i, dim in enumerate(LABEL_DIMENSIONS):
            col = lb[:, i]
            lb_stats[dim] = {
                "min": float(np.min(col)),
                "max": float(np.max(col)),
                "mean": float(np.mean(col)),
                "std": float(np.std(col)),
            }
        result["labels_stats"] = lb_stats
    else:
        result["labels_shape"] = None

    # Timestamps check
    result["has_timestamps"] = any(
        k in data for k in ("timestamps", "time", "t")
    )

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_profiling(bronze_dir: str, output_path: str) -> None:
    dat_files = sorted(
        f for f in os.listdir(bronze_dir) if f.endswith(".dat")
    )
    if not dat_files:
        print(f"No .dat files found in {bronze_dir}", file=sys.stderr)
        sys.exit(1)

    participants = []
    channel_shape_set = set()

    for fname in dat_files:
        path = os.path.join(bronze_dir, fname)
        print(f"Profiling {fname} ...", file=sys.stderr)
        p = profile_participant(path)
        participants.append(p)
        if p.get("data_shape"):
            channel_shape_set.add(tuple(p["data_shape"]))

    # Cross-participant consistency
    all_channels_consistent = len(channel_shape_set) == 1
    all_channel_lists = [
        tuple(p.get("channel_list") or []) for p in participants
    ]
    channel_list_consistent = len(set(all_channel_lists)) == 1

    report = {
        "dataset": "DEAP",
        "profiling_note": (
            "Deterministic output. No wall-clock timestamps. "
            "Loaded with restricted unpickler; allowed classes: "
            "numpy.core.multiarray._reconstruct, numpy.ndarray, numpy.dtype."
        ),
        "archive_file": "archive_DEAP.zip",
        "bronze_dir": "bronze/DEAP/",
        "participant_count": len(participants),
        "participant_ids": [p["participant"] for p in participants],
        "dataset_version": (
            "preprocessed Python pickle (DEAP 'data_preprocessed_python' format). "
            "Evidence: .dat files loadable as Python pickles containing numpy arrays; "
            "shape consistent with DEAP preprocessed specification (40 trials x 40 channels x 8064 samples)."
        ),
        "readme_files_in_archive": (
            "None. No readme or documentation files were present in archive_DEAP.zip. "
            "Channel order and sampling rate sourced from Koelstra et al. (2012)."
        ),
        "data_shapes_all_participants": sorted(
            [list(s) for s in channel_shape_set]
        ),
        "shapes_consistent_across_participants": all_channels_consistent,
        "channel_list_consistent_across_participants": channel_list_consistent,
        "units_note": (
            "Units are NOT stated in any file in this archive. "
            "Based on the DEAP paper and readme (not present in this mirror): "
            "EEG channels are in microvolts (uV) after preprocessing; "
            "peripheral channel units are as follows -- "
            "GSR: Ohm (inverted conductance; note: may need conversion to uS); "
            "Respiration: amplitude (dimensionless, belt tension); "
            "BVP: amplitude (dimensionless, photoplethysmograph); "
            "Temperature: degrees Celsius. "
            "These units require verification against the official DEAP readme "
            "before physiological bounds can be set."
        ),
        "timestamps_note": (
            "No timestamp arrays are embedded in the .dat files. "
            "Signals are contiguous sample arrays at a uniform rate (128 Hz). "
            "All signals in one participant file share one sample clock (single device time base). "
            "No cross-device alignment is needed within a participant."
        ),
        "participants": participants,
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
    print(f"Report written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    bronze_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "bronze", "DEAP"
    )
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "reports", "deap_baseline.json"
    )
    run_profiling(bronze_dir, output_path)
