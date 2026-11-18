"""
DEAP quality report generator -- before/after comparison.

Reads Bronze check reports ("before") and Silver post-cleaning report
("after") and produces a before/after quality comparison.

Thresholds sign-off gate: refuses to run if meta.signed_off is not true
in deap/config/thresholds.yaml.

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

REQUIRED_BRONZE = {
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

    # Load Bronze check reports (the "before")
    loaded = {}
    for key, fname in REQUIRED_BRONZE.items():
        path = os.path.join(reports_dir, fname)
        if not os.path.exists(path):
            print(f"  WARNING: {path} not found", file=sys.stderr)
            loaded[key] = None
        else:
            with open(path) as f:
                loaded[key] = json.load(f)

    # Load Silver post-cleaning report (the "after")
    post_path = os.path.join(reports_dir, "deap_post_cleaning.json")
    post = None
    if os.path.exists(post_path):
        with open(post_path) as f:
            post = json.load(f)

    def _status(report, _key=""):
        if report is None:
            return "missing"
        return "pass" if report.get("overall_pass") else "fail"

    comp = loaded["completeness"]
    conf = loaded["conformance"]
    lp = loaded["label_plausibility"]
    cons = loaded["consistency"]

    # Completeness (data array -- not affected by cleaning)
    completeness_row = {
        "dimension": "completeness",
        "note": "Checks the physiological data array. Not affected by label cleaning.",
        "status": _status(comp),
        "value": comp["total_nan_all_participants"] if comp else None,
        "threshold": (
            f"max_nan_count={thresholds['completeness']['max_nan_count']}, "
            f"max_inf_count={thresholds['completeness']['max_inf_count']}"
        ),
        "detail": (
            f"total NaN: {comp['total_nan_all_participants']}, "
            f"total Inf: {comp['total_inf_all_participants']}"
        ) if comp else None,
    }

    # Conformance (data array and shape -- not affected by label cleaning)
    conformance_row = {
        "dimension": "conformance",
        "note": "Checks data array shape and dtype. Not affected by label cleaning.",
        "status": _status(conf),
        "value": conf["total_violations"] if conf else None,
        "threshold": (
            f"max_violations={thresholds['conformance']['max_violations']}"
        ),
        "detail": (
            f"total violations: {conf['total_violations']}"
        ) if conf else None,
    }

    # Label plausibility -- before/after
    lp_before_val = lp["total_out_of_range_all_participants"] if lp else None
    lp_after_val = post["total_label_plausibility_oor"] if post else None
    lp_after_pass = (lp_after_val == 0) if lp_after_val is not None else None
    label_plausibility_row = {
        "dimension": "label_plausibility",
        "before": {
            "status": _status(lp),
            "value": lp_before_val,
            "threshold": (
                f"max_out_of_range={thresholds['label_plausibility']['max_out_of_range']}"
            ),
            "detail": (
                f"total out-of-SAM-range: {lp_before_val}"
            ) if lp_before_val is not None else None,
        },
        "after": {
            "status": "pass" if lp_after_pass else ("fail" if lp_after_pass is False else "missing"),
            "value": lp_after_val,
            "source": "silver/DEAP/labels/ (after label correction)",
            "detail": (
                f"total out-of-SAM-range: {lp_after_val}"
            ) if lp_after_val is not None else None,
        },
    }

    # Consistency -- before/after for cross-source; structure not affected
    cs_before = None
    cs_after_val = None
    cs_after_pass = None
    if cons:
        cs_before = cons["consistency_cross_source"]["total_mismatches"]
    if post:
        cs_after_val = post["total_cross_source_mismatches"]
        cs_after_pass = (cs_after_val == 0)

    consistency_row = {
        "dimension": "consistency",
        "sub_checks": {
            "structure": {
                "note": "Shape uniformity across participants. Not affected by label cleaning.",
                "status": (
                    "pass" if (cons and cons["consistency_structure"]["pass"]) else "fail"
                ) if cons else "missing",
                "value": cons["consistency_structure"]["total_mismatches"] if cons else None,
                "threshold": (
                    f"max_mismatches={thresholds['consistency_structure']['max_mismatches']}"
                ),
            },
            "cross_source": {
                "note": "dat labels vs participant_ratings.xls. Corrected by label cleaning.",
                "before": {
                    "status": "pass" if (cs_before == 0) else "fail",
                    "value": cs_before,
                    "threshold": (
                        f"max_mismatches=0, tolerance={thresholds['consistency_cross_source']['tolerance']}"
                    ),
                },
                "after": {
                    "status": "pass" if cs_after_pass else ("fail" if cs_after_pass is False else "missing"),
                    "value": cs_after_val,
                    "source": "silver/DEAP/labels/ (after label correction)",
                },
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

    # Overall gold pass: all measured dimensions pass in the "after" state
    # Completeness and conformance are single-state (data array, not affected by cleaning)
    # label_plausibility and cross_source use "after" state
    # structure uses single state
    comp_pass = comp["overall_pass"] if comp else False
    conf_pass = conf["overall_pass"] if conf else False
    struct_pass = cons["consistency_structure"]["pass"] if cons else False
    gold_passes = (
        comp_pass
        and conf_pass
        and struct_pass
        and bool(lp_after_pass)
        and bool(cs_after_pass)
    )

    report = {
        "dataset": "DEAP",
        "report_type": "before_after_quality_comparison",
        "threshold_source": "deap/config/thresholds.yaml",
        "participant_count": comp["participant_count"] if comp else None,
        "overall_pass": gold_passes,
        "note": (
            "overall_pass reflects the Gold (after-cleaning) state. "
            "label_plausibility and cross_source dimensions show before/after. "
            "completeness, conformance, and structure check the data array and "
            "are unaffected by label cleaning."
        ),
        "dimensions": {d["dimension"]: d for d in dimensions},
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(f"  quality report -> {output_path}", file=sys.stderr)
    return report


if __name__ == "__main__":
    run()
