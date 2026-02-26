from __future__ import annotations

import json
from uuid import uuid4
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskType
from app.services import agent_service


@pytest.fixture(autouse=True)
def _allow_legacy_unauthenticated_execute_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_EXECUTE_TOKEN_ALLOW_UNAUTH", "1")


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


@pytest.mark.asyncio
async def test_execute_endpoint_requires_token_when_configured(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_EXECUTE_TOKEN", "secret")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Return ok",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 5, "provider_request_id": "req_test", "response_id": "resp_test"},
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 403

        res2 = await client.post(
            f"/api/agent/tasks/{task['id']}/execute",
            headers={"X-Agent-Execute-Token": "secret"},
        )
        assert res2.status_code == 200


@pytest.mark.asyncio
async def test_execute_endpoint_completes_task_when_openrouter_is_stubbed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 5, "provider_request_id": "req_test", "response_id": "resp_test"},
        ),
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Return ok",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 200

        fetched = await client.get(f"/api/agent/tasks/{task['id']}")
        assert fetched.status_code == 200
        payload = fetched.json()
        assert payload["status"] == "completed"
        assert payload["output"] == "ok"


@pytest.mark.asyncio
async def test_execute_endpoint_retries_once_with_retry_hint_after_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_TASK_RETRY_MAX", "1")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    call_count = {"value": 0}
    prompt_history: list[str] = []

    def _flaky_chat_completion(**kwargs):
        prompt_history.append(str(kwargs.get("prompt") or ""))
        call_count["value"] += 1
        if call_count["value"] == 1:
            raise agent_execution_service.OpenRouterError("temporary failure: missing setup")
        return (
            "retry-ok",
            {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
            {"elapsed_ms": 8, "provider_request_id": "req_retry_ok", "response_id": "resp_retry_ok"},
        )

    monkeypatch.setattr(agent_execution_service, "chat_completion", _flaky_chat_completion)

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Return retry success",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 200

        fetched = await client.get(f"/api/agent/tasks/{task['id']}")
        assert fetched.status_code == 200
        payload = fetched.json()
        context = payload.get("context") or {}

        assert payload["status"] == "completed"
        assert payload["output"] == "retry-ok"
        assert int(context.get("failure_hits", 0)) == 1
        assert int(context.get("retry_count", 0)) == 1
        assert "Retry attempt 1" in str(context.get("retry_hint") or "")
        assert call_count["value"] == 2
        assert len(prompt_history) == 2
        assert "Retry guidance" in prompt_history[1]
        assert "temporary failure" in prompt_history[1]


@pytest.mark.asyncio
async def test_execute_endpoint_stops_retry_after_single_retry_budget(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_TASK_RETRY_MAX", "1")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    call_count = {"value": 0}

    def _always_fail_chat_completion(**_kwargs):
        call_count["value"] += 1
        raise agent_execution_service.OpenRouterError(
            f"persistent failure attempt {call_count['value']}"
        )

    monkeypatch.setattr(agent_execution_service, "chat_completion", _always_fail_chat_completion)

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Keep failing to test retry budget",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 200

        fetched = await client.get(f"/api/agent/tasks/{task['id']}")
        assert fetched.status_code == 200
        payload = fetched.json()
        context = payload.get("context") or {}

        assert payload["status"] == "failed"
        assert "persistent failure attempt 2" in payload["output"]
        assert int(context.get("failure_hits", 0)) == 2
        assert int(context.get("retry_count", 0)) == 1
        assert call_count["value"] == 2


@pytest.mark.asyncio
async def test_execute_endpoint_auto_retries_paid_provider_failure_with_openai_override(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_TASK_RETRY_MAX", "1")
    monkeypatch.setenv("AGENT_AUTO_RETRY_OPENAI_OVERRIDE", "1")
    monkeypatch.setenv("AGENT_RETRY_OPENAI_MODEL_OVERRIDE", "gpt-5-codex")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    call_count = {"value": 0}

    def _paid_retry_success(**_kwargs):
        call_count["value"] += 1
        return (
            "paid-retry-ok",
            {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            {"elapsed_ms": 5, "provider_request_id": "req_paid_retry", "response_id": "resp_paid_retry"},
        )

    monkeypatch.setattr(agent_execution_service, "chat_completion", _paid_retry_success)

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Retry paid route with override",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 200

        fetched = await client.get(f"/api/agent/tasks/{task['id']}")
        assert fetched.status_code == 200
        payload = fetched.json()
        context = payload.get("context") or {}

        assert payload["status"] == "completed"
        assert payload["output"] == "paid-retry-ok"
        assert int(context.get("failure_hits", 0)) == 1
        assert int(context.get("retry_count", 0)) == 1
        assert context.get("retry_paid_override_applied") is True
        assert context.get("force_paid_providers") is True
        assert context.get("force_paid_override_source") == "auto_retry_openai_override"
        assert context.get("model_override") == "gpt-5-codex"
        assert call_count["value"] == 1


@pytest.mark.asyncio
async def test_execute_endpoint_blocks_paid_provider_until_forced(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            {"elapsed_ms": 6, "provider_request_id": "req_paid", "response_id": "resp_paid"},
        ),
    )

    paid_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Assess codex route",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/agent/tasks/{paid_task['id']}/execute")
        blocked = await client.get(f"/api/agent/tasks/{paid_task['id']}")
        assert blocked.status_code == 200
        blocked_payload = blocked.json()
        assert blocked_payload["status"] == "failed"
        assert blocked_payload["output"] == (
            "Blocked: task routes to a paid provider and AGENT_ALLOW_PAID_PROVIDERS is disabled."
        )

        forced = agent_service.create_task(
            AgentTaskCreate(
                direction="Assess codex route",
                task_type=TaskType.IMPL,
                context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
            )
        )

        await client.post(
            f"/api/agent/tasks/{forced['id']}/execute?force_paid_providers=true"
        )
        completed = await client.get(f"/api/agent/tasks/{forced['id']}")
        assert completed.status_code == 200
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"
        assert completed_payload["output"] == "ok"

        events = await client.get("/api/runtime/events?limit=50")
        assert events.status_code == 200
        runtime_rows = events.json()
        tool_rows = [
            row
            for row in runtime_rows
            if str(row.get("metadata", {}).get("tracking_kind")).strip() == "agent_tool_call"
            and row.get("metadata", {}).get("task_id") == forced["id"]
        ]
        assert tool_rows, "Expected agent_tool_call runtime event"
        tool_metadata = tool_rows[0]["metadata"]
        assert tool_metadata["is_paid_provider"] is True
        assert int(tool_metadata["usage_prompt_tokens"]) == 3
        assert int(tool_metadata["usage_completion_tokens"]) == 2
        assert int(tool_metadata["usage_total_tokens"]) == 5


@pytest.mark.asyncio
async def test_execute_endpoint_accepts_force_paid_query_numeric_and_alternate_keys(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
            {"elapsed_ms": 4, "provider_request_id": "req_paid_num", "response_id": "resp_paid_num"},
        ),
    )

    paid_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Assess codex route",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/agent/tasks/{paid_task['id']}/execute?force_paid_providers=1")
        completed = await client.get(f"/api/agent/tasks/{paid_task['id']}")
        assert completed.status_code == 200
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"
        assert completed_payload["output"] == "ok"

        alt_task = agent_service.create_task(
            AgentTaskCreate(
                direction="Assess codex route",
                task_type=TaskType.IMPL,
                context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
            )
        )
        await client.post(
            f"/api/agent/tasks/{alt_task['id']}/execute?force_allow_paid_providers=true"
        )
        alt_completed = await client.get(f"/api/agent/tasks/{alt_task['id']}")
        assert alt_completed.status_code == 200
        alt_completed_payload = alt_completed.json()
        assert alt_completed_payload["status"] == "completed"
        assert alt_completed_payload["output"] == "ok"


@pytest.mark.asyncio
async def test_execute_endpoint_accepts_hyphenated_force_paid_query_key(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            {"elapsed_ms": 7, "provider_request_id": "req_paid_dash", "response_id": "resp_paid_dash"},
        ),
    )

    paid_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Assess hyphenated override",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/agent/tasks/{paid_task['id']}/execute?force-paid-providers=true"
        )
        completed = await client.get(f"/api/agent/tasks/{paid_task['id']}")
        assert completed.status_code == 200
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"
        assert completed_payload["output"] == "ok"


@pytest.mark.asyncio
async def test_execute_endpoint_accepts_case_insensitive_force_paid_query_key(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            {"elapsed_ms": 6, "provider_request_id": "req_paid_case", "response_id": "resp_paid_case"},
        ),
    )

    paid_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Assess case-insensitive override",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/agent/tasks/{paid_task['id']}/execute?FoRcE-PaId-PrOvIdErS"
        )
        completed = await client.get(f"/api/agent/tasks/{paid_task['id']}")
        assert completed.status_code == 200
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"
        assert completed_payload["output"] == "ok"


@pytest.mark.asyncio
async def test_execute_endpoint_accepts_force_paid_header_override(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            {"elapsed_ms": 6, "provider_request_id": "req_paid_header", "response_id": "resp_paid_header"},
        ),
    )

    paid_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Assess header override",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/agent/tasks/{paid_task['id']}/execute",
            headers={"X-Force-Paid-Providers": "true"},
        )
        completed = await client.get(f"/api/agent/tasks/{paid_task['id']}")
        assert completed.status_code == 200
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"
        assert completed_payload["output"] == "ok"

        events = await client.get("/api/runtime/events?limit=50")
        assert events.status_code == 200
        runtime_rows = events.json()
        summary_rows = [
            row
            for row in runtime_rows
            if str(row.get("metadata", {}).get("tracking_kind")).strip() == "agent_task_execution"
            and row.get("metadata", {}).get("task_id") == paid_task["id"]
        ]
        assert summary_rows, "Expected agent task execution summary event"
        assert summary_rows[0]["metadata"]["paid_provider_override"] is True


@pytest.mark.asyncio
async def test_execute_endpoint_blocks_paid_provider_when_usage_window_budget_exceeded(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("AGENT_ALLOW_PAID_PROVIDERS", "1")
    monkeypatch.setenv("PAID_TOOL_8H_LIMIT", "1")
    monkeypatch.setenv("PAID_TOOL_WINDOW_BUDGET_FRACTION", "0.333333")
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        seed = await client.post(
            "/api/runtime/events",
            json={
                "source": "worker",
                "endpoint": "tool:openrouter.chat_completion",
                "method": "RUN",
                "status_code": 200,
                "runtime_ms": 12.0,
                "metadata": {
                    "tracking_kind": "agent_tool_call",
                    "is_paid_provider": True,
                    "runtime_cost_usd": 0.003,
                    "task_id": "seed_task",
                },
                "idea_id": "coherence-network-agent-pipeline",
            },
        )
        assert seed.status_code == 201

        task = agent_service.create_task(
            AgentTaskCreate(
                direction="Assess codex route with budget cap",
                task_type=TaskType.IMPL,
                context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
            )
        )

        await client.post(f"/api/agent/tasks/{task['id']}/execute")
        blocked = await client.get(f"/api/agent/tasks/{task['id']}")
        assert blocked.status_code == 200
        blocked_payload = blocked.json()
        assert blocked_payload["status"] == "failed"
        assert blocked_payload["output"].startswith("Paid-provider usage blocked by window policy")

        friction = await client.get("/api/friction/events?status=open")
        assert friction.status_code == 200
        matching = [
            item
            for item in friction.json()
            if item.get("block_type") == "usage_window_budget_exceeded"
            and "Paid-provider usage blocked" in item.get("notes", "")
        ]
        assert matching
        row = matching[0]
        assert row.get("task_id") == task["id"]
        assert row.get("provider")
        assert row.get("billing_provider")
        assert row.get("tool") == "agent-task-execution-summary"
        assert row.get("model")
        assert any(
            item.get("block_type") == "usage_window_budget_exceeded"
            and "Paid-provider usage blocked" in item.get("notes", "")
            for item in friction.json()
        )

        # The same task can also be re-executed with explicit override.
        forced = agent_service.create_task(
            AgentTaskCreate(
                direction="Assess codex route with budget override",
                task_type=TaskType.IMPL,
                context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
            )
        )

        monkeypatch.setattr(
            agent_execution_service,
            "chat_completion",
            lambda **_: (
                json.dumps({"confidence": 0.91, "estimated_value": 1.0}),
                {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                {"elapsed_ms": 4, "provider_request_id": "req_forced", "response_id": "resp_forced"},
            ),
        )

        forced_exec = await client.post(
            f"/api/agent/tasks/{forced['id']}/execute?force_paid_providers=true"
        )
        assert forced_exec.status_code == 200
        completed = await client.get(f"/api/agent/tasks/{forced['id']}")
        assert completed.status_code == 200
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"


@pytest.mark.asyncio
async def test_execute_endpoint_blocks_paid_provider_when_provider_quota_guard_blocks(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("AGENT_ALLOW_PAID_PROVIDERS", "1")
    monkeypatch.delenv("PAID_TOOL_8H_LIMIT", raising=False)
    monkeypatch.delenv("PAID_TOOL_WEEK_LIMIT", raising=False)
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service.automation_usage_service,
        "provider_limit_guard_decision",
        lambda provider, force_refresh=False: {
            "allowed": False,
            "provider": provider,
            "reason": "monthly::credits remaining=4.0/100.0 ratio=0.04<=threshold=0.1",
            "blocked_metrics": [
                {
                    "metric_id": "credits",
                    "window": "monthly",
                    "remaining_ratio": 0.04,
                    "threshold_ratio": 0.1,
                }
            ],
            "evaluated_metrics": [],
        },
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Assess codex route with provider quota guard",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(f"/api/agent/tasks/{task['id']}/execute")
        blocked = await client.get(f"/api/agent/tasks/{task['id']}")
        assert blocked.status_code == 200
        payload = blocked.json()
        assert payload["status"] == "failed"
        assert payload["output"].startswith("Paid-provider usage blocked by provider quota policy")

        friction = await client.get("/api/friction/events?status=open")
        assert friction.status_code == 200
        matching = [
            item
            for item in friction.json()
            if item.get("block_type") == "provider_usage_limit_exceeded"
            and "provider quota policy" in item.get("notes", "")
        ]
        assert matching
        row = matching[0]
        assert row.get("task_id") == task["id"]
        assert row.get("provider")
        assert row.get("billing_provider")
        assert row.get("tool") == "agent-task-execution-summary"
        assert row.get("model")
        assert any(
            item.get("block_type") == "provider_usage_limit_exceeded"
            and "provider quota policy" in item.get("notes", "")
            for item in friction.json()
        )


@pytest.mark.asyncio
async def test_review_task_can_return_confidence_with_paid_override(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    expected_review_output = {
        "confidence": 0.93,
        "estimated_value": 15.0,
        "actual_value": 14.5,
    }
    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            json.dumps(expected_review_output),
            {"prompt_tokens": 8, "completion_tokens": 12, "total_tokens": 20},
            {"elapsed_ms": 8, "provider_request_id": "req_review", "response_id": "resp_review"},
        ),
    )

    review_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Review the implementation and provide confidence + value estimates.",
            task_type=TaskType.REVIEW,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            f"/api/agent/tasks/{review_task['id']}/execute?force_paid_providers=true"
        )
        completed = await client.get(f"/api/agent/tasks/{review_task['id']}")
        payload = completed.json()
        assert payload["status"] == "completed"
        parsed = json.loads(payload["output"])
        assert parsed["confidence"] == expected_review_output["confidence"]
        assert parsed["estimated_value"] == expected_review_output["estimated_value"]
        assert parsed["actual_value"] == expected_review_output["actual_value"]


@pytest.mark.asyncio
async def test_execute_task_fails_on_cost_limit_and_posts_friction(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("RUNTIME_COST_PER_SECOND", "1.0")
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            json.dumps({"confidence": 0.91, "estimated_value": 9.0, "actual_value": 7.0}),
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 6, "provider_request_id": "req_cost", "response_id": "resp_cost"},
        ),
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Run quick task",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute?max_cost_usd=0.001")
        assert res.status_code == 200

        fetched = await client.get(f"/api/agent/tasks/{task['id']}")
        assert fetched.status_code == 200
        payload = fetched.json()
        assert payload["status"] == "failed"
        assert "Execution budget exceeded" in payload["output"]

        friction = await client.get("/api/friction/events?status=open")
        assert friction.status_code == 200
        friction_rows = friction.json()
        assert any(
            row.get("block_type") == "cost_overrun" and row.get("notes", "").startswith("Execution budget exceeded")
            for row in friction_rows
        )


@pytest.mark.asyncio
async def test_execution_updates_cost_value_targets(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("RUNTIME_COST_PER_SECOND", "0.001")
    monkeypatch.setenv("FRICTION_EVENTS_PATH", str(tmp_path / "friction_events.jsonl"))
    monkeypatch.setenv("GOVERNANCE_DATABASE_URL", f"sqlite:///{tmp_path / 'governance.db'}")
    monkeypatch.setenv("IDEA_REGISTRY_DATABASE_URL", f"sqlite:///{tmp_path / 'ideas.db'}")
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service

    expected_idea_output = {
        "confidence": 0.85,
        "estimated_value": 42.0,
        "actual_value": 12.0,
        "estimated_cost": 3.0,
    }
    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            json.dumps(expected_idea_output),
            {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
            {"elapsed_ms": 4, "provider_request_id": "req_val", "response_id": "resp_val"},
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ideas = await client.get("/api/ideas")
        assert ideas.status_code == 200
        idea_id = ideas.json()["ideas"][0]["id"]

        spec_payload = {
            "spec_id": f"spec-{uuid4().hex[:8]}",
            "title": "Execution attribution test spec",
            "summary": "Spec for validating execution attribution plumbing.",
            "potential_value": 30.0,
            "estimated_cost": 2.5,
            "actual_value": 0.0,
            "actual_cost": 0.0,
            "idea_id": idea_id,
        }
        created_spec = await client.post("/api/spec-registry", json=spec_payload)
        assert created_spec.status_code == 201
        spec_id = created_spec.json()["spec_id"]

        task = agent_service.create_task(
            AgentTaskCreate(
                direction="Update value records with metrics",
                task_type=TaskType.IMPL,
                context={
                    "executor": "openclaw",
                    "model_override": "openrouter/free",
                    "idea_id": idea_id,
                    "spec_id": spec_id,
                },
            )
        )

        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 200

        completed = await client.get(f"/api/agent/tasks/{task['id']}")
        completed_payload = completed.json()
        assert completed_payload["status"] == "completed"
        parsed = json.loads(completed_payload["output"])
        assert parsed == expected_idea_output

        updated_idea = await client.get(f"/api/ideas/{idea_id}")
        assert updated_idea.status_code == 200
        idea_row = updated_idea.json()
        assert idea_row["actual_value"] == expected_idea_output["actual_value"]
        assert idea_row["confidence"] == expected_idea_output["confidence"]
        assert idea_row["potential_value"] == expected_idea_output["estimated_value"]
        assert idea_row["estimated_cost"] == expected_idea_output["estimated_cost"]

        updated_spec = await client.get(f"/api/spec-registry/{spec_id}")
        assert updated_spec.status_code == 200
        spec_row = updated_spec.json()
        assert spec_row["actual_value"] == expected_idea_output["actual_value"]
        assert spec_row["estimated_cost"] == expected_idea_output["estimated_cost"]
        assert spec_row["potential_value"] == expected_idea_output["estimated_value"]


def test_seed_next_tasks_falls_back_from_specs_to_idea_roi(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import agent_execution_service as _execution_service  # noqa: F401
    from app.services import agent_task_continuation_service
    from app.services import inventory_service

    monkeypatch.setattr(
        inventory_service,
        "sync_spec_implementation_gap_tasks",
        lambda create_task, limit=200: {"result": "no_spec_implementation_gaps", "created_tasks": []},
    )
    monkeypatch.setattr(
        inventory_service,
        "next_highest_roi_task_from_answered_questions",
        lambda create_task: {"result": "task_suggested", "created_task": {"id": "task_roi_1"}},
    )
    fallback_called = {"value": False}

    def _flow_fallback(*, create_task: bool, runtime_window_seconds: int) -> dict:
        fallback_called["value"] = True
        return {"result": "task_suggested", "created_task": {"id": "task_flow_1"}}

    monkeypatch.setattr(inventory_service, "next_unblock_task_from_flow", _flow_fallback)

    task_ids, source = agent_task_continuation_service._seed_next_tasks()
    assert task_ids == ["task_roi_1"]
    assert source == "idea_answered_question_roi"
    assert fallback_called["value"] is False


@pytest.mark.asyncio
async def test_execute_endpoint_continuous_autofill_schedules_followup_when_queue_empty(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_CONTINUOUS_AUTOFILL", "1")
    monkeypatch.setenv("AGENT_CONTINUOUS_AUTOFILL_AUTORUN", "1")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service
    from app.services import agent_task_continuation_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 5, "provider_request_id": "req_followup", "response_id": "resp_followup"},
        ),
    )
    monkeypatch.setattr(
        agent_task_continuation_service,
        "_seed_next_tasks",
        lambda: (["task_followup_from_spec"], "spec_implementation_gap"),
    )

    scheduled: list[str] = []

    def _capture_schedule(**kwargs: object) -> None:
        scheduled.append(str(kwargs.get("task_id") or ""))

    monkeypatch.setattr(agent_task_continuation_service, "_schedule_followup_execution", _capture_schedule)

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Complete and continue",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 200

    assert scheduled == ["task_followup_from_spec"]


@pytest.mark.asyncio
async def test_execute_endpoint_continuous_autofill_skips_when_open_tasks_exist(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("AGENT_CONTINUOUS_AUTOFILL", "1")
    monkeypatch.setenv("AGENT_CONTINUOUS_AUTOFILL_AUTORUN", "1")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_service
    from app.services import agent_task_continuation_service

    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 4, "provider_request_id": "req_no_seed", "response_id": "resp_no_seed"},
        ),
    )

    seed_called = {"count": 0}

    def _seed_counter() -> tuple[list[str], str]:
        seed_called["count"] += 1
        return (["task_should_not_run"], "spec_implementation_gap")

    monkeypatch.setattr(agent_task_continuation_service, "_seed_next_tasks", _seed_counter)
    scheduled: list[str] = []
    monkeypatch.setattr(
        agent_task_continuation_service,
        "_schedule_followup_execution",
        lambda **kwargs: scheduled.append(str(kwargs.get("task_id") or "")),
    )

    # Keep one pending task in queue so autofill should not trigger.
    agent_service.create_task(
        AgentTaskCreate(
            direction="Remain pending",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Complete without spawning follow-up",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 200

    assert seed_called["count"] == 0
    assert scheduled == []


@pytest.mark.asyncio
async def test_execute_endpoint_emits_lifecycle_runtime_events(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_hooks, agent_execution_service

    agent_execution_hooks.clear_lifecycle_hooks()
    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 5, "provider_request_id": "req_lifecycle", "response_id": "resp_lifecycle"},
        ),
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Emit lifecycle events",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert res.status_code == 200

        fetched = await client.get(f"/api/agent/tasks/{task['id']}")
        assert fetched.status_code == 200
        assert fetched.json()["status"] == "completed"

        events = await client.get("/api/runtime/events?limit=200")
        assert events.status_code == 200
        rows = events.json()
        lifecycle_rows = [
            row
            for row in rows
            if str(row.get("metadata", {}).get("tracking_kind")) == "agent_task_lifecycle"
            and str(row.get("metadata", {}).get("task_id")) == task["id"]
        ]
        lifecycle_events = {str(row.get("metadata", {}).get("lifecycle_event") or "") for row in lifecycle_rows}
        assert "claimed" in lifecycle_events
        assert "execution_started" in lifecycle_events
        assert "finalized" in lifecycle_events
        finalized = [
            row
            for row in lifecycle_rows
            if str(row.get("metadata", {}).get("lifecycle_event") or "") == "finalized"
        ]
        assert finalized
        assert str(finalized[0].get("metadata", {}).get("task_status") or "") == "completed"


@pytest.mark.asyncio
async def test_execute_endpoint_hook_error_listener_does_not_fail_execution(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_hooks, agent_execution_service

    hook_calls = {"count": 0}

    def _failing_hook(_payload: dict[str, object]) -> None:
        hook_calls["count"] += 1
        raise RuntimeError("synthetic hook failure")

    agent_execution_hooks.clear_lifecycle_hooks()
    agent_execution_hooks.register_lifecycle_hook(_failing_hook)
    try:
        monkeypatch.setattr(
            agent_execution_service,
            "chat_completion",
            lambda **_: (
                "ok",
                {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                {"elapsed_ms": 4, "provider_request_id": "req_hook_err", "response_id": "resp_hook_err"},
            ),
        )

        task = agent_service.create_task(
            AgentTaskCreate(
                direction="Run even when lifecycle listener fails",
                task_type=TaskType.IMPL,
                context={"executor": "openclaw", "model_override": "openrouter/free"},
            )
        )

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post(f"/api/agent/tasks/{task['id']}/execute")
            assert res.status_code == 200

            fetched = await client.get(f"/api/agent/tasks/{task['id']}")
            assert fetched.status_code == 200
            payload = fetched.json()
            assert payload["status"] == "completed"
            assert payload["output"] == "ok"

        assert hook_calls["count"] >= 2
    finally:
        agent_execution_hooks.clear_lifecycle_hooks()


@pytest.mark.asyncio
async def test_execute_endpoint_lifecycle_summary_endpoint_reports_recent_events(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("AGENT_LIFECYCLE_SUBSCRIBERS", "runtime")
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_hooks, agent_execution_service

    agent_execution_hooks.clear_lifecycle_hooks()
    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 3, "provider_request_id": "req_summary", "response_id": "resp_summary"},
        ),
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Emit lifecycle summary test",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        executed = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert executed.status_code == 200

        summary = await client.get("/api/agent/lifecycle/summary?seconds=3600&limit=200")
        assert summary.status_code == 200
        payload = summary.json()
        assert payload.get("window_seconds") == 3600
        assert payload.get("subscribers", {}).get("runtime") is True
        assert int(payload.get("total_events") or 0) >= 3
        by_event = payload.get("by_event") or {}
        assert int(by_event.get("claimed") or 0) >= 1
        assert int(by_event.get("execution_started") or 0) >= 1
        assert int(by_event.get("finalized") or 0) >= 1
        recent = payload.get("recent") or []
        assert recent
        assert any(str(row.get("task_id") or "") == task["id"] for row in recent)


@pytest.mark.asyncio
async def test_execute_endpoint_lifecycle_summary_respects_disabled_runtime_subscriber(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("AGENT_LIFECYCLE_SUBSCRIBERS", "none")
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_hooks, agent_execution_service

    agent_execution_hooks.clear_lifecycle_hooks()
    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 3, "provider_request_id": "req_no_runtime", "response_id": "resp_no_runtime"},
        ),
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Disable runtime lifecycle subscriber",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        executed = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert executed.status_code == 200

        summary = await client.get("/api/agent/lifecycle/summary?seconds=3600&limit=200")
        assert summary.status_code == 200
        payload = summary.json()
        assert payload.get("subscribers", {}).get("runtime") is False
        assert int(payload.get("total_events") or 0) == 0

        events = await client.get("/api/runtime/events?limit=200")
        assert events.status_code == 200
        lifecycle_rows = [
            row
            for row in events.json()
            if str(row.get("metadata", {}).get("tracking_kind")) == "agent_task_lifecycle"
            and str(row.get("metadata", {}).get("task_id")) == task["id"]
        ]
        assert lifecycle_rows == []


@pytest.mark.asyncio
async def test_execute_endpoint_lifecycle_jsonl_subscriber_writes_audit_lines_and_summary(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("AGENT_LIFECYCLE_SUBSCRIBERS", "jsonl")
    audit_path = tmp_path / "agent_lifecycle_events.jsonl"
    monkeypatch.setenv("AGENT_LIFECYCLE_JSONL_PATH", str(audit_path))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_hooks, agent_execution_service

    agent_execution_hooks.clear_lifecycle_hooks()
    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 3, "provider_request_id": "req_jsonl", "response_id": "resp_jsonl"},
        ),
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Write lifecycle jsonl audit lines",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        executed = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert executed.status_code == 200

        summary = await client.get("/api/agent/lifecycle/summary?seconds=3600&limit=200")
        assert summary.status_code == 200
        payload = summary.json()
        assert payload.get("subscribers", {}).get("runtime") is False
        assert payload.get("subscribers", {}).get("jsonl") is True
        assert str(payload.get("summary_source") or "") == "jsonl"
        assert int(payload.get("total_events") or 0) >= 3
        by_event = payload.get("by_event") or {}
        assert int(by_event.get("claimed") or 0) >= 1
        assert int(by_event.get("execution_started") or 0) >= 1
        assert int(by_event.get("finalized") or 0) >= 1

        events = await client.get("/api/runtime/events?limit=200")
        assert events.status_code == 200
        lifecycle_rows = [
            row
            for row in events.json()
            if str(row.get("metadata", {}).get("tracking_kind")) == "agent_task_lifecycle"
            and str(row.get("metadata", {}).get("task_id")) == task["id"]
        ]
        assert lifecycle_rows == []

    assert Path(audit_path).exists()
    lines = [line for line in Path(audit_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) >= 3
    parsed = [json.loads(line) for line in lines]
    task_rows = [row for row in parsed if str(row.get("task_id") or "") == task["id"]]
    assert task_rows
    lifecycle_events = {str(row.get("event") or "") for row in task_rows}
    assert "claimed" in lifecycle_events
    assert "execution_started" in lifecycle_events
    assert "finalized" in lifecycle_events


@pytest.mark.asyncio
async def test_execute_endpoint_lifecycle_source_override_uses_jsonl_when_requested(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("AGENT_LIFECYCLE_SUBSCRIBERS", "all")
    audit_path = tmp_path / "agent_lifecycle_events.jsonl"
    monkeypatch.setenv("AGENT_LIFECYCLE_JSONL_PATH", str(audit_path))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_hooks, agent_execution_service

    agent_execution_hooks.clear_lifecycle_hooks()
    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 3, "provider_request_id": "req_source", "response_id": "resp_source"},
        ),
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Force summary source override",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "openrouter/free"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        executed = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert executed.status_code == 200

        auto_summary = await client.get("/api/agent/lifecycle/summary?seconds=3600&limit=200")
        assert auto_summary.status_code == 200
        auto_payload = auto_summary.json()
        assert str(auto_payload.get("summary_source") or "") == "runtime"
        assert auto_payload.get("subscribers", {}).get("runtime") is True
        assert auto_payload.get("subscribers", {}).get("jsonl") is True

        forced_summary = await client.get("/api/agent/lifecycle/summary?seconds=3600&limit=200&source=jsonl")
        assert forced_summary.status_code == 200
        forced_payload = forced_summary.json()
        assert str(forced_payload.get("summary_source") or "") == "jsonl"
        assert int(forced_payload.get("total_events") or 0) >= 3
        assert int((forced_payload.get("by_event") or {}).get("finalized") or 0) >= 1


@pytest.mark.asyncio
async def test_execute_endpoint_lifecycle_jsonl_retention_caps_audit_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("AGENT_LIFECYCLE_SUBSCRIBERS", "jsonl")
    monkeypatch.setenv("AGENT_LIFECYCLE_JSONL_MAX_LINES", "5")
    audit_path = tmp_path / "agent_lifecycle_events.jsonl"
    monkeypatch.setenv("AGENT_LIFECYCLE_JSONL_PATH", str(audit_path))
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_hooks, agent_execution_service

    agent_execution_hooks.clear_lifecycle_hooks()
    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 3, "provider_request_id": "req_retain", "response_id": "resp_retain"},
        ),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for idx in range(2):
            task = agent_service.create_task(
                AgentTaskCreate(
                    direction=f"Retention test task {idx}",
                    task_type=TaskType.IMPL,
                    context={"executor": "openclaw", "model_override": "openrouter/free"},
                )
            )
            executed = await client.post(f"/api/agent/tasks/{task['id']}/execute")
            assert executed.status_code == 200

        summary = await client.get("/api/agent/lifecycle/summary?seconds=3600&limit=200&source=jsonl")
        assert summary.status_code == 200
        payload = summary.json()
        assert str(payload.get("summary_source") or "") == "jsonl"
        assert int(payload.get("total_events") or 0) <= 5

    assert Path(audit_path).exists()
    lines = [line for line in Path(audit_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) <= 5


@pytest.mark.asyncio
async def test_execute_endpoint_lifecycle_guidance_warns_when_no_subscribers_enabled(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("AGENT_LIFECYCLE_SUBSCRIBERS", "none")
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        summary = await client.get("/api/agent/lifecycle/summary?seconds=3600&limit=200")
        assert summary.status_code == 200
        payload = summary.json()
        guidance = payload.get("guidance") or []
        assert guidance
        ids = {str(item.get("id") or "") for item in guidance if isinstance(item, dict)}
        assert "no_subscribers_enabled" in ids


@pytest.mark.asyncio
async def test_execute_endpoint_lifecycle_guidance_flags_paid_guard_blocks(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    monkeypatch.setenv("AGENT_LIFECYCLE_SUBSCRIBERS", "runtime")
    monkeypatch.delenv("AGENT_ALLOW_PAID_PROVIDERS", raising=False)
    monkeypatch.delenv("AGENT_EXECUTE_TOKEN", raising=False)
    _reset_agent_store()

    from app.services import agent_execution_hooks, agent_execution_service

    agent_execution_hooks.clear_lifecycle_hooks()
    monkeypatch.setattr(
        agent_execution_service,
        "chat_completion",
        lambda **_: (
            "ok",
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            {"elapsed_ms": 3, "provider_request_id": "req_guard", "response_id": "resp_guard"},
        ),
    )

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Trigger paid guard guidance",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw", "model_override": "gpt-5.3-codex"},
        )
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        executed = await client.post(f"/api/agent/tasks/{task['id']}/execute")
        assert executed.status_code == 200

        summary = await client.get("/api/agent/lifecycle/summary?seconds=3600&limit=200")
        assert summary.status_code == 200
        payload = summary.json()
        guidance = payload.get("guidance") or []
        assert guidance
        ids = {str(item.get("id") or "") for item in guidance if isinstance(item, dict)}
        assert "paid_guard_blocks" in ids
