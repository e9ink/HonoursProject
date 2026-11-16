"""
Unit tests for src/gold_manifest.py verify_manifest function.

All tests use synthetic files in a temporary directory. No real WESAD
participant data is read.
"""
import hashlib
import json
from pathlib import Path


from src.gold_manifest import _sha256, verify_manifest


def _write_file(path: Path, content: bytes) -> str:
    """Write bytes to path and return its hex SHA-256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _make_manifest(tmp_path: Path, entries: list[dict]) -> Path:
    """
    Write a minimal manifest JSON to tmp_path/manifest.json.
    entries: list of {pid, signal, rel_path, sha256} dicts.
    """
    participants = {}
    for e in entries:
        pid = e["pid"]
        sig = e["signal"]
        if pid not in participants:
            participants[pid] = {"e4": {}, "respiban": None}
        if sig == "respiban":
            participants[pid]["respiban"] = {
                "authoritative_path": e["rel_path"],
                "sha256": e["sha256"],
            }
        else:
            participants[pid]["e4"][sig] = {
                "authoritative_path": e["rel_path"],
                "sha256": e["sha256"],
            }

    manifest = {"participants": participants}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


# ---------------------------------------------------------------------------
# _sha256
# ---------------------------------------------------------------------------

def test_sha256_known_value(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    expected = hashlib.sha256(b"hello").hexdigest()
    assert _sha256(f) == expected


def test_sha256_empty_file(tmp_path):
    f = tmp_path / "empty.bin"
    f.write_bytes(b"")
    assert _sha256(f) == hashlib.sha256(b"").hexdigest()


# ---------------------------------------------------------------------------
# verify_manifest -- passing cases
# ---------------------------------------------------------------------------

def test_verify_manifest_single_file_passes(tmp_path):
    content = b"synthetic e4 data\n"
    rel = "bronze/WESAD/Sx/Sx_E4_Data/EDA.csv"
    digest = _write_file(tmp_path / rel, content)
    manifest_path = _make_manifest(tmp_path, [{"pid": "Sx", "signal": "EDA", "rel_path": rel, "sha256": digest}])
    assert verify_manifest(manifest_path, root=tmp_path) is True


def test_verify_manifest_multiple_files_passes(tmp_path):
    files = [
        ("Sx", "ACC", "bronze/WESAD/Sx/Sx_E4_Data/ACC.csv", b"acc data"),
        ("Sx", "TEMP", "silver/WESAD/Sx/Sx_E4_Data/TEMP.csv", b"temp data"),
        ("Sx", "respiban", "bronze/WESAD/Sx/Sx_respiban.txt", b"rb data"),
        ("Sy", "HR", "bronze/WESAD/Sy/Sy_E4_Data/HR.csv", b"hr data"),
    ]
    entries = []
    for pid, sig, rel, content in files:
        digest = _write_file(tmp_path / rel, content)
        entries.append({"pid": pid, "signal": sig, "rel_path": rel, "sha256": digest})
    manifest_path = _make_manifest(tmp_path, entries)
    assert verify_manifest(manifest_path, root=tmp_path) is True


# ---------------------------------------------------------------------------
# verify_manifest -- failing cases
# ---------------------------------------------------------------------------

def test_verify_manifest_detects_modified_e4_file(tmp_path):
    rel = "bronze/WESAD/Sx/Sx_E4_Data/EDA.csv"
    digest = _write_file(tmp_path / rel, b"original content")
    manifest_path = _make_manifest(tmp_path, [{"pid": "Sx", "signal": "EDA", "rel_path": rel, "sha256": digest}])
    # Overwrite the file with different content
    (tmp_path / rel).write_bytes(b"modified content")
    assert verify_manifest(manifest_path, root=tmp_path) is False


def test_verify_manifest_detects_modified_respiban_file(tmp_path):
    rel = "bronze/WESAD/Sx/Sx_respiban.txt"
    digest = _write_file(tmp_path / rel, b"original rb content\n")
    manifest_path = _make_manifest(tmp_path, [{"pid": "Sx", "signal": "respiban", "rel_path": rel, "sha256": digest}])
    (tmp_path / rel).write_bytes(b"modified rb content\n")
    assert verify_manifest(manifest_path, root=tmp_path) is False


def test_verify_manifest_one_mismatch_among_many(tmp_path, capsys):
    files = [
        ("Sx", "ACC", "bronze/WESAD/Sx/Sx_E4_Data/ACC.csv", b"acc data"),
        ("Sx", "EDA", "bronze/WESAD/Sx/Sx_E4_Data/EDA.csv", b"eda data"),
    ]
    entries = []
    for pid, sig, rel, content in files:
        digest = _write_file(tmp_path / rel, content)
        entries.append({"pid": pid, "signal": sig, "rel_path": rel, "sha256": digest})
    manifest_path = _make_manifest(tmp_path, entries)
    # Corrupt only EDA
    (tmp_path / "bronze/WESAD/Sx/Sx_E4_Data/EDA.csv").write_bytes(b"corrupted eda")
    result = verify_manifest(manifest_path, root=tmp_path)
    assert result is False
    captured = capsys.readouterr()
    assert "EDA" in captured.out
    assert "ACC" not in captured.out


def test_verify_manifest_missing_sha256_field_is_skipped(tmp_path):
    """An entry without a sha256 key is silently skipped (no crash)."""
    rel = "bronze/WESAD/Sx/Sx_E4_Data/HR.csv"
    _write_file(tmp_path / rel, b"hr data")
    manifest = {
        "participants": {
            "Sx": {
                "e4": {
                    "HR": {"authoritative_path": rel}  # no sha256 key
                },
                "respiban": None,
            }
        }
    }
    mp = tmp_path / "manifest.json"
    mp.write_text(json.dumps(manifest), encoding="utf-8")
    assert verify_manifest(mp, root=tmp_path) is True
