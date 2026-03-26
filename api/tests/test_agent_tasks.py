"""Tests for agent task list and status counts (spec 156: /tasks page data contract)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


@pytest.mark.asyncio
async def test_list_tasks_includes_status_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/tasks total matches GET /api/agent/tasks/count aggregate."""
    monkeypatch.setenv("AGENT_AUTO_EXECUTE", "0")
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service.clear_store()
    agent_service._store_loaded = False

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        clear = await client.delete("/api/agent/tasks?confirm=clear")
        assert clear.status_code == 204

        created: list[str] = []
        for direction in ("count-pending", "count-running", "count-done"):
            r = await client.post(
                "/api/agent/tasks",
                json={"direction": direction, "task_type": "impl"},
            )
            assert r.status_code == 201, r.text
            created.append(r.json()["id"])

        patch_running = await client.patch(
            f"/api/agent/tasks/{created[1]}",
            json={"status": "running", "worker_id": "manual-test"},
        )
        assert patch_running.status_code == 200, patch_running.text

        patch_done = await client.patch(
            f"/api/agent/tasks/{created[2]}",
            json={"status": "completed", "worker_id": "manual-test"},
        )
        assert patch_done.status_code == 200, patch_done.text

        listed = await client.get("/api/agent/tasks?limit=50&offset=0")
        assert listed.status_code == 200
        body = listed.json()
        assert "tasks" in body
        assert body["total"] == 3
        assert len(body["tasks"]) == 3

        counted = await client.get("/api/agent/tasks/count")
        assert counted.status_code == 200
        cbody = counted.json()
        assert cbody["total"] == 3
        by_status = cbody["by_status"]
        assert sum(by_status.values()) == cbody["total"]
        assert by_status.get("pending", 0) == 1
        assert by_status.get("running", 0) == 1
        assert by_status.get("completed", 0) == 1
