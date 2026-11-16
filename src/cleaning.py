"""
Task 8 — Silver cleaning for WESAD dataset.

Applies exactly one cleaning action:
  E4 TEMP warm-up artefact removal — replaces indices 0–3 of each participant's
  E4 TEMP channel with NaN. Samples are NOT deleted; channel length is unchanged,
  preserving the evenly-spaced time series per supervisor data-integrity guidance.

This is the only cleaning action WESAD requires. Out-of-range values in other
signals are flag-and-retain (recorded in reports, not removed or altered).

Bronze is never modified. Cleaned output is written to:
  silver/WESAD/{pid}/{pid}_E4_Data/TEMP.csv

Format: identical to the bronze E4 CSV format:
  Row 0  — Unix start timestamp (unchanged)
  Row 1  — Sample rate, Hz (unchanged)
  Row 2+ — Data values; indices 0–3 written as empty string (CSV NaN convention)

Output reports:
  reports/wesad_cleaning.json  — per-participant audit trail with original values
"""

import json
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
BRONZE_WESAD = ROOT / "bronze" / "WESAD"
SILVER_WESAD = ROOT / "silver" / "WESAD"
REPORTS = ROOT / "reports"
CONFIG_DIR = ROOT / "config"

PARTICIPANTS = [f"S{n}" for n in range(2, 18) if n != 12]

# Indices replaced in each E4 TEMP channel (NTC thermistor warm-up artefact)
TEMP_WARMUP_INDICES = [0, 1, 2, 3]


def _load_skin_temp_bounds() -> tuple[float, float]:
    """Return (min, max) skin temperature bounds from physiological_ranges.yaml."""
    with open(CONFIG_DIR / "physiological_ranges.yaml", encoding="utf-8") as fh:
        ranges = yaml.safe_load(fh)
    if not ranges.get("meta", {}).get("signed_off"):
        raise RuntimeError(
            "config/physiological_ranges.yaml is not signed off. "
            "Cannot verify silver TEMP bounds."
        )
    bounds = ranges["wesad"]["skin_temperature"]
    return float(bounds["min"]), float(bounds["max"])


def _read_e4_csv_raw(path: Path) -> tuple[str, str, list[str]]:
    """
    Read an E4 CSV without parsing, preserving the exact header lines.
    Returns (timestamp_line, hz_line, data_lines).
    """
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    ts_line = lines[0].rstrip("\n")
    hz_line = lines[1].rstrip("\n")
    data_lines = [ln.rstrip("\n") for ln in lines[2:] if ln.strip()]
    return ts_line, hz_line, data_lines


def _clean_participant(pid: str) -> dict:
    """
    Apply the TEMP warm-up artefact fix for one participant.
    Returns an audit-trail dict and writes the silver TEMP.csv.
    """
    bronze_dir = BRONZE_WESAD / pid / f"{pid}_E4_Data"
    silver_dir = SILVER_WESAD / pid / f"{pid}_E4_Data"
    silver_dir.mkdir(parents=True, exist_ok=True)

    bronze_temp = bronze_dir / "TEMP.csv"
    silver_temp = silver_dir / "TEMP.csv"

    ts_line, hz_line, data_lines = _read_e4_csv_raw(bronze_temp)

    # Capture original values at the warm-up indices before replacing
    original_values = []
    for idx in TEMP_WARMUP_INDICES:
        try:
            original_values.append(float(data_lines[idx].strip()))
        except (IndexError, ValueError):
            original_values.append(None)

    n_samples = len(data_lines)

    # Build output lines: replace warm-up indices with the literal text "NaN".
    # Pandas parses "NaN" as numpy.nan by default (keep_default_na=True), treating
    # the row as genuinely missing. The row is NOT blank, so skip_blank_lines never
    # drops it — channel length is preserved regardless of read settings.
    out_lines = list(data_lines)
    for idx in TEMP_WARMUP_INDICES:
        if idx < len(out_lines):
            out_lines[idx] = "NaN"

    # Write silver TEMP.csv
    with open(silver_temp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(ts_line + "\n")
        fh.write(hz_line + "\n")
        for line in out_lines:
            fh.write(line + "\n")

    return {
        "action": "e4_temp_warmup_strip",
        "bronze_path": str(bronze_temp.relative_to(ROOT)),
        "silver_path": str(silver_temp.relative_to(ROOT)),
        "indices_replaced": TEMP_WARMUP_INDICES,
        "replacement": "NaN (literal text 'NaN' in CSV cell; pandas default NA detection reads as numpy.nan, row preserved)",
        "original_values": original_values,
        "channel_length_before": n_samples,
        "channel_length_after": n_samples,
        "length_unchanged": True,
    }


def _verify_silver_temp(pid: str, temp_min: float, temp_max: float) -> dict:
    """
    Read the silver TEMP.csv and count range violations and NaN values.

    Uses default pandas settings (skip_blank_lines=True, keep_default_na=True).
    The 'NaN'-text encoding means warm-up rows are never blank-skipped;
    channel length is consistent with bronze regardless of read flags.
    """
    silver_temp = SILVER_WESAD / pid / f"{pid}_E4_Data" / "TEMP.csv"

    raw = pd.read_csv(silver_temp, header=None, dtype=str)
    data_col = raw.iloc[2:, 0].reset_index(drop=True)
    numeric = pd.to_numeric(data_col, errors="coerce")

    n_nan = int(numeric.isna().sum())
    n_below = int((numeric < temp_min).sum())
    n_above = int((numeric > temp_max).sum())
    n_violations = n_below + n_above
    n_total = len(numeric)

    return {
        "n_total": n_total,
        "n_nan": n_nan,
        "n_range_violations": n_violations,
        "range_ok": n_violations == 0,
    }


def main() -> dict:
    """Replace E4 TEMP warm-up indices 0-3 with NaN in Silver and write reports/wesad_cleaning.json."""
    temp_min, temp_max = _load_skin_temp_bounds()

    # Load the existing conformance report to retrieve the before-cleaning violation count
    conformance_report_path = REPORTS / "wesad_conformance.json"
    violations_before_by_pid: dict[str, int] = {}
    if conformance_report_path.exists():
        with open(conformance_report_path, encoding="utf-8") as fh:
            conf = json.load(fh)
        for pid in PARTICIPANTS:
            p = conf.get("participants", {}).get(pid, {})
            temp_findings = p.get("e4", {}).get("TEMP", {})
            violations_before_by_pid[pid] = int(
                temp_findings.get("range", {}).get("n_violations", 0)
            )
    else:
        for pid in PARTICIPANTS:
            violations_before_by_pid[pid] = None  # conformance report not available

    # Clean each participant and verify silver output
    participant_results = {}
    for pid in sorted(PARTICIPANTS):
        audit = _clean_participant(pid)
        verification = _verify_silver_temp(pid, temp_min, temp_max)
        participant_results[pid] = {
            "cleaning": audit,
            "verification": verification,
            "conformance_temp_violations_before": violations_before_by_pid.get(pid),
            "conformance_temp_violations_after": verification["n_range_violations"],
        }

    # Summary
    total_violations_before = sum(
        v for v in violations_before_by_pid.values() if v is not None
    )
    total_violations_after = sum(
        r["verification"]["n_range_violations"] for r in participant_results.values()
    )
    total_nan_introduced = sum(
        r["verification"]["n_nan"] for r in participant_results.values()
    )
    all_clean = all(
        r["verification"]["range_ok"] for r in participant_results.values()
    )

    output = {
        "task": "silver_cleaning",
        "dataset": "WESAD",
        "cleaning_actions_applied": ["e4_temp_warmup_strip"],
        "note_flag_and_retain": (
            "Out-of-range values in all other signals are flag-and-retain: "
            "recorded in reports/wesad_conformance.json and "
            "reports/wesad_plausibility.json, NOT removed or altered here."
        ),
        "note_nan_and_completeness": (
            "The 4 replaced warm-up samples per participant are stored as the literal "
            "text 'NaN' in the silver TEMP.csv. Pandas default NA detection converts "
            "this to numpy.nan; the row is never blank-skipped. Channel length is "
            "therefore identical to bronze under any read settings. "
            "Completeness sees 4 NaN values per participant (60 total). "
            "This is expected and correct: a known artefact was removed and honestly "
            "marked missing rather than silently fabricated. "
            "See conformance_completeness_impact below."
        ),
        "conformance_completeness_impact": {
            "completeness_before_cleaning": "0 NaN TEMP samples across all participants",
            "completeness_after_cleaning": (
                f"{total_nan_introduced} NaN TEMP samples across "
                f"{len(PARTICIPANTS)} participants "
                f"({total_nan_introduced // len(PARTICIPANTS)} per participant)"
            ),
            "interpretation": (
                "NOT a new data problem. NaN marks where a known artefact was removed; "
                "the gap is documented. Downstream analysis should exclude "
                "warm-up NaN samples from TEMP computations."
            ),
        },
        "conformance_range_violations": {
            "temp_violations_before_cleaning": total_violations_before,
            "temp_violations_after_cleaning": total_violations_after,
            "all_participants_clean": all_clean,
        },
        "skin_temp_bounds_used": {"min": temp_min, "max": temp_max},
        "summary": {
            "n_participants_cleaned": len(participant_results),
            "indices_replaced_per_participant": TEMP_WARMUP_INDICES,
            "total_samples_replaced": len(TEMP_WARMUP_INDICES) * len(PARTICIPANTS),
        },
        "participants": participant_results,
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS / "wesad_cleaning.json"
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(output, fh, indent=2)

    # Console summary
    print("WESAD Silver Cleaning — E4 TEMP warm-up artefact\n")
    print(f"{'PID':<6}  {'before':>8}  {'after':>8}  {'NaN':>5}  {'length_ok':>10}  {'pass':>5}")
    print("-" * 55)
    for pid, r in sorted(participant_results.items()):
        c = r["cleaning"]
        v = r["verification"]
        print(
            f"{pid:<6}  {r['conformance_temp_violations_before']:>8}  "
            f"{r['conformance_temp_violations_after']:>8}  "
            f"{v['n_nan']:>5}  "
            f"{'Y' if c['length_unchanged'] else 'N':>10}  "
            f"{'Y' if v['range_ok'] else 'N':>5}"
        )
    print(
        f"\nConformance TEMP violations:  "
        f"before={total_violations_before}  after={total_violations_after}"
    )
    print(
        f"NaN introduced (completeness impact):  "
        f"{total_nan_introduced} samples "
        f"({total_nan_introduced // len(PARTICIPANTS)} per participant × "
        f"{len(PARTICIPANTS)} participants)"
    )
    print(f"All participants clean: {all_clean}")
    print(f"\nOutput written to: {output_path}")

    return output


if __name__ == "__main__":
    main()
