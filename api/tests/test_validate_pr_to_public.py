from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    api_root = Path(__file__).resolve().parents[1]
    script = api_root / "scripts" / "validate_pr_to_public.py"
    spec = importlib.util.spec_from_file_location("validate_pr_to_public", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_semver_handles_common_inputs() -> None:
    mod = _load_module()

    assert mod._parse_semver("1.123.17") == (1, 123, 17)
    assert mod._parse_semver("v2.5.2") == (2, 5, 2)
    assert mod._parse_semver("2.5.2-beta.1") == (2, 5, 2)
    assert mod._parse_semver("2.5") == (2, 5, 0)
    assert mod._parse_semver("bad") is None


def test_n8n_gate_blocks_old_v1() -> None:
    mod = _load_module()

    gate = mod._evaluate_n8n_minimum("1.123.16")
    assert gate["ok"] is False
    assert gate["minimum"] == "1.123.17"
    assert "below minimum" in str(gate["reason"])


def test_n8n_gate_allows_fixed_v1() -> None:
    mod = _load_module()

    gate = mod._evaluate_n8n_minimum("1.123.17")
    assert gate["ok"] is True
    assert gate["minimum"] == "1.123.17"


def test_n8n_gate_blocks_old_v2() -> None:
    mod = _load_module()

    gate = mod._evaluate_n8n_minimum("2.5.1")
    assert gate["ok"] is False
    assert gate["minimum"] == "2.5.2"


def test_n8n_gate_rejects_invalid_version() -> None:
    mod = _load_module()

    gate = mod._evaluate_n8n_minimum("version-unknown")
    assert gate["ok"] is False
    assert gate["reason"] == "invalid_n8n_version_format"
