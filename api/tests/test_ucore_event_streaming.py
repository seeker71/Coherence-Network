"""Acceptance tests for U-Core event streaming (idea: ucore-event-streaming).

Maps to agent task activity API: in-memory per-task event streams, filtered
recent activity, active-task visibility, and Server-Sent Events for live updates.
"""

from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import task_activity_service as tas


def _reset_task_activity() -> None:
    tas._ACTIVITY_LOG.clear()
    tas._TASK_STREAMS.clear()
    tas._ACTIVE_TASKS.clear()


@pytest.fixture(autouse=True)
def _clean_task_activity() -> None:
    _reset_task_activity()
    yield
    _reset_task_activity()


@pytest.mark.asyncio
async def test_post_activity_appears_in_task_stream_and_recent_feed() -> None:
    """Logged events are visible via per-task stream and global activity (pub/sub surface)."""
    tid = "task-stream-accept-1"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            f"/api/agent/tasks/{tid}/activity",
            json={
                "event_type": "progress",
                "node_id": "node-a",
                "node_name": "alpha",
                "provider": "cursor",
                "data": {"step": "compile", "progress_pct": 40},
            },
        )
        assert r.status_code == 201
        body = r.json()
        assert body["task_id"] == tid
        assert body["event_type"] == "progress"
        assert body["data"]["step"] == "compile"

        stream = await client.get(f"/api/agent/tasks/{tid}/stream")
        assert stream.status_code == 200
        events = stream.json()
        assert len(events) == 1
        assert events[0]["event_type"] == "progress"

        recent = await client.get("/api/agent/tasks/activity?limit=10")
        assert recent.status_code == 200
        feed = recent.json()
        assert any(e["task_id"] == tid and e["event_type"] == "progress" for e in feed)


@pytest.mark.asyncio
async def test_recent_activity_filters_by_task_id() -> None:
    """Subscriptions can narrow by task id (entity scope)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/agent/tasks/task-a/activity",
            json={"event_type": "output", "node_id": "n1", "data": {"chunk": "a"}},
        )
        await client.post(
            "/api/agent/tasks/task-b/activity",
            json={"event_type": "output", "node_id": "n1", "data": {"chunk": "b"}},
        )

        filtered = await client.get("/api/agent/tasks/activity?task_id=task-a&limit=50")
        assert filtered.status_code == 200
        rows = filtered.json()
        assert all(e["task_id"] == "task-a" for e in rows)


@pytest.mark.asyncio
async def test_recent_activity_filters_by_node_id() -> None:
    """Subscriptions can narrow by node id (origin filter)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/agent/tasks/t-node/activity",
            json={"event_type": "progress", "node_id": "node-x", "data": {}},
        )
        await client.post(
            "/api/agent/tasks/t-node/activity",
            json={"event_type": "progress", "node_id": "node-y", "data": {}},
        )

        filtered = await client.get("/api/agent/tasks/activity?node_id=node-x&limit=50")
        assert filtered.status_code == 200
        rows = filtered.json()
        assert all(e["node_id"] == "node-x" for e in rows)


@pytest.mark.asyncio
async def test_active_tasks_reflects_executing_and_clears_on_terminal() -> None:
    """Active task list tracks in-flight work and drops terminal tasks."""
    tid = "task-active-lifecycle"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/agent/tasks/{tid}/activity",
            json={"event_type": "executing", "node_id": "n1", "data": {}},
        )
        active = await client.get("/api/agent/tasks/active")
        assert active.status_code == 200
        assert any(e["task_id"] == tid for e in active.json())

        await client.post(
            f"/api/agent/tasks/{tid}/activity",
            json={"event_type": "completed", "node_id": "n1", "data": {}},
        )
        active2 = await client.get("/api/agent/tasks/active")
        assert active2.status_code == 200
        assert not any(e["task_id"] == tid for e in active2.json())


@pytest.mark.asyncio
async def test_sse_stream_delivers_events_and_end_for_completed_task() -> None:
    """SSE uses text/event-stream and emits terminal end envelope after completion."""
    tid = "task-sse-done"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/agent/tasks/{tid}/activity",
            json={"event_type": "completed", "node_id": "n1", "data": {}},
        )

        async with client.stream("GET", f"/api/agent/tasks/{tid}/events") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            assert resp.headers.get("cache-control") == "no-cache"
            assert resp.headers.get("x-accel-buffering") == "no"

            buf = b""
            async for chunk in resp.aiter_bytes():
                buf += chunk
                if b'"event_type": "end"' in buf:
                    break

        text = buf.decode()
        assert "data: " in text
        lines = [ln for ln in text.splitlines() if ln.startswith("data: ")]
        payloads = [json.loads(ln[6:]) for ln in lines]
        assert any(p.get("event_type") == "completed" for p in payloads)
        assert any(p.get("event_type") == "end" for p in payloads)


@pytest.mark.asyncio
async def test_sse_end_on_failed_and_timeout() -> None:
    """Terminal failed and timeout events close the SSE like completed."""
    for terminal in ("failed", "timeout"):
        _reset_task_activity()
        tid = f"task-term-{terminal}"
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                f"/api/agent/tasks/{tid}/activity",
                json={"event_type": terminal, "node_id": "n1", "data": {}},
            )
            async with client.stream("GET", f"/api/agent/tasks/{tid}/events") as resp:
                assert resp.status_code == 200
                buf = b""
                async for chunk in resp.aiter_bytes():
                    buf += chunk
                    if b'"event_type": "end"' in buf:
                        break
            assert b'"event_type": "end"' in buf
