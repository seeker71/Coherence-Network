"""Acceptance tests for spec 109 — Open Responses interoperability layer."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, NormalizedResponseCall, TaskType
from app.services import agent_service
from app.services import agent_service_executor
from app.services import agent_routing_service as routing


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


def test_normalized_response_call_model_enforces_open_responses_v1_envelope() -> None:
    """Data model: provider-agnostic envelope matches NormalizedResponseCall schema."""
    payload = {
        "task_id": "t-109",
        "executor": "claude",
        "provider": "anthropic",
        "model": "claude-3-5-sonnet-20241022",
        "request_schema": "open_responses_v1",
        "input": [
            {"role": "user", "content": [{"type": "input_text", "text": "Hello"}]},
        ],
    }
    call = NormalizedResponseCall.model_validate(payload)
    assert call.request_schema == "open_responses_v1"
    assert call.task_id == "t-109"
    assert call.provider == "anthropic"
    assert call.model == "claude-3-5-sonnet-20241022"
    assert call.input[0]["content"][0]["type"] == "input_text"


def test_build_normalized_response_call_maps_direction_to_input_text_without_rewrite() -> None:
    """Adapter maps execution direction into Open Responses input_text; no provider-specific prompt keys."""
    envelope = routing.build_normalized_response_call(
        task_id="abc",
        executor="codex",
        provider="openai-codex",
        model="codex/gpt-4o-mini",
        direction="Ship the feature",
    )
    assert envelope["request_schema"] == "open_responses_v1"
    assert envelope["task_id"] == "abc"
    assert envelope["executor"] == "codex"
    assert envelope["provider"] == "openai-codex"
    assert envelope["model"] == "gpt-4o-mini"
    assert envelope["input"][0]["role"] == "user"
    assert envelope["input"][0]["content"][0]["type"] == "input_text"
    assert envelope["input"][0]["content"][0]["text"] == "Ship the feature"


def test_normalize_open_responses_model_strips_executor_prefix() -> None:
    assert routing.normalize_open_responses_model("codex/gpt-4o-mini") == "gpt-4o-mini"
    assert routing.normalize_open_responses_model("cursor/auto") == "auto"
    assert routing.normalize_open_responses_model("bare-model") == "bare-model"


def test_two_executors_share_identical_normalized_prompt_and_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """At least two providers route through the same normalized interface without task-level rewrites."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    direction = "Interoperability check"
    cursor_task = agent_service.create_task(
        AgentTaskCreate(
            direction=direction,
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )
    codex_task = agent_service.create_task(
        AgentTaskCreate(
            direction=direction,
            task_type=TaskType.IMPL,
            context={"executor": "codex"},
        )
    )
    c0 = (cursor_task.get("context") or {}).get("normalized_response_call") or {}
    c1 = (codex_task.get("context") or {}).get("normalized_response_call") or {}
    assert c0.get("request_schema") == "open_responses_v1"
    assert c1.get("request_schema") == "open_responses_v1"
    assert c0["input"] == c1["input"]
    rd0 = (cursor_task.get("context") or {}).get("route_decision") or {}
    rd1 = (codex_task.get("context") or {}).get("route_decision") or {}
    assert rd0.get("request_schema") == "open_responses_v1"
    assert rd1.get("request_schema") == "open_responses_v1"
    assert rd0.get("model")
    assert rd1.get("model")


@pytest.mark.asyncio
async def test_task_get_exposes_route_and_normalized_call_for_audit(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Operator can read persisted route + model evidence on the task record."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _which = {"agent": "/usr/bin/agent", "aider": "/usr/bin/aider", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/agent/tasks",
            json={
                "direction": "Audit normalized call",
                "task_type": "impl",
                "context": {"executor": "cursor"},
            },
        )
        assert created.status_code == 201
        task_id = created.json()["id"]

        fetched = await client.get(f"/api/agent/tasks/{task_id}")
        assert fetched.status_code == 200
        body = fetched.json()
        ctx = body.get("context") or {}
        nrc = ctx.get("normalized_response_call") or {}
        rd = ctx.get("route_decision") or {}
        assert nrc.get("request_schema") == "open_responses_v1"
        assert nrc.get("task_id") == task_id
        assert nrc.get("model")
        assert nrc.get("provider")
        assert rd.get("request_schema") == "open_responses_v1"
        assert rd.get("model")


@pytest.mark.asyncio
async def test_completion_event_persists_schema_and_normalized_route_evidence(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runtime completion metadata carries request_schema and normalized model/provider for audits."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        task = await client.post(
            "/api/agent/tasks",
            json={"direction": "Emit audit metadata", "task_type": "impl"},
        )
        assert task.status_code == 201
        task_id = task.json()["id"]

        await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "openai-codex"},
        )
        await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "completed", "output": "ok"},
        )

        events = await client.get("/api/runtime/events", params={"limit": 200})
        assert events.status_code == 200
        rows = events.json()
        completion_events = [
            row
            for row in rows
            if row.get("source") == "worker"
            and row.get("endpoint") == "/tool:agent-task-completion"
            and (row.get("metadata") or {}).get("task_id") == task_id
        ]
        assert len(completion_events) == 1
        meta = completion_events[0]["metadata"]
        assert meta.get("request_schema") == "open_responses_v1"
        assert meta.get("normalized_model")
        assert meta.get("normalized_provider")
