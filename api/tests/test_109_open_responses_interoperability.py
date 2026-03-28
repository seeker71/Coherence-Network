"""Tests for Spec 109: Open Responses Interoperability Layer.

Verifies all acceptance criteria from specs/109-open-responses-interoperability-layer.md.
"""
from __future__ import annotations

import pytest

from app.models.agent import AgentTaskCreate, TaskType
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
# REQ-1: normalized_response_call key in task context
# ---------------------------------------------------------------------------

def test_normalized_response_call_present_on_task_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-1: Every AgentTask must include normalized_response_call in context."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Test open responses presence",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )

    context = task.get("context") or {}
    assert "normalized_response_call" in context, "normalized_response_call must be in task context"


# ---------------------------------------------------------------------------
# REQ-2: NormalizedResponseCall fields are all present
# ---------------------------------------------------------------------------

def test_normalized_response_call_has_all_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-2: normalized_response_call must have task_id, executor, provider, model, request_schema, input."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Check all fields present",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )

    nrc = (task.get("context") or {}).get("normalized_response_call") or {}
    required_fields = {"task_id", "executor", "provider", "model", "request_schema", "input"}
    for field in required_fields:
        assert field in nrc, f"Field '{field}' missing from normalized_response_call"


# ---------------------------------------------------------------------------
# REQ-3: request_schema == "open_responses_v1" for all executors
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("executor", ["cursor", "codex", "claude", "gemini"])
def test_request_schema_is_open_responses_v1_for_all_executors(
    executor: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """REQ-3: request_schema must be 'open_responses_v1' for all executors."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {
        "agent": "/usr/bin/agent",
        "codex": "/usr/bin/codex",
        "claude": "/usr/bin/claude",
        "gemini": "/usr/bin/gemini",
    }
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction=f"Test schema for {executor}",
            task_type=TaskType.IMPL,
            context={"executor": executor},
        )
    )

    nrc = (task.get("context") or {}).get("normalized_response_call") or {}
    assert nrc.get("request_schema") == "open_responses_v1"


# ---------------------------------------------------------------------------
# REQ-4: input list has exactly one user message with input_text
# ---------------------------------------------------------------------------

def test_input_list_has_exactly_one_item(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-4: input list must contain exactly one item with the correct structure."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Single input item test",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )

    nrc = (task.get("context") or {}).get("normalized_response_call") or {}
    input_list = nrc.get("input") or []
    assert len(input_list) == 1, "input must have exactly one item"
    item = input_list[0]
    assert item.get("role") == "user"
    content = item.get("content") or []
    assert len(content) == 1
    assert content[0].get("type") == "input_text"


# ---------------------------------------------------------------------------
# REQ-5: direction text is identical across executors for same task
# ---------------------------------------------------------------------------

def test_direction_text_identical_across_executors(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-5: The direction text must be identical across different executors for the same task.

    The NRC stores the full built direction (may include role preamble) but it must be the
    same for every executor since the build logic is executor-agnostic.
    """
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {
        "agent": "/usr/bin/agent",
        "codex": "/usr/bin/codex",
        "claude": "/usr/bin/claude",
    }
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    direction = "Normalize responses across all providers verbatim"

    cursor_task = agent_service.create_task(
        AgentTaskCreate(direction=direction, task_type=TaskType.IMPL, context={"executor": "cursor"})
    )
    codex_task = agent_service.create_task(
        AgentTaskCreate(direction=direction, task_type=TaskType.IMPL, context={"executor": "codex"})
    )
    claude_task = agent_service.create_task(
        AgentTaskCreate(direction=direction, task_type=TaskType.IMPL, context={"executor": "claude"})
    )

    def _get_text(task: dict) -> str:
        nrc = (task.get("context") or {}).get("normalized_response_call") or {}
        return (nrc.get("input") or [{}])[0].get("content", [{}])[0].get("text", "")

    cursor_text = _get_text(cursor_task)
    codex_text = _get_text(codex_task)
    claude_text = _get_text(claude_task)

    # All executors get the same built direction text (envelope does not rewrite per-provider)
    assert cursor_text == codex_text == claude_text, (
        f"Direction text must be identical across executors: "
        f"cursor={cursor_text!r}, codex={codex_text!r}, claude={claude_text!r}"
    )
    # The original direction must appear in the built text (no direction content is lost)
    assert direction in cursor_text, f"Original direction must appear in NRC text, got: {cursor_text!r}"


# ---------------------------------------------------------------------------
# REQ-6: model is stripped of provider prefix
# ---------------------------------------------------------------------------

def test_normalize_open_responses_model_strips_prefix() -> None:
    """REQ-6: Model prefix (e.g. 'cursor/gpt-4o') must be stripped to 'gpt-4o'."""
    assert normalize_open_responses_model("cursor/gpt-4o") == "gpt-4o"
    assert normalize_open_responses_model("codex/gpt-4o") == "gpt-4o"
    assert normalize_open_responses_model("gemini/gemini-2.0-flash") == "gemini-2.0-flash"


def test_normalize_open_responses_model_passes_through_bare() -> None:
    """REQ-6: Bare model names without prefix pass through unchanged."""
    assert normalize_open_responses_model("gpt-4o") == "gpt-4o"
    assert normalize_open_responses_model("claude-sonnet-4-6") == "claude-sonnet-4-6"


def test_normalize_open_responses_model_empty_string() -> None:
    """REQ-6 edge: empty model string passes through as empty."""
    assert normalize_open_responses_model("") == ""


def test_model_prefix_stripped_in_task_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-6: model in task normalized call strips provider prefix."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Strip prefix test",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )

    nrc = (task.get("context") or {}).get("normalized_response_call") or {}
    model = nrc.get("model", "")
    # Model in the normalized call must not contain "cursor/" prefix
    assert not model.startswith("cursor/"), f"Model should have prefix stripped, got: {model}"


# ---------------------------------------------------------------------------
# REQ-7: route_decision includes request_schema
# ---------------------------------------------------------------------------

def test_route_decision_has_request_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-7: route_decision dict must include request_schema == 'open_responses_v1'."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Route decision schema check",
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )

    context = task.get("context") or {}
    route_decision = context.get("route_decision") or {}
    assert route_decision.get("request_schema") == "open_responses_v1"


# ---------------------------------------------------------------------------
# REQ-9: direction is not altered (envelope-only, no prompt rewriting)
# ---------------------------------------------------------------------------

def test_direction_is_not_rewritten(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-9: The adapter must not alter the direction string."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    original_direction = "Exactly preserve this direction text: no modifications allowed!"

    task = agent_service.create_task(
        AgentTaskCreate(
            direction=original_direction,
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )

    # Task direction field is unchanged (the adapter does not modify the stored direction)
    assert task.get("direction") == original_direction

    # The NRC input text contains the original direction (may include role preamble)
    nrc = (task.get("context") or {}).get("normalized_response_call") or {}
    text = (nrc.get("input") or [{}])[0].get("content", [{}])[0].get("text", "")
    assert original_direction in text, (
        f"Original direction must appear in NRC text (envelope-only, no content rewriting). "
        f"Got: {text!r}"
    )


# ---------------------------------------------------------------------------
# REQ-10: invalid/unknown executor falls back to "claude" without raising
# ---------------------------------------------------------------------------

def test_unknown_executor_falls_back_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REQ-10: Invalid/unknown executor falls back without raising; NRC still has valid schema.

    The policy router resolves the unknown executor to a canonical executor (e.g. cursor or claude).
    The normalized call is still produced with request_schema == 'open_responses_v1'.
    """
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "claude": "/usr/bin/claude"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    # Must not raise
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Unknown executor fallback",
            task_type=TaskType.IMPL,
            context={"executor": "foobar_unknown_xyz"},
        )
    )

    nrc = (task.get("context") or {}).get("normalized_response_call") or {}
    # A canonical executor was selected (not the invalid "foobar_unknown_xyz")
    valid_executors = {"cursor", "codex", "claude", "gemini", "openrouter", "openclaw"}
    assert nrc.get("executor") in valid_executors, f"Expected canonical executor, got: {nrc.get('executor')!r}"
    assert nrc.get("request_schema") == "open_responses_v1"


def test_missing_executor_in_context_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-10: Missing executor in context defaults gracefully."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "claude": "/usr/bin/claude"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Edge test no executor",
            task_type=TaskType.IMPL,
            context={},
        )
    )

    context = task.get("context") or {}
    nrc = context.get("normalized_response_call") or {}
    assert nrc.get("request_schema") == "open_responses_v1"
    assert nrc.get("executor") in {"claude", "cursor", "codex", "gemini", "openrouter", "openclaw"}


# ---------------------------------------------------------------------------
# COMPAT: existing task fields are unaffected by normalization
# ---------------------------------------------------------------------------

def test_existing_task_fields_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
    """COMPAT: id, direction, task_type, status must be unaffected by normalization."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    direction = "Compatibility check direction"

    task = agent_service.create_task(
        AgentTaskCreate(
            direction=direction,
            task_type=TaskType.IMPL,
            context={"executor": "cursor"},
        )
    )

    assert task.get("id") is not None
    assert task.get("direction") == direction
    assert task.get("task_type") == TaskType.IMPL.value or task.get("task_type") == TaskType.IMPL
    assert task.get("status") is not None


# ---------------------------------------------------------------------------
# Unit tests for build_normalized_response_call() directly
# ---------------------------------------------------------------------------

def test_build_normalized_response_call_returns_correct_schema() -> None:
    """Direct unit test for build_normalized_response_call."""
    result = build_normalized_response_call(
        task_id="task_test_001",
        executor="cursor",
        provider="openai",
        model="cursor/gpt-4o",
        direction="Build envelope test",
    )

    assert result["task_id"] == "task_test_001"
    assert result["executor"] == "cursor"
    assert result["provider"] == "openai"
    assert result["model"] == "gpt-4o"  # prefix stripped
    assert result["request_schema"] == "open_responses_v1"
    assert len(result["input"]) == 1
    assert result["input"][0]["role"] == "user"
    assert result["input"][0]["content"][0]["type"] == "input_text"
    assert result["input"][0]["content"][0]["text"] == "Build envelope test"


def test_build_normalized_response_call_unknown_executor_falls_back() -> None:
    """REQ-10 unit: build_normalized_response_call falls back unknown executor to 'claude'."""
    result = build_normalized_response_call(
        task_id="task_test_002",
        executor="not_a_real_executor",
        provider="unknown",
        model="some-model",
        direction="Fallback executor test",
    )
    assert result["executor"] == "claude"
    assert result["request_schema"] == "open_responses_v1"


def test_build_normalized_response_call_preserves_direction_verbatim() -> None:
    """REQ-9 unit: build_normalized_response_call does not modify direction."""
    direction = "Verbatim: do not change me! $pecial ch@rs 123"
    result = build_normalized_response_call(
        task_id="task_test_003",
        executor="claude",
        provider="anthropic",
        model="claude-sonnet-4-6",
        direction=direction,
    )
    assert result["input"][0]["content"][0]["text"] == direction


def test_build_normalized_response_call_claude_provider_no_prefix() -> None:
    """REQ-6: Claude model without prefix passes through unchanged."""
    result = build_normalized_response_call(
        task_id="task_test_004",
        executor="claude",
        provider="anthropic",
        model="claude-sonnet-4-6",
        direction="Claude direct",
    )
    assert result["model"] == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Scenario 2 from spec: cross-executor normalization test (mirrors spec test)
# ---------------------------------------------------------------------------

def test_open_responses_normalization_shared_across_cursor_and_codex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scenario 2: Both cursor and codex produce identical input text and request_schema."""
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    _which = {"agent": "/usr/bin/agent", "codex": "/usr/bin/codex"}
    monkeypatch.setattr(agent_service_executor.shutil, "which", lambda name: _which.get(name))
    _reset_agent_store()

    direction = "Cross-provider normalization check"

    cursor_task = agent_service.create_task(
        AgentTaskCreate(direction=direction, task_type=TaskType.IMPL, context={"executor": "cursor"})
    )
    codex_task = agent_service.create_task(
        AgentTaskCreate(direction=direction, task_type=TaskType.IMPL, context={"executor": "codex"})
    )

    cursor_nrc = (cursor_task.get("context") or {}).get("normalized_response_call") or {}
    codex_nrc = (codex_task.get("context") or {}).get("normalized_response_call") or {}

    assert cursor_nrc["request_schema"] == "open_responses_v1"
    assert codex_nrc["request_schema"] == "open_responses_v1"
    assert cursor_nrc["input"][0]["content"][0]["type"] == "input_text"
    assert codex_nrc["input"][0]["content"][0]["type"] == "input_text"
    assert cursor_nrc["input"][0]["content"][0]["text"] == codex_nrc["input"][0]["content"][0]["text"]
    assert (cursor_task.get("context") or {}).get("route_decision", {}).get("request_schema") == "open_responses_v1"
    assert (codex_task.get("context") or {}).get("route_decision", {}).get("request_schema") == "open_responses_v1"
