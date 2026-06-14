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


def test_transmute_routes_and_reasons(monkeypatch):
    # transmute is ROUTED (form-native transmuter vs the sovereign reasoner) and
    # actually reasons — no metered API, no fake rewrite. With a reasoner present
    # it returns transmuted text; without one it hands back the instruction.
    monkeypatch.setattr(fct, "kernel_route", lambda a, b: {"winner": "agent-cli"})
    monkeypatch.setattr(fct, "_reason", lambda prompt, oracle, timeout=120.0:
                        "An opportunity with clear next data.")
    out = fct.transmute_text("this is too dangerous to attempt")
    assert out["route"] == "agent-cli"
    assert out["transmuted"] == "An opportunity with clear next data."

    # reasoner unreachable -> instruction handed back, never faked
    monkeypatch.setattr(fct, "_reason", lambda *a, **k: "")
    out2 = fct.transmute_text("this is risky")
    assert out2["transmuted"] == ""
    assert "opportunity" in out2["instruction"]


def test_transmute_and_capture_writes_full_pair(tmp_path, monkeypatch):
    monkeypatch.setattr(fct, "_CATALOG", tmp_path / "tc.jsonl")
    monkeypatch.setattr(fct, "kernel_route", lambda a, b: {"winner": "agent-cli"})
    monkeypatch.setattr(fct, "_reason", lambda *a, **k: "the gradient we walk")
    e = fct.transmute_and_capture("plan it", "this blocks us", "agent-cli:test")
    assert e["raw"] == "this blocks us"
    assert e["transmuted"] == "the gradient we walk"
    assert e["outcome"] == "turn"
    assert e["raw_sig"] != e["transmuted_sig"]


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


def test_stop_hook_spawns_detached_worker(tmp_path, monkeypatch):
    # the hook does NOT reason inline (no blocking) — it extracts the turn and
    # spawns a detached worker with the (request, raw) handed off in a temp file.
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

    spawned: dict = {}

    def fake_popen(argv, **kwargs):
        spawned["argv"] = argv
        spawned["detached"] = kwargs.get("start_new_session")
        payload = json.loads(Path(argv[2]).read_text(encoding="utf-8"))
        spawned["payload"] = payload
        Path(argv[2]).unlink()  # we consume the temp; worker would too

        class _P:  # a stand-in process handle
            pass
        return _P()

    monkeypatch.setattr(hook.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(sys, "stdin",
                        _Stdin(json.dumps({"transcript_path": str(transcript)})))
    assert hook.main() == 0
    assert spawned["detached"] is True
    assert spawned["argv"][1].endswith("capture_worker.py")
    assert spawned["payload"]["request"] == "plan the routing"
    assert spawned["payload"]["raw"] == "Here is a risky plan."


class _Stdin:
    def __init__(self, text: str):
        self._text = text

    def read(self) -> str:
        return self._text
