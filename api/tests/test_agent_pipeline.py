from __future__ import annotations

from typing import Any

import pytest

from app.services import pipeline_service
from scripts import agent_pipeline


def test_roi_ranking_selects_highest_score() -> None:
    ideas = [
        {"id": "low", "stage": "none", "coherence_score": 0.2, "urgency_weight": 1.0},
        {"id": "high", "stage": "none", "coherence_score": 0.6, "urgency_weight": 3.0},
        {"id": "mid", "stage": "none", "coherence_score": 0.7, "urgency_weight": 1.5},
    ]

    ranked = pipeline_service.rank_candidate_ideas(ideas, top_n=1)

    assert ranked[0]["id"] == "high"


def test_stage_to_task_type_mapping() -> None:
    assert pipeline_service.task_type_for_stage("none") == "spec"
    assert pipeline_service.task_type_for_stage("specced") == "impl"
    assert pipeline_service.task_type_for_stage("implementing") == "test"
    assert pipeline_service.task_type_for_stage("testing") == "review"


def test_skip_idea_with_running_task(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline_service.reset_for_tests()
    monkeypatch.setattr(pipeline_service, "DEFAULT_CONCURRENCY", 1)
    monkeypatch.setattr(
        agent_pipeline,
        "fetch_ideas",
        lambda: [
            {"id": "idea-running", "name": "running", "description": "x", "stage": "none"},
            {"id": "idea-free", "name": "free", "description": "y", "stage": "none"},
        ],
    )
    monkeypatch.setattr(agent_pipeline, "has_active_task", lambda idea_id: idea_id == "idea-running")
    seen: list[str] = []
    monkeypatch.setattr(
        agent_pipeline,
        "process_idea",
        lambda idea, dry_run=False: {
            "idea_id": seen.append(idea["id"]) or idea["id"],
            "task_type": "spec",
            "provider": "local_runner",
            "status": "skipped",
            "duration_ms": 1,
        },
    )
    monkeypatch.setattr(pipeline_service, "append_cycle_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pipeline_service, "persist_state", lambda *_args, **_kwargs: None)

    results = agent_pipeline.run_cycle(dry_run=True)

    assert [row["idea_id"] for row in results] == ["idea-free"]
    assert seen == ["idea-free"]


def test_retry_on_failure_with_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline_service.reset_for_tests()
    attempts = {"count": 0}
    sleeps: list[int] = []

    monkeypatch.setattr(agent_pipeline, "create_agent_task", lambda *_args, **_kwargs: {"id": f"task-{attempts['count']}"})

    def _run_local_runner(_task_id: str) -> tuple[bool, str]:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return False, "timeout"
        return True, "ok"

    monkeypatch.setattr(agent_pipeline, "run_local_runner", _run_local_runner)
    monkeypatch.setattr(agent_pipeline, "advance_idea", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(agent_pipeline.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = agent_pipeline.process_idea({"id": "idea-a", "name": "A", "description": "desc", "stage": "none"})

    assert result["status"] == "completed"
    assert attempts["count"] == 3
    assert sleeps == [2, 8]


def test_max_retries_marks_needs_attention(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline_service.reset_for_tests()
    sleeps: list[int] = []
    monkeypatch.setattr(agent_pipeline, "create_agent_task", lambda *_args, **_kwargs: {"id": "task-x"})
    monkeypatch.setattr(agent_pipeline, "run_local_runner", lambda *_args, **_kwargs: (False, "auth failed"))
    monkeypatch.setattr(agent_pipeline.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = agent_pipeline.process_idea({"id": "idea-z", "name": "Z", "description": "desc", "stage": "none"})

    assert result["status"] == "failed"
    assert result["error_classification"] == "auth"
    assert sleeps == [2, 8, 32]
    assert pipeline_service.is_needs_attention("idea-z") is True


def test_dry_run_no_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline_service.reset_for_tests()

    def _fail(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("should not execute side effects in dry-run")

    monkeypatch.setattr(agent_pipeline, "create_agent_task", _fail)
    monkeypatch.setattr(agent_pipeline, "run_local_runner", _fail)
    monkeypatch.setattr(agent_pipeline, "advance_idea", _fail)

    result = agent_pipeline.process_idea(
        {"id": "idea-d", "name": "Dry", "description": "desc", "stage": "none"},
        dry_run=True,
    )

    assert result["status"] == "skipped"
    assert result["task_type"] == "spec"


def test_once_mode_single_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline_service.reset_for_tests()
    calls = {"count": 0}
    monkeypatch.setattr(pipeline_service, "load_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(pipeline_service, "persist_state", lambda *_args, **_kwargs: None)

    def _run_cycle(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        calls["count"] += 1
        return []

    monkeypatch.setattr(agent_pipeline, "run_cycle", _run_cycle)

    code = agent_pipeline.run(once=True, dry_run=True, interval=1)

    assert code == 0
    assert calls["count"] == 1


def test_state_persistence_on_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline_service.reset_for_tests()
    snapshots: list[dict[str, Any]] = []
    monkeypatch.setattr(pipeline_service, "load_state", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        pipeline_service,
        "persist_state",
        lambda *_args, **_kwargs: snapshots.append(pipeline_service.get_status()),
    )

    def _run_cycle(*_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        agent_pipeline.STOP_REQUESTED = True
        return []

    monkeypatch.setattr(agent_pipeline, "run_cycle", _run_cycle)
    agent_pipeline.STOP_REQUESTED = False
    code = agent_pipeline.run(once=False, dry_run=True, interval=1)

    assert code == 0
    assert len(snapshots) >= 2
    assert snapshots[0]["running"] is True
    assert snapshots[-1]["running"] is False
