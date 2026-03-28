"""Agent service: Open Responses interoperability (spec 109)."""

from __future__ import annotations

import pytest

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.models.schemas import NormalizedResponseCall
from app.services import agent_service
from app.services import provider_usage_service


def _reset_stores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    provider_usage_service.clear_normalized_open_responses_evidence()


def test_open_responses_route_two_providers_share_adapter_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same normalized interface for different executors without rewriting the task prompt text."""
    _reset_stores(monkeypatch)
    direction = "Implement feature with shared envelope"
    cursor_task = {
        "id": "t-cursor",
        "direction": direction,
        "model": "cursor/auto",
        "context": {
            "executor": "cursor",
            "route_decision": {
                "executor": "cursor",
                "provider": "cursor",
                "model": "cursor/auto",
                "request_schema": "open_responses_v1",
            },
        },
    }
    claude_task = {
        "id": "t-claude",
        "direction": direction,
        "model": "claude-sonnet-4-20250514",
        "context": {
            "executor": "claude",
            "route_decision": {
                "executor": "claude",
                "provider": "anthropic",
                "model": "claude-sonnet-4-20250514",
                "request_schema": "open_responses_v1",
            },
        },
    }
    a = agent_service.map_task_payload_to_open_responses(cursor_task)
    b = agent_service.map_task_payload_to_open_responses(claude_task)
    assert a["request_schema"] == "open_responses_v1"
    assert b["request_schema"] == "open_responses_v1"
    assert set(a.keys()) == set(b.keys())
    assert a["input"] == b["input"]


def test_open_responses_provider_evidence_persisted_on_task_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Route and model evidence is stored for each normalized call when output is recorded."""
    _reset_stores(monkeypatch)
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Ship interoperability layer",
            task_type=TaskType.IMPL,
        )
    )
    task_id = str(task["id"])
    agent_service.update_task(task_id, output="completed work", status=TaskStatus.COMPLETED)
    rows = provider_usage_service.list_normalized_open_responses_evidence()
    assert len(rows) >= 1
    last = rows[-1]
    assert last["task_id"] == task_id
    assert last["request_schema"] == "open_responses_v1"
    assert "route_decision" in last
    rd = last["route_decision"]
    assert isinstance(rd, dict)
    assert rd.get("request_schema") == "open_responses_v1"


def test_normalized_response_call_schema_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    _reset_stores(monkeypatch)
    m = NormalizedResponseCall(
        task_id="tid",
        provider="cursor",
        model="auto",
        request_schema="open_responses_v1",
        output_text="ok",
    )
    assert m.request_schema == "open_responses_v1"
