"""
Gold dataset manifest generator for DEAP.

Produces gold/DEAP/deap_gold_manifest.json. The manifest defines the
analysis-ready Gold dataset as a set of authoritative paths (Bronze .dat
for signals; Silver CSV for labels) together with their SHA-256 checksums,
check outcomes, and flag-and-retain findings.

No participant .dat data is copied. The Gold label dataset is the Silver
CSV files described by this manifest; the physiological data array is
read directly from bronze/ .dat files.

Run from project root:
    python deap/src/gold_manifest.py
"""

import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # deap/
DATA_ROOT = ROOT.parent                        # project root

_BASELINE_RPT = ROOT / "reports" / "deap_baseline.json"
_COMPLETENESS_RPT = ROOT / "reports" / "deap_completeness.json"
_CONFORMANCE_RPT = ROOT / "reports" / "deap_conformance.json"
_LP_RPT = ROOT / "reports" / "deap_label_plausibility.json"
_CONS_RPT = ROOT / "reports" / "deap_consistency.json"
_CLEANING_RPT = ROOT / "reports" / "deap_cleaning.json"
_POST_CLEANING_RPT = ROOT / "reports" / "deap_post_cleaning.json"
_QUALITY_RPT = ROOT / "reports" / "deap_quality_report.json"

_OUTPUT_DIR = DATA_ROOT / "gold" / "DEAP"
_OUTPUT_PATH = _OUTPUT_DIR / "deap_gold_manifest.json"

_SILVER_LABEL_DIR = DATA_ROOT / "silver" / "DEAP" / "labels"
_DAT_DIR = DATA_ROOT / "bronze" / "DEAP" / "deap-dataset" / "data_preprocessed_python"
_XLS_PATH = DATA_ROOT / "bronze" / "DEAP" / "deap-dataset" / "Metadata" / "participant_ratings.xls"

# Channel indices in DEAP .dat data array (40 channels; EEG 0-31, peripheral 32-39)
_GSR_IDX = 36
_TEMP_IDX = 39

# Temp group classification: range (max - min) above this threshold = Group B
_TEMP_GROUP_B_THRESHOLD = 100.0

# Participants by group (Group A = s01-s23, s25; Group B = s24, s26-s32)
_GROUP_A = {f"s{i:02d}" for i in range(1, 24)} | {"s25"}
_GROUP_B = {"s24"} | {f"s{i:02d}" for i in range(26, 33)}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _count_rows(csv_path: Path) -> int:
    count = 0
    with open(csv_path, encoding="utf-8") as fh:
        next(fh)  # skip header
        for line in fh:
            if line.strip():
                count += 1
    return count


def _load_reports():
    """Load all pipeline reports needed to build the manifest."""
    with open(_BASELINE_RPT, encoding="utf-8") as f:
        baseline = json.load(f)
    with open(_COMPLETENESS_RPT, encoding="utf-8") as f:
        completeness = json.load(f)
    with open(_CONFORMANCE_RPT, encoding="utf-8") as f:
        conformance = json.load(f)
    with open(_LP_RPT, encoding="utf-8") as f:
        label_plaus = json.load(f)
    with open(_CONS_RPT, encoding="utf-8") as f:
        consistency = json.load(f)
    with open(_CLEANING_RPT, encoding="utf-8") as f:
        cleaning = json.load(f)
    with open(_POST_CLEANING_RPT, encoding="utf-8") as f:
        post_cleaning = json.load(f)
    with open(_QUALITY_RPT, encoding="utf-8") as f:
        quality = json.load(f)
    return (baseline, completeness, conformance, label_plaus, consistency,
            cleaning, post_cleaning, quality)


def _index_by_participant(report_obj, key="participant"):
    """Index participants from either a dict-of-dicts or a list-of-dicts."""
    if isinstance(report_obj, dict):
        return report_obj  # already keyed by pid
    return {item[key]: item for item in report_obj}  # list of dicts


def _cross_source_counts_by_pid(consistency):
    """Count cross-source mismatches per participant from the flat list."""
    counts = defaultdict(int)
    for m in consistency["consistency_cross_source"].get("mismatches", []):
        counts[m["participant"]] += 1
    return dict(counts)


def _gsr_negative_count(dat_path: Path) -> int:
    """Count samples where GSR channel value < 0 across all 40 trials."""
    import sys
    sys.path.insert(0, str(DATA_ROOT))
    from deap.src.loader import load_dat
    d = load_dat(str(dat_path))
    gsr = d["data"][:, _GSR_IDX, :]  # shape (40, 8064)
    return int((gsr < 0).sum())


def generate_manifest(root: Path = DATA_ROOT,
                      output_path: Path = _OUTPUT_PATH) -> None:
    (baseline, completeness, conformance, label_plaus, consistency,
     cleaning, post_cleaning, quality) = _load_reports()

    # Index per-participant records
    comp_by_pid = _index_by_participant(completeness["participants"])
    conf_by_pid = _index_by_participant(conformance["participants"])
    lp_by_pid = _index_by_participant(label_plaus["participants"])
    cs_counts = _cross_source_counts_by_pid(consistency)
    cons_struct_pass = consistency["consistency_structure"].get("pass", True)
    clean_by_pid = cleaning["participants"]
    post_by_pid = _index_by_participant(
        post_cleaning["participants"], key="participant"
    )
    baseline_by_pid = {p["participant"]: p for p in baseline["participants"]}

    # XLS checksum (reference source for label correction)
    xls_sha256 = _sha256(_XLS_PATH)
    xls_rel = str(_XLS_PATH.relative_to(root)).replace("\\", "/")

    participants = {}
    pids = sorted(baseline_by_pid.keys())

    for pid in pids:
        print(f"  {pid} ...", flush=True)

        # --- Bronze .dat entry ---
        dat_path = _DAT_DIR / f"{pid}.dat"
        dat_rel = str(dat_path.relative_to(root)).replace("\\", "/")

        comp_pid = comp_by_pid.get(pid, {})
        conf_pid = conf_by_pid.get(pid, {})
        lp_pid = lp_by_pid.get(pid, {})
        b_pid = baseline_by_pid[pid]

        # Flag-and-retain: Temp group, flatline, GSR negative count
        temp_stats = b_pid["channel_stats"].get("Temp", {})
        temp_range = temp_stats.get("max", 0) - temp_stats.get("min", 0)
        if pid in _GROUP_A:
            temp_group = "A"
        elif pid in _GROUP_B:
            temp_group = "B"
        else:
            temp_group = "B" if temp_range > _TEMP_GROUP_B_THRESHOLD else "A"

        gsr_neg = _gsr_negative_count(dat_path)

        dat_entry = {
            "authoritative_path": dat_rel,
            "layer": "bronze",
            "sha256": _sha256(dat_path),
            "check_outcomes": {
                "completeness": {
                    "total_nan": comp_pid.get("total_nan"),
                    "total_inf": comp_pid.get("total_inf"),
                    "pass": comp_pid.get("pass"),
                },
                "conformance": {
                    "violation_count": conf_pid.get("violation_count"),
                    "pass": conf_pid.get("pass"),
                },
                "label_plausibility_pre_cleaning": {
                    "total_out_of_range": lp_pid.get("total_out_of_range"),
                    "pass": lp_pid.get("pass"),
                },
                "consistency_structure": {
                    "pass": cons_struct_pass,
                },
                "consistency_cross_source_pre_cleaning": {
                    "total_mismatches": cs_counts.get(pid, 0),
                    "pass": cs_counts.get(pid, 0) == 0,
                },
            },
            "flag_and_retain": {
                "temp_group": temp_group,
                "temp_group_description": (
                    "Group A: baseline-corrected small values"
                    if temp_group == "A"
                    else "Group B: large raw values; preprocessing unknown"
                ),
                "temp_longest_flatline_samples": temp_stats.get("longest_flatline"),
                "gsr_negative_count": gsr_neg,
                "gsr_note": (
                    "Negative GSR values are a possible consequence of drift "
                    "removal; cause in released files is not confirmed."
                ),
            },
        }

        # --- Silver label CSV entry ---
        csv_path = _SILVER_LABEL_DIR / f"{pid}_labels.csv"
        csv_rel = str(csv_path.relative_to(root)).replace("\\", "/")

        clean_pid = clean_by_pid.get(pid, {})
        post_pid = post_by_pid.get(pid, {})
        post_lp = post_pid.get("label_plausibility", {})
        post_cs = post_pid.get("cross_source", {})

        labels_entry = {
            "authoritative_path": csv_rel,
            "authoritative_label_source": xls_rel,
            "layer": "silver",
            "sha256": _sha256(csv_path),
            "n_trials": _count_rows(csv_path),
            "intentional_changes": {
                "n_label_corrections": clean_pid.get("n_corrections", 0),
                "description": (
                    "v2 inversion artefact corrected: labels replaced with "
                    "participant_ratings.xls values where they differed."
                ),
            },
            "check_outcomes": {
                "label_plausibility_post_cleaning": {
                    "total_out_of_range": post_lp.get("total_out_of_range"),
                    "pass": post_lp.get("pass"),
                },
                "consistency_cross_source_post_cleaning": {
                    "total_mismatches": post_cs.get("total_mismatches"),
                    "pass": post_cs.get("pass"),
                },
            },
        }

        participants[pid] = {
            "dat": dat_entry,
            "labels": labels_entry,
        }

    total_corrections = cleaning.get("total_corrections", 0)

    manifest = {
        "schema": "deap_gold_manifest_v1",
        "dataset": "DEAP",
        "run_context": {
            "note": "This field is non-deterministic. Strip it for diffing.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "deap/src/gold_manifest.py",
        },
        "definition": (
            "The DEAP Gold dataset is defined by this manifest. "
            "It consists of the Bronze .dat files (physiological signals) "
            "and Silver label CSV files (XLS-corrected labels) listed below, "
            "identified by their authoritative paths and SHA-256 checksums. "
            "No physical copy of the data arrays is made. "
            "Analysis code should read from the paths listed in each entry."
        ),
        "quality_report": "deap/reports/deap_quality_report.json",
        "summary": {
            "n_participants": len(participants),
            "participant_ids": sorted(participants.keys()),
            "total_label_corrections": total_corrections,
            "post_cleaning_overall_pass": post_cleaning.get("overall_pass"),
            "gold_overall_pass": quality.get("overall_pass"),
            "provenance": (
                "Data sourced from v2 Kaggle mirror (32 participants). "
                "v1 mirror was incomplete (12 participants) and replaced. "
                "Labels verified against participant_ratings.xls; "
                "878 v2 inversion artefacts corrected in Silver."
            ),
            "physiological_plausibility_not_applied": (
                "Units and preprocessing for peripheral channels (GSR, Resp, "
                "BVP, Temp) are not documented in available sources; bounds "
                "cannot be set without confirmed units."
            ),
            "flag_and_retain_policy": (
                "Temp scale groups (A vs B), GSR negative values, and Temp "
                "flatlines are flagged per participant and retained unmodified. "
                "Their cause is not confirmed in available sources."
            ),
            "participant_ratings_xls": {
                "authoritative_path": xls_rel,
                "sha256": xls_sha256,
                "description": (
                    "Authoritative label source; v1 mirror matched exactly; "
                    "used to correct v2 inversion artefact in Silver."
                ),
            },
        },
        "participants": participants,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)

    print(f"  Written to {output_path.relative_to(root)}", flush=True)


def verify_manifest(
    manifest_path: Path = _OUTPUT_PATH,
    root: Path = DATA_ROOT,
) -> bool:
    """Verify every SHA-256 in the manifest (32 dat + 32 CSV + 1 XLS = 65)."""
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    all_ok = True
    n_checked = 0

    # Per-participant: dat and labels
    for pid, entry in manifest.get("participants", {}).items():
        for sub_key in ("dat", "labels"):
            sub = entry.get(sub_key, {})
            rel_path = sub.get("authoritative_path")
            expected = sub.get("sha256")
            if not rel_path or not expected:
                continue
            path = root / rel_path
            actual = _sha256(path)
            if actual != expected:
                print(
                    f"  MISMATCH {pid}/{sub_key}: "
                    f"expected {expected[:12]}... got {actual[:12]}..."
                )
                all_ok = False
            n_checked += 1

    # XLS checksum in summary
    xls_entry = manifest.get("summary", {}).get("participant_ratings_xls", {})
    xls_path = xls_entry.get("authoritative_path")
    xls_expected = xls_entry.get("sha256")
    if xls_path and xls_expected:
        actual = _sha256(root / xls_path)
        if actual != xls_expected:
            print(
                f"  MISMATCH participant_ratings.xls: "
                f"expected {xls_expected[:12]}... got {actual[:12]}..."
            )
            all_ok = False
        n_checked += 1

    if all_ok:
        print(f"PASS -- all {n_checked} checksums match.")
    return all_ok


def main() -> None:
    print("Gold manifest: generating ...", flush=True)
    generate_manifest()
    print("Gold manifest: verifying ...", flush=True)
    verify_manifest()
    print("Gold manifest: done.", flush=True)


if __name__ == "__main__":
    main()
