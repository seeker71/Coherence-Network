from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


@pytest.mark.asyncio
async def test_agent_usage_includes_execution_tracking_and_codex_attribution(
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
            json={"direction": "Implement Codex telemetry tracking", "task_type": "impl"},
        )
        assert task_one.status_code == 201
        task_one_id = task_one.json()["id"]

        task_two = await client.post(
            "/api/agent/tasks",
            json={"direction": "Implement non-codex telemetry tracking", "task_type": "impl"},
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

        runtime_event = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:agent",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 90.0,
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
        assert runtime_event.status_code == 201

        usage = await client.get("/api/agent/usage")
        assert usage.status_code == 200
        payload = usage.json()

        execution = payload["execution"]
        assert execution["tracked_runs"] == 3
        assert execution["failed_runs"] == 0
        assert execution["success_runs"] == 3
        assert execution["success_rate"] == 1.0
        assert execution["codex_runs"] == 2
        assert execution["by_executor"]["cursor"]["count"] >= 1
        assert execution["by_agent"]["openai-codex"]["count"] == 2
        assert execution["by_tool"]["agent-task-completion"]["count"] == 2

        coverage = execution["coverage"]
        assert coverage["completed_or_failed_tasks"] == 2
        assert coverage["tracked_task_runs"] == 2
        assert coverage["coverage_rate"] == 1.0
        assert coverage["untracked_task_ids"] == []


@pytest.mark.asyncio
async def test_completed_agent_tasks_emit_repeatable_completion_tool_calls(
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
            json={"direction": "Complete task and track repeatable call", "task_type": "impl"},
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

        events = await client.get("/api/runtime/events", params={"limit": 200})
        assert events.status_code == 200
        rows = events.json()
        completion_events = [
            row
            for row in rows
            if row.get("source") == "worker"
            and row.get("endpoint") == "/tool:agent-task-completion"
            and (row.get("metadata") or {}).get("task_id") == task_id
        ]
        assert len(completion_events) == 1
        metadata = completion_events[0]["metadata"]
        assert metadata["tracking_kind"] == "agent_task_completion"
        assert metadata["repeatable_tool_name"] == "agent_task_completion"
        assert metadata["repeatable_tool_call"]
        assert metadata["repeatable_tool_call_sha256"]
        assert metadata["task_final_status"] == "completed"
        assert metadata["provider"] == "openai-codex"
        assert metadata["request_schema"] == "open_responses_v1"
        assert metadata["normalized_model"]
        assert metadata["normalized_provider"]


@pytest.mark.asyncio
async def test_completion_tracking_event_is_idempotent_per_task_and_final_status(
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
            json={"direction": "Avoid duplicate completion tracking", "task_type": "impl"},
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
        completed_again = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "completed", "output": "still done"},
        )
        assert completed_again.status_code == 200

        events = await client.get("/api/runtime/events", params={"limit": 200})
        assert events.status_code == 200
        rows = events.json()
        completion_events = [
            row
            for row in rows
            if row.get("endpoint") == "/tool:agent-task-completion"
            and (row.get("metadata") or {}).get("task_id") == task_id
            and (row.get("metadata") or {}).get("task_final_status") == "completed"
        ]
        assert len(completion_events) == 1


@pytest.mark.asyncio
async def test_failed_task_records_linked_friction_and_failed_completion_tracking(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("FRICTION_USE_DB", "0")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        task = await client.post(
            "/api/agent/tasks",
            json={"direction": "Force host-runner failure telemetry", "task_type": "impl"},
        )
        assert task.status_code == 201
        task_id = task.json()["id"]

        running = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "openai-codex:railway-runner"},
        )
        assert running.status_code == 200
        failed = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "failed", "output": "simulated failure"},
        )
        assert failed.status_code == 200

        events = await client.get("/api/runtime/events", params={"limit": 200, "source": "worker"})
        assert events.status_code == 200
        rows = events.json()
        failed_completion = [
            row
            for row in rows
            if row.get("endpoint") == "/tool:agent-task-completion"
            and (row.get("metadata") or {}).get("task_id") == task_id
            and (row.get("metadata") or {}).get("task_final_status") == "failed"
            and int(row.get("status_code") or 0) >= 400
        ]
        assert len(failed_completion) == 1

        friction = await client.get("/api/friction/events", params={"limit": 200})
        assert friction.status_code == 200
        linked_friction = [row for row in friction.json() if row.get("task_id") == task_id]
        assert len(linked_friction) == 1
        assert linked_friction[0]["block_type"] == "task_failure"


@pytest.mark.asyncio
async def test_failed_task_friction_link_is_idempotent_on_repeat_failed_patch(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("FRICTION_USE_DB", "0")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        task = await client.post(
            "/api/agent/tasks",
            json={"direction": "Keep failed friction idempotent", "task_type": "impl"},
        )
        assert task.status_code == 201
        task_id = task.json()["id"]

        running = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "openai-codex:railway-runner"},
        )
        assert running.status_code == 200
        failed_first = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "failed", "output": "first failure"},
        )
        assert failed_first.status_code == 200
        failed_again = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "failed", "output": "second failure"},
        )
        assert failed_again.status_code == 200

        friction = await client.get("/api/friction/events", params={"limit": 200})
        assert friction.status_code == 200
        linked_friction = [row for row in friction.json() if row.get("task_id") == task_id]
        assert len(linked_friction) == 1


@pytest.mark.asyncio
async def test_openclaw_openrouter_override_tracks_openrouter_provider(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("OPENCLAW_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        task = await client.post(
            "/api/agent/tasks",
            json={
                "direction": "Track openrouter free path",
                "task_type": "impl",
                "context": {"executor": "openclaw", "model_override": "openrouter/free"},
            },
        )
        assert task.status_code == 201
        body = task.json()
        task_id = body["id"]
        assert body["model"] == "openrouter/free"
        assert body["context"]["executor"] == "openrouter"
        assert "--model openrouter/free" in str(body["command"])

        running = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "openclaw-worker"},
        )
        assert running.status_code == 200
        completed = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "completed", "output": "done"},
        )
        assert completed.status_code == 200

        events = await client.get("/api/runtime/events", params={"limit": 200})
        assert events.status_code == 200
        rows = events.json()
        completion_events = [
            row
            for row in rows
            if row.get("endpoint") == "/tool:agent-task-completion"
            and (row.get("metadata") or {}).get("task_id") == task_id
        ]
        assert len(completion_events) == 1
        metadata = completion_events[0]["metadata"]
        assert metadata["provider"] == "openrouter"
        assert metadata["billing_provider"] == "openrouter"
        assert metadata["is_paid_provider"] is False


@pytest.mark.asyncio
async def test_clawwork_alias_openrouter_override_tracks_openrouter_provider(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("OPENCLAW_COMMAND_TEMPLATE", 'codex exec "{{direction}}" --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        task = await client.post(
            "/api/agent/tasks",
            json={
                "direction": "Track clawwork openrouter free path",
                "task_type": "impl",
                "context": {"executor": "clawwork", "model_override": "openrouter/free"},
            },
        )
        assert task.status_code == 201
        body = task.json()
        task_id = body["id"]
        assert body["model"] == "openrouter/free"
        assert body["context"]["executor"] == "openrouter"
        assert "--model openrouter/free" in str(body["command"])

        running = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "openclaw-worker"},
        )
        assert running.status_code == 200
        completed = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "completed", "output": "done"},
        )
        assert completed.status_code == 200

        events = await client.get("/api/runtime/events", params={"limit": 200})
        assert events.status_code == 200
        rows = events.json()
        completion_events = [
            row
            for row in rows
            if row.get("endpoint") == "/tool:agent-task-completion"
            and (row.get("metadata") or {}).get("task_id") == task_id
        ]
        assert len(completion_events) == 1
        metadata = completion_events[0]["metadata"]
        assert metadata["executor"] == "openrouter"
        assert metadata["provider"] == "openrouter"
        assert metadata["billing_provider"] == "openrouter"
        assert metadata["is_paid_provider"] is False
