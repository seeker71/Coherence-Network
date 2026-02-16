from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, TaskType
from app.services import agent_service


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


@pytest.mark.asyncio
async def test_agent_integration_endpoint_reports_role_coverage() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/integration")
    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "provider_readiness" in payload
    integration = payload["integration"]
    assert integration["unmapped_task_types"] == []
    assert integration["missing_profile_files"] == []
    assert integration["unbound_profiles"] == []
    assert "spec-guard" in integration["guard_bindings"]["review"]


def test_review_task_includes_primary_and_guard_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Review and validate implementation against spec",
            task_type=TaskType.REVIEW,
        )
    )
    context = task.get("context") or {}
    assert context.get("task_agent") == "reviewer"
    assert "spec-guard" in (context.get("guard_agents") or [])
    assert "Role agent: reviewer." in str(task.get("command"))
    assert "Guard agents: spec-guard." in str(task.get("command"))


def test_agent_integration_readiness_reports_missing_openclaw(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_REQUIRED_INTEGRATIONS", "codex,claude,openclaw")
    which_map = {"agent": "/usr/bin/agent", "claude": "/usr/bin/claude", "openclaw": None}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: which_map.get(name))

    payload = agent_service.get_agent_integration_status()
    readiness = payload["provider_readiness"]
    providers = readiness["providers"]

    assert providers["codex"]["ready"] is True
    assert providers["claude"]["ready"] is True
    assert providers["openclaw"]["ready"] is False
    assert "openclaw" in readiness["missing_required"]
    assert readiness["overall_ready"] is False
    assert payload["status"] == "needs_attention"


def test_agent_integration_readiness_reports_all_required_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_REQUIRED_INTEGRATIONS", "codex,claude,openclaw")
    which_map = {"agent": "/usr/bin/agent", "claude": "/usr/bin/claude", "openclaw": "/usr/bin/openclaw"}
    monkeypatch.setattr(agent_service.shutil, "which", lambda name: which_map.get(name))

    payload = agent_service.get_agent_integration_status()
    readiness = payload["provider_readiness"]
    providers = readiness["providers"]

    assert providers["codex"]["ready"] is True
    assert providers["claude"]["ready"] is True
    assert providers["openclaw"]["ready"] is True
    assert readiness["missing_required"] == []
    assert readiness["overall_ready"] is True
