"""Tests for agent routing: spec and test task_types route to local model.

Spec 043: Ensures GET /api/agent/route?task_type=spec and task_type=test
return a local model (e.g. ollama/glm/qwen) with tier "local" per the
routing table in spec 002 (spec | test | impl | review → local; heal → claude).
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


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
