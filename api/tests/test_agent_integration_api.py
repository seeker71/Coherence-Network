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


def test_task_target_state_contract_is_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement contract-aware runner behavior",
            task_type=TaskType.IMPL,
            target_state="Runner task stores explicit contract fields",
            success_evidence=["contract saved", "target_state_observation"],
            abort_evidence=["fatal error", "abort now"],
            observation_window_sec=180,
        )
    )
    context = task.get("context") or {}
    assert context.get("target_state") == "Runner task stores explicit contract fields"
    assert context.get("success_evidence") == ["contract saved", "target_state_observation"]
    assert context.get("abort_evidence") == ["fatal error", "abort now"]
    assert context.get("observation_window_sec") == 180
    assert isinstance(context.get("target_state_contract"), dict)
