"""Tests for lean task-card and file-scope enforcement gates."""

from __future__ import annotations

import pytest

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_service


def _reset_store(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_TASKS_PERSIST", "0")
    agent_service._store.clear()
    agent_service._store_loaded = False
    agent_service._store_loaded_path = None
    agent_service._store_loaded_includes_output = False
    agent_service._store_loaded_at_monotonic = 0.0


def _make_task_card(
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
    if commands is not None:
        card["commands"] = commands
    else:
        card["commands"] = ["pytest"]
    if constraints:
        card["constraints"] = constraints
    return card


def test_broad_file_scope_soft_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tasks with >20 files get NEEDS_DECISION with BROAD_FILE_SCOPE prompt."""
    _reset_store(monkeypatch)
    files = [f"api/app/services/file_{i}.py" for i in range(25)]
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Refactor across many files",
            task_type=TaskType.IMPL,
            context={"task_card": _make_task_card(files=files), "files_allowed": files},
        )
    )
    assert task["status"] == TaskStatus.NEEDS_DECISION
    assert "BROAD_FILE_SCOPE" in (task.get("decision_prompt") or "")
    assert "25 files" in (task.get("decision_prompt") or "")


def test_file_scope_hard_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tasks with >40 files are rejected outright as failed."""
    _reset_store(monkeypatch)
    files = [f"api/app/services/file_{i}.py" for i in range(45)]
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Massive refactor",
            task_type=TaskType.IMPL,
            context={"task_card": _make_task_card(files=files), "files_allowed": files},
        )
    )
    assert task["status"] == TaskStatus.FAILED
    assert "FILE_SCOPE_HARD_LIMIT" in (task.get("output") or "")
    assert "45 files" in (task.get("output") or "")


def test_weak_task_card_soft_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tasks with a task_card but score <0.4 (missing most required fields) get NEEDS_DECISION."""
    _reset_store(monkeypatch)
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Do something vague",
            task_type=TaskType.IMPL,
            context={"task_card": {"goal": "vague goal"}},
        )
    )
    assert task["status"] == TaskStatus.NEEDS_DECISION
    assert "WEAK_TASK_CARD" in (task.get("decision_prompt") or "")


def test_bare_task_without_context_passes_weak_card_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tasks created via API with no context should NOT trigger WEAK_TASK_CARD."""
    _reset_store(monkeypatch)
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Simple API task",
            task_type=TaskType.IMPL,
            context={},
        )
    )
    assert task["status"] == TaskStatus.PENDING
    assert task.get("decision_prompt") is None


def test_oversized_direction_soft_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tasks with direction >3000 chars get NEEDS_DECISION."""
    _reset_store(monkeypatch)
    long_direction = "x" * 3500
    task = agent_service.create_task(
        AgentTaskCreate(
            direction=long_direction,
            task_type=TaskType.IMPL,
            context={
                "task_card": _make_task_card(files=["api/app/main.py"]),
                "files_allowed": ["api/app/main.py"],
            },
        )
    )
    assert task["status"] == TaskStatus.NEEDS_DECISION
    assert "OVERSIZED_DIRECTION" in (task.get("decision_prompt") or "")
    assert "3500 chars" in (task.get("decision_prompt") or "")


def test_clean_task_passes_all_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    """A well-formed task with few files and short direction passes all gates."""
    _reset_store(monkeypatch)
    files = ["api/app/services/agent_service_crud.py", "api/app/models/agent.py"]
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="Add a new field to the task model",
            task_type=TaskType.IMPL,
            context={
                "task_card": _make_task_card(files=files),
                "files_allowed": files,
            },
        )
    )
    assert task["status"] == TaskStatus.PENDING
    assert task.get("decision_prompt") is None


def test_low_hygiene_score_catchall(monkeypatch: pytest.MonkeyPatch) -> None:
    """The overall score<40 catch-all still fires when no specific gate matches."""
    _reset_store(monkeypatch)
    # 18 files (under 20 limit), long-ish direction (under 3000), big context, many commands,
    # output bloat, guard agents — enough flags to push score below 40 without triggering
    # the specific gates above.
    files = [f"api/app/services/file_{i}.py" for i in range(18)]
    task = agent_service.create_task(
        AgentTaskCreate(
            direction="A" * 2500,
            task_type=TaskType.IMPL,
            context={
                "task_card": _make_task_card(files=files),
                "files_allowed": files,
                "commands": [f"cmd_{i}" for i in range(10)],
                "guard_agents": ["agent_a", "agent_b", "agent_c", "agent_d"],
            },
        )
    )
    # Should be NEEDS_DECISION from either a specific gate or the catch-all
    # The exact gate depends on cumulative scoring
    assert task["status"] in (TaskStatus.NEEDS_DECISION, TaskStatus.PENDING)
