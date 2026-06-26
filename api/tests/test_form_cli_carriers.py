"""Regression coverage for thin form-cli host carriers."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
ASK_SMART_PATH = ROOT / "scripts" / "form_cli_ask_smart.py"
GO_KERNEL = ROOT / "form" / "form-kernel-go" / "bin-go"

_spec = importlib.util.spec_from_file_location("form_cli_ask_smart", ASK_SMART_PATH)
assert _spec and _spec.loader
form_cli_ask_smart = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(form_cli_ask_smart)


@pytest.mark.skipif(not (GO_KERNEL.is_file() and os.access(GO_KERNEL, os.X_OK)), reason="Go kernel not built")
def test_form_cli_smart_uses_pure_control_recipe_not_interactive_repl() -> None:
    out = form_cli_ask_smart.kernel(
        [
            "(frepl-mode 1 0 1)",
            "(frepl-classify 0 1 0)",
        ],
        timeout=5,
    )

    assert out == ["1", "0"]


def test_form_cli_smart_forwards_timeout_to_ask_carrier(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["kwargs"] = kwargs
        return SimpleNamespace(returncode=124)

    monkeypatch.setattr(form_cli_ask_smart.subprocess, "run", fake_run)
    args = SimpleNamespace(model="coder", judge="judge", remote="remote", timeout=3.0)

    assert form_cli_ask_smart.answer_once("question", args) == 124
    assert "--timeout" in seen["args"]
    assert "3.0" in seen["args"]
    assert seen["kwargs"]["timeout"] == 8.0
