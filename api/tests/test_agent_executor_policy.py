from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


def test_policy_uses_cheap_executor_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_CHEAP_DEFAULT", "cursor")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_TO", "claude")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD", "3")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "openclaw": None}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(direction="Implement policy default cheap route", task_type=TaskType.IMPL)
    )

    assert str(task["model"]).startswith("cursor/")
    assert str(task["command"]).startswith("agent ")
    context = task.get("context") or {}
    assert context.get("executor") == "cursor"
    policy = context.get("executor_policy") or {}
    assert policy.get("policy_applied") is True
    assert policy.get("reason") == "cheap_default"


def test_policy_escalates_after_failure_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_CHEAP_DEFAULT", "cursor")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_TO", "claude")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD", "10")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "openclaw": None}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    first = agent_service.create_task(
        AgentTaskCreate(direction="Fix flaky endpoint test", task_type=TaskType.TEST)
    )
    agent_service.update_task(first["id"], status=TaskStatus.FAILED, output="failed attempt")

    second = agent_service.create_task(
        AgentTaskCreate(direction="Fix flaky endpoint test", task_type=TaskType.TEST)
    )

    assert str(second["model"]).startswith("openrouter/")
    assert str(second["command"]).startswith("aider ")
    context = second.get("context") or {}
    assert context.get("executor") == "claude"
    policy = context.get("executor_policy") or {}
    assert policy.get("reason") == "failure_threshold"
    assert int(policy.get("historical_failures", 0)) >= 1


@pytest.mark.asyncio
async def test_route_auto_executor_uses_policy_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_EXECUTOR_CHEAP_DEFAULT", "cursor")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/route", params={"task_type": "impl", "executor": "auto"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["executor"] == "cursor"
    assert payload["tier"] == "cursor"
    assert str(payload["model"]).startswith("cursor/")


def test_explicit_executor_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "openclaw": None}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Run with explicit executor",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw"},
        )
    )
    context = task.get("context") or {}
    assert context.get("executor") == "openclaw"
    policy = context.get("executor_policy") or {}
    assert policy == {}


def test_policy_falls_back_when_selected_executor_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_CHEAP_DEFAULT", "cursor")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_TO", "claude")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD", "10")
    _which = {"agent": "/usr/bin/agent", "aider": None, "openclaw": None}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    first = agent_service.create_task(
        AgentTaskCreate(direction="Escalation target unavailable", task_type=TaskType.IMPL)
    )
    agent_service.update_task(first["id"], status=TaskStatus.FAILED, output="failed")

    second = agent_service.create_task(
        AgentTaskCreate(direction="Escalation target unavailable", task_type=TaskType.IMPL)
    )
    context = second.get("context") or {}
    assert context.get("executor") == "cursor"
    policy = context.get("executor_policy") or {}
    assert policy.get("reason") == "selected_executor_unavailable"
    assert policy.get("selected_executor") == "claude"
    assert policy.get("fallback_executor") == "cursor"
