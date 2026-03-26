"""Extended acceptance tests for spec 156 (ux-tasks-page-broken).

Covers API contract guarantees the /tasks page depends on:
- Empty store returns zero total and empty task list
- Status filter returns only matching tasks
- Count endpoint shape has required keys
- List response total matches actual task count
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


def _reset_agent_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_AUTO_EXECUTE", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


@pytest.mark.asyncio
async def test_empty_store_returns_zero_total_and_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """When no tasks exist, total=0 and tasks=[] — UI may show zero-state (spec 156)."""
    _reset_agent_store(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agent/tasks", params={"limit": 20, "offset": 0})
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 0
        assert body["tasks"] == []


@pytest.mark.asyncio
async def test_count_endpoint_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/tasks/count returns {total: int, by_status: dict} (spec 156)."""
    _reset_agent_store(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Seed one task
        await client.post(
            "/api/agent/tasks",
            json={"direction": "Count shape test", "task_type": "impl"},
        )

        res = await client.get("/api/agent/tasks/count")
        assert res.status_code == 200
        body = res.json()
        assert isinstance(body["total"], int)
        assert body["total"] >= 1
        assert isinstance(body["by_status"], dict)
        # by_status values must be ints
        for status_name, count in body["by_status"].items():
            assert isinstance(count, int), f"by_status[{status_name}] should be int, got {type(count)}"


@pytest.mark.asyncio
async def test_status_filter_returns_only_matching_tasks(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/tasks?status=pending returns only pending tasks (spec 156)."""
    _reset_agent_store(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a pending task
        r1 = await client.post(
            "/api/agent/tasks",
            json={"direction": "Pending task for filter", "task_type": "impl"},
        )
        assert r1.status_code == 201

        # Create and complete another task
        r2 = await client.post(
            "/api/agent/tasks",
            json={"direction": "Completed task for filter", "task_type": "test"},
        )
        assert r2.status_code == 201
        done_id = r2.json()["id"]
        await client.patch(
            f"/api/agent/tasks/{done_id}",
            json={"status": "completed", "output": "done"},
        )

        # Filter for pending only
        res = await client.get("/api/agent/tasks", params={"status": "pending", "limit": 50})
        assert res.status_code == 200
        body = res.json()
        tasks = body["tasks"]
        assert len(tasks) >= 1
        for task in tasks:
            assert task["status"] == "pending", f"Expected pending, got {task['status']}"


@pytest.mark.asyncio
async def test_list_total_matches_actual_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """List total field must be >= the number of returned tasks (spec 156)."""
    _reset_agent_store(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(3):
            await client.post(
                "/api/agent/tasks",
                json={"direction": f"Total test {i}", "task_type": "impl"},
            )

        res = await client.get("/api/agent/tasks", params={"limit": 100, "offset": 0})
        assert res.status_code == 200
        body = res.json()
        assert body["total"] >= len(body["tasks"])
        assert body["total"] == 3
        assert len(body["tasks"]) == 3


@pytest.mark.asyncio
async def test_pagination_offset_works(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pagination via limit+offset returns correct slices (spec 156)."""
    _reset_agent_store(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(5):
            await client.post(
                "/api/agent/tasks",
                json={"direction": f"Pagination test {i}", "task_type": "impl"},
            )

        # Get first page
        page1 = await client.get("/api/agent/tasks", params={"limit": 2, "offset": 0})
        assert page1.status_code == 200
        body1 = page1.json()
        assert len(body1["tasks"]) == 2
        assert body1["total"] == 5

        # Get second page
        page2 = await client.get("/api/agent/tasks", params={"limit": 2, "offset": 2})
        assert page2.status_code == 200
        body2 = page2.json()
        assert len(body2["tasks"]) == 2
        assert body2["total"] == 5

        # Pages must have different tasks
        ids1 = {t["id"] for t in body1["tasks"]}
        ids2 = {t["id"] for t in body2["tasks"]}
        assert ids1.isdisjoint(ids2), "Paginated pages should not overlap"
