"""
DEAP quality report generator.

Reads all check reports and produces a summary with per-dimension
pass/fail verdicts. Marks physiological_plausibility and timeliness
as "not_applied" with reasons from thresholds.yaml.

Output: deap/reports/deap_quality_report.json (deterministic, sorted keys).

Run from project root:
    python -c "from deap.src.report import run; run()"
"""

import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "config", "thresholds.yaml")
REPORTS = os.path.join(ROOT, "reports")
OUTPUT = os.path.join(REPORTS, "deap_quality_report.json")

REQUIRED_REPORTS = {
    "completeness": "deap_completeness.json",
    "conformance": "deap_conformance.json",
    "label_plausibility": "deap_label_plausibility.json",
    "consistency": "deap_consistency.json",
}


def run(reports_dir: str = REPORTS, output_path: str = OUTPUT) -> dict:
    with open(CONFIG) as f:
        thresholds = yaml.safe_load(f)

    if not thresholds.get("meta", {}).get("signed_off"):
        raise RuntimeError(
            "deap/config/thresholds.yaml is not signed off "
            "(meta.signed_off is not true). Quality report refused."
        )

    # Load check reports
    loaded = {}
    for key, fname in REQUIRED_REPORTS.items():
        path = os.path.join(reports_dir, fname)
        if not os.path.exists(path):
            print(f"  WARNING: {path} not found", file=sys.stderr)
            loaded[key] = None
        else:
            with open(path) as f:
                loaded[key] = json.load(f)

    def _status(report, key):
        if report is None:
            return "missing"
        return "pass" if report.get("overall_pass") else "fail"

    # Completeness
    comp = loaded["completeness"]
    completeness_row = {
        "dimension": "completeness",
        "status": _status(comp, "completeness"),
        "value": comp["total_nan_all_participants"] if comp else None,
        "threshold": f"max_nan_count={thresholds['completeness']['max_nan_count']}, "
                     f"max_inf_count={thresholds['completeness']['max_inf_count']}",
        "detail": (
            f"total NaN: {comp['total_nan_all_participants']}, "
            f"total Inf: {comp['total_inf_all_participants']}"
        ) if comp else None,
    }

    # Conformance
    conf = loaded["conformance"]
    conformance_row = {
        "dimension": "conformance",
        "status": _status(conf, "conformance"),
        "value": conf["total_violations"] if conf else None,
        "threshold": f"max_violations={thresholds['conformance']['max_violations']}",
        "detail": f"total violations: {conf['total_violations']}" if conf else None,
    }

    # Label plausibility
    lp = loaded["label_plausibility"]
    label_plausibility_row = {
        "dimension": "label_plausibility",
        "status": _status(lp, "label_plausibility"),
        "value": lp["total_out_of_range_all_participants"] if lp else None,
        "threshold": f"max_out_of_range={thresholds['label_plausibility']['max_out_of_range']}",
        "detail": (
            f"total out-of-SAM-range: {lp['total_out_of_range_all_participants']}"
        ) if lp else None,
    }

    # Consistency
    cons = loaded["consistency"]
    consistency_structure_pass = cons["consistency_structure"]["pass"] if cons else None
    consistency_cross_pass = cons["consistency_cross_source"]["pass"] if cons else None
    consistency_row = {
        "dimension": "consistency",
        "status": _status(cons, "consistency"),
        "sub_checks": {
            "structure": {
                "status": "pass" if consistency_structure_pass else "fail",
                "value": cons["consistency_structure"]["total_mismatches"] if cons else None,
                "threshold": f"max_mismatches={thresholds['consistency_structure']['max_mismatches']}",
            },
            "cross_source": {
                "status": "pass" if consistency_cross_pass else "fail",
                "value": cons["consistency_cross_source"]["total_mismatches"] if cons else None,
                "threshold": f"max_mismatches=0, tolerance={thresholds['consistency_cross_source']['tolerance']}",
            },
            "scale_descriptive": {
                "status": "not_applicable",
                "detail": "Descriptive only; no threshold.",
            },
        },
    }

    # Not applied
    phys_plaus_row = {
        "dimension": "physiological_plausibility",
        "status": "not_applied",
        "reason": thresholds["physiological_plausibility"]["reason"],
    }
    timeliness_row = {
        "dimension": "timeliness",
        "status": "not_applied",
        "reason": thresholds["timeliness"]["reason"],
    }

    dimensions = [
        completeness_row,
        conformance_row,
        label_plausibility_row,
        consistency_row,
        phys_plaus_row,
        timeliness_row,
    ]

    measured_pass = [
        d for d in dimensions
        if d["status"] not in ("not_applied", "not_applicable", "missing")
    ]
    overall_pass = all(d["status"] == "pass" for d in measured_pass)

    report = {
        "dataset": "DEAP",
        "threshold_source": "deap/config/thresholds.yaml",
        "participant_count": comp["participant_count"] if comp else None,
        "overall_pass": overall_pass,
        "dimensions": {d["dimension"]: d for d in dimensions},
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"  quality report -> {output_path}", file=sys.stderr)
    return report


if __name__ == "__main__":
    run()
