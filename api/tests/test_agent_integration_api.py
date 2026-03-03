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


def test_task_graph_state_contract_is_persisted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Validate graph state schema on creation",
            task_type=TaskType.IMPL,
        )
    )
    context = task.get("context") or {}
    graph_state = context.get("agent_graph_state") or {}
    schema = context.get("agent_graph_state_schema") or {}
    assert schema.get("schema_id") == "coherence_agent_graph_state_v1"
    assert set(schema.get("required_fields") or []) == {"task_id", "task_type", "phase", "direction"}
    assert graph_state.get("task_id") == task.get("id")
    assert graph_state.get("task_type") == "impl"
    assert graph_state.get("phase") == "queued"
    assert graph_state.get("direction") == "Validate graph state schema on creation"
    assert context.get("agent_graph_state_status") == "valid"
    assert context.get("agent_graph_state_errors") == []


def test_update_task_graph_state_validation_reports_actionable_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Validate graph state schema on update",
            task_type=TaskType.IMPL,
        )
    )
    updated = agent_service.update_task(
        str(task.get("id")),
        context={"agent_graph_state": {"task_id": "", "phase": "invalid", "attempt": -1}},
    )
    assert updated is not None
    context = updated.get("context") or {}
    errors = context.get("agent_graph_state_errors") or []
    assert context.get("agent_graph_state_status") == "invalid"
    assert "missing_or_invalid_required_field:task_id" in errors
    assert "missing_or_invalid_required_field:task_type" in errors
    assert "missing_or_invalid_required_field:direction" in errors
    assert "invalid_phase:invalid" in errors
    assert "invalid_attempt_non_negative_int_required" in errors
    assert "State schema validation failed" in str(context.get("agent_graph_state_last_error") or "")


def test_build_command_escapes_shell_sensitive_direction_tokens() -> None:
    command = agent_service._build_command(
        'Check `uname -a` and "$HOME" value',
        TaskType.IMPL,
        executor="openclaw",
    )

    assert "\\`uname -a\\`" in command
    assert '\\"\\$HOME\\"' in command
