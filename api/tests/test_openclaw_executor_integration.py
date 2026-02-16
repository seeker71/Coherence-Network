from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskType
from app.services import agent_service


def test_create_task_supports_openclaw_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("OPENCLAW_MODEL", "openclaw/test-model")
    monkeypatch.setenv("OPENCLAW_COMMAND_TEMPLATE", 'openclaw run "{{direction}}" --model {{model}} --json')
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement openclaw executor support",
            task_type=TaskType.IMPL,
            context={"executor": "openclaw"},
        )
    )

    assert task["model"].startswith("openclaw/")
    assert task["tier"] == "openclaw"
    assert task["command"].startswith("openclaw run ")
    assert "--json" in task["command"]


@pytest.mark.asyncio
async def test_agent_route_endpoint_accepts_openclaw_executor() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agent/route", params={"task_type": "impl", "executor": "openclaw"})
        assert res.status_code == 200
        payload = res.json()
        assert payload["executor"] == "openclaw"
        assert payload["tier"] == "openclaw"
        assert str(payload["model"]).startswith("openclaw/")
        assert "openclaw" in str(payload["command_template"])
