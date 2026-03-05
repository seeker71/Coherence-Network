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
    agent_service._MODEL_COOLDOWN_CACHE.clear()
    agent_service._MODEL_COOLDOWN_SIGNAL_SEEN.clear()


@pytest.fixture(autouse=True)
def _reset_model_cooldown_state() -> None:
    agent_service._MODEL_COOLDOWN_CACHE.clear()
    agent_service._MODEL_COOLDOWN_SIGNAL_SEEN.clear()
    yield
    agent_service._MODEL_COOLDOWN_CACHE.clear()
    agent_service._MODEL_COOLDOWN_SIGNAL_SEEN.clear()


def test_policy_uses_cheap_executor_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_CHEAP_DEFAULT", "cursor")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_TO", "claude")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD", "3")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": None}
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
    _which = {"agent": "/usr/bin/agent", "claude": "/usr/bin/claude", "codex": None}
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
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": "/usr/bin/codex"}
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
    assert context.get("executor") == "codex"
    policy = context.get("executor_policy") or {}
    assert policy == {}


def test_explicit_executor_is_forced_when_unavailable_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": None, "claude": None, "codex": "/usr/bin/codex"}
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
    assert context.get("executor") == "claude"
    policy = context.get("executor_policy") or {}
    assert policy.get("reason") == "explicit_executor_forced"
    assert policy.get("explicit_executor") == "claude"
    assert policy.get("availability") == "unavailable_on_api_node"


def test_explicit_executor_falls_back_when_unavailable_and_forcing_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_ALLOW_UNAVAILABLE_EXPLICIT", "0")
    _which = {"agent": None, "claude": None, "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Run with explicit unavailable executor and forcing disabled",
            task_type=TaskType.IMPL,
            context={"executor": "claude"},
        )
    )
    context = task.get("context") or {}
    assert context.get("executor") == "codex"
    policy = context.get("executor_policy") or {}
    assert policy.get("reason") == "explicit_executor_unavailable"
    assert policy.get("explicit_executor") == "claude"
    assert policy.get("fallback_executor") == "codex"


def test_policy_disabled_falls_back_when_default_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_DEFAULT", "claude")
    _which = {"agent": None, "claude": None, "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
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


def test_explicit_clawwork_executor_alias_is_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": "/usr/bin/codex"}
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
    assert context.get("executor") == "codex"
    policy = context.get("executor_policy") or {}
    assert policy == {}


def test_policy_falls_back_when_selected_executor_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_CHEAP_DEFAULT", "cursor")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_TO", "claude")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD", "10")
    _which = {"agent": "/usr/bin/agent", "aider": None, "codex": None}
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


@pytest.mark.asyncio
async def test_route_all_task_types_all_executors_return_valid_template() -> None:
    """All four provider CLIs (Codex, Claude Code, Cursor, Gemini) support all task types (spec 108)."""
    executors = ["claude", "cursor", "openclaw", "codex", "gemini"]
    task_types = [t.value for t in TaskType]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for task_type in task_types:
            for executor in executors:
                res = await client.get(
                    "/api/agent/route",
                    params={"task_type": task_type, "executor": executor},
                )
                assert res.status_code == 200, f"{task_type}/{executor}: {res.status_code}"
                payload = res.json()
                template = str(payload.get("command_template") or "").strip()
                assert "{{direction}}" in template, f"{task_type}/{executor}: missing {{direction}}"
                assert payload.get("task_type") == task_type
                expected_executor = "codex" if executor == "openclaw" else executor
                assert payload.get("executor") == expected_executor


def test_repo_scoped_question_prefers_repo_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_REPO_DEFAULT", "cursor")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": "/usr/bin/codex"}
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


def test_open_question_prefers_codex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_OPEN_QUESTION_DEFAULT", "codex")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": "/usr/bin/codex"}
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
    assert context.get("executor") == "codex"
    assert policy.get("reason") == "open_question_default"
    assert str(task["model"]).startswith("codex/")


def test_policy_does_not_escalate_away_from_gemini_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTOR_POLICY_ENABLED", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_CHEAP_DEFAULT", "gemini")
    monkeypatch.delenv("AGENT_EXECUTOR_ESCALATE_TO", raising=False)
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_FAILURE_THRESHOLD", "1")
    monkeypatch.setenv("AGENT_EXECUTOR_ESCALATE_RETRY_THRESHOLD", "10")
    _which = {"agent": None, "claude": "/usr/bin/claude", "codex": None, "gemini": "/usr/bin/gemini"}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
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
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
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
            context={"executor": "openclaw"},
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


def test_create_task_includes_orchestrator_model_selection_with_ab_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {
        "agent": "/usr/bin/agent",
        "claude": "/usr/bin/claude",
        "codex": "/usr/bin/codex",
        "gemini": "/usr/bin/gemini",
    }
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(direction="Compare providers for implementation stability", task_type=TaskType.IMPL)
    )
    selection = (task.get("context") or {}).get("orchestrator_model_selection") or {}
    primary = selection.get("primary") or {}
    challenger = selection.get("ab_test_candidate") or {}

    assert str(selection.get("selection_mode") or "") == "orchestrator_guided"
    assert str(primary.get("executor") or "")
    assert str(primary.get("model") or "")
    assert "executor_scorecard" in selection
    if challenger:
        assert str(challenger.get("executor") or "") != str(primary.get("executor") or "")
        assert str(challenger.get("model") or "")


def test_model_cooldown_remaps_codex_spark_after_usage_limit_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_MODEL_COOLDOWN_SECONDS", "7200")
    _which = {"agent": "/usr/bin/agent", "claude": "/usr/bin/claude", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    first = agent_service.create_task(
        AgentTaskCreate(
            direction="Run with spark model first",
            task_type=TaskType.IMPL,
            context={"executor": "codex", "model_override": "gpt-5.3-codex-spark"},
        )
    )
    assert first["model"] == "codex/gpt-5.3-codex-spark"
    agent_service.update_task(
        first["id"],
        status=TaskStatus.FAILED,
        output="spark weekly usage limit reached for this model",
    )

    second = agent_service.create_task(
        AgentTaskCreate(
            direction="Retry after spark usage cap",
            task_type=TaskType.IMPL,
            context={"executor": "codex", "model_override": "gpt-5.3-codex-spark"},
        )
    )
    assert second["model"] == "codex/gpt-5.3-codex"
    assert "--model gpt-5.3-codex" in str(second["command"])
    assert "--model gpt-5.3-codex-spark" not in str(second["command"])
    second_context = second.get("context") or {}
    active = second_context.get("model_cooldown_active") or {}
    assert active.get("requested_model") == "codex/gpt-5.3-codex-spark"
    assert active.get("effective_model") == "codex/gpt-5.3-codex"
    assert str(active.get("source_task_id") or "") == str(first["id"])
    assert str(active.get("reason") or "").startswith("task_failed_model_limit:")
    route_decision = second_context.get("route_decision") or {}
    model_selection = route_decision.get("model_selection") or {}
    assert model_selection.get("policy") == "model_cooldown"
    assert model_selection.get("requested_model") == "codex/gpt-5.3-codex-spark"
    assert model_selection.get("effective_model") == "codex/gpt-5.3-codex"


def test_model_cooldown_expires_and_retries_requested_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_MODEL_COOLDOWN_SECONDS", "60")
    monkeypatch.setenv("AGENT_MODEL_COOLDOWN_LOOKBACK_SECONDS", "43200")
    _which = {"agent": "/usr/bin/agent", "claude": "/usr/bin/claude", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    base = agent_service.datetime(2026, 3, 5, 10, 0, 0, tzinfo=agent_service.timezone.utc)
    now_state = {"value": base}
    monkeypatch.setattr(agent_service, "_now", lambda: now_state["value"])

    first = agent_service.create_task(
        AgentTaskCreate(
            direction="Spark model run",
            task_type=TaskType.IMPL,
            context={"executor": "codex", "model_override": "gpt-5.3-codex-spark"},
        )
    )
    agent_service.update_task(
        first["id"],
        status=TaskStatus.FAILED,
        output="out of weekly usage for spark",
    )

    now_state["value"] = base + agent_service.timedelta(seconds=10)
    remapped = agent_service.create_task(
        AgentTaskCreate(
            direction="Immediate retry should remap",
            task_type=TaskType.IMPL,
            context={"executor": "codex", "model_override": "gpt-5.3-codex-spark"},
        )
    )
    assert remapped["model"] == "codex/gpt-5.3-codex"

    now_state["value"] = base + agent_service.timedelta(hours=3)
    after_expiry = agent_service.create_task(
        AgentTaskCreate(
            direction="Retry after cooldown should use requested model again",
            task_type=TaskType.IMPL,
            context={"executor": "codex", "model_override": "gpt-5.3-codex-spark"},
        )
    )
    assert after_expiry["model"] == "codex/gpt-5.3-codex-spark"
