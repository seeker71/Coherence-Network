"""Form-native grammar contract: host parser bridges are not completion."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "form_native_grammar_contract.py"
FORM_CLI = ROOT / "scripts" / "form_cli.py"


def _contract_module():
    spec = importlib.util.spec_from_file_location("form_native_grammar_contract", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_audit_separates_declared_grammar_from_native_stream() -> None:
    report = _contract_module().audit()

    rows = {row["extension"]: row for row in report["extensions"]}
    assert rows["png"]["grammar_declared"] is True
    assert rows["png"]["form_native_stream"] is False
    assert "png" in report["summary"]["binary_declared_not_native"]


def test_audit_names_host_bridges_as_debt() -> None:
    report = _contract_module().audit()

    assert "python" in report["host_bridges"]
    assert "ast.parse" in report["host_bridges"]["python"]
    assert report["summary"]["form_native_stream_extensions"] == 0


def test_form_cli_refuses_host_bridge_by_default(tmp_path: Path) -> None:
    sample = tmp_path / "sample.json"
    sample.write_text('{"ok": true}\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(FORM_CLI), "convert", "in", "--tongue", "json", str(sample)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 2
    assert "host-language bridge" in result.stderr


def test_form_cli_host_bridge_requires_explicit_flag(tmp_path: Path) -> None:
    sample = tmp_path / "sample.json"
    sample.write_text('{"ok": true}\n', encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(FORM_CLI),
            "convert",
            "--allow-host-bridge",
            "in",
            "--tongue",
            "json",
            str(sample),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert '"source_tongue": "json"' in result.stdout
