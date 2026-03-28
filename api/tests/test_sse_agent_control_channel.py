"""Tests for SSE task activity and native-agent control channel (steer, checkpoint, abort, ask).

Covers:
- POST /api/agent/tasks/{task_id}/activity — log events (including control_response_*)
- GET /api/agent/tasks/{task_id}/stream — JSON timeline
- GET /api/agent/tasks/{task_id}/events — SSE until terminal event
- scripts/task_control_channel.py — JSONL control file + prompt injection

API paths are prefixed with /api via app.main (see task_activity_routes on agent router).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client() -> TestClient:
    from app.main import app

    return TestClient(app)


def _task_id(suffix: str) -> str:
    return f"ssectl-{suffix}"


def test_post_activity_and_get_stream_full_timeline(client: TestClient) -> None:
    """Scenario 1: POST executing + progress; GET stream lists both (create–read cycle)."""
    tid = _task_id("crud-1")
    r1 = client.post(
        f"/api/agent/tasks/{tid}/activity",
        json={
            "event_type": "executing",
            "node_id": "node-sse-01",
            "provider": "codex",
            "data": {"phase": "cli"},
        },
    )
    assert r1.status_code == 201, r1.text
    body1 = r1.json()
    assert body1["event_type"] == "executing"
    assert "timestamp" in body1

    listed = client.get(f"/api/agent/tasks/{tid}/stream")
    assert listed.status_code == 200
    arr = listed.json()
    assert len(arr) >= 1
    assert arr[-1]["event_type"] == "executing"

    r2 = client.post(
        f"/api/agent/tasks/{tid}/activity",
        json={"event_type": "progress", "data": {"pct": 50}},
    )
    assert r2.status_code == 201, r2.text

    listed2 = client.get(f"/api/agent/tasks/{tid}/stream")
    assert listed2.status_code == 200
    types = [e["event_type"] for e in listed2.json()]
    assert "executing" in types and "progress" in types


def test_post_activity_missing_event_type_422(client: TestClient) -> None:
    """Edge: invalid body — missing required event_type."""
    tid = _task_id("bad-1")
    r = client.post(f"/api/agent/tasks/{tid}/activity", json={})
    assert r.status_code == 422
    detail = r.json().get("detail")
    assert detail is not None


def test_get_stream_unknown_task_returns_empty_list(client: TestClient) -> None:
    """Scenario 4: no events yet — stream snapshot is empty, not an error."""
    tid = _task_id("never-logged-xxxxx")
    r = client.get(f"/api/agent/tasks/{tid}/stream")
    assert r.status_code == 200
    assert r.json() == []


def test_task_events_sse_emits_completed_and_end(client: TestClient) -> None:
    """Scenario 2: after terminal event, SSE yields data lines and end marker."""
    tid = _task_id("sse-done")
    post = client.post(
        f"/api/agent/tasks/{tid}/activity",
        json={"event_type": "completed", "data": {"outcome": "ok"}},
    )
    assert post.status_code == 201, post.text

    with client.stream("GET", f"/api/agent/tasks/{tid}/events") as resp:
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")
        raw = b"".join(resp.iter_bytes())

    text = raw.decode("utf-8", errors="replace")
    assert "data:" in text
    assert "completed" in text
    assert '"event_type": "end"' in text or '"event_type":"end"' in text


def test_control_response_event_round_trip(client: TestClient) -> None:
    """Scenario 3: runner-posted control_response_* events appear on stream."""
    tid = _task_id("ctrl-resp")
    r = client.post(
        f"/api/agent/tasks/{tid}/activity",
        json={
            "event_type": "control_response_ack",
            "data": {"type": "ack", "note": "steer applied"},
        },
    )
    assert r.status_code == 201, r.text

    listed = client.get(f"/api/agent/tasks/{tid}/stream")
    assert listed.status_code == 200
    evs = listed.json()
    assert any(e.get("event_type") == "control_response_ack" for e in evs)
    ack = next(e for e in evs if e.get("event_type") == "control_response_ack")
    assert ack["data"].get("type") == "ack"


def test_recent_activity_filter_by_task_id(client: TestClient) -> None:
    """GET /api/agent/tasks/activity?task_id= filters to one task."""
    tid = _task_id("filter-me")
    client.post(
        f"/api/agent/tasks/{tid}/activity",
        json={"event_type": "progress", "data": {"step": "a"}},
    )
    r = client.get(f"/api/agent/tasks/activity?task_id={tid}&limit=20")
    assert r.status_code == 200
    items = r.json()
    assert all(e["task_id"] == tid for e in items)


def test_task_control_channel_send_command_writes_jsonl(tmp_path: Path) -> None:
    """Control file protocol: send_command appends JSONL with type and payload."""
    from scripts.task_control_channel import TaskControlChannel

    ch = TaskControlChannel("n0de000000000001", "task-jsonl-1", tmp_path, "http://127.0.0.1:9")
    ch.send_command("steer", {"direction": "focus on tests"})
    ch.send_command("checkpoint", {})

    ctrl = tmp_path / ".task-control"
    assert ctrl.is_file()
    lines = [ln for ln in ctrl.read_text().splitlines() if ln.strip()]
    assert len(lines) == 2
    j0 = json.loads(lines[0])
    j1 = json.loads(lines[1])
    assert j0["type"] == "steer"
    assert j0["payload"]["direction"] == "focus on tests"
    assert j1["type"] == "checkpoint"


def test_inject_control_instructions_contains_cli_guidance(tmp_path: Path) -> None:
    """Prompt injection documents checkpoint, steer, abort, ask, and cc inbox."""
    from scripts.task_control_channel import inject_control_instructions

    base = "TASK_PROMPT_BODY"
    out = inject_control_instructions(base, tmp_path)
    assert base in out
    assert "cc inbox" in out
    assert "checkpoint" in out
    assert "steer" in out
    assert "abort" in out
    assert "ask" in out


def test_task_events_sse_failed_terminal_event(client: TestClient) -> None:
    """Terminal event 'failed' also closes SSE with end."""
    tid = _task_id("sse-fail")
    client.post(
        f"/api/agent/tasks/{tid}/activity",
        json={"event_type": "failed", "data": {"reason": "test"}},
    )
    with client.stream("GET", f"/api/agent/tasks/{tid}/events") as resp:
        assert resp.status_code == 200
        raw = b"".join(resp.iter_bytes())
    assert b"failed" in raw
    assert b"end" in raw
