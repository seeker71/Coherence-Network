from __future__ import annotations

import json
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_service, agent_task_store_service


@pytest.mark.asyncio
async def test_upsert_active_task_creates_once_and_reuses_by_session_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

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
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

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
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

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
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

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


def test_agent_tasks_persist_and_reload_from_db(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "agent_tasks.db"
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "1")
    monkeypatch.setenv("AGENT_TASKS_USE_DB", "1")
    monkeypatch.setenv("AGENT_TASKS_DATABASE_URL", f"sqlite:///{db_path}")

    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

    created = agent_service.create_task(
        AgentTaskCreate(
            direction="Persist this task in DB",
            task_type=TaskType.IMPL,
            context={"source": "db-persistence-test"},
        )
    )
    task_id = created["id"]
    updated = agent_service.update_task(
        task_id=task_id,
        status=TaskStatus.RUNNING,
        worker_id="openai-codex",
    )
    assert updated is not None

    # Simulate process restart and verify DB-backed reload.
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

    rows, total = agent_service.list_tasks(limit=50, offset=0)
    assert total == 1
    assert rows[0]["id"] == task_id
    assert rows[0]["status"] == TaskStatus.RUNNING


def test_db_reload_without_output_does_not_erase_task_output(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "agent_tasks_output.db"
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "1")
    monkeypatch.setenv("AGENT_TASKS_USE_DB", "1")
    monkeypatch.setenv("AGENT_TASKS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AGENT_TASK_OUTPUT_MAX_CHARS", "1200")

    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

    created = agent_service.create_task(
        AgentTaskCreate(
            direction="Persist and retain output",
            task_type=TaskType.IMPL,
        )
    )
    task_id = created["id"]
    long_output = "x" * 2000

    updated = agent_service.update_task(
        task_id=task_id,
        status=TaskStatus.COMPLETED,
        output=long_output,
        worker_id="openai-codex",
    )
    assert updated is not None
    assert str(updated.get("output") or "").endswith("...[truncated]")

    # No output provided here; DB row should keep the previously stored output.
    again = agent_service.update_task(
        task_id=task_id,
        current_step="post-completion marker",
        worker_id="openai-codex",
    )
    assert again is not None

    fetched = agent_service.get_task(task_id)
    assert fetched is not None
    assert str(fetched.get("output") or "").endswith("...[truncated]")


def test_db_list_tasks_uses_paginated_query_not_full_table_reload(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "agent_tasks_paged.db"
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "1")
    monkeypatch.setenv("AGENT_TASKS_USE_DB", "1")
    monkeypatch.setenv("AGENT_TASKS_DATABASE_URL", f"sqlite:///{db_path}")

    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

    created = agent_service.create_task(
        AgentTaskCreate(
            direction="DB paged list task",
            task_type=TaskType.IMPL,
        )
    )
    task_id = created["id"]

    def _fail_load_tasks(*args, **kwargs):
        raise AssertionError("full-table load_tasks should not be used in DB paged list flow")

    monkeypatch.setattr(agent_task_store_service, "load_tasks", _fail_load_tasks)
    rows, total = agent_service.list_tasks(limit=20, offset=0)

    assert total == 1
    assert rows[0]["id"] == task_id


def test_db_update_task_hydrates_single_task_without_full_table_reload(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "agent_tasks_update_single.db"
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "1")
    monkeypatch.setenv("AGENT_TASKS_USE_DB", "1")
    monkeypatch.setenv("AGENT_TASKS_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("AGENT_TASKS_DB_RELOAD_TTL_SECONDS", "300")

    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

    created = agent_service.create_task(
        AgentTaskCreate(
            direction="DB single-task update",
            task_type=TaskType.IMPL,
        )
    )
    task_id = created["id"]

    # Simulate warm cache with empty in-memory map; update should hydrate this task by id only.
    agent_service._store.clear()
    agent_service._store_loaded = True
    agent_service._store_loaded_path = str(agent_service._store_path())
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = time.monotonic()

    def _fail_load_tasks(*args, **kwargs):
        raise AssertionError("full-table load_tasks should not be used in single-task update flow")

    monkeypatch.setattr(agent_task_store_service, "load_tasks", _fail_load_tasks)
    updated = agent_service.update_task(
        task_id=task_id,
        status=TaskStatus.RUNNING,
        worker_id="openai-codex",
    )

    assert updated is not None
    assert updated["id"] == task_id
    assert updated["status"] == TaskStatus.RUNNING


def test_update_task_backfills_failed_output_from_context_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

    created = agent_service.create_task(
        AgentTaskCreate(
            direction="Fail with context error",
            task_type=TaskType.IMPL,
        )
    )
    task_id = created["id"]
    updated = agent_service.update_task(
        task_id=task_id,
        status=TaskStatus.FAILED,
        context={"error": "Execution timed out while waiting for provider response"},
    )

    assert updated is not None
    output = str(updated.get("output") or "")
    assert output.startswith("Failure diagnostic (context.error):")
    assert "timed out" in output.lower()
    context = updated.get("context") if isinstance(updated.get("context"), dict) else {}
    assert context.get("failure_diagnostics_present") is True
    assert context.get("failure_diagnostics_source") == "context.error"
    assert context.get("failure_reason_bucket") == "timeout"


def test_update_task_backfills_failed_output_with_fallback_when_error_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

    created = agent_service.create_task(
        AgentTaskCreate(
            direction="Fail without explicit output",
            task_type=TaskType.REVIEW,
        )
    )
    task_id = created["id"]
    updated = agent_service.update_task(
        task_id=task_id,
        status=TaskStatus.FAILED,
    )

    assert updated is not None
    output = str(updated.get("output") or "")
    assert output.startswith("Task failed without explicit error output.")
    context = updated.get("context") if isinstance(updated.get("context"), dict) else {}
    assert context.get("failure_diagnostics_present") is True
    assert context.get("failure_diagnostics_source") == "fallback"
    assert context.get("failure_reason_bucket") in {"other", "empty_output"}


def test_create_task_records_task_card_validation_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0

    created = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement task-card scoring metadata",
            task_type=TaskType.IMPL,
            context={
                "task_card": {
                    "goal": "Add scoring metadata to task context",
                    "files_allowed": ["api/app/services/agent_service.py"],
                    "done_when": ["context.task_card_validation.score is present"],
                    "commands": ["cd api && pytest -q tests/test_agent_task_persistence.py -k task_card"],
                    "constraints": ["no placeholder fields"],
                }
            },
        )
    )
    context = created.get("context") if isinstance(created.get("context"), dict) else {}
    validation = context.get("task_card_validation") if isinstance(context.get("task_card_validation"), dict) else {}
    assert validation.get("present") is True
    assert validation.get("missing") == []
    assert validation.get("score") == pytest.approx(1.0, rel=1e-6)

    partial = agent_service.create_task(
        AgentTaskCreate(
            direction="Create a task with an incomplete task card",
            task_type=TaskType.IMPL,
            context={"task_card": {"goal": "Only goal is set"}},
        )
    )
    partial_context = partial.get("context") if isinstance(partial.get("context"), dict) else {}
    partial_validation = (
        partial_context.get("task_card_validation")
        if isinstance(partial_context.get("task_card_validation"), dict)
        else {}
    )
    assert partial_validation.get("present") is True
    assert partial_validation.get("score", 1.0) < 1.0
    assert set(partial_validation.get("missing") or []) == {
        "files_allowed",
        "done_when",
        "commands",
        "constraints",
    }
