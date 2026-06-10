"""Regression tests for kernel attribution parity sensing."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_report_module():
    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "scripts" / "kernel_attribution_report.py"
    spec = importlib.util.spec_from_file_location("kernel_attribution_report_under_test", src)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["kernel_attribution_report_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_value_parity_accepts_numeric_display_equivalence():
    mod = _load_report_module()

    assert mod._value_parity_matches("2", "2.0")
    assert mod._value_parity_matches("1", "1.0")
    assert mod._value_parity_matches(
        "[19.9998, 4.9999, 8.3332, 0, 0, 33.333]",
        "[19.9998, 4.9999, 8.3332, 0.0, 0.0, 33.333]",
    )
    assert mod._value_parity_matches(
        "[48, 25.333, 0.5278]",
        "[48.0, 25.333, 0.5278]",
    )


def test_value_parity_rejects_actual_numeric_drift():
    mod = _load_report_module()

    assert not mod._value_parity_matches("0.9999999999999998", "1.0")
    assert not mod._value_parity_matches(
        "[48, 25.334, 0.5278]",
        "[48.0, 25.333, 0.5278]",
    )
