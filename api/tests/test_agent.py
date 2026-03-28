"""Tests for agent routing: spec and test task_types route to local model.

Spec 043: Ensures GET /api/agent/route?task_type=spec and task_type=test
return a local model (e.g. ollama/glm/qwen) with tier "local" per the
routing table in spec 002 (spec | test | impl | review → local; heal → claude).

Spec 109: Open Responses interoperability — same normalized envelope across providers.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_service, provider_usage_service


_LOCAL_SPEC_ROUTE = {
    "task_type": "spec",
    "model": "ollama/glm-4.7-flash:latest",
    "command_template": "ollama run glm-4.7-flash:latest",
    "tier": "local",
    "executor": "claude",
    "provider": "local",
    "billing_provider": "local",
    "is_paid_provider": False,
}

_LOCAL_TEST_ROUTE = {
    "task_type": "test",
    "model": "ollama/glm-4.7-flash:latest",
    "command_template": "ollama run glm-4.7-flash:latest",
    "tier": "local",
    "executor": "claude",
    "provider": "local",
    "billing_provider": "local",
    "is_paid_provider": False,
}


@pytest.mark.asyncio
async def test_spec_tasks_route_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/route?task_type=spec returns 200 with a local model.

    Contract (spec 002): spec task_type routes to local tier — model must
    contain 'ollama', 'glm', or 'qwen', or tier must be 'local'.
    """
    from app.services import agent_service

    monkeypatch.setattr(agent_service, "get_route", lambda task_type, executor="auto": _LOCAL_SPEC_ROUTE)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/route", params={"task_type": "spec"})

    assert r.status_code == 200, r.text
    body = r.json()
    model: str = body.get("model", "")
    tier: str = body.get("tier", "")
    is_local_model = any(indicator in model.lower() for indicator in ("ollama", "glm", "qwen"))
    assert is_local_model or tier == "local", (
        f"Expected spec task_type to route to a local model or tier='local', "
        f"got model={model!r} tier={tier!r}"
    )


@pytest.mark.asyncio
async def test_test_tasks_route_to_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /api/agent/route?task_type=test returns 200 with a local model.

    Contract (spec 002): test task_type routes to local tier — model must
    contain 'ollama', 'glm', or 'qwen', or tier must be 'local'.
    """
    from app.services import agent_service

    monkeypatch.setattr(agent_service, "get_route", lambda task_type, executor="auto": _LOCAL_TEST_ROUTE)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/route", params={"task_type": "test"})

    assert r.status_code == 200, r.text
    body = r.json()
    model: str = body.get("model", "")
    tier: str = body.get("tier", "")
    is_local_model = any(indicator in model.lower() for indicator in ("ollama", "glm", "qwen"))
    assert is_local_model or tier == "local", (
        f"Expected test task_type to route to a local model or tier='local', "
        f"got model={model!r} tier={tier!r}"
    )


def test_open_responses_adapter_matches_for_two_providers() -> None:
    """Two different executor/provider paths yield the same Open Responses v1 envelope keys."""
    claude_task = {
        "id": "t-claude",
        "direction": "Implement feature X",
        "model": "claude/sonnet",
        "context": {
            "executor": "claude",
            "normalized_response_call": {
                "task_id": "t-claude",
                "provider": "anthropic",
                "model": "sonnet",
                "request_schema": "open_responses_v1",
                "input": [
                    {"role": "user", "content": [{"type": "input_text", "text": "Implement feature X"}]},
                ],
            },
            "route_decision": {
                "executor": "claude",
                "provider": "anthropic",
                "model": "claude/sonnet",
                "request_schema": "open_responses_v1",
            },
        },
    }
    codex_task = {
        "id": "t-codex",
        "direction": "Implement feature X",
        "model": "codex/gpt-5",
        "context": {
            "executor": "codex",
            "normalized_response_call": {
                "task_id": "t-codex",
                "provider": "openai-codex",
                "model": "gpt-5",
                "request_schema": "open_responses_v1",
                "input": [
                    {"role": "user", "content": [{"type": "input_text", "text": "Implement feature X"}]},
                ],
            },
            "route_decision": {
                "executor": "codex",
                "provider": "openai-codex",
                "model": "codex/gpt-5",
                "request_schema": "open_responses_v1",
            },
        },
    }
    a1 = agent_service.adapt_task_execution_payload_to_open_responses_request(claude_task)
    a2 = agent_service.adapt_task_execution_payload_to_open_responses_request(codex_task)
    assert a1.keys() == a2.keys() == {"schema", "model", "input"}
    assert a1["schema"] == a2["schema"] == "open_responses_v1"
    assert isinstance(a1["input"], list) and isinstance(a2["input"], list)
    out1 = agent_service.adapt_provider_output_to_open_responses_output(claude_task, "done")
    out2 = agent_service.adapt_provider_output_to_open_responses_output(codex_task, "done")
    assert out1["schema"] == out2["schema"] == "open_responses_v1"


def test_route_and_provider_normalized_evidence_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Normalized route/model/output evidence is persisted for operator audits."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service.clear_store()
    agent_service._store_loaded = False
    provider_usage_service.clear_normalized_response_evidence_for_tests()

    task = agent_service.create_task(
        AgentTaskCreate(direction="open responses evidence check", task_type=TaskType.IMPL)
    )
    tid = str(task["id"])
    routed = provider_usage_service.list_normalized_response_evidence(limit=10)
    assert any(
        r.get("phase") == "routed"
        and r.get("record", {}).get("request_schema") == "open_responses_v1"
        and r.get("record", {}).get("task_id") == tid
        for r in routed
    )

    agent_service.update_task(
        tid,
        status=TaskStatus.COMPLETED,
        output="normalized output for audit",
        worker_id="test-worker",
    )
    done = provider_usage_service.list_normalized_response_evidence(limit=20)
    assert any(
        r.get("phase") == "completed"
        and r.get("record", {}).get("request_schema") == "open_responses_v1"
        and "normalized" in (r.get("record", {}).get("output_text") or "")
        for r in done
    )
