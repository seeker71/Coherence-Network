"""form_cli `agent` — the drop-in agent loop: reason -> tool-channel -> observe -> repeat.

This is the trunk that makes form-cli a drop-in for codex/claude/grok/gemini/cursor.
The loop body and tool catalog are proven Form (form-cli-agent.fk / tool-channel.fk);
these tests prove the carrier drives the loop correctly with a scripted oracle (no
network): it really reads, runs bash, writes files, finishes, and captures every
oracle step + the final reasoning pair into the training catalog.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

_FORM_CLI_PATH = Path(__file__).resolve().parents[2] / "scripts" / "form_cli.py"
_spec = importlib.util.spec_from_file_location("form_cli", _FORM_CLI_PATH)
assert _spec and _spec.loader
form_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(form_cli)


def _ns(**kw) -> argparse.Namespace:
    base = dict(task=["do the thing"], oracle="cmd:scripted", max_steps=12,
                timeout=5.0, cwd=None, no_capture=False)
    base.update(kw)
    return argparse.Namespace(**base)


def _scripted_oracle(actions):
    """Return a fake _oracle_call that emits scripted actions in order, and answers
    any transmute request (prompt starts with the transmute instruction)."""
    seq = list(actions)

    def fake(prompt, backend, model, timeout):
        if prompt.startswith(form_cli._TRANSMUTE_INSTR):
            return "VITALITY: opportunity + data", None
        if seq:
            return json.dumps(seq.pop(0)), None
        return json.dumps({"tool": "done", "args": {"answer": "fallback"}}), None

    return fake


def test_agent_loop_reads_runs_writes_finishes(tmp_path, monkeypatch):
    (tmp_path / "note.txt").write_text("hello", encoding="utf-8")
    monkeypatch.setattr(form_cli, "_CATALOG", tmp_path / "catalog.jsonl")
    monkeypatch.setattr(form_cli, "_ASK_CAPTURE", tmp_path / "io.jsonl")
    monkeypatch.setattr(form_cli, "_oracle_call", _scripted_oracle([
        {"thought": "look", "tool": "read_file", "args": {"path": "note.txt"}},
        {"thought": "make it loud", "tool": "write_file",
         "args": {"path": "out.txt", "content": "HELLO"}},
        {"thought": "finish", "tool": "done", "args": {"answer": "wrote HELLO"}},
    ]))
    rc = form_cli.cmd_agent(_ns(cwd=str(tmp_path)))
    assert rc == 0
    # the loop actually did the work via the host channels
    assert (tmp_path / "out.txt").read_text(encoding="utf-8") == "HELLO"


def test_agent_captures_every_step_and_the_reasoning_pair(tmp_path, monkeypatch):
    cat = tmp_path / "catalog.jsonl"
    io = tmp_path / "io.jsonl"
    monkeypatch.setattr(form_cli, "_CATALOG", cat)
    monkeypatch.setattr(form_cli, "_ASK_CAPTURE", io)
    monkeypatch.setattr(form_cli, "_oracle_call", _scripted_oracle([
        {"tool": "bash", "args": {"cmd": "echo hi"}},
        {"tool": "done", "args": {"answer": "fear: this is risky and might fail"}},
    ]))
    form_cli.cmd_agent(_ns(task=["echo task"], cwd=str(tmp_path)))
    # every oracle step -> an io-match row (usage becomes learning): 2 steps
    io_rows = io.read_text(encoding="utf-8").strip().splitlines()
    assert len(io_rows) == 2
    # the final reasoning pair -> exactly one training-catalog entry, raw AND transmuted
    cat_rows = [json.loads(x) for x in cat.read_text(encoding="utf-8").strip().splitlines()]
    assert len(cat_rows) == 1
    entry = cat_rows[0]
    assert entry["request"] == "echo task"
    assert entry["raw"].startswith("fear:")          # the raw answer is kept
    assert entry["transmuted"].startswith("VITALITY")  # and its transmutation
    assert entry["raw_sig"] != entry["transmuted_sig"]


def test_agent_no_capture_writes_nothing(tmp_path, monkeypatch):
    cat = tmp_path / "catalog.jsonl"
    monkeypatch.setattr(form_cli, "_CATALOG", cat)
    monkeypatch.setattr(form_cli, "_ASK_CAPTURE", tmp_path / "io.jsonl")
    monkeypatch.setattr(form_cli, "_oracle_call", _scripted_oracle([
        {"tool": "done", "args": {"answer": "ok"}},
    ]))
    form_cli.cmd_agent(_ns(no_capture=True, cwd=str(tmp_path)))
    assert not cat.exists()


def test_parse_action_tolerates_fences_and_prose():
    # fenced JSON
    a = form_cli._parse_action('```json\n{"tool": "bash", "args": {"cmd": "ls"}}\n```')
    assert a["tool"] == "bash" and a["args"]["cmd"] == "ls"
    # prose around the object
    b = form_cli._parse_action('Sure! {"tool": "done", "args": {"answer": "x"}} hope that helps')
    assert b["tool"] == "done"
    # no JSON at all -> graceful done carrying the raw text
    c = form_cli._parse_action("I cannot find any JSON here")
    assert c["tool"] == "done" and c["_parse"] == "no-json"


def test_parse_oracle_splits_on_first_colon_only():
    assert form_cli._parse_oracle("ollama:llama3.2:3b") == ("ollama", "llama3.2:3b")
    assert form_cli._parse_oracle("openrouter:anthropic/claude-3.5-sonnet") == (
        "openrouter", "anthropic/claude-3.5-sonnet")
    assert form_cli._parse_oracle("") == ("ollama", "llama3.2:3b")
