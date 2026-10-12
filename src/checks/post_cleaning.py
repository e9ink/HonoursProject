"""
Post-cleaning CCP checks (Part 2 of quality-report fix).

Runs conformance, completeness, and plausibility on the effective cleaned
dataset:
    E4 TEMP   → read from silver/WESAD/<pid>/<pid>_E4_Data/TEMP.csv
    everything else → read from bronze/ (unchanged)

Intentional removals (E4 TEMP indices 0-3 for all 15 participants) are loaded
from reports/wesad_cleaning.json and excluded from the completeness missingness
rate, reported separately.

Outputs (original Bronze-baseline reports are NOT overwritten):
    reports/wesad_conformance_post_cleaning.json
    reports/wesad_completeness_post_cleaning.json
    reports/wesad_plausibility_post_cleaning.json

Read-only on bronze/ and silver/.
"""

import json
from pathlib import Path

import yaml

from src.checks import conformance as _conf
from src.checks import completeness as _comp
from src.checks import plausibility as _plaus

ROOT = Path(__file__).resolve().parent.parent.parent
BRONZE_WESAD = ROOT / "bronze" / "WESAD"
SILVER_WESAD = ROOT / "silver" / "WESAD"
REPORTS = ROOT / "reports"
CONFIG_DIR = ROOT / "config"


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def _load_thresholds() -> dict:
    with open(CONFIG_DIR / "thresholds.yaml", "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_ranges() -> dict:
    with open(CONFIG_DIR / "physiological_ranges.yaml", "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    if not cfg.get("meta", {}).get("signed_off", False):
        raise RuntimeError(
            "physiological_ranges.yaml: meta.signed_off is False. "
            "Plausibility check is gated until the file is signed off."
        )
    return cfg


def _load_cleaning_report() -> dict:
    path = REPORTS / "wesad_cleaning.json"
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# Post-cleaning surprise check (TEMP violations now expected = 0)
# ---------------------------------------------------------------------------

def _check_surprises_post_cleaning(participants: dict) -> None:
    """
    After cleaning, Silver TEMP has NaN at the warm-up indices.  Plausibility
    calls values.dropna() before checking, so those samples are invisible to
    the range check.  Expected violations for TEMP = 0 (all other signals
    unchanged at 0).
    """
    unexpected: list[str] = []
    for pid, p in sorted(participants.items()):
        for mod, findings in sorted(p["e4"].items()):
            if findings.get("excluded") or findings.get("error"):
                continue
            phys = findings.get("physiological_implausible_count", 0)
            if phys > 0:
                unexpected.append(
                    f"{pid}/E4/{mod}: {phys} physiological_implausible violations "
                    f"(expected 0 after cleaning)"
                )
        for sig, findings in sorted(p["chest"].items()):
            if findings.get("excluded") or findings.get("error"):
                continue
            phys = findings.get("physiological_implausible_count", 0)
            if phys > 0:
                unexpected.append(
                    f"{pid}/chest/{sig}: {phys} physiological_implausible violations "
                    f"(expected 0)"
                )
    if unexpected:
        raise RuntimeError(
            "UNEXPECTED post-cleaning plausibility violations:\n"
            + "\n".join(f"  {u}" for u in unexpected)
        )
    print("  Post-cleaning surprise check passed: 0 violations for all signals.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    thresholds = _load_thresholds()
    ranges = _load_ranges()
    cleaning = _load_cleaning_report()

    completeness_threshold = float(thresholds["completeness"]["max_missingness_rate"])
    conformance_threshold = float(
        thresholds["validity"]["max_conformance_violation_rate"]
    )
    plausibility_threshold = float(
        thresholds["validity"]["max_plausibility_failure_rate"]
    )
    wesad_cfg = ranges["wesad"]

    REPORTS.mkdir(exist_ok=True)

    participant_dirs = sorted(
        (d for d in BRONZE_WESAD.iterdir() if d.is_dir()),
        key=lambda p: p.name,
    )

    conf_participants: dict = {}
    comp_participants: dict = {}
    plaus_participants: dict = {}

    for pdir in participant_dirs:
        pid = pdir.name
        print(f"  Post-cleaning checks for {pid} ...")

        # Silver TEMP path (must exist — cleaning wrote it for all 15 participants).
        silver_temp = SILVER_WESAD / pid / f"{pid}_E4_Data" / "TEMP.csv"
        if not silver_temp.exists():
            raise FileNotFoundError(
                f"Silver TEMP not found for {pid}: {silver_temp}\n"
                "Run src/cleaning.py first."
            )
        e4_overrides = {"TEMP": silver_temp}

        # Intentional removals for this participant (from cleaning report).
        indices = (
            cleaning["participants"][pid]["cleaning"]["indices_replaced"]
        )
        intentional_by_mod = {"TEMP": indices}

        # ── Conformance ────────────────────────────────────────────────────
        conf_participants[pid] = _conf.check_participant(
            pdir, ranges, e4_overrides
        )

        # ── Completeness ───────────────────────────────────────────────────
        e4 = _comp.check_e4(
            pdir, completeness_threshold, e4_overrides, intentional_by_mod
        )
        chest_path = pdir / f"{pid}_respiban.txt"
        chest = (
            _comp.check_chest(chest_path, completeness_threshold)
            if chest_path.exists()
            else {"error": "file_not_found", "sequence_gap_passes_threshold": False}
        )
        comp_participants[pid] = {"chest": chest, "e4": e4}

        # ── Plausibility ───────────────────────────────────────────────────
        e4_plaus = _plaus.check_e4(pdir, wesad_cfg, plausibility_threshold, e4_overrides)
        txt_path = pdir / f"{pid}_respiban.txt"
        chest_plaus = (
            _plaus.check_respiban(txt_path, wesad_cfg, plausibility_threshold)
            if txt_path.exists()
            else {"error": "file_not_found"}
        )
        plaus_participants[pid] = {"chest": chest_plaus, "e4": e4_plaus}

    # ── Conformance: aggregate and write ───────────────────────────────────
    print("\n  Aggregating post-cleaning conformance ...")
    conf_summary = _conf._aggregate(conf_participants)
    conf_report = {
        "dataset": "WESAD",
        "check": "conformance_post_cleaning",
        "note": (
            "Effective cleaned dataset: Silver TEMP + Bronze for all other signals. "
            "Original Bronze-baseline report (wesad_conformance.json) is unchanged."
        ),
        "n_participants": len(conf_participants),
        "participant_ids": sorted(conf_participants.keys()),
        "participants": conf_participants,
        "summary": conf_summary,
    }
    conf_path = REPORTS / "wesad_conformance_post_cleaning.json"
    with open(conf_path, "w", encoding="utf-8") as fh:
        json.dump(conf_report, fh, indent=2, sort_keys=True)
    print(f"  Conformance post-cleaning: {conf_summary['total_range_violations']} violations "
          f"(rate {conf_summary['overall_range_violation_rate']})")

    # ── Completeness: cross-check + aggregate + write ──────────────────────
    print("\n  Running post-cleaning completeness cross-check ...")
    _comp._cross_check_baseline(comp_participants)
    comp_summary = _comp._summarise(comp_participants, completeness_threshold)
    comp_report = {
        "dataset": "WESAD",
        "check": "completeness_post_cleaning",
        "note": (
            "Effective cleaned dataset: Silver TEMP + Bronze for all other signals. "
            "Intentional removals (E4 TEMP warm-up, 60 samples) are excluded from "
            "missingness_rate and reported separately. "
            "Original Bronze-baseline report (wesad_completeness.json) is unchanged."
        ),
        "n_participants": len(comp_participants),
        "participant_ids": sorted(comp_participants.keys()),
        "participants": comp_participants,
        "summary": comp_summary,
    }
    comp_path = REPORTS / "wesad_completeness_post_cleaning.json"
    with open(comp_path, "w", encoding="utf-8") as fh:
        json.dump(comp_report, fh, indent=2, sort_keys=True)
    print(f"  Completeness post-cleaning: e4_overall_missingness_rate = "
          f"{comp_summary['e4_overall_missingness_rate']}, "
          f"intentional_removals = {comp_summary.get('e4_intentional_removals', 0)}")

    # ── Plausibility: surprise check + aggregate + write ───────────────────
    print("\n  Running post-cleaning plausibility surprise check ...")
    _check_surprises_post_cleaning(plaus_participants)
    plaus_summary = _plaus._summarise(plaus_participants, plausibility_threshold)
    plaus_report = {
        "dataset": "WESAD",
        "check": "plausibility_post_cleaning",
        "note": (
            "Effective cleaned dataset: Silver TEMP + Bronze for all other signals. "
            "Silver TEMP has NaN at warm-up indices 0-3; these are excluded from "
            "range checks (dropna). "
            "Original Bronze-baseline report (wesad_plausibility.json) is unchanged."
        ),
        "n_participants": len(plaus_participants),
        "participant_ids": sorted(plaus_participants.keys()),
        "participants": plaus_participants,
        "summary": plaus_summary,
    }
    plaus_path = REPORTS / "wesad_plausibility_post_cleaning.json"
    with open(plaus_path, "w", encoding="utf-8") as fh:
        json.dump(
            plaus_report, fh, indent=2, sort_keys=True,
            default=_plaus._json_default,
        )
    print(f"  Plausibility post-cleaning: overall_failure_rate = "
          f"{plaus_summary['overall_failure_rate']}, "
          f"total_violations = {plaus_summary['total_violations']}")

    print("\nPost-cleaning reports written:")
    print(f"  {conf_path}")
    print(f"  {comp_path}")
    print(f"  {plaus_path}")
    print("\nOriginal Bronze-baseline reports (wesad_conformance.json, "
          "wesad_completeness.json, wesad_plausibility.json) are unchanged.")


if __name__ == "__main__":
    main()
