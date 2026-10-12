"""
Silver-layer plausibility check for WESAD dataset (Task 5).

Checks whether measured signal values fall within the physiologically or
technically credible bounds registered in config/physiological_ranges.yaml.
Produces a findings record only — never modifies data (cleaning is Task 8).

Gate: refuses to run if config/physiological_ranges.yaml is not signed off.

Signal coverage
---------------
RespiBAN chest (raw 16-bit ADC; transfer functions applied in-memory):
  ECG   (CH1) → config key "ECG", mV, device_rail bounds
  EMG   (CH3) → config key "EMG", mV, device_rail bounds
  RESP  (CH8) → config key "respiration", %, device_rail bounds
  ACC   (CH5–7) → config key "accelerometry_respiban", g, device_rail bounds
  CH2 (EDA, raw ADC)  — NOT in config; skipped, noted as no-bound-defined.
  CH4 (TEMP, raw ADC) — NOT in config; skipped, noted as no-bound-defined.
    (These are chest-sensor channels distinct from the E4 EDA/TEMP signals;
     the config EDA/skin_temperature entries apply to the E4 wrist device only.)

E4 wristband (values already in physical or near-physical units):
  EDA  → config key "EDA",              µS  (below=physiological_implausible,
                                              above=device_capacity per Tobi 27-Aug)
  TEMP → config key "skin_temperature", °C  (physiological_implausible)
  HR   → config key "heart_rate",       bpm (physiological_implausible)
  ACC  → config key "accelerometry_e4", g   (device_rail; stored in 1/64 g units)
  BVP  — EXCLUDED (no unit or range documented; supervisor confirmed, 27-Aug)
  IBI  — EXCLUDED (HRV derivation out of scope; supervisor confirmed, 27-Aug)

Breach classification
---------------------
Each violation is tagged with one of:
  "physiological_implausible" — value is outside a bound that represents the
      credible physiological range; likely candidate for corrupt or artifact data.
  "device_capacity"           — value has reached the sensor's hardware ceiling;
      per supervisor guidance (Tobi, 27-Aug) these are flagged and RETAINED as
      "device reached measurement capacity," not treated as corrupt.
  "device_rail"               — value has exceeded the sensor's design output
      range (e.g. calibration window, full-scale rail); not indicative of
      corruption on its own.

RespiBAN transfer functions (wesad_readme.pdf §II.1)
----------------------------------------------------
  ECG/EMG (mV):   (raw / 65536 − 0.5) × 3
  RESP (%):       (raw / 65536 − 0.5) × 100
  ACC (g):        (raw − 28000) / (38000 − 28000) × 2 − 1

Note: ECG, EMG, and RESP config bounds map exactly to the full 16-bit ADC
range ([0, 65535]). Since conformance (Task 3) already verified ADC bounds,
these channels are guaranteed to produce 0 plausibility violations. They are
still checked here for completeness and auditability.

Output: reports/wesad_plausibility.json
Deterministic: same input always produces identical output.
Never writes to, moves, or modifies anything in bronze/.
"""

import datetime
import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_WESAD = ROOT / "bronze" / "WESAD"
REPORTS = ROOT / "reports"
CONFIG_DIR = ROOT / "config"

# ── RespiBAN transfer-function constants (from wesad_readme.pdf §II.1) ────────
_VCC = 3.0
_CHAN_BIT = 65536.0
_ACC_CMIN = 28000.0
_ACC_CMAX = 38000.0

# E4 ACC: stored in 1/64 g units; config bounds are in g.
_E4_ACC_G_TO_STORED = 64.0

RESPIBAN_COLS = ["nSeq", "DI", "CH1", "CH2", "CH3", "CH4", "CH5", "CH6", "CH7", "CH8"]

# ── Breach classification per config key (below_min_class, above_max_class) ───
# Sourced from config provenance notes and supervisor guidance (Tobi, 27-Aug).
BREACH_CLASS: dict[str, tuple[str, str]] = {
    "ECG":                    ("device_rail",               "device_rail"),
    "EMG":                    ("device_rail",               "device_rail"),
    "respiration":            ("device_rail",               "device_rail"),
    "accelerometry_respiban": ("device_rail",               "device_rail"),
    "EDA":                    ("physiological_implausible", "device_capacity"),
    "skin_temperature":       ("physiological_implausible", "physiological_implausible"),
    "heart_rate":             ("physiological_implausible", "physiological_implausible"),
    "accelerometry_e4":       ("device_rail",               "device_rail"),
}

# Maximum number of violation sample indices to list in the report.
_MAX_REPORTED_INDICES = 20


# ── Config loading ─────────────────────────────────────────────────────────────

def _json_default(obj):
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _load_config() -> tuple[dict, dict]:
    """Load and validate both config files. Enforce the sign-off gate."""
    def _read(path):
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    ranges = _read(CONFIG_DIR / "physiological_ranges.yaml")
    thresholds = _read(CONFIG_DIR / "thresholds.yaml")

    if not ranges.get("meta", {}).get("signed_off"):
        raise RuntimeError(
            "config/physiological_ranges.yaml is not signed off. "
            "Task 5 (plausibility check) must not run until meta.signed_off is true."
        )
    return thresholds, ranges


# ── Core checking helper ───────────────────────────────────────────────────────

def _check_series(
    values: "pd.Series",
    cfg_min: float,
    cfg_max: float,
    below_class: str,
    above_class: str,
    threshold: float,
    label: str = "",
) -> dict:
    """
    Check a single series of physical-unit values against [cfg_min, cfg_max].
    Returns a findings dict with violation counts, rates, and classification.
    NaNs are excluded from the comparison (they are a completeness concern,
    not a plausibility concern).
    """
    n_total = len(values)
    n_nan = int(values.isna().sum())
    valid = values.dropna()

    below_mask = valid < cfg_min
    above_mask = valid > cfg_max
    n_below = int(below_mask.sum())
    n_above = int(above_mask.sum())
    n_violations = n_below + n_above
    rate = round(n_violations / n_total, 8) if n_total > 0 else 0.0

    phys_impl = (
        (n_below if below_class == "physiological_implausible" else 0)
        + (n_above if above_class == "physiological_implausible" else 0)
    )
    device_flagged = n_violations - phys_impl

    result: dict = {
        "cfg_min": cfg_min,
        "cfg_max": cfg_max,
        "breach_class_below_min": below_class,
        "breach_class_above_max": above_class,
        "n_total": n_total,
        "n_nan_excluded": n_nan,
        "n_below_min": n_below,
        "n_above_max": n_above,
        "n_violations": n_violations,
        "physiological_implausible_count": phys_impl,
        "device_flagged_count": device_flagged,
        "violation_rate": rate,
        "passes_threshold": rate <= threshold,
    }

    if 0 < n_violations <= _MAX_REPORTED_INDICES:
        result["violation_indices"] = sorted(
            valid.index[below_mask | above_mask].tolist()
        )
    elif n_violations > _MAX_REPORTED_INDICES:
        result["first_violation_indices"] = sorted(
            valid.index[below_mask | above_mask].tolist()
        )[:_MAX_REPORTED_INDICES]
        result["violation_indices_truncated"] = True

    return result


# ── E4 wristband plausibility ─────────────────────────────────────────────────

def _check_e4_signal(
    csv_path: Path,
    config_key: str,
    wesad_cfg: dict,
    threshold: float,
    stored_unit_factor: float = 1.0,
) -> dict:
    """
    Check one E4 fixed-rate CSV against its config bounds.
    stored_unit_factor: multiply config g-bounds by this to get stored units
    (used for ACC: 1/64g stored → factor=64; all others: factor=1).
    """
    raw = pd.read_csv(csv_path, header=None, dtype=str)
    declared_hz = float(raw.iloc[1, 0].strip())
    data = (
        raw.iloc[2:]
        .apply(lambda col: pd.to_numeric(col, errors="coerce"))
        .reset_index(drop=True)
    )

    cfg = wesad_cfg[config_key]
    cfg_min = float(cfg["min"]) * stored_unit_factor
    cfg_max = float(cfg["max"]) * stored_unit_factor
    below_class, above_class = BREACH_CLASS[config_key]
    unit = cfg.get("unit", "")

    if stored_unit_factor != 1.0:
        unit = f"stored_units (1/{int(stored_unit_factor)}g)"

    n_cols = data.shape[1]
    findings: dict = {
        "config_key": config_key,
        "unit": unit,
        "declared_hz": declared_hz,
        "n_columns": n_cols,
        "excluded": False,
    }

    if n_cols == 1:
        col_result = _check_series(
            data.iloc[:, 0], cfg_min, cfg_max,
            below_class, above_class, threshold,
        )
        findings.update(col_result)
        # Annotate known E4 TEMP warm-up artifact when detected.
        if (config_key == "skin_temperature"
                and col_result["n_violations"] > 0
                and col_result.get("n_above_max", 0) > 0):
            viol_idx = col_result.get(
                "violation_indices", col_result.get("first_violation_indices", [])
            )
            sentinel_vals = data.iloc[viol_idx, 0].tolist() if viol_idx else []
            all_leading = viol_idx == list(range(len(viol_idx)))
            is_sentinel = all(v > 300 for v in sentinel_vals)
            if all_leading and is_sentinel:
                findings["artifact_annotation"] = {
                    "pattern": "E4_TEMP_initialization",
                    "description": (
                        f"All {len(viol_idx)} above-max violation(s) are confined "
                        f"to the first sample(s) (indices {viol_idx}) with value(s) "
                        f"~{round(sentinel_vals[0], 2)} °C. Known Empatica E4 NTC "
                        "thermistor warm-up artifact — sensor outputs an unphysical "
                        "sentinel value for ~1 s while stabilising. To be stripped "
                        "in Task 8 (Silver cleaning)."
                    ),
                    "sentinel_values": sentinel_vals,
                    "violation_indices": viol_idx,
                }
    else:
        # Multi-column (ACC: x, y, z)
        col_names = ["x", "y", "z"][: n_cols]
        per_axis: dict = {}
        total_n = 0
        total_below = 0
        total_above = 0
        for i, axis in enumerate(col_names):
            r = _check_series(
                data.iloc[:, i], cfg_min, cfg_max,
                below_class, above_class, threshold,
            )
            per_axis[axis] = r
            total_n += r["n_total"]
            total_below += r["n_below_min"]
            total_above += r["n_above_max"]
        n_viol = total_below + total_above
        findings["per_axis"] = per_axis
        findings["n_total"] = total_n
        findings["n_below_min"] = total_below
        findings["n_above_max"] = total_above
        findings["n_violations"] = n_viol
        findings["physiological_implausible_count"] = (
            (total_below if below_class == "physiological_implausible" else 0)
            + (total_above if above_class == "physiological_implausible" else 0)
        )
        findings["device_flagged_count"] = (
            n_viol - findings["physiological_implausible_count"]
        )
        findings["violation_rate"] = (
            round(n_viol / total_n, 8) if total_n > 0 else 0.0
        )
        findings["passes_threshold"] = findings["violation_rate"] <= threshold

    return findings


def check_e4(
    participant_dir: Path,
    wesad_cfg: dict,
    threshold: float,
    e4_path_overrides: "dict[str, Path] | None" = None,
) -> dict:
    """
    e4_path_overrides: optional dict {modality: Path} — when provided, the
    override path is used instead of the default bronze path for that modality.
    Used by post-cleaning checks to read Silver TEMP while keeping all other
    signals on bronze.
    """
    pid = participant_dir.name
    e4_dir = participant_dir / f"{pid}_E4_Data"
    result: dict = {}

    # EDA: stored in µS; check directly against config bounds.
    eda_path = (e4_path_overrides or {}).get("EDA") or e4_dir / "EDA.csv"
    if eda_path.exists():
        result["EDA"] = _check_e4_signal(eda_path, "EDA", wesad_cfg, threshold)
    else:
        result["EDA"] = {"excluded": False, "error": "file_not_found"}

    # TEMP: stored in °C.
    temp_path = (e4_path_overrides or {}).get("TEMP") or e4_dir / "TEMP.csv"
    if temp_path.exists():
        result["TEMP"] = _check_e4_signal(
            temp_path, "skin_temperature", wesad_cfg, threshold
        )
    else:
        result["TEMP"] = {"excluded": False, "error": "file_not_found"}

    # HR: stored in bpm.
    hr_path = (e4_path_overrides or {}).get("HR") or e4_dir / "HR.csv"
    if hr_path.exists():
        result["HR"] = _check_e4_signal(
            hr_path, "heart_rate", wesad_cfg, threshold
        )
    else:
        result["HR"] = {"excluded": False, "error": "file_not_found"}

    # ACC: stored in 1/64 g; config bounds are in g → multiply by 64.
    acc_path = (e4_path_overrides or {}).get("ACC") or e4_dir / "ACC.csv"
    if acc_path.exists():
        result["ACC"] = _check_e4_signal(
            acc_path, "accelerometry_e4", wesad_cfg, threshold,
            stored_unit_factor=_E4_ACC_G_TO_STORED,
        )
    else:
        result["ACC"] = {"excluded": False, "error": "file_not_found"}

    # BVP: excluded — no unit or range documented; supervisor confirmed 27-Aug.
    result["BVP"] = {
        "excluded": True,
        "reason": (
            "BVP is excluded from plausibility checking. No device output range "
            "is documented in WESAD materials. Supervisor (Dr. Tobias Cibis, "
            "2026-08-27) confirmed exclusion."
        ),
    }

    # IBI: excluded — HRV derivation out of scope; supervisor confirmed 27-Aug.
    result["IBI"] = {
        "excluded": True,
        "reason": (
            "IBI is excluded from plausibility checking. HRV derivation requires "
            "≥3 min consecutive intervals and a different discretisation; HRV is "
            "out of scope. Supervisor (Dr. Tobias Cibis, 2026-08-27) confirmed "
            "exclusion."
        ),
    }

    return result


# ── RespiBAN chest plausibility ───────────────────────────────────────────────

def check_respiban(txt_path: Path, wesad_cfg: dict, threshold: float) -> dict:
    # Load data once; apply transfer functions per channel group.
    with open(txt_path, "r", encoding="utf-8", errors="replace") as fh:
        fh.readline()
        meta_line = fh.readline()
    json_str = meta_line.lstrip("# ").strip()
    meta = json.loads(json_str)
    device_key = next(iter(meta))
    declared_hz = int(meta[device_key]["sampling rate"])

    data = pd.read_csv(
        txt_path, sep="\t", skiprows=3, header=None,
        usecols=range(10), dtype={0: int},
    )
    data.columns = RESPIBAN_COLS

    result: dict = {}

    # ── ECG (CH1) ──
    cfg = wesad_cfg["ECG"]
    raw = pd.to_numeric(data["CH1"], errors="coerce")
    phys = (raw / _CHAN_BIT - 0.5) * _VCC   # mV
    r = _check_series(
        phys, float(cfg["min"]), float(cfg["max"]),
        *BREACH_CLASS["ECG"], threshold,
    )
    result["ECG"] = {
        "config_key": "ECG", "channel": "CH1", "unit": "mV",
        "declared_hz": declared_hz, "excluded": False, **r,
    }

    # ── EMG (CH3) ──
    cfg = wesad_cfg["EMG"]
    raw = pd.to_numeric(data["CH3"], errors="coerce")
    phys = (raw / _CHAN_BIT - 0.5) * _VCC   # mV
    r = _check_series(
        phys, float(cfg["min"]), float(cfg["max"]),
        *BREACH_CLASS["EMG"], threshold,
    )
    result["EMG"] = {
        "config_key": "EMG", "channel": "CH3", "unit": "mV",
        "declared_hz": declared_hz, "excluded": False, **r,
    }

    # ── Respiration (CH8) ──
    cfg = wesad_cfg["respiration"]
    raw = pd.to_numeric(data["CH8"], errors="coerce")
    phys = (raw / _CHAN_BIT - 0.5) * 100.0   # %
    r = _check_series(
        phys, float(cfg["min"]), float(cfg["max"]),
        *BREACH_CLASS["respiration"], threshold,
    )
    result["RESP"] = {
        "config_key": "respiration", "channel": "CH8", "unit": "%",
        "declared_hz": declared_hz, "excluded": False, **r,
    }

    # ── Accelerometry (CH5 = x, CH6 = y, CH7 = z) ──
    cfg = wesad_cfg["accelerometry_respiban"]
    cfg_min = float(cfg["min"])
    cfg_max = float(cfg["max"])
    below_class, above_class = BREACH_CLASS["accelerometry_respiban"]
    acc_axes = {"x": "CH5", "y": "CH6", "z": "CH7"}
    per_axis: dict = {}
    total_n = total_below = total_above = 0
    for axis, ch in sorted(acc_axes.items()):
        raw = pd.to_numeric(data[ch], errors="coerce")
        phys = (raw - _ACC_CMIN) / (_ACC_CMAX - _ACC_CMIN) * 2.0 - 1.0  # g
        r = _check_series(phys, cfg_min, cfg_max, below_class, above_class, threshold)
        r["channel"] = ch
        per_axis[axis] = r
        total_n += r["n_total"]
        total_below += r["n_below_min"]
        total_above += r["n_above_max"]

    n_viol = total_below + total_above
    phys_impl = (
        (total_below if below_class == "physiological_implausible" else 0)
        + (total_above if above_class == "physiological_implausible" else 0)
    )
    result["ACC"] = {
        "config_key": "accelerometry_respiban",
        "channels": "CH5(x) CH6(y) CH7(z)",
        "unit": "g",
        "declared_hz": declared_hz,
        "excluded": False,
        "per_axis": per_axis,
        "n_total": total_n,
        "n_below_min": total_below,
        "n_above_max": total_above,
        "n_violations": n_viol,
        "physiological_implausible_count": phys_impl,
        "device_flagged_count": n_viol - phys_impl,
        "violation_rate": round(n_viol / total_n, 8) if total_n > 0 else 0.0,
        "passes_threshold": (
            round(n_viol / total_n, 8) if total_n > 0 else 0.0
        ) <= threshold,
    }

    # ── CH2 (EDA) and CH4 (TEMP): not in config ──
    for label, ch, reason in [
        ("EDA_chest", "CH2",
         "RespiBAN CH2 (EDA) has no config bound. The config EDA entry applies "
         "to the E4 wrist sensor (stored in µS); the chest EDA is raw 16-bit ADC "
         "requiring a different transfer function, and no separate config bound was "
         "defined for it."),
        ("TEMP_chest", "CH4",
         "RespiBAN CH4 (TEMP) has no config bound. The config skin_temperature entry "
         "applies to the E4 wrist sensor (stored in °C); the chest TEMP is raw ADC "
         "with a different transfer function, and no separate config bound was defined."),
    ]:
        result[label] = {"channel": ch, "excluded": True, "reason": reason}

    return result


# ── Surprise check ────────────────────────────────────────────────────────────

def _check_for_surprises(participants: dict, n_participants: int) -> None:
    """
    Scan results for unexpected physiological_implausible violations.
    Expected:
      E4 TEMP: ≤ 4 per participant (warm-up artifact), max 4 × n_participants total.
      All other signals: 0 physiological_implausible violations.
    Raises RuntimeError if anything unexpected is found.
    """
    unexpected: list[str] = []

    for pid, p in sorted(participants.items()):
        # E4 checks
        e4 = p["e4"]
        for mod, findings in sorted(e4.items()):
            if findings.get("excluded"):
                continue
            phys = findings.get("physiological_implausible_count", 0)
            if mod == "TEMP" and phys > 4:
                unexpected.append(
                    f"{pid}/E4/TEMP: {phys} physiological_implausible violations "
                    f"(expected ≤ 4 from warm-up artifact)"
                )
            elif mod != "TEMP" and phys > 0:
                unexpected.append(
                    f"{pid}/E4/{mod}: {phys} physiological_implausible violations "
                    f"(expected 0)"
                )
        # RespiBAN checks
        chest = p["chest"]
        for sig, findings in sorted(chest.items()):
            if findings.get("excluded"):
                continue
            phys = findings.get("physiological_implausible_count", 0)
            if phys > 0:
                unexpected.append(
                    f"{pid}/chest/{sig}: {phys} physiological_implausible violations "
                    f"(expected 0 — all RespiBAN bounds are device_rail)"
                )

    if unexpected:
        raise RuntimeError(
            "UNEXPECTED physiological_implausible violations detected. "
            "Investigate before accepting these results:\n"
            + "\n".join(f"  {u}" for u in unexpected)
        )

    print("  Surprise check passed: no unexpected physiological_implausible violations.")


# ── Aggregate summary ─────────────────────────────────────────────────────────

def _summarise(participants: dict, threshold: float) -> dict:
    total_n = total_viol = phys_impl_total = device_flagged_total = 0
    per_participant_passes: dict[str, bool] = {}

    for pid, p in sorted(participants.items()):
        pid_passes = True

        for mod, findings in sorted(p["e4"].items()):
            if findings.get("excluded") or findings.get("error"):
                continue
            n = findings.get("n_total", 0)
            if "per_axis" in findings:
                n = findings.get("n_total", 0)
            total_n += n
            v = findings.get("n_violations", 0)
            total_viol += v
            phys_impl_total += findings.get("physiological_implausible_count", 0)
            device_flagged_total += findings.get("device_flagged_count", 0)
            if not findings.get("passes_threshold", True):
                pid_passes = False

        for sig, findings in sorted(p["chest"].items()):
            if findings.get("excluded") or findings.get("error"):
                continue
            n = findings.get("n_total", 0)
            total_n += n
            v = findings.get("n_violations", 0)
            total_viol += v
            phys_impl_total += findings.get("physiological_implausible_count", 0)
            device_flagged_total += findings.get("device_flagged_count", 0)
            if not findings.get("passes_threshold", True):
                pid_passes = False

        per_participant_passes[pid] = pid_passes

    overall_rate = round(total_viol / total_n, 8) if total_n > 0 else 0.0
    phys_rate = round(phys_impl_total / total_n, 8) if total_n > 0 else 0.0
    device_rate = round(device_flagged_total / total_n, 8) if total_n > 0 else 0.0

    dataset_passes = overall_rate <= threshold and all(per_participant_passes.values())

    return {
        "threshold_max_plausibility_failure_rate": threshold,
        "total_samples_checked": total_n,
        "total_violations": total_viol,
        "overall_failure_rate": overall_rate,
        "physiological_implausible_rate": phys_rate,
        "physiological_implausible_count": phys_impl_total,
        "device_flagged_rate": device_rate,
        "device_flagged_count": device_flagged_total,
        "per_participant_passes": per_participant_passes,
        "dataset_passes_threshold": dataset_passes,
        "note_excluded": (
            "BVP and IBI are excluded from plausibility checking per supervisor "
            "confirmation (Dr. Tobias Cibis, 2026-08-27). RespiBAN CH2 (EDA) and "
            "CH4 (TEMP) have no config bounds and are not checked."
        ),
    }


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    thresholds, ranges = _load_config()
    threshold = float(thresholds["validity"]["max_plausibility_failure_rate"])
    wesad_cfg = ranges["wesad"]

    print(f"  Threshold: max_plausibility_failure_rate = {threshold}")
    print(f"  Config signed off by: {ranges['meta']['signed_off_by']}, "
          f"{ranges['meta']['date_locked']}")

    REPORTS.mkdir(exist_ok=True)

    participant_dirs = sorted(
        (d for d in BRONZE_WESAD.iterdir() if d.is_dir()),
        key=lambda p: p.name,
    )

    participants: dict = {}
    for pdir in participant_dirs:
        print(f"  Checking {pdir.name} ...")
        pid = pdir.name
        e4 = check_e4(pdir, wesad_cfg, threshold)
        txt_path = pdir / f"{pid}_respiban.txt"
        chest = (
            check_respiban(txt_path, wesad_cfg, threshold)
            if txt_path.exists()
            else {"error": "file_not_found"}
        )
        participants[pid] = {"chest": chest, "e4": e4}

    print("  Running surprise check ...")
    _check_for_surprises(participants, len(participants))

    summary = _summarise(participants, threshold)

    report = {
        "dataset": "WESAD",
        "check": "plausibility",
        "config_ranges_signed_off_by": str(ranges["meta"]["signed_off_by"]),
        "config_ranges_date_locked": ranges["meta"]["date_locked"],
        "config_thresholds_date_locked": thresholds["meta"]["date_locked"],
        "n_participants": len(participants),
        "participant_ids": sorted(participants.keys()),
        "participants": participants,
        "summary": summary,
    }

    output_path = REPORTS / "wesad_plausibility.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True, default=_json_default)

    print(f"\nPlausibility report written to: {output_path}")
    print(f"Overall failure rate           : {summary['overall_failure_rate']}")
    print(f"  Physiological-implausible    : {summary['physiological_implausible_rate']} "
          f"({summary['physiological_implausible_count']} samples)")
    print(f"  Device-flagged               : {summary['device_flagged_rate']} "
          f"({summary['device_flagged_count']} samples)")
    print(f"Dataset passes threshold       : {summary['dataset_passes_threshold']}")


if __name__ == "__main__":
    main()
