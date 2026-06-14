"""io-match capture carrier: real tool calls become content-addressed records.

The bootstrap host-native execution of io-match.fk's `iom-capture`. These tests
prove the carrier stays faithful to the canonical Form recipe — sha256 (FIPS
180-4) content-addressing, identical inputs sharing a sig — and that the tool
telemetry carries the io-match fields the learning loop reads. The learning logic
itself lives in Form (io-match.fk / tool-embodiment.fk), proven four-way there.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_AGENT_RUNNER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "agent_runner.py"
_spec = importlib.util.spec_from_file_location("agent_runner", _AGENT_RUNNER_PATH)
assert _spec and _spec.loader
agent_runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agent_runner)


class _CaptureClient:
    def __init__(self):
        self.posts = []

    def post(self, url, json=None, timeout=None):
        self.posts.append({"url": url, "json": json})
        return None


def test_io_match_sig_is_canonical_sha256():
    # FIPS 180-4 vector: sha256("abc") — the same bytes form-stdlib/sha256.fk defines.
    assert agent_runner._io_match_sig("abc") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
    # content-addressing: same input -> same sig; different input -> different sig.
    assert agent_runner._io_match_sig("ls -la") == agent_runner._io_match_sig("ls -la")
    assert agent_runner._io_match_sig("ls -la") != agent_runner._io_match_sig("ls -lah")
    # the digest reveals nothing of the content (no secret leak): 64 hex chars, no input.
    sig = agent_runner._io_match_sig("export TOKEN=sk-secret-123")
    assert len(sig) == 64 and "secret" not in sig


def _post(returncode, **kw):
    client = _CaptureClient()
    agent_runner._post_runtime_event(
        client,
        tool_name="bash",
        status_code=200 if returncode == 0 else 500,
        runtime_ms=12.0,
        task_id="t1",
        task_type="impl",
        model="form-native",
        returncode=returncode,
        output_len=3,
        worker_id="w1",
        executor="form-native",
        is_openai_codex=False,
        **kw,
    )
    return client.posts[0]["json"]["metadata"] if client.posts else {}


def test_telemetry_carries_io_match_record_when_sigs_present():
    meta = _post(0, input_sig=agent_runner._io_match_sig("echo hi"), output_sig=agent_runner._io_match_sig("hi"))
    assert meta["io_match"] == "1"
    assert meta["input_sig"] == agent_runner._io_match_sig("echo hi")
    assert meta["output_sig"] == agent_runner._io_match_sig("hi")
    assert meta["outcome"] == "success"


def test_outcome_is_fail_on_nonzero_returncode():
    meta = _post(1, input_sig=agent_runner._io_match_sig("false"), output_sig="")
    assert meta["outcome"] == "fail"


def test_no_io_match_fields_when_sigs_absent():
    # backward compatible: telemetry without capture carries no io-match fields.
    meta = _post(0)
    assert "io_match" not in meta and "input_sig" not in meta
