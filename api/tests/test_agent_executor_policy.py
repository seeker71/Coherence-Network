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
    route_decision = context.get("route_decision") or {}
    assert route_decision.get("executor") == "cursor"
    assert route_decision.get("provider") in {"cursor", "openrouter", "openai-codex"}
    assert "is_paid_provider" in route_decision
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
    _which = {"agent": "/usr/bin/agent", "claude": "/usr/bin/claude", "openclaw": None}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    first = agent_service.create_task(
        AgentTaskCreate(direction="Fix flaky endpoint test", task_type=TaskType.TEST)
    )
    agent_service.update_task(first["id"], status=TaskStatus.FAILED, output="failed attempt")

    second = agent_service.create_task(
        AgentTaskCreate(direction="Fix flaky endpoint test", task_type=TaskType.TEST)
    )

    assert str(second["model"]).startswith("claude/")
    assert str(second["command"]).startswith("claude ")
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
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "openclaw": "/usr/bin/openclaw"}
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


def test_explicit_executor_falls_back_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": None, "claude": None, "openclaw": "/usr/bin/openclaw", "codex": None}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Run with explicit unavailable executor",
            task_type=TaskType.IMPL,
            context={"executor": "claude"},
        )
    )
    context = task.get("context") or {}
    assert context.get("executor") == "openclaw"
    policy = context.get("executor_policy") or {}
    assert policy.get("reason") == "explicit_executor_unavailable"
    assert policy.get("explicit_executor") == "claude"
    assert policy.get("fallback_executor") == "openclaw"


def test_policy_disabled_falls_back_when_default_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_DEFAULT", "claude")
    _which = {"agent": None, "claude": None, "openclaw": "/usr/bin/openclaw", "codex": None}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(direction="Policy disabled fallback path", task_type=TaskType.IMPL)
    )
    context = task.get("context") or {}
    assert context.get("executor") == "openclaw"
    policy = context.get("executor_policy") or {}
    assert policy.get("reason") == "policy_disabled_default_unavailable"
    assert policy.get("default_executor") == "claude"
    assert policy.get("fallback_executor") == "openclaw"


def test_explicit_clawwork_executor_alias_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "openclaw": "/usr/bin/openclaw"}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Run with explicit clawwork alias",
            task_type=TaskType.IMPL,
            context={"executor": "clawwork"},
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


def test_repo_scoped_question_prefers_repo_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_REPO_DEFAULT", "cursor")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "openclaw": "/usr/bin/openclaw"}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="In this repo, which tests cover /api/agent/tasks?",
            task_type=TaskType.IMPL,
        )
    )

    context = task.get("context") or {}
    policy = context.get("executor_policy") or {}
    assert context.get("executor") == "cursor"
    assert policy.get("reason") == "repo_scoped_question"
    assert str(task["model"]).startswith("cursor/")
    assert str(task["command"]).startswith("agent ")


def test_open_question_prefers_openclaw(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_OPEN_QUESTION_DEFAULT", "openclaw")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "openclaw": "/usr/bin/openclaw"}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="What are three practical ways to reduce API latency?",
            task_type=TaskType.IMPL,
        )
    )

    context = task.get("context") or {}
    policy = context.get("executor_policy") or {}
    assert context.get("executor") == "openclaw"
    assert policy.get("reason") == "open_question_default"
    assert str(task["model"]).startswith("openclaw/")


def test_open_responses_normalization_is_shared_across_executors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "openclaw": "/usr/bin/openclaw"}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    cursor_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Normalize responses across providers",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )
    openclaw_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Normalize responses across providers",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw"},
        )
    )

    cursor_ctx = cursor_task.get("context") or {}
    claw_ctx = openclaw_task.get("context") or {}
    cursor_call = cursor_ctx.get("normalized_response_call") or {}
    claw_call = claw_ctx.get("normalized_response_call") or {}

    assert cursor_call.get("request_schema") == "open_responses_v1"
    assert claw_call.get("request_schema") == "open_responses_v1"
    assert cursor_call.get("input")[0]["content"][0]["type"] == "input_text"
    assert claw_call.get("input")[0]["content"][0]["type"] == "input_text"
    assert (
        cursor_call.get("input")[0]["content"][0]["text"]
        == claw_call.get("input")[0]["content"][0]["text"]
    )
    assert (cursor_ctx.get("route_decision") or {}).get("request_schema") == "open_responses_v1"
    assert (claw_ctx.get("route_decision") or {}).get("request_schema") == "open_responses_v1"
