"""Flow-centric enforcement gate tests.

Validates that wasteful task execution is prevented by enforcement gates
in create_task (file scope, task card, direction size, hygiene catch-all)
and by the context hygiene scoring system.
"""

from __future__ import annotations

import pytest

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_service
from app.services.context_hygiene_service import summarize_task_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0


def _full_task_card(
    *,
    files: list[str] | None = None,
    goal: str = "implement feature",
    done_when: str = "tests pass",
    commands: list[str] | None = None,
    constraints: str = "no scope creep",
) -> dict:
    card: dict = {}
    if goal:
        card["goal"] = goal
    if files is not None:
        card["files_allowed"] = files
    if done_when:
        card["done_when"] = done_when
    card["commands"] = commands if commands is not None else ["pytest"]
    if constraints:
        card["constraints"] = constraints
    return card


# ===========================================================================
# File Scope Gates (3 tests)
# ===========================================================================

def test_broad_file_scope_soft_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task with 25 files -> NEEDS_DECISION with BROAD_FILE_SCOPE."""
    _reset(monkeypatch)
    files = [f"api/app/services/mod_{i}.py" for i in range(25)]
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Refactor across many modules",
            task_type=TaskType.IMPL,
            context={
                "task_card": _full_task_card(files=files),
                "files_allowed": files,
            },
        )
    )
    assert task["status"] == TaskStatus.NEEDS_DECISION
    prompt = task.get("decision_prompt") or ""
    assert "BROAD_FILE_SCOPE" in prompt
    assert "25 files" in prompt


def test_file_scope_hard_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task with 45 files -> FAILED with FILE_SCOPE_HARD_LIMIT."""
    _reset(monkeypatch)
    files = [f"api/app/services/mod_{i}.py" for i in range(45)]
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Massive refactor across entire codebase",
            task_type=TaskType.IMPL,
            context={
                "task_card": _full_task_card(files=files),
                "files_allowed": files,
            },
        )
    )
    assert task["status"] == TaskStatus.FAILED
    output = task.get("output") or ""
    assert "FILE_SCOPE_HARD_LIMIT" in output
    assert "45 files" in output


def test_file_scope_under_limit_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task with 10 files -> PENDING (no gate fires)."""
    _reset(monkeypatch)
    files = [f"api/app/services/mod_{i}.py" for i in range(10)]
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Small refactor across a few modules",
            task_type=TaskType.IMPL,
            context={
                "task_card": _full_task_card(files=files),
                "files_allowed": files,
            },
        )
    )
    assert task["status"] == TaskStatus.PENDING


# ===========================================================================
# Task Card Validation (3 tests)
# ===========================================================================

def test_weak_task_card_soft_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task with only goal (score <0.4) -> NEEDS_DECISION with WEAK_TASK_CARD."""
    _reset(monkeypatch)
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Do something vague",
            task_type=TaskType.IMPL,
            context={"task_card": {"goal": "vague"}},
        )
    )
    assert task["status"] == TaskStatus.NEEDS_DECISION
    prompt = task.get("decision_prompt") or ""
    assert "WEAK_TASK_CARD" in prompt


def test_bare_task_without_context_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task with empty context={} -> PENDING (no gate fires)."""
    _reset(monkeypatch)
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Simple bare task",
            task_type=TaskType.IMPL,
            context={},
        )
    )
    assert task["status"] == TaskStatus.PENDING
    assert task.get("decision_prompt") is None


def test_complete_task_card_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Task with all 5 fields (goal, files_allowed, done_when, commands, constraints) -> PENDING."""
    _reset(monkeypatch)
    files = ["api/app/main.py"]
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Add health check endpoint",
            task_type=TaskType.IMPL,
            context={
                "task_card": {
                    "goal": "Add /health endpoint",
                    "files_allowed": files,
                    "done_when": "tests pass",
                    "commands": ["pytest"],
                    "constraints": "none",
                },
                "files_allowed": files,
            },
        )
    )
    assert task["status"] == TaskStatus.PENDING
    assert task.get("decision_prompt") is None


# ===========================================================================
# Direction Size Gate (2 tests)
# ===========================================================================

def test_oversized_direction_soft_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """3500-char direction -> NEEDS_DECISION with OVERSIZED_DIRECTION."""
    _reset(monkeypatch)
    long_direction = "x" * 3500
    task = agent_service.create_task(
        AgentTaskCreate(
            direction=long_direction,
            task_type=TaskType.IMPL,
            context={
                "task_card": _full_task_card(files=["api/app/main.py"]),
                "files_allowed": ["api/app/main.py"],
            },
        )
    )
    assert task["status"] == TaskStatus.NEEDS_DECISION
    prompt = task.get("decision_prompt") or ""
    assert "OVERSIZED_DIRECTION" in prompt
    assert "3500 chars" in prompt


def test_normal_direction_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """500-char direction -> PENDING (no gate fires)."""
    _reset(monkeypatch)
    direction = "y" * 500
    task = agent_service.create_task(
        AgentTaskCreate(
            direction=direction,
            task_type=TaskType.IMPL,
            context={
                "task_card": _full_task_card(files=["api/app/main.py"]),
                "files_allowed": ["api/app/main.py"],
            },
        )
    )
    assert task["status"] == TaskStatus.PENDING


# ===========================================================================
# Context Hygiene Scoring (4 tests)
# ===========================================================================

def test_hygiene_score_clean_task() -> None:
    """Minimal task -> score close to 100."""
    summary = summarize_task_context({
        "direction": "Short task",
        "context": {},
        "output": "",
    })
    assert summary["score"] >= 90


def test_hygiene_flags_long_direction() -> None:
    """Direction >1200 chars -> 'long_direction' flag."""
    summary = summarize_task_context({
        "direction": "x" * 1500,
        "context": {},
        "output": "",
    })
    assert any(f["id"] == "long_direction" for f in summary["flags"])


def test_hygiene_flags_broad_file_scope() -> None:
    """>12 files -> 'broad_file_scope' flag."""
    files = [f"file_{i}.py" for i in range(15)]
    summary = summarize_task_context({
        "direction": "task",
        "context": {"files_allowed": files},
        "output": "",
    })
    assert any(f["id"] == "broad_file_scope" for f in summary["flags"])


def test_hygiene_flags_output_bloat() -> None:
    """Output >2000 chars -> 'output_bloat' flag."""
    summary = summarize_task_context({
        "direction": "task",
        "context": {},
        "output": "z" * 2500,
    })
    assert any(f["id"] == "output_bloat" for f in summary["flags"])


# ===========================================================================
# Catch-all Gate (2 tests)
# ===========================================================================

def test_low_hygiene_score_catchall(monkeypatch: pytest.MonkeyPatch) -> None:
    """Enough flags to push score <40 without triggering specific gates -> not PENDING."""
    _reset(monkeypatch)
    # 19 files (under >20 soft gate), direction 2900 chars (under 3000 gate),
    # extra_notes padding inflates context past 12000 bytes -> large_context=high.
    # Penalties: long_direction=high(18) + large_context=high(18) +
    #   broad_file_scope=medium(10) + large_command_set=medium(10) +
    #   tool_overhead=medium(10) = 66 -> score ~34.
    files = [f"api/app/services/mod_{i}.py" for i in range(19)]
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="A" * 2900,
            task_type=TaskType.IMPL,
            context={
                "task_card": _full_task_card(files=files),
                "files_allowed": files,
                "commands": [f"cmd_{i}" for i in range(10)],
                "guard_agents": ["agent_a", "agent_b", "agent_c", "agent_d"],
                "extra_notes": "B" * 3000,
            },
        )
    )
    # Should not be PENDING -- the catch-all fires due to score < 40
    assert task["status"] in (TaskStatus.NEEDS_DECISION, TaskStatus.FAILED)


def test_clean_task_passes_all_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Well-formed task with few files and short direction -> PENDING, no decision_prompt."""
    _reset(monkeypatch)
    files = ["api/app/services/agent_service_crud.py", "api/app/models/agent.py"]
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Add a new field to the task model",
            task_type=TaskType.IMPL,
            context={
                "task_card": {
                    "goal": "Add new field",
                    "files_allowed": files,
                    "done_when": "tests pass",
                    "commands": ["pytest"],
                    "constraints": "none",
                },
                "files_allowed": files,
            },
        )
    )
    assert task["status"] == TaskStatus.PENDING
    assert task.get("decision_prompt") is None
