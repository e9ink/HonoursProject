"""
Shared fixtures and file-writing helpers for CCP check tests.

All helpers write synthetic data in the exact same format the check code
expects, so planted faults are unambiguous and tests are self-contained.
No real WESAD data is read anywhere in this test suite.
"""
import json
from pathlib import Path


# ── File-writing helpers ────────────────────────────────────��──────────────────

def make_e4_csv(path: Path, values, hz: float = 4.0, start_time: float = 1000.0):
    """
    Write a minimal single-column E4 fixed-rate CSV.
    Row 0: start timestamp. Row 1: sample rate. Rows 2+: data values.
    values may contain numeric values or strings like 'nan' to test NaN handling.
    """
    lines = [str(start_time), str(hz)] + [str(v) for v in values]
    path.write_text("\n".join(lines), encoding="utf-8")


def make_e4_acc_csv(path: Path, rows, hz: float = 32.0, start_time: float = 1000.0):
    """
    Write a minimal 3-column E4 ACC CSV.
    rows: list of (x, y, z) tuples in stored 1/64g units.
    Header rows are padded to 3 columns so pandas reads the file as uniformly
    3-column (matching the format pd.read_csv with header=None expects).
    """
    lines = [f"{start_time},,", f"{hz},,"]
    lines += [f"{r[0]},{r[1]},{r[2]}" for r in rows]
    path.write_text("\n".join(lines), encoding="utf-8")


def make_respiban_txt(path: Path, rows, hz: int = 700):
    """
    Write a minimal RespiBAN txt file.
    rows: list of 10-element sequences (nSeq, DI, CH1..CH8).
    Produces the standard 3-line header + tab-separated body with trailing tab.
    """
    meta = json.dumps({
        "AA:BB:CC:DD:EE:FF": {
            "sampling rate": hz,
            "sensor": ["ECG", "EDA", "EMG", "TEMP", "XYZ", "XYZ", "XYZ", "RESPIRATION"],
            "resolution": [16, 16, 16, 16, 16, 16, 16, 16],
            "channels": [1, 2, 3, 4, 5, 6, 7, 8],
            "column": ["nSeq", "DI", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"],
        }
    })
    header = "\n".join([
        "# OpenSignals Text File Format",
        f"# {meta}",
        "# EndOfHeader",
    ])
    body = "\n".join("\t".join(str(v) for v in row) + "\t" for row in rows)
    path.write_text(header + "\n" + body, encoding="utf-8")


# ── Neutral row builders ───────────────────────────────────────────────────────

def neutral_respiban_row(nseq: int, di: int = 0) -> tuple:
    """
    A RespiBAN row with all channels at in-bounds values.
      ECG/EMG (CH1,CH3): 32768 → (32768/65536-0.5)*3 = 0.0 mV  (in [-1.5, 1.5])
      EDA (CH2), TEMP (CH4): 32768 → not plausibility-checked
      ACC (CH5-7): 33000 → (33000-28000)/(38000-28000)*2-1 = 0.0 g  (in [-1, 1])
      RESP (CH8): 32768 → (32768/65536-0.5)*100 = 0.0 %  (in [-50, 50])
    """
    return (nseq, di, 32768, 32768, 32768, 32768, 33000, 33000, 33000, 32768)


# ── Fake config dicts (used in conformance and plausibility tests) ─────────────

FAKE_RANGES = {
    "meta": {"signed_off": True, "date_locked": "2026-09-09"},
    "wesad": {
        "ECG":                    {"unit": "mV",  "min": -1.5, "max":  1.5},
        "EMG":                    {"unit": "mV",  "min": -1.5, "max":  1.5},
        "respiration":            {"unit": "%",   "min": -50,  "max":  50},
        "accelerometry_respiban": {"unit": "g",   "min": -1,   "max":  1},
        "EDA":                    {"unit": "µS",  "min":  0,   "max": 100},
        "skin_temperature":       {"unit": "°C",  "min": 15,   "max":  42},
        "heart_rate":             {"unit": "bpm", "min": 20,   "max": 250},
        "accelerometry_e4":       {"unit": "g",   "min": -2,   "max":  2},
    },
}
