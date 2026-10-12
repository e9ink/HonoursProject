"""
Silver-layer conformance check for WESAD dataset (Task 3).

Verifies each signal against three classes of constraint:
  1. Format   — files are parseable; headers meet the declared structure.
  2. Sampling — declared sampling rates match the expected rates for each
                modality (E4) or match the JSON-header declaration (RespiBAN).
  3. Range    — data values lie within the device's documented output range.

Known structural quirks that are NOT violations:
  - E4 HR start_time_unix is always exactly 10 s later than other E4 channels.
    This is a documented E4 firmware export behaviour, not a recording defect.
  - E4 CSVs carry no per-sample timestamps, so the actual inter-sample interval
    cannot be independently verified.  The declared rate is reported but the
    absence of per-sample timestamps is NOT flagged as a sampling violation.

Constraints sourced from config:
  - config/physiological_ranges.yaml: device-output ranges for E4 signals.
    This file must be signed off (meta.signed_off: true) before its bounds
    are used; the check aborts if the gate is not clear.
  - config/thresholds.yaml: max_conformance_violation_rate (recorded in
    the output for reference; pass/fail is assessed in Task 11).

RespiBAN raw ADC range is derived from the resolution field in each
participant's own JSON header (not from config), because it is a hardware
property declared in the data itself.

Output: reports/wesad_conformance.json
Deterministic: same input always produces identical output.
Never writes to, moves, or modifies anything in bronze/.
"""

import datetime
import json
from pathlib import Path

import pandas as pd
import yaml


def _json_default(obj):
    """Serialize types that json.dump can't handle (e.g. yaml date objects)."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_WESAD = ROOT / "bronze" / "WESAD"
REPORTS = ROOT / "reports"
CONFIG_DIR = ROOT / "config"

# Expected E4 sampling rates (Hz) per modality.
# Source: WESAD README (Schmidt et al., 2018) and E4 documentation.
E4_EXPECTED_HZ: dict[str, float] = {
    "ACC": 32.0,
    "BVP": 64.0,
    "EDA": 4.0,
    "HR": 1.0,
    "TEMP": 4.0,
}

# E4 ACC is stored in 1/64 g units; ±2 g hardware range → raw range ±128.
# This conversion factor is applied to the config g-bounds at runtime.
E4_ACC_STORED_UNIT_PER_G = 64.0

# E4 BVP: no device output range is documented anywhere in WESAD.
# Range conformance is therefore skipped for BVP.
BVP_RANGE_UNDOCUMENTED = True

# RespiBAN channel column names, in order.
RESPIBAN_COLS = ["nSeq", "DI", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"]
RESPIBAN_EXPECTED_HZ = 700


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def _load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_config() -> tuple[dict, dict]:
    """
    Load and validate config files. Returns (thresholds, ranges).
    Aborts if physiological_ranges.yaml is not signed off — its bounds are
    used for device-output range conformance checks.
    """
    thresholds = _load_yaml(CONFIG_DIR / "thresholds.yaml")
    ranges = _load_yaml(CONFIG_DIR / "physiological_ranges.yaml")

    if not ranges.get("meta", {}).get("signed_off"):
        raise RuntimeError(
            "config/physiological_ranges.yaml is not signed off "
            "(meta.signed_off is not true). Conformance range checks cannot "
            "run until bounds are approved."
        )
    return thresholds, ranges


def _e4_range_bounds(modality: str, ranges: dict) -> tuple[float, float] | None:
    """
    Return (min, max) in the file's stored units for an E4 modality, or None
    if no range check is defined for that modality.
    """
    wesad = ranges["wesad"]
    if modality == "EDA":
        return wesad["EDA"]["min"], wesad["EDA"]["max"]
    if modality == "TEMP":
        return wesad["skin_temperature"]["min"], wesad["skin_temperature"]["max"]
    if modality == "HR":
        return wesad["heart_rate"]["min"], wesad["heart_rate"]["max"]
    if modality == "ACC":
        # Config holds g-bounds; file stores in 1/64 g units.
        cfg_min = wesad["accelerometry_e4"]["min"]
        cfg_max = wesad["accelerometry_e4"]["max"]
        return cfg_min * E4_ACC_STORED_UNIT_PER_G, cfg_max * E4_ACC_STORED_UNIT_PER_G
    if modality == "BVP":
        return None  # device range not documented
    return None


# ---------------------------------------------------------------------------
# E4 wristband checks
# ---------------------------------------------------------------------------

def _check_e4_modality(csv_path: Path, modality: str, ranges: dict) -> dict:
    findings: dict = {}

    # --- Format ---
    try:
        raw = pd.read_csv(csv_path, header=None, dtype=str)
        start_time = float(raw.iloc[0, 0].strip())
        declared_hz = float(raw.iloc[1, 0].strip())
        raw_data = raw.iloc[2:].reset_index(drop=True)
        data = raw_data.apply(lambda col: pd.to_numeric(col, errors="coerce"))
        findings["format"] = {"ok": True}
    except Exception as exc:
        findings["format"] = {"ok": False, "error": str(exc)}
        return findings

    findings["start_time_unix"] = start_time
    findings["declared_hz"] = declared_hz

    # --- Sampling rate ---
    expected_hz = E4_EXPECTED_HZ[modality]
    hz_ok = declared_hz == expected_hz
    findings["sampling_rate"] = {
        "declared_hz": declared_hz,
        "expected_hz": expected_hz,
        "ok": hz_ok,
        "note": (
            "E4 CSVs carry no per-sample timestamps; actual inter-sample "
            "interval cannot be independently verified. Declared rate only."
        ),
    }
    if not hz_ok:
        findings["sampling_rate"]["violation"] = (
            f"Declared {declared_hz} Hz does not match expected {expected_hz} Hz."
        )

    # --- Non-numeric check ---
    # An empty cell is genuinely missing (completeness's concern).
    # A present-but-non-parseable cell is malformed data (conformance's concern).
    genuinely_empty = raw_data.apply(
        lambda col: col.map(
            lambda v: pd.isna(v) or (isinstance(v, str) and v.strip() == "")
        )
    )
    n_non_numeric = int((data.isna() & ~genuinely_empty).sum().sum())
    findings["non_numeric"] = {
        "n_non_numeric": n_non_numeric,
        "ok": n_non_numeric == 0,
    }

    # --- Range ---
    bounds = _e4_range_bounds(modality, ranges)
    if bounds is None:
        findings["range"] = {
            "checked": False,
            "reason": "No device output range documented for this modality.",
        }
    else:
        rmin, rmax = bounds
        n_samples = len(data)
        n_cols = data.shape[1]
        total_cells = n_samples * n_cols

        # Count cells below min or above max (NaNs already reported via missingness).
        below = int((data < rmin).sum().sum())
        above = int((data > rmax).sum().sum())
        n_violations = below + above
        rate = round(n_violations / total_cells, 8) if total_cells > 0 else 0.0

        range_entry: dict = {
            "checked": True,
            "range_min": rmin,
            "range_max": rmax,
            "n_samples": n_samples,
            "n_columns": n_cols,
            "total_cells": total_cells,
            "n_below_min": below,
            "n_above_max": above,
            "n_violations": n_violations,
            "violation_rate": rate,
            "ok": n_violations == 0,
        }
        if modality == "ACC":
            range_entry["stored_unit_note"] = (
                "ACC stored in 1/64 g units; bounds converted from config g-range "
                f"(±{int(rmax / E4_ACC_STORED_UNIT_PER_G)} g)."
            )
        if modality == "TEMP" and n_violations > 0:
            # Detect the E4 TEMP thermistor initialization artifact: the E4 NTC
            # temperature sensor outputs an unphysical sentinel value (~382 °C)
            # for the first ~1 second (4 samples at 4 Hz) while it stabilises.
            # If ALL above-max violations are confined to the leading samples and
            # the values are in the ~380 °C range, annotate as a known artifact.
            violation_indices = sorted(
                data.index[(data.iloc[:, 0] > rmax)].tolist()
            )
            n_above = above
            all_leading = violation_indices == list(range(n_above))
            sentinel_values = data.iloc[violation_indices, 0].tolist() if violation_indices else []
            is_sentinel = all(v > 300 for v in sentinel_values)
            if all_leading and is_sentinel:
                range_entry["artifact_annotation"] = {
                    "pattern": "E4_TEMP_initialization",
                    "description": (
                        "All above-max violations are confined to the first "
                        f"{n_above} sample(s) (indices {violation_indices}) with "
                        f"value(s) ~{round(sentinel_values[0], 2)} °C. This matches "
                        "the known Empatica E4 NTC thermistor warm-up behaviour: "
                        "the sensor outputs an unphysical sentinel value for "
                        "approximately 1 s while stabilising. These samples should "
                        "be stripped in the Silver cleaning step (Task 9)."
                    ),
                    "sentinel_values": sentinel_values,
                    "violation_indices": violation_indices,
                }
        findings["range"] = range_entry

    return findings


def check_e4(
    participant_dir: Path,
    ranges: dict,
    e4_path_overrides: "dict[str, Path] | None" = None,
) -> dict:
    """
    Check all E4 modalities for one participant.

    e4_path_overrides: optional dict {modality: Path} — when provided,
    the override path is used instead of the default bronze path for that
    modality.  Used by post-cleaning checks to read Silver TEMP while
    keeping all other signals on bronze.
    """
    pid = participant_dir.name
    e4_dir = participant_dir / f"{pid}_E4_Data"
    result: dict = {}
    for modality in sorted(E4_EXPECTED_HZ.keys()):
        csv_path = (
            (e4_path_overrides or {}).get(modality)
            or e4_dir / f"{modality}.csv"
        )
        if not csv_path.exists():
            result[modality] = {"format": {"ok": False, "error": "file_not_found"}}
            continue
        findings = _check_e4_modality(csv_path, modality, ranges)
        # Annotate HR's known 10-second start offset so it is not mistaken for
        # a defect by any downstream reader.
        if modality == "HR":
            findings["start_time_note"] = (
                "HR start_time_unix is structurally 10 s later than other E4 "
                "channels (documented E4 firmware export behaviour, not a defect)."
            )
        result[modality] = findings
    return result


# ---------------------------------------------------------------------------
# RespiBAN chest checks
# ---------------------------------------------------------------------------

def check_respiban(txt_path: Path) -> dict:
    findings: dict = {}

    # --- Format: header parseable ---
    try:
        with open(txt_path, "r", encoding="utf-8", errors="replace") as fh:
            fh.readline()              # "# OpenSignals Text File Format"
            meta_line = fh.readline()  # "# {JSON...}"
            end_line = fh.readline()   # "# EndOfHeader"

        json_str = meta_line.lstrip("# ").strip()
        meta = json.loads(json_str)
        device_key = next(iter(meta))
        device_info = meta[device_key]
        declared_hz = int(device_info["sampling rate"])
        resolution_list: list[int] = device_info.get("resolution", [])
        end_ok = end_line.strip() == "# EndOfHeader"
        findings["format"] = {"ok": True, "endofheader_present": end_ok}
    except Exception as exc:
        findings["format"] = {"ok": False, "error": str(exc)}
        return findings

    # --- Sampling rate ---
    hz_ok = declared_hz == RESPIBAN_EXPECTED_HZ
    findings["sampling_rate"] = {
        "declared_hz": declared_hz,
        "expected_hz": RESPIBAN_EXPECTED_HZ,
        "ok": hz_ok,
    }
    if not hz_ok:
        findings["sampling_rate"]["violation"] = (
            f"Declared {declared_hz} Hz does not match expected {RESPIBAN_EXPECTED_HZ} Hz."
        )

    # --- ADC resolution from JSON header ---
    n_channels = 8
    expected_bits = 16
    all_16bit = (
        len(resolution_list) == n_channels
        and all(b == expected_bits for b in resolution_list)
    )
    findings["adc_resolution"] = {
        "resolution_from_header": resolution_list,
        "expected_bits": expected_bits,
        "all_channels_16bit": all_16bit,
        "ok": all_16bit,
    }

    # ADC range derived from the declared resolution (not from config, because
    # the config holds post-conversion bounds, not raw ADC bounds).
    if all_16bit:
        adc_min = 0
        adc_max = 2**expected_bits - 1
    else:
        # Fall back to 16-bit assumption if resolution field is malformed.
        adc_min = 0
        adc_max = 65535

    # --- Load data ---
    try:
        data = pd.read_csv(
            txt_path,
            sep="\t",
            skiprows=3,
            header=None,
            usecols=range(10),
            dtype={0: int},
        )
        data.columns = RESPIBAN_COLS
    except Exception as exc:
        findings["data_load"] = {"ok": False, "error": str(exc)}
        return findings

    n_samples = len(data)
    findings["n_samples"] = n_samples

    # --- Column count ---
    findings["column_count"] = {
        "expected": len(RESPIBAN_COLS),
        "actual": data.shape[1],
        "ok": data.shape[1] == len(RESPIBAN_COLS),
    }

    # --- Per-channel raw ADC range ---
    channel_cols = [c for c in RESPIBAN_COLS if c.startswith("CH")]
    per_channel: dict = {}
    for ch in sorted(channel_cols):
        raw_col = data[ch]
        col = pd.to_numeric(raw_col, errors="coerce")
        n_total = len(col)
        # Detect non-numeric: present cells that failed numeric conversion.
        is_genuinely_empty = raw_col.isna() | (raw_col.astype(str).str.strip() == "")
        n_non_numeric = int((col.isna() & ~is_genuinely_empty).sum())
        below = int((col < adc_min).sum())
        above = int((col > adc_max).sum())
        n_violations = below + above
        rate = round(n_violations / n_total, 8) if n_total > 0 else 0.0
        per_channel[ch] = {
            "adc_min": adc_min,
            "adc_max": adc_max,
            "n_samples": n_total,
            "n_non_numeric": n_non_numeric,
            "n_below_min": below,
            "n_above_max": above,
            "n_violations": n_violations,
            "violation_rate": rate,
            "ok": n_violations == 0 and n_non_numeric == 0,
        }

    findings["per_channel_range"] = per_channel
    total_ch_cells = sum(v["n_samples"] for v in per_channel.values())
    total_ch_violations = sum(v["n_violations"] for v in per_channel.values())
    total_ch_non_numeric = sum(v["n_non_numeric"] for v in per_channel.values())
    findings["range_summary"] = {
        "total_cells_checked": total_ch_cells,
        "total_non_numeric": total_ch_non_numeric,
        "total_violations": total_ch_violations,
        "violation_rate": (
            round(total_ch_violations / total_ch_cells, 8)
            if total_ch_cells > 0
            else 0.0
        ),
        "ok": total_ch_violations == 0 and total_ch_non_numeric == 0,
    }

    return findings


# ---------------------------------------------------------------------------
# Per-participant coordinator
# ---------------------------------------------------------------------------

def check_participant(
    participant_dir: Path,
    ranges: dict,
    e4_path_overrides: "dict[str, Path] | None" = None,
) -> dict:
    pid = participant_dir.name
    txt_path = participant_dir / f"{pid}_respiban.txt"

    e4_findings = check_e4(participant_dir, ranges, e4_path_overrides)
    chest_findings = (
        check_respiban(txt_path)
        if txt_path.exists()
        else {"format": {"ok": False, "error": "file_not_found"}}
    )

    return {"chest": chest_findings, "e4": e4_findings}


# ---------------------------------------------------------------------------
# Aggregate violation counts
# ---------------------------------------------------------------------------

def _aggregate(participants: dict) -> dict:
    total_cells = 0
    total_violations = 0
    total_non_numeric = 0
    format_errors: list[str] = []
    sampling_violations: list[str] = []

    for pid, p in sorted(participants.items()):
        # E4
        for modality, m in sorted(p["e4"].items()):
            if not m.get("format", {}).get("ok", False):
                format_errors.append(f"{pid}/E4/{modality}: format error")
                continue
            sr = m.get("sampling_rate", {})
            if not sr.get("ok", True):
                sampling_violations.append(
                    f"{pid}/E4/{modality}: {sr.get('violation', 'rate mismatch')}"
                )
            rng = m.get("range", {})
            if rng.get("checked"):
                total_cells += rng["total_cells"]
                total_violations += rng["n_violations"]
            total_non_numeric += m.get("non_numeric", {}).get("n_non_numeric", 0)

        # RespiBAN
        chest = p["chest"]
        if not chest.get("format", {}).get("ok", False):
            format_errors.append(f"{pid}/chest: format error")
            continue
        sr = chest.get("sampling_rate", {})
        if not sr.get("ok", True):
            sampling_violations.append(
                f"{pid}/chest: {sr.get('violation', 'rate mismatch')}"
            )
        rs = chest.get("range_summary", {})
        if rs:
            total_cells += rs.get("total_cells_checked", 0)
            total_violations += rs.get("total_violations", 0)
            total_non_numeric += rs.get("total_non_numeric", 0)

    overall_rate = (
        round(total_violations / total_cells, 8) if total_cells > 0 else 0.0
    )
    return {
        "total_range_cells_checked": total_cells,
        "total_range_violations": total_violations,
        "overall_range_violation_rate": overall_rate,
        "total_non_numeric_violations": total_non_numeric,
        "format_errors": sorted(format_errors),
        "sampling_violations": sorted(sampling_violations),
        "n_format_errors": len(format_errors),
        "n_sampling_violations": len(sampling_violations),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    thresholds, ranges = load_config()
    threshold_rate = thresholds["completeness"]  # read full block for reference
    conf_threshold = thresholds["validity"]["max_conformance_violation_rate"]

    REPORTS.mkdir(exist_ok=True)

    participant_dirs = sorted(
        (d for d in BRONZE_WESAD.iterdir() if d.is_dir()),
        key=lambda p: p.name,
    )

    participants: dict = {}
    for pdir in participant_dirs:
        print(f"  Checking {pdir.name} ...")
        participants[pdir.name] = check_participant(pdir, ranges)

    summary = _aggregate(participants)
    passes = (
        summary["overall_range_violation_rate"] <= conf_threshold
        and summary["n_format_errors"] == 0
        and summary["n_sampling_violations"] == 0
        and summary["total_non_numeric_violations"] == 0
    )
    summary["threshold_max_conformance_violation_rate"] = conf_threshold
    summary["passes_threshold"] = passes

    report = {
        "dataset": "WESAD",
        "check": "conformance",
        "config_ranges_date_locked": ranges["meta"]["date_locked"],
        "config_thresholds_date_locked": thresholds["meta"]["date_locked"],
        "n_participants": len(participants),
        "participant_ids": sorted(participants.keys()),
        "participants": participants,
        "summary": summary,
    }

    output_path = REPORTS / "wesad_conformance.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True, default=_json_default)

    print(f"\nConformance report written to: {output_path}")
    print(f"Overall range violation rate : {summary['overall_range_violation_rate']}")
    print(f"Non-numeric violations       : {summary['total_non_numeric_violations']}")
    print(f"Format errors                : {summary['n_format_errors']}")
    print(f"Sampling violations          : {summary['n_sampling_violations']}")
    print(f"Passes threshold             : {passes}")


if __name__ == "__main__":
    main()
