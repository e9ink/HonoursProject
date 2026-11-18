"""
Tests for the sign-off gate in all DEAP check modules and report.

Each module must raise RuntimeError when meta.signed_off is false in
thresholds.yaml (and cleaning.yaml for cleaning.py).
"""
import os
import sys
import tempfile
import pickle

import numpy as np
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from deap.src.checks.completeness import run as run_completeness
from deap.src.checks.conformance import run as run_conformance
from deap.src.checks.label_plausibility import run as run_label_plausibility
from deap.src.checks.consistency import run as run_consistency
from deap.src.checks.post_cleaning import run as run_post_cleaning
from deap.src.report import run as run_report


def _write_yaml(path: str, content: str) -> None:
    with open(path, "w") as f:
        f.write(content)


def _make_dat(tmpdir: str) -> str:
    data = np.ones((40, 40, 8064), dtype=np.float64)
    labels = np.ones((40, 4), dtype=np.float64) * 5.0
    path = os.path.join(tmpdir, "s99.dat")
    with open(path, "wb") as f:
        pickle.dump({"data": data, "labels": labels}, f, protocol=4)
    return tmpdir


def test_completeness_gate_blocks_when_not_signed_off(tmp_path):
    cfg = tmp_path / "thresholds.yaml"
    _write_yaml(str(cfg), "meta:\n  signed_off: false\ncompleteness:\n  max_nan_count: 0\n  max_inf_count: 0\n")
    with pytest.raises(RuntimeError, match="signed off"):
        run_completeness.__wrapped__ if hasattr(run_completeness, '__wrapped__') else None
        import deap.src.checks.completeness as m
        orig = m.CONFIG
        m.CONFIG = str(cfg)
        try:
            m.run(dat_dir=str(tmp_path), output_path=str(tmp_path / "out.json"))
        finally:
            m.CONFIG = orig


def test_conformance_gate_blocks_when_not_signed_off(tmp_path):
    cfg = tmp_path / "thresholds.yaml"
    _write_yaml(str(cfg), "meta:\n  signed_off: false\nconformance:\n  expected_data_shape: [40,40,8064]\n  expected_labels_shape: [40,4]\n  expected_dtype: float64\n  max_violations: 0\n")
    import deap.src.checks.conformance as m
    orig = m.CONFIG
    m.CONFIG = str(cfg)
    try:
        with pytest.raises(RuntimeError, match="signed off"):
            m.run(dat_dir=str(tmp_path), output_path=str(tmp_path / "out.json"))
    finally:
        m.CONFIG = orig


def test_label_plausibility_gate_blocks_when_not_signed_off(tmp_path):
    cfg = tmp_path / "thresholds.yaml"
    _write_yaml(str(cfg), "meta:\n  signed_off: false\nlabel_plausibility:\n  min_label_value: 1\n  max_label_value: 9\n  max_out_of_range: 0\n")
    import deap.src.checks.label_plausibility as m
    orig = m.CONFIG
    m.CONFIG = str(cfg)
    try:
        with pytest.raises(RuntimeError, match="signed off"):
            m.run(dat_dir=str(tmp_path), output_path=str(tmp_path / "out.json"))
    finally:
        m.CONFIG = orig


def test_consistency_gate_blocks_when_not_signed_off(tmp_path):
    cfg = tmp_path / "thresholds.yaml"
    _write_yaml(str(cfg), "meta:\n  signed_off: false\nconsistency_cross_source:\n  tolerance: 1e-4\nconsistency_structure:\n  max_mismatches: 0\nconformance:\n  expected_data_shape: [40,40,8064]\n  expected_labels_shape: [40,4]\n")
    import deap.src.checks.consistency as m
    orig = m.CONFIG
    m.CONFIG = str(cfg)
    try:
        with pytest.raises(RuntimeError, match="signed off"):
            m.run(dat_dir=str(tmp_path), xls_path=str(tmp_path / "x.xls"),
                  output_path=str(tmp_path / "out.json"))
    finally:
        m.CONFIG = orig


def test_post_cleaning_gate_blocks_when_not_signed_off(tmp_path):
    cfg = tmp_path / "thresholds.yaml"
    _write_yaml(str(cfg), "meta:\n  signed_off: false\nlabel_plausibility:\n  min_label_value: 1\n  max_label_value: 9\n  max_out_of_range: 0\nconsistency_cross_source:\n  tolerance: 1e-4\n  max_mismatches: 0\n")
    import deap.src.checks.post_cleaning as m
    orig = m.CONFIG
    m.CONFIG = str(cfg)
    try:
        silver = tmp_path / "labels"
        silver.mkdir()
        with pytest.raises(RuntimeError, match="signed off"):
            m.run(silver_dir=str(silver),
                  xls_path=str(tmp_path / "x.xls"),
                  output_path=str(tmp_path / "out.json"))
    finally:
        m.CONFIG = orig


def test_report_gate_blocks_when_not_signed_off(tmp_path):
    cfg = tmp_path / "thresholds.yaml"
    _write_yaml(str(cfg), "meta:\n  signed_off: false\ncompleteness:\n  max_nan_count: 0\n  max_inf_count: 0\nconformance:\n  max_violations: 0\nlabel_plausibility:\n  max_out_of_range: 0\nconsistency_structure:\n  max_mismatches: 0\nconsistency_cross_source:\n  tolerance: 1e-4\nphysiological_plausibility:\n  reason: deferred\ntimeliness:\n  reason: N/A\n")
    import deap.src.report as m
    orig = m.CONFIG
    m.CONFIG = str(cfg)
    try:
        with pytest.raises(RuntimeError, match="signed off"):
            m.run(reports_dir=str(tmp_path),
                  output_path=str(tmp_path / "out.json"))
    finally:
        m.CONFIG = orig


def test_cleaning_gate_blocks_when_not_signed_off(tmp_path):
    cfg = tmp_path / "cleaning.yaml"
    _write_yaml(str(cfg), "meta:\n  signed_off: false\n")
    import deap.src.cleaning as m
    orig = m.CLEANING_CONFIG
    m.CLEANING_CONFIG = str(cfg)
    try:
        with pytest.raises(RuntimeError, match="signed off"):
            m.run(dat_dir=str(tmp_path),
                  xls_path=str(tmp_path / "x.xls"),
                  silver_dir=str(tmp_path / "s"),
                  output_path=str(tmp_path / "out.json"))
    finally:
        m.CLEANING_CONFIG = orig
