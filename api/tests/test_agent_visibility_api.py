from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


@pytest.mark.asyncio
async def test_agent_visibility_exposes_pipeline_usage_and_remaining_gap(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        task_one = await client.post(
            "/api/agent/tasks",
            json={"direction": "Track execution telemetry for task one", "task_type": "impl"},
        )
        assert task_one.status_code == 201
        task_one_id = task_one.json()["id"]

        task_two = await client.post(
            "/api/agent/tasks",
            json={"direction": "Track execution telemetry for task two", "task_type": "impl"},
        )
        assert task_two.status_code == 201
        task_two_id = task_two.json()["id"]

        start_one = await client.patch(
            f"/api/agent/tasks/{task_one_id}",
            json={"status": "running", "worker_id": "openai-codex"},
        )
        assert start_one.status_code == 200
        finish_one = await client.patch(
            f"/api/agent/tasks/{task_one_id}",
            json={"status": "completed", "output": "done"},
        )
        assert finish_one.status_code == 200

        start_two = await client.patch(
            f"/api/agent/tasks/{task_two_id}",
            json={"status": "running", "worker_id": "worker-b"},
        )
        assert start_two.status_code == 200
        finish_two = await client.patch(
            f"/api/agent/tasks/{task_two_id}",
            json={"status": "completed", "output": "done"},
        )
        assert finish_two.status_code == 200

        tracked_runtime = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 75.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "task_id": task_one_id,
                    "executor": "cursor",
                    "worker_id": "openai-codex",
                    "agent_id": "openai-codex",
                    "is_openai_codex": True,
                },
            },
        )
        assert tracked_runtime.status_code == 201

        visibility = await client.get("/api/agent/visibility")
        assert visibility.status_code == 200
        payload = visibility.json()

        assert payload["pipeline"]["recent_completed_count"] == 2
        assert payload["usage"]["execution"]["tracked_runs"] == 1
        assert payload["usage"]["execution"]["codex_runs"] == 1
        assert payload["remaining_usage"]["coverage_rate"] == 0.5
        assert payload["remaining_usage"]["remaining_to_full_coverage"] == 1
        assert payload["remaining_usage"]["health"] == "red"
        assert payload["remaining_usage"]["untracked_task_ids"] == [task_two_id]


@pytest.mark.asyncio
async def test_agent_visibility_reports_green_when_all_completed_tasks_are_tracked(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        task = await client.post(
            "/api/agent/tasks",
            json={"direction": "Track fully covered task", "task_type": "impl"},
        )
        assert task.status_code == 201
        task_id = task.json()["id"]

        running = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "openai-codex"},
        )
        assert running.status_code == 200
        completed = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "completed", "output": "done"},
        )
        assert completed.status_code == 200

        tracked_runtime = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 31.0,
                "idea_id": "coherence-network-agent-pipeline",
                "metadata": {
                    "task_id": task_id,
                    "executor": "cursor",
                    "worker_id": "openai-codex",
                    "agent_id": "openai-codex",
                    "is_openai_codex": True,
                },
            },
        )
        assert tracked_runtime.status_code == 201

        visibility = await client.get("/api/agent/visibility")
        assert visibility.status_code == 200
        payload = visibility.json()
        assert payload["remaining_usage"]["coverage_rate"] == 1.0
        assert payload["remaining_usage"]["remaining_to_full_coverage"] == 0
        assert payload["remaining_usage"]["health"] == "green"
