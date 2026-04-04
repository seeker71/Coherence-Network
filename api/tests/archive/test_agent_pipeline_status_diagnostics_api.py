from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


@pytest.mark.asyncio
async def test_pipeline_status_includes_queue_mix_and_failure_reason_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        pending_spec = await client.post(
            "/api/agent/tasks",
            json={"direction": "Pending spec task", "task_type": "spec"},
        )
        assert pending_spec.status_code == 201

        pending_impl = await client.post(
            "/api/agent/tasks",
            json={"direction": "Pending impl task", "task_type": "impl"},
        )
        assert pending_impl.status_code == 201

        timeout_task = await client.post(
            "/api/agent/tasks",
            json={"direction": "Fail by timeout", "task_type": "impl"},
        )
        assert timeout_task.status_code == 201
        timeout_id = timeout_task.json()["id"]
        assert (
            await client.patch(
                f"/api/agent/tasks/{timeout_id}",
                json={"status": "running", "worker_id": "openai-codex"},
            )
        ).status_code == 200
        assert (
            await client.patch(
                f"/api/agent/tasks/{timeout_id}",
                json={"status": "failed", "output": "Task timed out while waiting on provider response"},
            )
        ).status_code == 200

        auth_task = await client.post(
            "/api/agent/tasks",
            json={"direction": "Fail by auth error", "task_type": "review"},
        )
        assert auth_task.status_code == 201
        auth_id = auth_task.json()["id"]
        assert (
            await client.patch(
                f"/api/agent/tasks/{auth_id}",
                json={"status": "running", "worker_id": "openai-codex"},
            )
        ).status_code == 200
        assert (
            await client.patch(
                f"/api/agent/tasks/{auth_id}",
                json={"status": "failed", "output": "HTTP 401 Unauthorized: invalid api key"},
            )
        ).status_code == 200

        response = await client.get("/api/agent/pipeline-status")
        assert response.status_code == 200
        payload = response.json()

    diagnostics = payload["diagnostics"]
    pending_mix = diagnostics["pending_by_task_type"]
    assert pending_mix["spec"] >= 1
    assert pending_mix["impl"] >= 1
    assert diagnostics["recent_failed_count"] >= 2
    reasons = {row["reason"] for row in diagnostics["recent_failed_reasons"]}
    assert "timeout" in reasons
    assert "auth" in reasons
    assert diagnostics["queue_mix_warning"] is False

