from __future__ import annotations

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_service


@pytest.mark.asyncio
async def test_upsert_active_task_creates_once_and_reuses_by_session_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/api/agent/tasks/upsert-active",
            json={
                "session_key": "codex-thread-1",
                "direction": "Track active Codex task in API task list",
                "task_type": "impl",
                "worker_id": "openai-codex",
                "context": {"source": "test"},
            },
        )
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["created"] is True
        assert first_payload["task"]["status"] == "running"
        task_id = first_payload["task"]["id"]

        second = await client.post(
            "/api/agent/tasks/upsert-active",
            json={
                "session_key": "codex-thread-1",
                "direction": "Track active Codex task in API task list",
                "task_type": "impl",
                "worker_id": "openai-codex",
            },
        )
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["created"] is False
        assert second_payload["task"]["id"] == task_id
        assert second_payload["task"]["claimed_by"] == "openai-codex"

        listed = await client.get("/api/agent/tasks")
        assert listed.status_code == 200
        listed_payload = listed.json()
        assert listed_payload["total"] == 1


def test_agent_tasks_persist_and_reload_from_disk(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_path = tmp_path / "agent_tasks.json"
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "1")
    monkeypatch.setenv("AGENT_TASKS_PATH", str(tasks_path))

    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    created = agent_service.create_task(
        AgentTaskCreate(
            direction="Persist this task",
            task_type=TaskType.IMPL,
            context={"source": "persistence-test"},
        )
    )
    task_id = created["id"]
    updated = agent_service.update_task(
        task_id=task_id,
        status=TaskStatus.RUNNING,
        worker_id="openai-codex",
    )
    assert updated is not None

    assert tasks_path.exists()
    payload = json.loads(tasks_path.read_text(encoding="utf-8"))
    assert isinstance(payload.get("tasks"), list)
    assert any(row.get("id") == task_id for row in payload["tasks"])

    # Simulate process restart and verify disk-backed reload.
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    rows, total = agent_service.list_tasks(limit=50, offset=0)
    assert total == 1
    assert rows[0]["id"] == task_id
    assert rows[0]["status"] == TaskStatus.RUNNING


def test_agent_store_isolated_between_pytest_test_contexts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_agent_task_persistence.py::first")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_test_context = None

    created = agent_service.create_task(
        AgentTaskCreate(
            direction="first test context task",
            task_type=TaskType.IMPL,
        )
    )
    assert created["id"]
    rows, total = agent_service.list_tasks(limit=50, offset=0)
    assert total == 1

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "tests/test_agent_task_persistence.py::second")
    rows_after, total_after = agent_service.list_tasks(limit=50, offset=0)
    assert total_after == 0
    assert rows_after == []
