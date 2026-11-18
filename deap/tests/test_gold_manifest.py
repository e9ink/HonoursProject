"""
Tests for deap/src/gold_manifest.py.
"""
import csv
import hashlib
import json
import os
import sys
import tempfile

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from deap.src.gold_manifest import _sha256, verify_manifest, _OUTPUT_PATH


def test_sha256_round_trip(tmp_path):
    """SHA-256 of a written file must match re-computation."""
    p = tmp_path / "test.csv"
    p.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    h1 = _sha256(p)
    h2 = _sha256(p)
    assert h1 == h2
    assert len(h1) == 64  # 256-bit = 64 hex chars


def test_sha256_different_for_different_content(tmp_path):
    """Different file content must produce different SHA-256."""
    p1 = tmp_path / "a.csv"
    p2 = tmp_path / "b.csv"
    p1.write_text("hello", encoding="utf-8")
    p2.write_text("world", encoding="utf-8")
    assert _sha256(p1) != _sha256(p2)


def test_verify_manifest_passes_on_live_data():
    """verify_manifest() must pass for the current pipeline output."""
    if not _OUTPUT_PATH.exists():
        pytest.skip("deap_gold_manifest.json not found; run pipeline first")
    result = verify_manifest()
    assert result is True


def test_gold_manifest_has_32_participants():
    """Manifest must list exactly 32 participants."""
    if not _OUTPUT_PATH.exists():
        pytest.skip("deap_gold_manifest.json not found; run pipeline first")
    with open(_OUTPUT_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["summary"]["n_participants"] == 32


def test_gold_manifest_total_corrections_matches_cleaning():
    """Gold manifest total_corrections must match deap_cleaning.json."""
    if not _OUTPUT_PATH.exists():
        pytest.skip("deap_gold_manifest.json not found; run pipeline first")
    cleaning_path = os.path.join(
        PROJECT_ROOT, "deap", "reports", "deap_cleaning.json"
    )
    if not os.path.exists(cleaning_path):
        pytest.skip("deap_cleaning.json not found; run pipeline first")
    with open(_OUTPUT_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(cleaning_path) as f:
        cleaning = json.load(f)
    assert manifest["summary"]["total_label_corrections"] == cleaning["total_corrections"]


def test_gold_manifest_post_cleaning_pass_true():
    """Manifest summary must report post_cleaning_overall_pass = True."""
    if not _OUTPUT_PATH.exists():
        pytest.skip("deap_gold_manifest.json not found; run pipeline first")
    with open(_OUTPUT_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["summary"]["post_cleaning_overall_pass"] is True


def test_gold_manifest_all_participants_have_silver_path():
    """Every participant entry must have an authoritative_path under silver/DEAP/labels/."""
    if not _OUTPUT_PATH.exists():
        pytest.skip("deap_gold_manifest.json not found; run pipeline first")
    with open(_OUTPUT_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    for pid, entry in manifest["participants"].items():
        assert entry["authoritative_path"].startswith("silver/DEAP/labels/"), (
            f"{pid} has unexpected path: {entry['authoritative_path']}"
        )
        assert entry["layer"] == "silver"
