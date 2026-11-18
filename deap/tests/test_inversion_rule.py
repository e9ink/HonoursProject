"""
Tests for the inversion rule verification in deap/reports/deap_label_audit.json.

The rule: a v2 trial is inverted (both Valence and Arousal follow 9 - xls_val)
if and only if its XLS Valence > 5 AND XLS Arousal > 5.
Expected: 439 trials meet the condition, all 439 are inverted, 0 exceptions.
"""
import json
import os
import sys

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AUDIT_PATH = os.path.join(PROJECT_ROOT, "deap", "reports", "deap_label_audit.json")


def _load_audit():
    if not os.path.exists(AUDIT_PATH):
        pytest.skip("deap_label_audit.json not found; run label_audit first")
    with open(AUDIT_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_inversion_rule_section_present():
    """deap_label_audit.json must contain an inversion_rule section."""
    audit = _load_audit()
    assert "inversion_rule" in audit, "inversion_rule key missing from label audit report"


def test_trials_meeting_condition():
    """439 trials must have XLS Valence > 5 AND Arousal > 5."""
    audit = _load_audit()
    ir = audit["inversion_rule"]
    assert ir["trials_meeting_condition"] == 439, (
        f"Expected 439 trials meeting condition, got {ir['trials_meeting_condition']}"
    )


def test_all_condition_trials_inverted():
    """All 439 trials meeting the condition must be inverted in v2."""
    audit = _load_audit()
    ir = audit["inversion_rule"]
    assert ir["trials_inverted_in_condition"] == 439, (
        f"Expected 439 inverted, got {ir['trials_inverted_in_condition']}"
    )


def test_no_inversions_outside_condition():
    """No trials outside XLS Valence > 5 AND Arousal > 5 must be inverted."""
    audit = _load_audit()
    ir = audit["inversion_rule"]
    outside = ir["trials_inverted_outside_condition"]
    assert outside == 0, (
        f"Expected 0 inversions outside condition, got {outside}"
    )


def test_rule_exceptions_zero():
    """The inversion rule must have zero exceptions (no partial inversions)."""
    audit = _load_audit()
    ir = audit["inversion_rule"]
    n_exc = ir["rule_exceptions_count"]
    assert n_exc == 0, (
        f"Expected 0 rule exceptions, got {n_exc}: {ir.get('rule_exceptions', [])[:3]}"
    )


def test_quadrant_counts_sum_to_1280():
    """Four quadrant trial counts must sum to 1280 (32 participants * 40 trials)."""
    audit = _load_audit()
    ir = audit["inversion_rule"]
    total = sum(v["trials"] for v in ir["quadrant_counts"].values())
    assert total == 1280, f"Expected 1280 total trials, got {total}"


def test_total_inversions_match_cross_source():
    """Total inversions from inversion_rule must equal cross-source mismatch count / 2."""
    audit = _load_audit()
    ir = audit["inversion_rule"]
    total_inv = sum(v["inverted"] for v in ir["quadrant_counts"].values())
    cross_source_mismatches = audit["v2_mirror"]["xls_comparison"]["summary"]["total_inverted"]
    # Each inverted trial contributes 2 entries (Valence + Arousal)
    assert total_inv * 2 == cross_source_mismatches, (
        f"Total inverted trials ({total_inv}) * 2 should equal cross-source mismatches "
        f"({cross_source_mismatches})"
    )
