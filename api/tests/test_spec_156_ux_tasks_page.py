"""Acceptance tests for spec 156 (ux-tasks-page-broken).

Validates API contracts the /tasks page relies on: list + count shape, status totals
alignment, and the same-origin task list path used by the browser (GET /api/agent/tasks).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app import config_loader
from app.main import app
from app.services import agent_service


def _reset_agent_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    config_loader.set_config_value("agent_executor", "auto_execute", False)
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


def _aggregate_statuses(tasks: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in tasks:
        s = str(row.get("status") or "")
        out[s] = out.get(s, 0) + 1
    return out


@pytest.mark.asyncio
async def test_list_tasks_includes_status_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/tasks/count by_status matches aggregating GET /api/agent/tasks (spec 156)."""
    _reset_agent_store(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        pending = await client.post(
            "/api/agent/tasks",
            json={"direction": "Spec 156 pending task", "task_type": "impl"},
        )
        assert pending.status_code == 201
        pending_id = pending.json()["id"]

        running = await client.post(
            "/api/agent/tasks",
            json={"direction": "Spec 156 running task", "task_type": "test"},
        )
        assert running.status_code == 201
        running_id = running.json()["id"]
        r_run = await client.patch(
            f"/api/agent/tasks/{running_id}",
            json={"status": "running", "worker_id": "manual-spec-156"},
        )
        assert r_run.status_code == 200

        done = await client.post(
            "/api/agent/tasks",
            json={"direction": "Spec 156 completed task", "task_type": "review"},
        )
        assert done.status_code == 201
        done_id = done.json()["id"]
        r_done = await client.patch(
            f"/api/agent/tasks/{done_id}",
            json={"status": "completed", "output": "spec 156 done"},
        )
        assert r_done.status_code == 200

        count_res = await client.get("/api/agent/tasks/count")
        assert count_res.status_code == 200
        count_body = count_res.json()
        assert "total" in count_body
        assert "by_status" in count_body
        by_status = count_body["by_status"]

        list_res = await client.get("/api/agent/tasks", params={"limit": 100, "offset": 0})
        assert list_res.status_code == 200
        list_body = list_res.json()
        tasks = list_body.get("tasks") or []
        assert isinstance(tasks, list)
        agg = _aggregate_statuses(tasks)

        for key in ("pending", "running", "completed"):
            assert by_status.get(key, 0) == agg.get(key, 0), (
                f"count endpoint and list disagree on {key}: {by_status} vs {agg}"
            )

        ids = {t.get("id") for t in tasks}
        assert pending_id in ids
        assert running_id in ids
        assert done_id in ids
        assert list_body.get("total") == count_body["total"]


@pytest.mark.asyncio
async def test_tasks_list_uses_documented_path_for_browser_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tasks page fetches /api/agent/tasks (same-origin); endpoint must respond when API is up (spec 156)."""
    _reset_agent_store(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={"direction": "Spec 156 path check", "task_type": "impl"},
        )
        assert created.status_code == 201

        res = await client.get("/api/agent/tasks", params={"limit": 20, "offset": 0})
        assert res.status_code == 200
        body = res.json()
        assert "tasks" in body
        assert "total" in body
        assert isinstance(body["tasks"], list)
        assert body["total"] >= 1


@pytest.mark.asyncio
async def test_list_tasks_nonzero_total_implies_nonempty_items_when_limit_sufficient(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When total > 0 and limit covers all rows, tasks array must be non-empty (spec 156)."""
    _reset_agent_store(monkeypatch)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/agent/tasks",
            json={"direction": "Spec 156 nonempty list", "task_type": "impl"},
        )
        res = await client.get("/api/agent/tasks", params={"limit": 50, "offset": 0})
        assert res.status_code == 200
        body = res.json()
        assert body["total"] >= 1
        assert len(body["tasks"]) >= 1
