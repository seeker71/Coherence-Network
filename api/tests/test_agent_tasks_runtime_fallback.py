from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


@pytest.mark.asyncio
async def test_tasks_list_includes_runtime_completion_events_when_store_empty(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task_id = "task_runtime_only"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent-task-completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 12.3,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "tracking_kind": "agent_task_completion",
                    "task_id": task_id,
                    "task_type": "impl",
                    "task_final_status": "completed",
                    "model": "openclaw/openrouter/free",
                    "worker_id": "openclaw-worker:test",
                    "repeatable_tool_call": "codex exec \"Direction: hello\" --model openrouter/free",
                    "provider": "openrouter",
                },
            },
        )
        assert res.status_code == 201

        tasks = await client.get("/api/agent/tasks", params={"limit": 50})
        assert tasks.status_code == 200
        payload = tasks.json()
        ids = [row.get("id") for row in (payload.get("tasks") or [])]
        assert task_id in ids

        one = await client.get(f"/api/agent/tasks/{task_id}")
        assert one.status_code == 200
        body = one.json()
        assert body["id"] == task_id
        assert body["status"] == "completed"
        assert body["model"] == "openclaw/openrouter/free"

