"""
Tests for deap/src/gold_manifest.py.
"""
import json
import os
import sys

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
    """verify_manifest() must pass (65 checksums) for the current pipeline output."""
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


def test_gold_manifest_participants_have_dat_and_labels():
    """Every participant entry must have both 'dat' and 'labels' sub-entries."""
    if not _OUTPUT_PATH.exists():
        pytest.skip("deap_gold_manifest.json not found; run pipeline first")
    with open(_OUTPUT_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    for pid, entry in manifest["participants"].items():
        assert "dat" in entry, f"{pid} missing 'dat' sub-entry"
        assert "labels" in entry, f"{pid} missing 'labels' sub-entry"
        assert entry["dat"]["layer"] == "bronze", f"{pid}.dat has wrong layer"
        assert entry["labels"]["layer"] == "silver", f"{pid}.labels has wrong layer"
        assert entry["dat"]["authoritative_path"].startswith("bronze/DEAP/"), (
            f"{pid}.dat has unexpected path: {entry['dat']['authoritative_path']}"
        )
        assert entry["labels"]["authoritative_path"].startswith("silver/DEAP/labels/"), (
            f"{pid}.labels has unexpected path: {entry['labels']['authoritative_path']}"
        )


def test_gold_manifest_xls_entry_present():
    """Manifest summary must contain participant_ratings.xls with a SHA-256."""
    if not _OUTPUT_PATH.exists():
        pytest.skip("deap_gold_manifest.json not found; run pipeline first")
    with open(_OUTPUT_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    xls = manifest["summary"].get("participant_ratings_xls", {})
    assert "authoritative_path" in xls, "XLS entry missing authoritative_path"
    assert "sha256" in xls, "XLS entry missing sha256"
    assert len(xls["sha256"]) == 64, "XLS sha256 must be 64 hex chars"
    assert "participant_ratings.xls" in xls["authoritative_path"]


def test_gold_manifest_65_checksums(tmp_path):
    """verify_manifest must check exactly 65 checksums (32 dat + 32 CSV + 1 XLS)."""
    if not _OUTPUT_PATH.exists():
        pytest.skip("deap_gold_manifest.json not found; run pipeline first")
    with open(_OUTPUT_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    # Count entries that have both authoritative_path and sha256
    count = 0
    for pid, entry in manifest["participants"].items():
        for sub_key in ("dat", "labels"):
            sub = entry.get(sub_key, {})
            if sub.get("authoritative_path") and sub.get("sha256"):
                count += 1
    xls = manifest.get("summary", {}).get("participant_ratings_xls", {})
    if xls.get("authoritative_path") and xls.get("sha256"):
        count += 1
    assert count == 65, f"Expected 65 checksums, found {count}"


def test_gold_manifest_tampered_checksum_detected(tmp_path):
    """verify_manifest must return False when a Silver CSV is tampered."""
    if not _OUTPUT_PATH.exists():
        pytest.skip("deap_gold_manifest.json not found; run pipeline first")

    # Copy manifest and alter s01 labels sha256
    with open(_OUTPUT_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    manifest["participants"]["s01"]["labels"]["sha256"] = "a" * 64

    tampered = tmp_path / "tampered.json"
    with open(tampered, "w", encoding="utf-8") as f:
        json.dump(manifest, f)

    result = verify_manifest(manifest_path=tampered)
    assert result is False
