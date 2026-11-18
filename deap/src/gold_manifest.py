"""
Gold dataset manifest generator for DEAP.

Produces gold/DEAP/deap_gold_manifest.json. The manifest defines the
analysis-ready Gold dataset as a set of authoritative Silver label CSV
paths together with their SHA-256 checksums and correction counts.

No participant .dat data is copied. The Gold label dataset is the Silver
CSV files described by this manifest; the physiological data array is
read directly from bronze/ .dat files.

Run from project root:
    python deap/src/gold_manifest.py
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # deap/
DATA_ROOT = ROOT.parent                        # project root

_CLEANING_RPT = ROOT / "reports" / "deap_cleaning.json"
_POST_CLEANING_RPT = ROOT / "reports" / "deap_post_cleaning.json"
_QUALITY_RPT = ROOT / "reports" / "deap_quality_report.json"

_OUTPUT_DIR = DATA_ROOT / "gold" / "DEAP"
_OUTPUT_PATH = _OUTPUT_DIR / "deap_gold_manifest.json"

_SILVER_LABEL_DIR = DATA_ROOT / "silver" / "DEAP" / "labels"


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


def generate_manifest(root: Path = DATA_ROOT,
                      output_path: Path = _OUTPUT_PATH) -> None:
    with open(_CLEANING_RPT, encoding="utf-8") as f:
        clean_rpt = json.load(f)
    with open(_POST_CLEANING_RPT, encoding="utf-8") as f:
        post_rpt = json.load(f)
    with open(_QUALITY_RPT, encoding="utf-8") as f:
        qr = json.load(f)

    clean_all = clean_rpt.get("participants", {})
    post_all = post_rpt.get("participants", {})

    participants = {}
    for pid_str in sorted(clean_all.keys()):
        csv_path = _SILVER_LABEL_DIR / f"{pid_str}_labels.csv"
        if not csv_path.exists():
            print(f"  WARNING: {csv_path} not found -- skipping {pid_str}")
            continue

        print(f"  {pid_str} ...", flush=True)

        clean_pid = clean_all.get(pid_str, {})
        post_pid = post_all.get(pid_str, {})

        rel = str(csv_path.relative_to(root)).replace("\\", "/")

        post_lp = post_pid.get("label_plausibility", {})
        post_cs = post_pid.get("cross_source", {})

        participants[pid_str] = {
            "authoritative_path": rel,
            "layer": "silver",
            "sha256": _sha256(csv_path),
            "n_trials": _count_rows(csv_path),
            "n_label_corrections": clean_pid.get("n_corrections", 0),
            "authoritative_label_source": (
                "bronze/DEAP/deap-dataset/Metadata/participant_ratings.xls"
            ),
            "check_outcomes": {
                "label_plausibility_post_cleaning": {
                    "total_out_of_range": post_lp.get("total_out_of_range"),
                    "pass": post_lp.get("pass"),
                },
                "cross_source_post_cleaning": {
                    "total_mismatches": post_cs.get("total_mismatches"),
                    "pass": post_cs.get("pass"),
                },
            },
        }

    manifest = {
        "schema": "deap_gold_manifest_v1",
        "dataset": "DEAP",
        "run_context": {
            "note": "This field is non-deterministic. Strip it for diffing.",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "generator": "deap/src/gold_manifest.py",
        },
        "definition": (
            "The DEAP Gold label dataset is defined by this manifest. "
            "It consists of the Silver label CSV files listed below, "
            "identified by their authoritative paths and SHA-256 checksums. "
            "No physical copy is made of the 40-channel physiological data array; "
            "that is read directly from bronze/ .dat files. "
            "Silver label CSVs contain XLS-corrected labels (v2 inversion artefact resolved)."
        ),
        "quality_report": "deap/reports/deap_quality_report.json",
        "summary": {
            "n_participants": len(participants),
            "participant_ids": sorted(participants.keys()),
            "total_label_corrections": clean_rpt.get("total_corrections", 0),
            "post_cleaning_overall_pass": post_rpt.get("overall_pass"),
            "gold_overall_pass": qr.get("overall_pass"),
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
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)

    all_ok = True
    for pid, entry in manifest.get("participants", {}).items():
        path = root / entry["authoritative_path"]
        expected = entry.get("sha256")
        if expected is None:
            continue
        actual = _sha256(path)
        if actual != expected:
            print(
                f"  MISMATCH {pid}: "
                f"expected {expected[:12]}... got {actual[:12]}..."
            )
            all_ok = False

    if all_ok:
        print(
            f"PASS -- all {len(manifest.get('participants', {}))} "
            "checksums match."
        )
    return all_ok


def main() -> None:
    print("Gold manifest: generating ...", flush=True)
    generate_manifest()
    print("Gold manifest: done.", flush=True)


if __name__ == "__main__":
    main()
