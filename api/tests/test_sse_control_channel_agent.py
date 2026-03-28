"""SSE control channel + agent activity — API parity for native CLI runners.

Covers:
- POST /api/agent/tasks/{id}/activity (runner → API)
- GET /api/agent/tasks/{id}/stream (JSON event list)
- GET /api/agent/tasks/{id}/events (SSE)
- PATCH /api/agent/tasks/{id} with context.control (control plane the runner polls)
- scripts.agent_runner._extract_control_signals (abort/diagnostic parsing)

See: specs/sse-agent-control-channel.md
"""

from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


@pytest_asyncio.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    monkeypatch.setenv("AGENT_AUTO_EXECUTE", "0")
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service.clear_store()
    agent_service._store_loaded = False
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        clear = await ac.delete("/api/agent/tasks?confirm=clear")
        assert clear.status_code == 204
        yield ac


def _new_task_id() -> str:
    return f"sse-task-{uuid.uuid4().hex[:12]}"


@pytest.mark.asyncio
async def test_post_activity_201_and_event_shape(client: AsyncClient) -> None:
    """POST activity returns 201 with id, task_id, event_type, timestamp."""
    tid = _new_task_id()
    r = await client.post(
        f"/api/agent/tasks/{tid}/activity",
        json={
            "event_type": "executing",
            "provider": "claude",
            "node_id": "node-a",
            "data": {"step": "thinking"},
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["task_id"] == tid
    assert body["event_type"] == "executing"
    assert "id" in body and len(body["id"]) >= 8
    assert "timestamp" in body


@pytest.mark.asyncio
async def test_post_activity_missing_event_type_422(client: AsyncClient) -> None:
    tid = _new_task_id()
    r = await client.post(
        f"/api/agent/tasks/{tid}/activity",
        json={"provider": "codex"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_get_task_stream_round_trip(client: AsyncClient) -> None:
    """POST multiple events; GET stream returns them in order."""
    tid = _new_task_id()
    for et, extra in (
        ("claimed", {}),
        ("progress", {"pct": 10}),
        ("output", {"tail": "ok"}),
    ):
        pr = await client.post(
            f"/api/agent/tasks/{tid}/activity",
            json={"event_type": et, "provider": "gemini", "data": extra},
        )
        assert pr.status_code == 201, pr.text

    gr = await client.get(f"/api/agent/tasks/{tid}/stream")
    assert gr.status_code == 200
    events = gr.json()
    assert len(events) == 3
    assert [e["event_type"] for e in events] == ["claimed", "progress", "output"]
    assert events[1]["data"].get("pct") == 10


@pytest.mark.asyncio
async def test_get_tasks_activity_filter_by_task_id(client: AsyncClient) -> None:
    """GET /tasks/activity?task_id= only returns matching task events."""
    a = _new_task_id()
    b = _new_task_id()
    for tid in (a, b):
        r = await client.post(
            f"/api/agent/tasks/{tid}/activity",
            json={"event_type": "progress", "data": {"n": tid}},
        )
        assert r.status_code == 201

    filt = await client.get(f"/api/agent/tasks/activity?task_id={a}&limit=50")
    assert filt.status_code == 200
    rows = filt.json()
    assert all(e["task_id"] == a for e in rows)
    assert not any(e["task_id"] == b for e in rows)


@pytest.mark.asyncio
async def test_sse_events_stream_media_type_and_end_marker(client: AsyncClient) -> None:
    """SSE returns text/event-stream and includes data lines + end event after completed."""
    tid = _new_task_id()
    for et in ("executing", "completed"):
        await client.post(
            f"/api/agent/tasks/{tid}/activity",
            json={"event_type": et, "provider": "cursor", "data": {}},
        )

    async with client.stream("GET", f"/api/agent/tasks/{tid}/events") as resp:
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "text/event-stream" in ct
        buf = b""
        async for chunk in resp.aiter_bytes():
            buf += chunk
            if b'"event_type": "end"' in buf or b'"event_type":"end"' in buf:
                break
        text = buf.decode("utf-8", errors="replace")
        assert "data: " in text
        assert "executing" in text
        assert "completed" in text
        assert "end" in text


@pytest.mark.asyncio
async def test_patch_context_control_abort_merged_into_task(client: AsyncClient) -> None:
    """PATCH merges context.control; GET task reflects abort signal for runner polling."""
    create = await client.post(
        "/api/agent/tasks",
        json={
            "direction": "Implement SSE tests",
            "task_type": "impl",
        },
    )
    assert create.status_code == 201, create.text
    tid = create.json()["id"]

    claim = await client.patch(
        f"/api/agent/tasks/{tid}",
        json={"status": "running", "worker_id": "manual-test"},
    )
    assert claim.status_code == 200, claim.text

    patch = await client.patch(
        f"/api/agent/tasks/{tid}",
        json={
            "context": {
                "control": {
                    "action": "abort",
                    "reason": "operator stop",
                }
            }
        },
    )
    assert patch.status_code == 200, patch.text

    got = await client.get(f"/api/agent/tasks/{tid}")
    assert got.status_code == 200
    ctx = got.json().get("context") or {}
    ctrl = ctx.get("control") or {}
    assert str(ctrl.get("action", "")).lower() == "abort"
    assert "operator stop" in str(ctrl.get("reason", ""))


@pytest.mark.asyncio
async def test_patch_empty_fields_400(client: AsyncClient) -> None:
    create = await client.post(
        "/api/agent/tasks",
        json={"direction": "x", "task_type": "test"},
    )
    assert create.status_code == 201
    tid = create.json()["id"]
    r = await client.patch(f"/api/agent/tasks/{tid}", json={})
    assert r.status_code == 400
    assert "At least one field" in r.text


def test_extract_control_signals_abort_and_diagnostic() -> None:
    """Runner helper: abort from control dict and diagnostic_request."""
    from scripts import agent_runner

    fn = agent_runner._extract_control_signals
    assert fn(None) == (False, "", None)
    assert fn({}) == (False, "", None)

    snap = {
        "context": {
            "control": {"action": "abort", "reason": "user requested"},
        }
    }
    abort, reason, diag = fn(snap)
    assert abort is True
    assert "user requested" in reason
    assert diag is None

    snap2 = {
        "context": {
            "abort_requested": True,
            "abort_reason": "stop",
        }
    }
    a2, r2, _ = fn(snap2)
    assert a2 is True
    assert r2 == "stop"

    snap3 = {
        "context": {
            "diagnostic_request": {"id": "d1", "command": "echo test"},
        }
    }
    a3, _, d3 = fn(snap3)
    assert a3 is False
    assert d3 is not None
    assert d3.get("command") == "echo test"


def test_extract_control_signals_steer_direction_not_abort() -> None:
    """Non-abort control payload should not set abort unless action says abort."""
    from scripts import agent_runner

    fn = agent_runner._extract_control_signals
    snap = {
        "context": {
            "control": {"action": "steer", "direction": "focus on tests only"},
        }
    }
    abort, reason, _ = fn(snap)
    assert abort is False
    assert reason == ""
