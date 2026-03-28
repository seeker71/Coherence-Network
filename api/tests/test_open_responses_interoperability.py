"""Tests for Spec 109: Open Responses Interoperability Layer.

Verifies that:
- normalize_open_responses_model() strips executor prefixes correctly
- build_normalized_response_call() produces a valid v1 envelope
- Task creation embeds route_decision + normalized_response_call in context
- Two executors (cursor, codex) produce identical input structure
- Completion tracking persists request_schema == "open_responses_v1"
- GET /api/agent/tasks/{task_id} exposes route_decision and normalized_response_call
- Error handling returns correct HTTP status codes
- NormalizedResponseCall Pydantic model enforces schema contract
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.agent import AgentTaskCreate, NormalizedResponseCall, TaskType
from app.services import agent_service
from app.services import agent_service_executor
from app.services.agent_routing_service import (
    build_normalized_response_call,
    normalize_open_responses_model,
)


def _reset_agent_store() -> None:
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None


# ---------------------------------------------------------------------------
# Scenario 4: normalize_open_responses_model() — prefix stripping
# ---------------------------------------------------------------------------


def test_normalize_strips_cursor_prefix() -> None:
    assert normalize_open_responses_model("cursor/gpt-4o-mini") == "gpt-4o-mini"


def test_normalize_strips_codex_prefix() -> None:
    assert normalize_open_responses_model("codex/o3-mini") == "o3-mini"


def test_normalize_strips_gemini_prefix() -> None:
    assert normalize_open_responses_model("gemini/gemini-1.5-pro") == "gemini-1.5-pro"


def test_normalize_strips_openrouter_prefix_preserves_inner_slash() -> None:
    assert normalize_open_responses_model("openrouter/meta-llama/3") == "meta-llama/3"


def test_normalize_strips_claude_prefix() -> None:
    result = normalize_open_responses_model("claude/claude-sonnet-4-6")
    assert result == "claude-sonnet-4-6"


def test_normalize_does_not_strip_openai_prefix() -> None:
    """openai is a provider, not an executor — prefix must be preserved."""
    assert normalize_open_responses_model("openai/gpt-4o") == "openai/gpt-4o"


def test_normalize_passthrough_no_prefix() -> None:
    assert normalize_open_responses_model("claude-sonnet-4-6") == "claude-sonnet-4-6"


def test_normalize_empty_string_no_crash() -> None:
    assert normalize_open_responses_model("") == ""


def test_normalize_all_spec_cases() -> None:
    """Verify all cases from Scenario 4 in the spec."""
    cases = [
        ("cursor/gpt-4o-mini", "gpt-4o-mini"),
        ("codex/o3-mini", "o3-mini"),
        ("gemini/gemini-1.5-pro", "gemini-1.5-pro"),
        ("openrouter/meta-llama/3", "meta-llama/3"),
        ("openai/gpt-4o", "openai/gpt-4o"),
        ("claude-sonnet-4-6", "claude-sonnet-4-6"),
        ("", ""),
    ]
    for raw, expected in cases:
        result = normalize_open_responses_model(raw)
        assert result == expected, f"normalize_open_responses_model({raw!r}) = {result!r}, expected {expected!r}"


# ---------------------------------------------------------------------------
# build_normalized_response_call() unit tests
# ---------------------------------------------------------------------------


def test_build_normalized_response_call_schema_tag() -> None:
    call = build_normalized_response_call(
        task_id="task_001",
        executor="cursor",
        provider="openai",
        model="cursor/gpt-4o-mini",
        direction="Write a hello-world function",
    )
    assert call["request_schema"] == "open_responses_v1"


def test_build_normalized_response_call_strips_model_prefix() -> None:
    call = build_normalized_response_call(
        task_id="task_002",
        executor="codex",
        provider="openai",
        model="codex/o3-mini",
        direction="Implement feature X",
    )
    assert call["model"] == "o3-mini"


def test_build_normalized_response_call_input_structure() -> None:
    call = build_normalized_response_call(
        task_id="task_003",
        executor="cursor",
        provider="openai",
        model="cursor/gpt-4o-mini",
        direction="Check system health",
    )
    assert isinstance(call["input"], list)
    assert len(call["input"]) == 1
    item = call["input"][0]
    assert item["role"] == "user"
    assert isinstance(item["content"], list)
    assert len(item["content"]) == 1
    assert item["content"][0]["type"] == "input_text"
    assert item["content"][0]["text"] == "Check system health"


def test_build_normalized_response_call_task_id_and_executor() -> None:
    call = build_normalized_response_call(
        task_id="task_abc123",
        executor="cursor",
        provider="openai",
        model="cursor/gpt-4o-mini",
        direction="Do something",
    )
    assert call["task_id"] == "task_abc123"
    assert call["executor"] == "cursor"
    assert call["provider"] == "openai"


def test_build_normalized_response_call_two_executors_same_input() -> None:
    """cursor and codex must produce identical input content for the same direction."""
    direction = "Normalize responses across providers"
    cursor_call = build_normalized_response_call(
        task_id="t1",
        executor="cursor",
        provider="openai",
        model="cursor/gpt-4o-mini",
        direction=direction,
    )
    codex_call = build_normalized_response_call(
        task_id="t2",
        executor="codex",
        provider="openai",
        model="codex/o3-mini",
        direction=direction,
    )
    assert cursor_call["input"][0]["content"][0]["text"] == codex_call["input"][0]["content"][0]["text"]
    assert cursor_call["request_schema"] == codex_call["request_schema"] == "open_responses_v1"
    assert cursor_call["executor"] != codex_call["executor"]


# ---------------------------------------------------------------------------
# NormalizedResponseCall Pydantic model tests
# ---------------------------------------------------------------------------


def test_normalized_response_call_model_validates_correctly() -> None:
    nrc = NormalizedResponseCall(
        task_id="task_x",
        executor="cursor",
        provider="openai",
        model="gpt-4o-mini",
        request_schema="open_responses_v1",
        input=[{"role": "user", "content": [{"type": "input_text", "text": "hello"}]}],
    )
    assert nrc.request_schema == "open_responses_v1"
    assert nrc.model == "gpt-4o-mini"
    assert nrc.executor == "cursor"


def test_normalized_response_call_default_request_schema() -> None:
    nrc = NormalizedResponseCall(
        task_id="t",
        executor="codex",
        provider="openai",
        model="o3-mini",
        input=[],
    )
    assert nrc.request_schema == "open_responses_v1"


# ---------------------------------------------------------------------------
# Scenario 1 & 2: Task creation embeds route_decision + normalized_response_call
# ---------------------------------------------------------------------------


def test_task_creation_embeds_normalized_response_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Write a hello-world function",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )
    ctx = task.get("context") or {}
    nrc = ctx.get("normalized_response_call") or {}

    assert nrc.get("request_schema") == "open_responses_v1"
    assert nrc.get("executor") == "cursor"
    assert isinstance(nrc.get("input"), list)
    assert len(nrc["input"]) > 0
    assert nrc["input"][0]["role"] == "user"
    assert nrc["input"][0]["content"][0]["type"] == "input_text"


def test_task_creation_embeds_route_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement feature",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )
    ctx = task.get("context") or {}
    rd = ctx.get("route_decision") or {}

    assert rd.get("request_schema") == "open_responses_v1"
    assert rd.get("executor") == "cursor"
    assert "task_type" in rd
    assert "tier" in rd
    assert "model" in rd
    assert "provider" in rd
    assert "billing_provider" in rd
    assert "is_paid_provider" in rd


def test_route_decision_contains_all_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """route_decision block must contain all 8 required fields per spec."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(direction="Route check", task_type=TaskType.TEST)
    )
    rd = (task.get("context") or {}).get("route_decision") or {}

    required_fields = {"executor", "task_type", "tier", "model", "provider", "billing_provider", "is_paid_provider", "request_schema"}
    missing = required_fields - set(rd.keys())
    assert not missing, f"route_decision missing fields: {missing}"


# ---------------------------------------------------------------------------
# Scenario 2: Two executors produce identical input structure
# ---------------------------------------------------------------------------


def test_open_responses_normalization_shared_across_executors_service(monkeypatch: pytest.MonkeyPatch) -> None:
    """cursor and codex tasks carry identical input structure and request_schema."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    cursor_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement feature X",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )
    codex_task = agent_service.create_task(
        AgentTaskCreate(
            direction="Implement feature X",
            task_type=TaskType.IMPL,
            context={"executor": "codex"},
        )
    )

    cursor_nrc = (cursor_task.get("context") or {}).get("normalized_response_call") or {}
    codex_nrc = (codex_task.get("context") or {}).get("normalized_response_call") or {}

    assert cursor_nrc.get("request_schema") == "open_responses_v1"
    assert codex_nrc.get("request_schema") == "open_responses_v1"
    assert cursor_nrc["input"][0]["content"][0]["type"] == "input_text"
    assert codex_nrc["input"][0]["content"][0]["type"] == "input_text"
    assert cursor_nrc["input"][0]["content"][0]["text"] == codex_nrc["input"][0]["content"][0]["text"]
    # executors must differ
    assert cursor_nrc.get("executor") != codex_nrc.get("executor")
    # both route_decisions carry the schema tag
    assert (cursor_task.get("context") or {}).get("route_decision", {}).get("request_schema") == "open_responses_v1"
    assert (codex_task.get("context") or {}).get("route_decision", {}).get("request_schema") == "open_responses_v1"


def test_model_prefix_stripped_in_normalized_call(monkeypatch: pytest.MonkeyPatch) -> None:
    """When model_override has a provider prefix, normalized_response_call.model strips it."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Use explicit model",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )
    nrc = (task.get("context") or {}).get("normalized_response_call") or {}
    # model in normalized call should have no cursor/ prefix
    assert not nrc.get("model", "").startswith("cursor/")


# ---------------------------------------------------------------------------
# Scenario 3: Completion event persists normalized fields (via API)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_completion_tracking_persists_request_schema(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/agent/tasks",
            json={"direction": "Check system health", "task_type": "review"},
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["id"]

        running = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "test-worker"},
        )
        assert running.status_code == 200

        completed = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "completed", "output": "All checks pass."},
        )
        assert completed.status_code == 200

        # Verify completion event carries request_schema == "open_responses_v1"
        events = await client.get("/api/runtime/events", params={"limit": 200})
        assert events.status_code == 200
        rows = events.json()
        completion_events = [
            r for r in rows
            if r.get("endpoint") == "/tool:agent-task-completion"
            and (r.get("metadata") or {}).get("task_id") == task_id
        ]
        assert len(completion_events) == 1
        meta = completion_events[0]["metadata"]
        assert meta["request_schema"] == "open_responses_v1"
        assert meta.get("normalized_model")
        assert meta.get("normalized_provider")


@pytest.mark.asyncio
async def test_failed_task_completion_still_has_request_schema(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Normalization is unconditional — failed tasks also carry request_schema."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/agent/tasks",
            json={"direction": "Task that will fail", "task_type": "impl"},
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["id"]

        running = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "running", "worker_id": "test-worker"},
        )
        assert running.status_code == 200

        failed = await client.patch(
            f"/api/agent/tasks/{task_id}",
            json={"status": "failed", "output": "something went wrong"},
        )
        assert failed.status_code == 200

        events = await client.get("/api/runtime/events", params={"limit": 200})
        assert events.status_code == 200
        rows = events.json()
        completion_events = [
            r for r in rows
            if r.get("endpoint") == "/tool:agent-task-completion"
            and (r.get("metadata") or {}).get("task_id") == task_id
            and (r.get("metadata") or {}).get("task_final_status") == "failed"
        ]
        assert len(completion_events) == 1
        meta = completion_events[0]["metadata"]
        assert meta["request_schema"] == "open_responses_v1"


# ---------------------------------------------------------------------------
# Scenario 1 & GET context exposure via API
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_task_exposes_route_decision_and_normalized_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/agent/tasks",
            json={
                "direction": "Write a hello-world function",
                "task_type": "impl",
                "context": {"executor": "cursor"},
            },
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["id"]

        get_resp = await client.get(f"/api/agent/tasks/{task_id}")
        assert get_resp.status_code == 200
        ctx = get_resp.json().get("context") or {}

        rd = ctx.get("route_decision") or {}
        assert rd.get("request_schema") == "open_responses_v1"

        nrc = ctx.get("normalized_response_call") or {}
        assert nrc.get("request_schema") == "open_responses_v1"
        assert nrc.get("input", [{}])[0].get("role") == "user"
        assert nrc.get("input", [{}])[0].get("content", [{}])[0].get("type") == "input_text"


@pytest.mark.asyncio
async def test_unknown_executor_still_gets_schema_tag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown executor falls back to default; schema tag is always present."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _reset_agent_store()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        create_resp = await client.post(
            "/api/agent/tasks",
            json={
                "direction": "test",
                "task_type": "spec",
                "context": {"executor": "nonexistent"},
            },
        )
        assert create_resp.status_code == 201
        task_id = create_resp.json()["id"]

        get_resp = await client.get(f"/api/agent/tasks/{task_id}")
        assert get_resp.status_code == 200
        ctx = get_resp.json().get("context") or {}
        nrc = ctx.get("normalized_response_call") or {}
        assert nrc.get("request_schema") == "open_responses_v1"


# ---------------------------------------------------------------------------
# Scenario 5: Error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_direction_returns_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"task_type": "impl"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_empty_direction_returns_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"direction": "", "task_type": "impl"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_task_type_returns_422() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/agent/tasks",
            json={"direction": "Do something", "task_type": "invalid_type"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_nonexistent_task_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/agent/tasks/nonexistent_task_abc999")
        assert resp.status_code == 404
