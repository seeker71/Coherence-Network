"""form_cli `capture` — live training catalog: request + raw + transmuted, both kept.

When the form-cli routes to an oracle, the agent records the raw (fear-based)
answer AND its transmutation (fear -> opportunity, risk -> data). Both have value;
from one entry the three separable training pairs derive. Mirrors
form/form-stdlib/training-catalog.fk (tc-entry), proven four-way there.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_FORM_CLI_PATH = Path(__file__).resolve().parents[2] / "scripts" / "form_cli.py"
_spec = importlib.util.spec_from_file_location("form_cli", _FORM_CLI_PATH)
assert _spec and _spec.loader
form_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(form_cli)


def test_capture_keeps_both_raw_and_transmuted(tmp_path, monkeypatch):
    cat = tmp_path / "catalog.jsonl"
    monkeypatch.setattr(form_cli, "_CATALOG", cat)
    entry = form_cli.catalog_capture(
        request="plan the form-cli",
        raw="this is risky and will fail and underestimates the complexity",
        transmuted="a growth list + data constraints; the gradient we walk",
        lane="oracle:gemini",
        outcome="success",
    )
    # both kept as full text (both have value)
    assert entry["raw"].startswith("this is risky")
    assert entry["transmuted"].startswith("a growth list")
    # content-addressed, and raw != transmuted (a real transmutation changed it)
    assert entry["raw_sig"] != entry["transmuted_sig"]
    assert entry["request_sig"] == form_cli._io_sig("plan the form-cli")


def test_capture_derives_three_separable_pairs(tmp_path, monkeypatch):
    monkeypatch.setattr(form_cli, "_CATALOG", tmp_path / "c.jsonl")
    e = form_cli.catalog_capture("R", "RAW", "VIT", "oracle:claude", "success")
    rs, raws, vits = e["request_sig"], e["raw_sig"], e["transmuted_sig"]
    # raw (reference), transmute (the block), reasoning (native target)
    assert e["pairs"]["raw"] == [rs, raws]
    assert e["pairs"]["transmute"] == [raws, vits]
    assert e["pairs"]["reasoning"] == [rs, vits]


def test_capture_appends_durably(tmp_path, monkeypatch):
    cat = tmp_path / "c.jsonl"
    monkeypatch.setattr(form_cli, "_CATALOG", cat)
    form_cli.catalog_capture("R1", "raw1", "vit1", "oracle:gemini", "success")
    form_cli.catalog_capture("R2", "raw2", "vit2", "oracle:codex", "success")
    lines = cat.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["request"] == "R2"
