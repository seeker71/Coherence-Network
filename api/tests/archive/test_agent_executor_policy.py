from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_service
from app.services import agent_service_executor


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
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": None}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
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
    assert policy.get("reason") in ("cheap_default", "open_question_default")


def test_policy_reserves_openrouter_for_budget_pressure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_CHEAP_DEFAULT", "openrouter")
    monkeypatch.setenv("AGENT_EXECUTOR_OPEN_QUESTION_DEFAULT", "cursor")
    _which = {"agent": "/usr/bin/agent", "claude": None, "codex": "/usr/bin/codex", "gemini": None}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(direction="Implement provider orchestration policy", task_type=TaskType.IMPL)
    )
    context = task.get("context") or {}
    policy = context.get("executor_policy") or {}

    assert context.get("executor") != "openrouter"
    assert policy.get("budget_pressure") is False
    assert policy.get("selection_engine") == "budget-aware-router-lite-v1"


def test_policy_can_route_to_openrouter_when_budget_pressure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_CHEAP_DEFAULT", "openrouter")
    monkeypatch.setenv("AGENT_EXECUTOR_OPEN_QUESTION_DEFAULT", "cursor")
    _which = {"agent": "/usr/bin/agent", "claude": None, "codex": "/usr/bin/codex", "gemini": None}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement provider orchestration policy",
            task_type=TaskType.IMPL,
            context={"budget_pressure": "exhausted"},
        )
    )
    context = task.get("context") or {}
    policy = context.get("executor_policy") or {}

    assert context.get("executor") == "openrouter"
    assert policy.get("budget_pressure") is True
    assert "context_budget_pressure_hint" in list(policy.get("budget_reasons") or [])
    assert isinstance(policy.get("routing_experiment"), dict)


def test_policy_escalates_after_failure_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_CHEAP_DEFAULT", "cursor")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_TO", "claude")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD", "10")
    _which = {"agent": "/usr/bin/agent", "claude": "/usr/bin/claude", "codex": None}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
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
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Run with explicit executor",
            task_type=TaskType.IMPL,
            context={"executor": "codex"},
        )
    )
    context = task.get("context") or {}
    assert context.get("executor") == "codex"
    policy = context.get("executor_policy") or {}
    assert policy == {}


def test_explicit_executor_is_forced_when_unavailable_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": None, "claude": None, "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Run with explicit unavailable executor",
            task_type=TaskType.IMPL,
            context={"executor": "claude"},
        )
    )
    context = task.get("context") or {}
    assert context.get("executor") == "claude"
    policy = context.get("executor_policy") or {}
    assert policy.get("reason") == "explicit_executor_forced"
    assert policy.get("explicit_executor") == "claude"
    assert policy.get("availability") == "unavailable_on_api_node"


def test_explicit_executor_always_honored_even_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Client-requested executor is always used so local runners get the right command (API node may not have claude)."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_ALLOW_UNAVAILABLE_EXPLICIT", "0")
    _which = {"agent": None, "claude": None, "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Run with explicit unavailable executor",
            task_type=TaskType.IMPL,
            context={"executor": "claude"},
        )
    )
    context = task.get("context") or {}
    assert context.get("executor") == "claude"
    policy = context.get("executor_policy") or {}
    assert policy.get("reason") == "explicit_executor_forced"
    assert policy.get("explicit_executor") == "claude"
    assert policy.get("availability") == "unavailable_on_api_node"


def test_policy_disabled_falls_back_when_default_unavailable(set_config, monkeypatch: pytest.MonkeyPatch) -> None:
    set_config("agent_tasks", "persist", False)
    set_config("agent_executor", "policy_enabled", False)
    set_config("agent_executor", "default", "claude")
    _which = {"agent": None, "claude": None, "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(direction="Policy disabled fallback path", task_type=TaskType.IMPL)
    )
    context = task.get("context") or {}
    assert context.get("executor") == "codex"
    policy = context.get("executor_policy") or {}
    assert policy.get("reason") == "policy_disabled_default_unavailable"
    assert policy.get("default_executor") == "claude"
    assert policy.get("fallback_executor") == "codex"


def test_unknown_executor_gets_policy_default(set_config, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unknown executor name (not in canonical list) is ignored; policy selects executor (e.g. codex for open question)."""
    set_config("agent_tasks", "persist", False)
    set_config("agent_executor", "open_question_default", "codex")
    _which = {"agent": "/usr/bin/agent", "claude": "/usr/bin/claude", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Task with unknown executor name",
            task_type=TaskType.IMPL,
            context={"executor": "unknown_executor"},
        )
    )
    context = task.get("context") or {}
    assert context.get("executor") == "codex"


def test_policy_falls_back_when_selected_executor_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_CHEAP_DEFAULT", "cursor")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_TO", "claude")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD", "10")
    _which = {"agent": "/usr/bin/agent", "aider": None, "codex": None}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
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
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
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


def test_open_question_prefers_codex(set_config, monkeypatch: pytest.MonkeyPatch) -> None:
    set_config("agent_tasks", "persist", False)
    set_config("agent_executor", "policy_enabled", True)
    set_config("agent_executor", "open_question_default", "codex")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="What are three practical ways to reduce API latency?",
            task_type=TaskType.IMPL,
        )
    )

    context = task.get("context") or {}
    policy = context.get("executor_policy") or {}
    assert context.get("executor") == "codex"
    assert policy.get("reason") == "open_question_default"
    assert str(task["model"]).startswith("codex/")


def test_policy_does_not_escalate_away_from_gemini_default(set_config, monkeypatch: pytest.MonkeyPatch) -> None:
    set_config("agent_tasks", "persist", False)
    set_config("agent_executor", "policy_enabled", True)
    set_config("agent_executor", "cheap_default", "gemini")
    set_config("agent_executor", "open_question_default", "gemini")
    set_config("agent_executor", "escalate_to", None)
    set_config("agent_executor", "escalate_failure_threshold", 1)
    set_config("agent_executor", "escalate_retry_threshold", 10)
    _which = {"agent": None, "claude": "/usr/bin/claude", "codex": None, "gemini": "/usr/bin/gemini"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    first = agent_service.create_task(
        AgentTaskCreate(direction="Investigate repository drift signal", task_type=TaskType.IMPL)
    )
    assert (first.get("context") or {}).get("executor") == "gemini"
    agent_service.update_task(first["id"], status=TaskStatus.FAILED, output="failed attempt")

    second = agent_service.create_task(
        AgentTaskCreate(direction="Investigate repository drift signal", task_type=TaskType.IMPL)
    )

    assert str(second["model"]).startswith("gemini/")
    assert str(second["command"]).startswith("gemini ")
    context = second.get("context") or {}
    assert context.get("executor") == "gemini"
    policy = context.get("executor_policy") or {}
    assert policy.get("reason") == "failure_threshold"
    assert policy.get("escalation_executor") == "gemini"


def test_open_responses_normalization_is_shared_across_executors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    cursor_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Normalize responses across providers",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )
    codex_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Normalize responses across providers",
            task_type=TaskType.IMPL,
            context={"executor": "codex"},
        )
    )

    cursor_ctx = cursor_task.get("context") or {}
    claw_ctx = codex_task.get("context") or {}
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


def test_apply_resume_to_command_claude_injects_c_and_other_executors_unchanged() -> None:
    from app.services.agent_service_executor import apply_resume_to_command, build_command

    claude_cmd = build_command("Direction", TaskType.IMPL, executor="claude")
    assert "claude -c -p" not in claude_cmd
    resumed = apply_resume_to_command("claude", claude_cmd, {"resume": True})
    assert "claude -c -p" in resumed

    cursor_cmd = build_command("Direction", TaskType.IMPL, executor="cursor")
    cursor_resumed = apply_resume_to_command("cursor", cursor_cmd, {"resume": True})
    assert cursor_cmd == cursor_resumed


def test_create_task_reuses_existing_when_fingerprint_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    first = agent_service.create_task(
        AgentTaskCreate(
            direction="Impl with fingerprint",
            task_type=TaskType.IMPL,
            context={"task_fingerprint": "spec_impl::007"},
        )
    )
    first_id = first["id"]

    second = agent_service.create_task(
        AgentTaskCreate(
            direction="Same fingerprint",
            task_type=TaskType.IMPL,
            context={"task_fingerprint": "spec_impl::007"},
        )
    )
    assert second["id"] == first_id
    assert second["updated_at"] is not None
