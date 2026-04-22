"""Flow-centric tests for agent task lifecycle.

Six flows cover the entire surface: CRUD, state transitions,
context/upsert, management, routing/metrics, and runner registry.
Each flow walks one coherent user journey with error paths as
inline assertions rather than sibling test functions.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service

BASE = "http://test"

REALISTIC_OUTPUT = (
    "Implementation complete. Modified api/app/services/agent_service.py to add "
    "the new status count endpoint with proper filtering. Updated the router to "
    "wire the endpoint at /api/agent/tasks/count. Added Pydantic response model "
    "for type safety. FILES_CHANGED=api/app/services/agent_service.py,api/app/routers/agent_tasks_routes.py "
    "COMMIT=abc1234def All tests passing. Verified output matches spec requirements."
)


async def _clear(c: AsyncClient) -> None:
    r = await c.delete("/api/agent/tasks?confirm=clear")
    assert r.status_code == 204


async def _create_task(
    c: AsyncClient,
    direction: str = "implement the feature",
    task_type: str = "impl",
    context: dict | None = None,
) -> dict:
    payload: dict = {"direction": direction, "task_type": task_type}
    if context is not None:
        payload["context"] = context
    r = await c.post("/api/agent/tasks", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def _claim(c: AsyncClient, task_id: str, worker_id: str = "test-worker-1") -> dict:
    r = await c.patch(f"/api/agent/tasks/{task_id}",
                      json={"status": "running", "worker_id": worker_id})
    assert r.status_code == 200, r.text
    return r.json()


async def _complete(c: AsyncClient, task_id: str,
                    worker_id: str = "test-worker-1",
                    output: str | None = None) -> dict:
    r = await c.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "completed", "worker_id": worker_id,
              "output": output or REALISTIC_OUTPUT},
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_task_crud_flow():
    """Create across every task_type, reject invalid type (422), get,
    get-404, list, filter-by-status, count."""
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)

        # Create one of each valid task_type.
        created = []
        for tt in ("impl", "spec", "test", "code-review", "review"):
            task = await _create_task(c, direction=f"task for {tt}", task_type=tt)
            assert task["task_type"] == tt and task["status"] == "pending"
            created.append(task)

        # Invalid type → 422.
        bad = await c.post("/api/agent/tasks",
                           json={"direction": "x", "task_type": "nonexistent-type"})
        assert bad.status_code == 422

        # Get + 404.
        head = created[0]
        got = await c.get(f"/api/agent/tasks/{head['id']}")
        assert got.status_code == 200 and got.json()["id"] == head["id"]
        assert (await c.get("/api/agent/tasks/nonexistent-task-id-999")).status_code == 404

        # List.
        listed = await c.get("/api/agent/tasks")
        assert listed.status_code == 200
        body = listed.json()
        assert body["total"] >= 5 and len(body["tasks"]) >= 5

        # Filter by status — claim one so we have a mix.
        await _claim(c, created[1]["id"])
        pending_only = (await c.get("/api/agent/tasks?status=pending")).json()
        assert {t["status"] for t in pending_only["tasks"]} == {"pending"}

        # Count.
        count = await c.get("/api/agent/tasks/count")
        assert count.status_code == 200
        cb = count.json()
        assert "total" in cb and "by_status" in cb
        assert cb["by_status"].get("pending", 0) >= 4


@pytest.mark.asyncio
async def test_task_lifecycle_transitions_flow():
    """pending → running → (completed | failed). Claim conflict on a
    second worker is 409. Progress updates mid-flight. Failed tasks
    surface in the attention endpoint."""
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)

        # Happy path: pending → running → progress → completed.
        t1 = await _create_task(c, direction="happy path")
        claimed = await _claim(c, t1["id"])
        assert claimed["status"] == "running" and claimed["claimed_by"] == "test-worker-1"
        prog = await c.patch(f"/api/agent/tasks/{t1['id']}",
                             json={"progress_pct": 75, "current_step": "Finalizing"})
        assert prog.status_code == 200 and prog.json()["progress_pct"] == 75
        done = await _complete(c, t1["id"])
        assert done["status"] == "completed"
        fetched = (await c.get(f"/api/agent/tasks/{t1['id']}")).json()
        assert fetched["output"] and len(fetched["output"]) > 0

        # Failure path: pending → running → failed → surfaces in attention.
        t2 = await _create_task(c, direction="will fail")
        await _claim(c, t2["id"])
        failed = await c.patch(f"/api/agent/tasks/{t2['id']}",
                               json={"status": "failed", "worker_id": "test-worker-1",
                                     "output": "Error: compilation failed"})
        assert failed.status_code == 200 and failed.json()["status"] == "failed"
        attention = (await c.get("/api/agent/tasks/attention")).json()
        assert t2["id"] in [t["id"] for t in attention["tasks"]]

        # Claim conflict: worker-a claims, worker-b gets 409.
        t3 = await _create_task(c, direction="contested")
        await _claim(c, t3["id"], worker_id="worker-a")
        conflict = await c.patch(f"/api/agent/tasks/{t3['id']}",
                                 json={"status": "running", "worker_id": "worker-b"})
        assert conflict.status_code == 409


@pytest.mark.asyncio
async def test_task_context_and_upsert_flow():
    """Tasks carry arbitrary context (spec_ref, task_card, idea_id)
    round-trip. upsert-active is idempotent on session_key."""
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)

        # Context round-trip — three representative shapes.
        t_spec = await _create_task(c, context={"spec_ref": "specs/042.md", "priority": "high"})
        assert (await c.get(f"/api/agent/tasks/{t_spec['id']}")).json()["context"]["spec_ref"] == "specs/042.md"

        task_card = {"goal": "Implement the widget",
                     "files_allowed": ["api/app/services/widget.py"],
                     "done_when": "tests pass", "commands": ["pytest"],
                     "constraints": "none"}
        t_card = await _create_task(c, context={"task_card": task_card})
        ctx = (await c.get(f"/api/agent/tasks/{t_card['id']}")).json().get("context") or {}
        assert "task_card" in ctx or "task_card_validation" in ctx

        t_idea = await _create_task(c, context={"idea_id": "idea-123"})
        got_ctx = (await c.get(f"/api/agent/tasks/{t_idea['id']}")).json().get("context") or {}
        assert got_ctx.get("idea_id") == "idea-123"

        # upsert-active — first call creates, second with same session_key returns existing.
        payload = {"session_key": "test-session-upsert-1", "direction": "upsert test",
                   "task_type": "impl", "worker_id": "test-worker-1"}
        r1 = await c.post("/api/agent/tasks/upsert-active", json=payload)
        assert r1.status_code == 200 and r1.json()["created"] is True
        first_id = r1.json()["task"]["id"]
        r2 = await c.post("/api/agent/tasks/upsert-active", json=payload)
        assert r2.status_code == 200 and r2.json()["task"]["id"] == first_id


@pytest.mark.asyncio
async def test_task_management_flow():
    """Delete-all with confirm wipes the store; without confirm → 400.
    Task log + reap history read surfaces return the expected shape."""
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Missing confirm → 400 (no clear first; the guard is the point).
        assert (await c.delete("/api/agent/tasks")).status_code == 400

        # With confirm → wipe succeeds.
        await _create_task(c, direction="to be deleted")
        assert (await c.delete("/api/agent/tasks?confirm=clear")).status_code == 204
        assert (await c.get("/api/agent/tasks")).json()["total"] == 0

        # Task log.
        task = await _create_task(c, direction="log test")
        log_body = (await c.get(f"/api/agent/tasks/{task['id']}/log")).json()
        assert log_body["task_id"] == task["id"] and "log" in log_body

        # Reap history.
        reap = (await c.get("/api/agent/reap-history")).json()
        assert "items" in reap and "total" in reap


@pytest.mark.asyncio
async def test_agent_routing_and_metrics_flow():
    """Route resolves task_type to a model; pipeline-status summarises
    running/pending/attention; metrics record + aggregate."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        route = (await c.get("/api/agent/route?task_type=impl")).json()
        assert route["task_type"] == "impl" and "model" in route

        pipe = (await c.get("/api/agent/pipeline-status")).json()
        assert all(k in pipe for k in ("running", "pending", "attention"))

        rec = await c.post("/api/agent/metrics", json={
            "task_id": "metric-test-001", "task_type": "impl",
            "model": "claude-sonnet-4-20250514",
            "duration_seconds": 42.5, "status": "completed",
        })
        assert rec.status_code == 201 and rec.json().get("recorded") is True

        agg = (await c.get("/api/agent/metrics")).json()
        assert isinstance(agg, dict)


@pytest.mark.asyncio
async def test_runners_flow():
    """Runner heartbeats register, list-runners surfaces them, and
    lifecycle-summary returns the overview structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        hb = await c.post("/api/agent/runners/heartbeat", json={
            "runner_id": "test-runner-hb-1", "status": "idle", "lease_seconds": 90,
            "host": "localhost", "pid": 12345, "version": "0.1.0",
        })
        assert hb.status_code == 200 and hb.json()["runner_id"] == "test-runner-hb-1"

        listed = (await c.get("/api/agent/runners?include_stale=true")).json()
        assert "runners" in listed and "total" in listed

        summary = (await c.get("/api/agent/lifecycle/summary")).json()
        assert isinstance(summary, dict)
