"""form-cli MCP tools + Stop-hook — the learning flywheel inside an agent session.

route delegates to the four-way-proven Form recipe (form-cli-router.fk) on the
kernel; capture/transmute/hook are thin carriers over the training-catalog shape.
The body is Form; these tests prove the carrier delegates and persists honestly.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_MCP = Path(__file__).resolve().parents[2] / "mcp-server"
sys.path.insert(0, str(_MCP))

from coherence_mcp_server import form_cli_tools as fct  # noqa: E402


def test_capture_keeps_both_and_derives_three_pairs(tmp_path, monkeypatch):
    monkeypatch.setattr(fct, "_CATALOG", tmp_path / "cat.jsonl")
    e = fct.catalog_capture("design the surface",
                            "this is risky and blocks us",
                            "a gradient with clear next data",
                            "agent-cli:claude", "turn")
    assert e["raw"].startswith("this is risky")
    assert e["transmuted"].startswith("a gradient")
    assert e["raw_sig"] != e["transmuted_sig"]
    rs, raws, vits = e["request_sig"], e["raw_sig"], e["transmuted_sig"]
    assert e["pairs"]["raw"] == [rs, raws]
    assert e["pairs"]["transmute"] == [raws, vits]
    assert e["pairs"]["reasoning"] == [rs, vits]


def test_capture_appends_durably(tmp_path, monkeypatch):
    cat = tmp_path / "c.jsonl"
    monkeypatch.setattr(fct, "_CATALOG", cat)
    fct.catalog_capture("R1", "raw1", "vit1", "agent-cli", "turn")
    fct.catalog_capture("R2", "raw2", "vit2", "agent-cli", "turn")
    lines = cat.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["request"] == "R2"


def test_transmute_is_routed_not_faked():
    plan = fct.transmute_plan("this is too dangerous to attempt")
    # transmute routes to the agent (no metered API, no fake rewrite here)
    assert plan["route"] == "agent-cli"
    assert "opportunity" in plan["instruction"]
    assert plan["raw"] == "this is too dangerous to attempt"


def test_route_uses_the_kernel_recipe(tmp_path):
    # route delegates to fcr-route on the kernel; if the kernel binary isn't
    # built it reports that honestly rather than guessing in Python.
    out = fct.kernel_route(
        {"sovereignty": 100, "trust": 80, "capability": 80, "confidence": 80},
        {"sovereignty": 50, "trust": 90, "capability": 100, "confidence": 100},
    )
    if "error" in out:
        assert "kernel" in out["error"].lower()  # honest "not built" path
    else:
        assert out["winner"] == "form-native" and out["sovereign"] is True


def test_stop_hook_captures_a_turn(tmp_path, monkeypatch):
    monkeypatch.setattr(fct, "_CATALOG", tmp_path / "hook.jsonl")
    transcript = tmp_path / "t.jsonl"
    transcript.write_text("\n".join(json.dumps(r) for r in [
        {"type": "user", "message": {"role": "user", "content": "plan the routing"}},
        {"type": "assistant", "message": {"role": "assistant",
         "content": [{"type": "text", "text": "Here is a risky plan."}]}},
    ]), encoding="utf-8")

    spec = importlib.util.spec_from_file_location(
        "capture_hook", _MCP / "coherence_mcp_server" / "capture_hook.py")
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)

    monkeypatch.setattr(sys, "stdin",
                        _Stdin(json.dumps({"transcript_path": str(transcript)})))
    assert hook.main() == 0
    entry = json.loads((tmp_path / "hook.jsonl").read_text().strip())
    assert entry["request"] == "plan the routing"
    assert entry["raw"] == "Here is a risky plan."
    assert entry["outcome"] == "turn-raw" and entry["transmuted"] == ""


class _Stdin:
    def __init__(self, text: str):
        self._text = text

    def read(self) -> str:
        return self._text
