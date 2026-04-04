"""Flow-centric integration tests for agent task lifecycle.

Tests the full agent task CRUD, lifecycle transitions, context handling,
management operations, routing/metrics, and runner registry via HTTP only.
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


async def _clear(client: AsyncClient) -> None:
    """Clear task store via API."""
    r = await client.delete("/api/agent/tasks?confirm=clear")
    assert r.status_code == 204


async def _create_task(
    client: AsyncClient,
    direction: str = "implement the feature",
    task_type: str = "impl",
    context: dict | None = None,
) -> dict:
    payload: dict = {"direction": direction, "task_type": task_type}
    if context is not None:
        payload["context"] = context
    r = await client.post("/api/agent/tasks", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


async def _claim_task(client: AsyncClient, task_id: str, worker_id: str = "test-worker-1") -> dict:
    r = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "running", "worker_id": worker_id},
    )
    assert r.status_code == 200, r.text
    return r.json()


async def _complete_task(
    client: AsyncClient, task_id: str, worker_id: str = "test-worker-1", output: str | None = None,
) -> dict:
    r = await client.patch(
        f"/api/agent/tasks/{task_id}",
        json={"status": "completed", "worker_id": worker_id, "output": output or REALISTIC_OUTPUT},
    )
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Task CRUD (8 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_task() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        task = await _create_task(c)
        assert "id" in task
        assert task["direction"] == "implement the feature"
        assert task["task_type"] == "impl"
        assert task["status"] == "pending"


@pytest.mark.asyncio
async def test_create_task_all_types() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        for tt in ("impl", "spec", "test", "code-review", "review"):
            task = await _create_task(c, direction=f"task for {tt}", task_type=tt)
            assert task["task_type"] == tt, f"Expected {tt}, got {task['task_type']}"
            assert task["status"] == "pending"


@pytest.mark.asyncio
async def test_invalid_task_type_returns_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/agent/tasks",
            json={"direction": "do something", "task_type": "nonexistent-type"},
        )
        assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_get_task() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        created = await _create_task(c)
        r = await c.get(f"/api/agent/tasks/{created['id']}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["id"] == created["id"]
        assert body["direction"] == "implement the feature"


@pytest.mark.asyncio
async def test_get_missing_task_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/agent/tasks/nonexistent-task-id-999")
        assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_list_tasks() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        await _create_task(c, direction="task one")
        await _create_task(c, direction="task two")
        r = await c.get("/api/agent/tasks")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "tasks" in body
        assert body["total"] >= 2
        assert len(body["tasks"]) >= 2


@pytest.mark.asyncio
async def test_list_tasks_filter_by_status() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        t1 = await _create_task(c, direction="pending task")
        t2 = await _create_task(c, direction="will run")
        await _claim_task(c, t2["id"])

        r = await c.get("/api/agent/tasks?status=pending")
        assert r.status_code == 200, r.text
        body = r.json()
        statuses = {t["status"] for t in body["tasks"]}
        assert statuses == {"pending"}, f"Expected only pending, got {statuses}"


@pytest.mark.asyncio
async def test_task_count() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        await _create_task(c, direction="count me")
        r = await c.get("/api/agent/tasks/count")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "total" in body
        assert "by_status" in body
        assert body["total"] >= 1
        assert body["by_status"].get("pending", 0) >= 1


# ---------------------------------------------------------------------------
# Task Lifecycle (8 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_pending_to_running() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        task = await _create_task(c)
        updated = await _claim_task(c, task["id"])
        assert updated["status"] == "running"
        assert updated["claimed_by"] == "test-worker-1"


@pytest.mark.asyncio
async def test_task_running_to_completed() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        task = await _create_task(c)
        await _claim_task(c, task["id"])
        completed = await _complete_task(c, task["id"])
        assert completed["status"] == "completed"


@pytest.mark.asyncio
async def test_task_running_to_failed() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        task = await _create_task(c)
        await _claim_task(c, task["id"])
        r = await c.patch(
            f"/api/agent/tasks/{task['id']}",
            json={"status": "failed", "worker_id": "test-worker-1", "output": "Error: compilation failed"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_task_claim_conflict() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        task = await _create_task(c)
        await _claim_task(c, task["id"], worker_id="worker-a")
        r = await c.patch(
            f"/api/agent/tasks/{task['id']}",
            json={"status": "running", "worker_id": "worker-b"},
        )
        assert r.status_code == 409, r.text


@pytest.mark.asyncio
async def test_completed_task_has_output() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        task = await _create_task(c)
        await _claim_task(c, task["id"])
        await _complete_task(c, task["id"])
        r = await c.get(f"/api/agent/tasks/{task['id']}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["output"] is not None
        assert len(body["output"]) > 0


@pytest.mark.asyncio
async def test_task_progress_update() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        task = await _create_task(c)
        await _claim_task(c, task["id"])
        r = await c.patch(
            f"/api/agent/tasks/{task['id']}",
            json={"progress_pct": 50, "current_step": "Running tests"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["progress_pct"] == 50
        assert body["current_step"] == "Running tests"


@pytest.mark.asyncio
async def test_full_task_lifecycle() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        # Create
        task = await _create_task(c, direction="full lifecycle test")
        assert task["status"] == "pending"
        # Claim
        claimed = await _claim_task(c, task["id"])
        assert claimed["status"] == "running"
        # Progress
        r = await c.patch(
            f"/api/agent/tasks/{task['id']}",
            json={"progress_pct": 75, "current_step": "Finalizing"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["progress_pct"] == 75
        # Complete
        completed = await _complete_task(c, task["id"])
        assert completed["status"] == "completed"
        assert completed["output"] is not None


@pytest.mark.asyncio
async def test_task_attention() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        task = await _create_task(c, direction="will fail for attention")
        await _claim_task(c, task["id"])
        await c.patch(
            f"/api/agent/tasks/{task['id']}",
            json={"status": "failed", "worker_id": "test-worker-1", "output": "broken"},
        )
        r = await c.get("/api/agent/tasks/attention")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "tasks" in body
        ids = [t["id"] for t in body["tasks"]]
        assert task["id"] in ids


# ---------------------------------------------------------------------------
# Task Context (4 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_with_context() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        ctx = {"spec_ref": "specs/042.md", "priority": "high"}
        task = await _create_task(c, context=ctx)
        r = await c.get(f"/api/agent/tasks/{task['id']}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["context"] is not None
        assert body["context"].get("spec_ref") == "specs/042.md"


@pytest.mark.asyncio
async def test_task_with_task_card() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        task_card = {
            "goal": "Implement the widget",
            "files_allowed": ["api/app/services/widget.py"],
            "done_when": "tests pass",
            "commands": ["pytest"],
            "constraints": "none",
        }
        task = await _create_task(c, context={"task_card": task_card})
        r = await c.get(f"/api/agent/tasks/{task['id']}")
        assert r.status_code == 200, r.text
        body = r.json()
        ctx = body.get("context") or {}
        # task_card should be stored (possibly with validation metadata added)
        assert "task_card" in ctx or "task_card_validation" in ctx


@pytest.mark.asyncio
async def test_task_with_idea_id() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        task = await _create_task(c, context={"idea_id": "idea-123"})
        r = await c.get(f"/api/agent/tasks/{task['id']}")
        assert r.status_code == 200, r.text
        body = r.json()
        ctx = body.get("context") or {}
        assert ctx.get("idea_id") == "idea-123"


@pytest.mark.asyncio
async def test_upsert_active_task() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        payload = {
            "session_key": "test-session-upsert-1",
            "direction": "upsert test direction",
            "task_type": "impl",
            "worker_id": "test-worker-1",
        }
        r1 = await c.post("/api/agent/tasks/upsert-active", json=payload)
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["created"] is True
        task_id = body1["task"]["id"]

        # Second call with same session_key returns existing
        r2 = await c.post("/api/agent/tasks/upsert-active", json=payload)
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["task"]["id"] == task_id


# ---------------------------------------------------------------------------
# Task Management (4 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_all_tasks() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_task(c, direction="to be deleted")
        r = await c.delete("/api/agent/tasks?confirm=clear")
        assert r.status_code == 204
        listed = await c.get("/api/agent/tasks")
        assert listed.status_code == 200
        assert listed.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_without_confirm_returns_400() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.delete("/api/agent/tasks")
        assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_task_log() -> None:
    agent_service._store.clear()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _clear(c)
        task = await _create_task(c, direction="log test task")
        r = await c.get(f"/api/agent/tasks/{task['id']}/log")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "task_id" in body
        assert body["task_id"] == task["id"]
        assert "log" in body


@pytest.mark.asyncio
async def test_reap_history() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/agent/reap-history")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "items" in body
        assert "total" in body


# ---------------------------------------------------------------------------
# Routing & Metrics (4 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_route() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/agent/route?task_type=impl")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "task_type" in body
        assert body["task_type"] == "impl"
        assert "model" in body


@pytest.mark.asyncio
async def test_pipeline_status() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/agent/pipeline-status")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "running" in body
        assert "pending" in body
        assert "attention" in body


@pytest.mark.asyncio
async def test_record_metric() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/agent/metrics",
            json={
                "task_id": "metric-test-001",
                "task_type": "impl",
                "model": "claude-sonnet-4-20250514",
                "duration_seconds": 42.5,
                "status": "completed",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body.get("recorded") is True


@pytest.mark.asyncio
async def test_aggregate_metrics() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/agent/metrics")
        assert r.status_code == 200, r.text
        body = r.json()
        # Should return some aggregation structure
        assert isinstance(body, dict)


# ---------------------------------------------------------------------------
# Runners (3 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_heartbeat() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/agent/runners/heartbeat",
            json={
                "runner_id": "test-runner-hb-1",
                "status": "idle",
                "lease_seconds": 90,
                "host": "localhost",
                "pid": 12345,
                "version": "0.1.0",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["runner_id"] == "test-runner-hb-1"


@pytest.mark.asyncio
async def test_list_runners() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Register a runner first
        await c.post(
            "/api/agent/runners/heartbeat",
            json={
                "runner_id": "test-runner-list-1",
                "status": "idle",
                "lease_seconds": 90,
            },
        )
        r = await c.get("/api/agent/runners?include_stale=true")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "runners" in body
        assert "total" in body


@pytest.mark.asyncio
async def test_lifecycle_summary() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/agent/lifecycle/summary")
        assert r.status_code == 200, r.text
        body = r.json()
        assert isinstance(body, dict)
