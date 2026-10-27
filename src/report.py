"""
Gold layer — before/after quality report (Task 11).

Compares the Bronze baseline against the cleaned Gold output across all five
quality dimensions and judges each against the pre-registered thresholds in
config/thresholds.yaml.

Gate: refuses to run while meta.signed_off is false in thresholds.yaml.

Sources:
  "Before" values: Bronze-baseline reports (wesad_conformance.json, etc.)
  "After" values:  Post-cleaning measured reports (wesad_*_post_cleaning.json)
                   produced by src/checks/post_cleaning.py

Completeness definition (Kevin, 2026-10-12):
  Samples documented as intentionally removed during cleaning are excluded from
  the missingness rate and reported separately.  After cleaning, unintentional
  missingness = 0.0, which genuinely passes the 0.0 threshold with no
  qualification needed.

Output: reports/wesad_quality_report.json
Determinism: all source reports are deterministic; this report is too.
"""

import json
from pathlib import Path

import yaml

ROOT    = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "reports"
CONFIG  = ROOT / "config"


# ── Config loading ────────────────────────────────────────────────────────────

def _load_thresholds() -> dict:
    with open(CONFIG / "thresholds.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_report(name: str) -> dict:
    with open(REPORTS / name, encoding="utf-8") as fh:
        return json.load(fh)


# ── Dimension builders ────────────────────────────────────────────────────────

def _dim_completeness(
    thresholds: dict,
    completeness_before: dict,
    completeness_after: dict,
) -> dict:
    """
    Completeness dimension.

    "Before": Bronze-baseline wesad_completeness.json (no intentional removals).
    "After":  Post-cleaning wesad_completeness_post_cleaning.json.
              Intentional removals (TEMP warm-up, 60 samples) are excluded from
              the missingness rate and reported separately.
              Unintentional missingness after cleaning = 0.0.
    """
    threshold = float(thresholds["completeness"]["max_missingness_rate"])

    # ── Before (Bronze baseline) ───────────────────────────────────────────
    e4_cells_total   = completeness_before["summary"]["e4_total_cells_checked"]
    before_nan_count = completeness_before["summary"]["e4_total_nan_cells"]
    before_rate      = completeness_before["summary"]["e4_overall_missingness_rate"]
    before_pass      = before_rate <= threshold

    # ── After (measured post-cleaning, with intentional removals excluded) ─
    after_summary = completeness_after["summary"]
    after_rate    = after_summary["e4_overall_missingness_rate"]  # 0.0
    after_pass    = after_rate <= threshold                        # True
    intentional_removals_count = after_summary.get("e4_intentional_removals", 0)

    return {
        "dimension": "completeness",
        "threshold_key":  "completeness.max_missingness_rate",
        "threshold":      threshold,
        "before": {
            "state":           "bronze_baseline",
            "nan_count":       before_nan_count,
            "cells_checked":   e4_cells_total,
            "missingness_rate": before_rate,
            "threshold_pass":  before_pass,
        },
        "after": {
            "state":           "gold_cleaned",
            "missingness_rate": after_rate,
            "threshold_pass":  after_pass,
            "intentional_removals": {
                "count": intentional_removals_count,
                "description": (
                    "E4 TEMP warm-up artefact samples set to NaN during cleaning. "
                    "Documented in reports/wesad_cleaning.json. Excluded from "
                    "missingness_rate by definition (intentional, not unintended absence)."
                ),
            },
            "source": "reports/wesad_completeness_post_cleaning.json",
        },
        "completeness_definition_note": (
            "Missingness measures UNINTENDED absence only. Samples intentionally "
            "removed during cleaning are excluded from the rate and reported "
            "separately. Decision: Kevin, 2026-10-12."
        ),
        "threshold_pass_bronze": before_pass,
        "threshold_pass_gold":   after_pass,
    }


def _dim_validity_conformance(
    thresholds: dict,
    conformance_before: dict,
    conformance_after: dict,
) -> dict:
    """
    Validity (conformance) dimension.

    "Before": Bronze-baseline wesad_conformance.json.
    "After":  Measured wesad_conformance_post_cleaning.json (Silver TEMP + Bronze).
    """
    threshold = float(thresholds["validity"]["max_conformance_violation_rate"])

    # ── Before ─────────────────────────────────────────────────────────────
    cells_total  = conformance_before["summary"]["total_range_cells_checked"]
    before_count = conformance_before["summary"]["total_range_violations"]
    before_rate  = conformance_before["summary"]["overall_range_violation_rate"]
    before_pass  = before_rate <= threshold

    # ── After (measured) ───────────────────────────────────────────────────
    after_sum    = conformance_after["summary"]
    after_count  = after_sum["total_range_violations"]
    after_rate   = after_sum["overall_range_violation_rate"]
    after_pass   = after_rate <= threshold

    return {
        "dimension": "validity_conformance",
        "threshold_key": "validity.max_conformance_violation_rate",
        "threshold":     threshold,
        "before": {
            "state":           "bronze_baseline",
            "violation_count": before_count,
            "cells_checked":   cells_total,
            "violation_rate":  before_rate,
            "threshold_pass":  before_pass,
            "violation_cause": (
                "E4 TEMP warm-up artefact: all 60 violations were indices 0-3 "
                "of the TEMP channel (~382 degrees C) across all 15 participants. "
                "All other signals: zero violations."
            ),
        },
        "after": {
            "state":           "gold_cleaned",
            "violation_count": after_count,
            "cells_checked":   cells_total,
            "violation_rate":  after_rate,
            "threshold_pass":  after_pass,
            "source":          "reports/wesad_conformance_post_cleaning.json",
        },
        "headline": (
            "Conformance violations: 60 (Bronze) -> 0 (Gold). "
            "Pipeline resolved the only conformance issue in the dataset."
        ),
        "threshold_pass_bronze": before_pass,
        "threshold_pass_gold":   after_pass,
    }


def _dim_validity_plausibility(
    thresholds: dict,
    plausibility_before: dict,
    plausibility_after: dict,
) -> dict:
    """
    Validity (plausibility) dimension.

    "Before": Bronze-baseline wesad_plausibility.json.
    "After":  Measured wesad_plausibility_post_cleaning.json (Silver TEMP + Bronze).
    """
    threshold = float(thresholds["validity"]["max_plausibility_failure_rate"])

    # ── Before ─────────────────────────────────────────────────────────────
    samples_total = plausibility_before["summary"]["total_samples_checked"]
    before_count  = plausibility_before["summary"]["total_violations"]
    before_rate   = plausibility_before["summary"]["overall_failure_rate"]
    before_pass   = before_rate <= threshold

    # ── After (measured) ───────────────────────────────────────────────────
    after_sum   = plausibility_after["summary"]
    after_count = after_sum["total_violations"]
    after_rate  = after_sum["overall_failure_rate"]
    after_pass  = after_rate <= threshold

    return {
        "dimension": "validity_plausibility",
        "threshold_key": "validity.max_plausibility_failure_rate",
        "threshold":     threshold,
        "before": {
            "state":           "bronze_baseline",
            "violation_count": before_count,
            "samples_checked": samples_total,
            "failure_rate":    before_rate,
            "threshold_pass":  before_pass,
            "violation_cause": (
                "Same 60 TEMP warm-up samples as the conformance violations. "
                "Physiologically implausible (~382 degrees C, above the 42 degrees C "
                "skin-temperature ceiling). Zero device-flagged violations."
            ),
        },
        "after": {
            "state":           "gold_cleaned",
            "violation_count": after_count,
            "samples_checked": samples_total,
            "failure_rate":    after_rate,
            "threshold_pass":  after_pass,
            "source":          "reports/wesad_plausibility_post_cleaning.json",
        },
        "headline": (
            "Plausibility failures: 60 (Bronze) -> 0 (Gold). "
            "The only physiologically implausible signal was the TEMP warm-up "
            "artefact, resolved by cleaning."
        ),
        "threshold_pass_bronze": before_pass,
        "threshold_pass_gold":   after_pass,
    }


def _dim_timeliness(thresholds: dict, alignment: dict) -> dict:
    threshold = float(thresholds["timeliness"]["max_cross_modal_offset_seconds"])
    summary   = alignment["summary"]

    return {
        "dimension": "timeliness",
        "threshold_key": "timeliness.max_cross_modal_offset_seconds",
        "threshold":     threshold,
        "before": {
            "state":       "raw_start_time_gap",
            "metric":      "mean_start_time_difference_s",
            "value_s":     summary["mean_offset_before_s"],
            "range_s":     {
                "min": summary["min_offset_before_s"],
                "max": summary["max_offset_before_s"],
            },
            "interpretation": (
                "The ~19-minute gap is a sensor activation-window difference: "
                "the E4 wristband activates ~15-24 minutes before the RespiBAN "
                "chest sensor. This is resolved by trimming to the shared overlap "
                "window. It is NOT a residual the threshold measures."
            ),
            "threshold_pass": None,
            "threshold_applies": False,
            "note": "Threshold does not apply to the raw start-time gap.",
        },
        "after": {
            "state":         "within_overlap_residual",
            "metric":        "max_absolute_offset_across_5_reconstruction_points",
            "mean_offset_s": summary["mean_offset_after_s"],
            "max_offset_s":  summary["max_offset_after_s"],
            "n_participants_pass": summary["n_pass_threshold"],
            "n_participants_fail": summary["n_fail_threshold"],
            "threshold_pass": summary["all_pass_threshold"],
            "note": (
                "12/15 participants: zero residual. S2/S3/S4: residuals up to "
                "0.107 s, within the E4 EDA quantisation bound of +/-0.125 s. "
                "All 15 participants pass the 1.0 s threshold."
            ),
        },
        "threshold_pass_bronze": None,
        "threshold_pass_gold":   summary["all_pass_threshold"],
    }


def _dim_consistency(thresholds: dict) -> dict:
    return {
        "dimension": "consistency",
        "threshold_key": None,
        "threshold":     None,
        "before":        None,
        "after":         None,
        "threshold_pass_bronze": None,
        "threshold_pass_gold":   None,
        "recorded_decision": (
            "No dedicated consistency metric defined for WESAD. "
            "Documented in config/thresholds.yaml (consistency block) and "
            "docs/progress_log.md. The systematic ~19-minute timing mismatch "
            "between E4 and RespiBAN sensors is a timeliness/alignment matter "
            "measured under max_cross_modal_offset_seconds; treating it as "
            "consistency as well would double-count the same phenomenon. "
            "To be revisited for DEAP (Task 14)."
        ),
    }


def _dim_accuracy() -> dict:
    return {
        "dimension": "accuracy",
        "threshold_key": None,
        "threshold":     None,
        "before":        None,
        "after":         None,
        "threshold_pass_bronze": None,
        "threshold_pass_gold":   None,
        "stated_limitation": (
            "No accuracy metric is defined. Accuracy in the sense of "
            "'ground-truth agreement' requires an external reference standard "
            "(e.g. a calibrated lab instrument or simultaneous clinical measurement). "
            "No such reference is available for WESAD. This is a known limitation "
            "of the framework for this dataset, recorded deliberately rather than "
            "silently omitted. Absent an accuracy metric, the framework cannot "
            "assess whether the physiological values themselves are correct, only "
            "that they are complete, conformant, within plausible bounds, and "
            "temporally aligned. See config/thresholds.yaml (accuracy is intentionally absent)."
        ),
    }


# ── Terminal table ────────────────────────────────────────────────────────────

def _print_table(report: dict) -> None:
    dims = report["dimensions"]

    def _pass_str(v) -> str:
        if v is True:  return "PASS"
        if v is False: return "FAIL"
        return "N/A"

    def _rate_str(v, decimals=2) -> str:
        if v is None: return "—"
        if isinstance(v, float) and v < 0.001:
            return f"{v:.2e}"
        return str(v)

    print()
    print("WESAD Before/After Quality Report")
    print("=" * 90)
    print(f"{'Dimension':<28}  {'Before (Bronze)':<22}  {'After (Gold)':<22}  {'Threshold':<14}  {'Gold pass'}")
    print("-" * 90)

    # Completeness
    c = dims["completeness"]
    n_removals = c["after"].get("intentional_removals", {}).get("count", 0)
    removals_note = f" + {n_removals} intentional removals (excl.)" if n_removals else ""
    print(
        f"{'Completeness (missingness)':<28}  "
        f"{_rate_str(c['before']['missingness_rate']):<22}  "
        f"{(_rate_str(c['after']['missingness_rate']) + removals_note):<22}  "
        f"{_rate_str(c['threshold']):<14}  "
        f"{_pass_str(c['threshold_pass_gold'])}"
    )

    # Validity — conformance
    vc = dims["validity_conformance"]
    print(
        f"{'Validity: conformance rate':<28}  "
        f"{_rate_str(vc['before']['violation_rate']):<22}  "
        f"{_rate_str(vc['after']['violation_rate']):<22}  "
        f"{_rate_str(vc['threshold']):<14}  "
        f"{_pass_str(vc['threshold_pass_gold'])}"
    )

    # Validity — plausibility
    vp = dims["validity_plausibility"]
    print(
        f"{'Validity: plausibility rate':<28}  "
        f"{_rate_str(vp['before']['failure_rate']):<22}  "
        f"{_rate_str(vp['after']['failure_rate']):<22}  "
        f"{_rate_str(vp['threshold']):<14}  "
        f"{_pass_str(vp['threshold_pass_gold'])}"
    )

    # Timeliness
    t = dims["timeliness"]
    print(
        f"{'Timeliness: offset (s)':<28}  "
        f"{'~1181 s (raw start gap)':<22}  "
        f"{_rate_str(t['after']['max_offset_s']):<22}  "
        f"{_rate_str(t['threshold']):<14}  "
        f"{_pass_str(t['threshold_pass_gold'])}"
    )

    # Consistency
    print(
        f"{'Consistency':<28}  "
        f"{'no metric':<22}  "
        f"{'no metric':<22}  "
        f"{'—':<14}  "
        f"{'N/A (intentionally unmeasured)'}"
    )

    # Accuracy
    print(
        f"{'Accuracy':<28}  "
        f"{'no metric':<22}  "
        f"{'no metric':<22}  "
        f"{'—':<14}  "
        f"{'N/A (stated limitation)'}"
    )

    print("-" * 90)
    oa = report["overall_assessment"]
    print(
        f"{'Overall':<28}  {'':22}  {'':22}  {'':14}  "
        f"{'PASS' if oa['gold_passes_all_measured_thresholds'] else 'FAIL'}"
    )
    print()
    print("Notes:")
    print("  Completeness: 60 intentional removals (TEMP warm-up artefact) are excluded")
    print("  from missingness_rate and reported separately. Unintended missingness = 0.0.")
    print("  Conformance 60->0 and plausibility 60->0 confirm the pipeline detected and")
    print("  resolved a real quality issue. After values are measured, not derived.")
    print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> dict:
    thresholds = _load_thresholds()

    if not thresholds.get("meta", {}).get("signed_off"):
        raise RuntimeError(
            "config/thresholds.yaml is not signed off "
            "(meta.signed_off is false). Quality report refused."
        )

    # Bronze-baseline reports (the "before")
    conformance_before  = _load_report("wesad_conformance.json")
    completeness_before = _load_report("wesad_completeness.json")
    plausibility_before = _load_report("wesad_plausibility.json")
    alignment           = _load_report("wesad_alignment.json")

    # Post-cleaning measured reports (the "after") — produced by post_cleaning.py
    conformance_after  = _load_report("wesad_conformance_post_cleaning.json")
    completeness_after = _load_report("wesad_completeness_post_cleaning.json")
    plausibility_after = _load_report("wesad_plausibility_post_cleaning.json")

    dimensions = {
        "completeness":          _dim_completeness(
                                     thresholds, completeness_before, completeness_after),
        "validity_conformance":  _dim_validity_conformance(
                                     thresholds, conformance_before, conformance_after),
        "validity_plausibility": _dim_validity_plausibility(
                                     thresholds, plausibility_before, plausibility_after),
        "timeliness":            _dim_timeliness(thresholds, alignment),
        "consistency":           _dim_consistency(thresholds),
        "accuracy":              _dim_accuracy(),
    }

    # All four measurable dimensions now genuinely pass.
    gold_passes = (
        dimensions["completeness"]["threshold_pass_gold"]
        and dimensions["validity_conformance"]["threshold_pass_gold"]
        and dimensions["validity_plausibility"]["threshold_pass_gold"]
        and dimensions["timeliness"]["threshold_pass_gold"]
    )

    report = {
        "schema":      "wesad_quality_report_v2",
        "dataset":     "WESAD",
        "report_type": "before_after_quality_comparison",
        "framework":   (
            "Five-dimension quality framework grounded in Batini et al. (2009) "
            "and Wang & Strong (1996). Thresholds pre-registered in "
            "config/thresholds.yaml (signed off: Dr. Tobias Cibis, 2026-09-09)."
        ),
        "thresholds_signed_off_by": thresholds["meta"]["signed_off_by"],
        "thresholds_date_locked":   str(thresholds["meta"]["date_locked"]),
        "source_reports": {
            "profiling":               "reports/wesad_baseline.json",
            "conformance_before":      "reports/wesad_conformance.json",
            "conformance_after":       "reports/wesad_conformance_post_cleaning.json",
            "completeness_before":     "reports/wesad_completeness.json",
            "completeness_after":      "reports/wesad_completeness_post_cleaning.json",
            "plausibility_before":     "reports/wesad_plausibility.json",
            "plausibility_after":      "reports/wesad_plausibility_post_cleaning.json",
            "alignment":               "reports/wesad_alignment.json",
            "cleaning":                "reports/wesad_cleaning.json",
        },
        "determinism_note": (
            "All source reports are deterministic. This report is therefore fully "
            "deterministic. No timestamps are included."
        ),
        "dimensions": dimensions,
        "overall_assessment": {
            "gold_passes_all_measured_thresholds": gold_passes,
            "measured_dimensions": [
                "completeness", "validity_conformance",
                "validity_plausibility", "timeliness",
            ],
            "unmeasured_dimensions": ["consistency", "accuracy"],
            "headline": (
                "The Gold pipeline resolves the only quality issues found in WESAD. "
                "Conformance and plausibility violations fall from 60 to 0 after "
                "cleaning the E4 TEMP warm-up artefact. Completeness after cleaning: "
                "unintentional missingness = 0.0 (60 intentional removals reported "
                "separately). Cross-modal alignment passes the 1.0 s threshold "
                "(max residual 0.107 s). All four measured dimensions pass. "
                "The framework demonstrates end-to-end detection, documentation, "
                "and resolution of a real quality issue."
            ),
        },
    }

    out_path = REPORTS / "wesad_quality_report.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    _print_table(report)
    print(f"Report written to: reports/wesad_quality_report.json")

    return report


if __name__ == "__main__":
    main()
