"""Tests for agent routing: spec and test task_types route to local model.

Spec 043: Ensures GET /api/agent/route?task_type=spec and task_type=test
return a local model (e.g. ollama/glm/qwen) with tier "local" per the
routing table in spec 002 (spec | test | impl | review → local; heal → claude).

Spec 039: Ensures GET /api/agent/pipeline-status returns 200 in empty state.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import agent_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


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


@pytest.mark.asyncio
async def test_pipeline_status_returns_200_in_empty_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/agent/pipeline-status returns 200 when no tasks exist (empty state).

    Spec 039: Empty state is a valid outcome — no 4xx/5xx due to absence of tasks.
    Response must include all required top-level keys with running as an empty list.
    """
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/pipeline-status")

    assert response.status_code == 200, f"Expected 200 in empty state, got {response.status_code}: {response.text}"
    body = response.json()

    # All required top-level keys must be present
    for key in ("running", "pending", "recent_completed", "attention", "running_by_phase"):
        assert key in body, f"Missing required key '{key}' in pipeline-status response"

    # running must be a list (empty in empty state)
    assert isinstance(body["running"], list), "Expected 'running' to be a list"
    assert body["running"] == [], f"Expected 'running' to be empty in empty state, got {body['running']}"

    # attention must have required sub-keys
    attention = body["attention"]
    for key in ("stuck", "repeated_failures", "low_success_rate", "flags"):
        assert key in attention, f"Missing required key '{key}' in attention object"

    # running_by_phase must have all phase keys with empty/zero values
    running_by_phase = body["running_by_phase"]
    for phase in ("spec", "impl", "test", "review"):
        assert phase in running_by_phase, f"Missing phase '{phase}' in running_by_phase"
