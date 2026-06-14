"""form_cli `ask` front door: serve Form-native, route the rest, capture for learning.

The usable entry an agent asks first. These tests cover the routing decision and
the io-match capture without requiring the kernel; the Form-native compute path is
exercised when the kernel binary is present (skipped otherwise).
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

_FORM_CLI_PATH = Path(__file__).resolve().parents[2] / "scripts" / "form_cli.py"
_spec = importlib.util.spec_from_file_location("form_cli", _FORM_CLI_PATH)
assert _spec and _spec.loader
form_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(form_cli)

_KERNEL = form_cli._KERNEL_BIN
_HAVE_KERNEL = _KERNEL.is_file() and os.access(_KERNEL, os.X_OK)


def test_is_form_expr_routing():
    assert form_cli._is_form_expr("(mul 17 23)") is True
    assert form_cli._is_form_expr("  (add 1 2)") is True
    assert form_cli._is_form_expr("write me a poem") is False


def test_non_form_request_routes_to_oracle():
    res = form_cli.ask_handle("summarize this document")
    assert res["lane"] == "oracle"
    assert res["outcome"] == "route"
    assert res["tokens"] is None


def test_capture_writes_io_match_record(tmp_path, monkeypatch):
    cap = tmp_path / "cap.jsonl"
    monkeypatch.setattr(form_cli, "_ASK_CAPTURE", cap)
    res = {"result": "391", "lane": "form-native:compute", "outcome": "success", "tokens": 0}
    form_cli.ask_capture("(mul 17 23)", res)
    rec = json.loads(cap.read_text().strip())
    # content-addressed in/out (sha256), lane + outcome carried.
    assert rec["input_sig"] == form_cli._io_sig("(mul 17 23)")
    assert rec["output_sig"] == form_cli._io_sig("391")
    assert rec["lane"] == "form-native:compute" and rec["outcome"] == "success" and rec["tokens"] == 0


def test_same_input_same_sig():
    assert form_cli._io_sig("(mul 17 23)") == form_cli._io_sig("(mul 17 23)")
    assert form_cli._io_sig("(mul 17 23)") != form_cli._io_sig("(mul 17 24)")


@pytest.mark.skipif(not _HAVE_KERNEL, reason="form-kernel-rust binary not built in this env")
def test_compute_lane_runs_form_native():
    res = form_cli.ask_handle("(mul 17 23)")
    assert res["lane"] == "form-native:compute"
    assert res["outcome"] == "success"
    assert res["tokens"] == 0
    assert res["result"] == "391"
