"""
Gold dataset manifest generator for WESAD.

Produces gold/WESAD/wesad_gold_manifest.json. The manifest defines the
analysis-ready Gold dataset as a set of authoritative file paths (Silver for
E4 TEMP, Bronze for all other signals) together with their SHA-256 checksums,
sample counts, post-cleaning check outcomes, and any documented intentional
removals.

No participant data is copied. The Gold dataset exists as the Silver and
Bronze files described by this manifest.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_COMPLETENESS_RPT = ROOT / "reports" / "wesad_completeness_post_cleaning.json"
_CONFORMANCE_RPT = ROOT / "reports" / "wesad_conformance_post_cleaning.json"
_PLAUSIBILITY_RPT = ROOT / "reports" / "wesad_plausibility_post_cleaning.json"
_CLEANING_RPT = ROOT / "reports" / "wesad_cleaning.json"
_QUALITY_RPT = ROOT / "reports" / "wesad_quality_report.json"

_OUTPUT_DIR = ROOT / "gold" / "WESAD"
_OUTPUT_PATH = _OUTPUT_DIR / "wesad_gold_manifest.json"

_E4_SIGNALS = ["ACC", "BVP", "EDA", "HR", "IBI", "TEMP"]

# IBI is event-based: excluded from conformance range/type checks
_CONFORMANCE_EXCLUDED_E4 = frozenset({"IBI"})

# Plausibility exclusion reasons (short form for manifest)
_PLS_EXCLUDE = {
    "BVP": (
        "BVP is excluded from plausibility checking. "
        "No device output range is documented in WESAD materials."
    ),
    "IBI": (
        "IBI is excluded from plausibility checking. "
        "HRV derivation requires consecutive intervals and is out of scope."
    ),
    "EDA_chest": (
        "RespiBAN CH2 (EDA) has no config bound. "
        "The config EDA entry applies to the E4 wrist sensor."
    ),
    "TEMP_chest": (
        "RespiBAN CH4 (TEMP) has no config bound. "
        "The config skin_temperature entry applies to the E4 wrist sensor."
    ),
}


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    """Return the hex SHA-256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_e4_samples(csv_path: Path) -> int:
    """Count data rows in an E4 CSV (total rows minus the 2-line header)."""
    count = 0
    with open(csv_path, "r", encoding="utf-8") as fh:
        for i, _ in enumerate(fh):
            if i >= 2:
                count += 1
    return count


def _count_rb_rows(txt_path: Path) -> int:
    """Count data rows in a RespiBAN txt (total lines minus the 3-line header)."""
    count = 0
    with open(txt_path, "rb") as fh:
        fh.readline()
        fh.readline()
        fh.readline()
        for line in fh:
            if line.strip():
                count += 1
    return count


# ---------------------------------------------------------------------------
# Check outcome extractors
# ---------------------------------------------------------------------------

def _e4_check_outcomes(sig: str, comp_p: dict, conf_p: dict, pls_p: dict) -> dict:
    """Extract per-check summary for one E4 signal from per-participant dicts."""
    outcomes = {}

    comp_sig = comp_p.get("e4", {}).get(sig)
    if comp_sig is not None:
        if sig == "IBI":
            outcomes["completeness"] = {
                "n_events": comp_sig.get("n_events"),
                "n_nan": comp_sig.get("n_nan"),
                "threshold_applied": False,
                "note": "Event-based signal; missingness rate is undefined.",
            }
        else:
            outcomes["completeness"] = {
                "n_samples": comp_sig.get("n_samples"),
                "n_nan": comp_sig.get("n_nan"),
                "missingness_rate": comp_sig.get("missingness_rate"),
                "passes_threshold": comp_sig.get("passes_threshold"),
            }

    if sig in _CONFORMANCE_EXCLUDED_E4:
        outcomes["conformance"] = {
            "excluded": True,
            "reason": "IBI is event-based; not included in conformance range check.",
        }
    else:
        conf_sig = conf_p.get("e4", {}).get(sig)
        if conf_sig is not None:
            nm = conf_sig.get("non_numeric", {})
            rng = conf_sig.get("range", {})
            sr = conf_sig.get("sampling_rate", {})
            outcomes["conformance"] = {
                "non_numeric_ok": nm.get("ok"),
                "n_non_numeric": nm.get("n_non_numeric"),
                "range_ok": rng.get("ok") if rng.get("checked") else None,
                "n_above_max": rng.get("n_above_max"),
                "n_below_min": rng.get("n_below_min"),
                "sampling_rate_ok": sr.get("ok") if sr else None,
            }

    pls_sig = pls_p.get("e4", {}).get(sig)
    if pls_sig is not None:
        if pls_sig.get("excluded"):
            outcomes["plausibility"] = {
                "excluded": True,
                "reason": _PLS_EXCLUDE.get(sig, pls_sig.get("reason", "")),
            }
        else:
            outcomes["plausibility"] = {
                "excluded": False,
                "n_violations": pls_sig.get("n_violations"),
                "passes_threshold": pls_sig.get("passes_threshold"),
            }

    return outcomes


def _rb_check_outcomes(comp_p: dict, conf_p: dict, pls_p: dict) -> dict:
    """Extract per-check summary for the RespiBAN file."""
    outcomes = {}

    comp_chest = comp_p.get("chest", {})
    if comp_chest:
        outcomes["completeness"] = {
            "n_samples": comp_chest.get("n_samples"),
            "n_sequence_gaps": comp_chest.get("n_sequence_gaps"),
            "passes_threshold": comp_chest.get("n_sequence_gaps") == 0,
        }

    conf_chest = conf_p.get("chest", {})
    if conf_chest:
        rs = conf_chest.get("range_summary", {})
        outcomes["conformance"] = {
            "range_ok": rs.get("ok"),
            "total_violations": rs.get("total_violations"),
            "format_ok": conf_chest.get("format", {}).get("ok"),
            "column_count_ok": conf_chest.get("column_count", {}).get("ok"),
            "sampling_rate_ok": conf_chest.get("sampling_rate", {}).get("ok"),
        }

    pls_chest = pls_p.get("chest", {})
    if pls_chest:
        ch_summary = {}
        for ch_name, ch_val in pls_chest.items():
            if ch_val.get("excluded"):
                ch_summary[ch_name] = {
                    "excluded": True,
                    "reason": _PLS_EXCLUDE.get(ch_name, ch_val.get("reason", "")),
                }
            else:
                ch_summary[ch_name] = {
                    "excluded": False,
                    "n_violations": ch_val.get("n_violations"),
                    "passes_threshold": ch_val.get("passes_threshold"),
                }
        outcomes["plausibility"] = ch_summary

    return outcomes


# ---------------------------------------------------------------------------
# Manifest generator
# ---------------------------------------------------------------------------

def generate_manifest(root: Path = ROOT, output_path: Path = _OUTPUT_PATH) -> None:
    """Generate the Gold manifest and write it to output_path."""
    with open(_COMPLETENESS_RPT, encoding="utf-8") as f:
        comp_rpt = json.load(f)
    with open(_CONFORMANCE_RPT, encoding="utf-8") as f:
        conf_rpt = json.load(f)
    with open(_PLAUSIBILITY_RPT, encoding="utf-8") as f:
        pls_rpt = json.load(f)
    with open(_CLEANING_RPT, encoding="utf-8") as f:
        clean_rpt = json.load(f)
    with open(_QUALITY_RPT, encoding="utf-8") as f:
        qr = json.load(f)

    comp_all = comp_rpt.get("participants", {})
    conf_all = conf_rpt.get("participants", {})
    pls_all = pls_rpt.get("participants", {})
    clean_all = clean_rpt.get("participants", {})

    participant_ids = sorted(comp_all.keys())
    participants = {}

    for pid in participant_ids:
        print(f"  {pid} ...", flush=True)
        comp_p = comp_all.get(pid, {})
        conf_p = conf_all.get(pid, {})
        pls_p = pls_all.get(pid, {})
        clean_p = clean_all.get(pid, {})

        bronze_e4 = root / "bronze" / "WESAD" / pid / f"{pid}_E4_Data"
        silver_e4 = root / "silver" / "WESAD" / pid / f"{pid}_E4_Data"
        rb_path = root / "bronze" / "WESAD" / pid / f"{pid}_respiban.txt"

        e4_entries = {}
        for sig in _E4_SIGNALS:
            if sig == "TEMP":
                auth = silver_e4 / "TEMP.csv"
                layer = "silver"
            else:
                auth = bronze_e4 / f"{sig}.csv"
                layer = "bronze"

            if not auth.exists():
                continue

            removals = None
            if sig == "TEMP" and clean_p:
                cl = clean_p.get("cleaning", {})
                removals = {
                    "action": cl.get("action"),
                    "indices_replaced": cl.get("indices_replaced"),
                    "original_values": cl.get("original_values"),
                    "replacement": "NaN",
                    "source_report": "reports/wesad_cleaning.json",
                }

            check_exclusions = {}
            if sig in _CONFORMANCE_EXCLUDED_E4:
                check_exclusions["conformance"] = (
                    "IBI is event-based; not included in conformance range check."
                )
            if sig in _PLS_EXCLUDE:
                check_exclusions["plausibility"] = _PLS_EXCLUDE[sig]

            rel = str(auth.relative_to(root)).replace("\\", "/")
            e4_entries[sig] = {
                "authoritative_path": rel,
                "layer": layer,
                "sha256": _sha256(auth),
                "n_samples": _count_e4_samples(auth),
                "intentional_removals": removals,
                "check_exclusions": check_exclusions,
                "check_outcomes": _e4_check_outcomes(sig, comp_p, conf_p, pls_p),
            }

        rel_rb = str(rb_path.relative_to(root)).replace("\\", "/")
        rb_exclusions = {
            "plausibility": {
                "EDA_chest": _PLS_EXCLUDE["EDA_chest"],
                "TEMP_chest": _PLS_EXCLUDE["TEMP_chest"],
            }
        }
        participants[pid] = {
            "e4": e4_entries,
            "respiban": {
                "authoritative_path": rel_rb,
                "layer": "bronze",
                "sha256": _sha256(rb_path),
                "n_rows": _count_rb_rows(rb_path),
                "intentional_removals": None,
                "check_exclusions": rb_exclusions,
                "check_outcomes": _rb_check_outcomes(comp_p, conf_p, pls_p),
            },
        }

    qr_overall = qr.get("overall_assessment", {})

    manifest = {
        "schema": "wesad_gold_manifest_v1",
        "dataset": "WESAD",
        "run_context": {
            "note": "This field is non-deterministic. Strip it for diffing.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "src/gold_manifest.py",
        },
        "definition": (
            "The WESAD Gold dataset is defined by this manifest. "
            "It consists of the Silver and Bronze files listed below, "
            "identified by their authoritative paths and SHA-256 checksums. "
            "No physical copy is made; analysis code should read from the "
            "paths listed in each entry. Silver TEMP files contain the "
            "cleaned warm-up replacement (NaN at indices 0-3); all other "
            "signals are Bronze."
        ),
        "quality_report": "reports/wesad_quality_report.json",
        "summary": {
            "participants": participant_ids,
            "n_participants": len(participant_ids),
            "e4_signals": _E4_SIGNALS,
            "signal_files_per_participant": len(_E4_SIGNALS) + 1,
            "total_signal_files": len(participant_ids) * (len(_E4_SIGNALS) + 1),
            "gold_passes_all_measured_thresholds": qr_overall.get(
                "gold_passes_all_measured_thresholds"
            ),
            "quality_headline": qr_overall.get("headline", ""),
            "gold_definition_note": (
                "Gold is a manifest, not a physical copy. "
                "Each entry points to the authoritative file in Silver or Bronze. "
                "The manifest checksums guarantee that any future verification "
                "detects accidental modification of any source file."
            ),
        },
        "participants": participants,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"  Written to {output_path.relative_to(root)}", flush=True)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_manifest(
    manifest_path: Path = _OUTPUT_PATH,
    root: Path = ROOT,
) -> bool:
    """
    Recompute every SHA-256 checksum in the manifest and compare it to the
    stored value. Returns True if all match. Prints a line for each mismatch.
    """
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    all_ok = True
    for pid, pid_data in manifest.get("participants", {}).items():
        for sig, entry in pid_data.get("e4", {}).items():
            path = root / entry["authoritative_path"]
            expected = entry.get("sha256")
            if expected is None:
                continue
            actual = _sha256(path)
            if actual != expected:
                print(
                    f"  MISMATCH {pid}/{sig}: "
                    f"expected {expected[:12]}... got {actual[:12]}..."
                )
                all_ok = False

        rb = pid_data.get("respiban") or {}
        if not rb:
            continue
        rb_path = root / rb["authoritative_path"]
        expected_rb = rb.get("sha256")
        if expected_rb is not None:
            actual_rb = _sha256(rb_path)
            if actual_rb != expected_rb:
                print(
                    f"  MISMATCH {pid}/respiban: "
                    f"expected {expected_rb[:12]}... got {actual_rb[:12]}..."
                )
                all_ok = False

    return all_ok


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("Gold manifest: generating ...", flush=True)
    generate_manifest()
    print("Gold manifest: done.", flush=True)


if __name__ == "__main__":
    main()
