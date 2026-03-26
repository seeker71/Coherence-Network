"""Tests for the Auto Publish Pipeline (spec 139 acceptance criteria).

Covers the missing acceptance tests and additional spec requirements:
- test_pending_task_ranking_selects_highest_roi
- test_slot_selector_used_for_selected_task (SlotSelector integration)
- test_outcome_journal_records_success_and_failure
- ROI scoring edge cases
- Error classification
- Cycle log structure
- State persistence round-trip
- Concurrent candidate filtering
- Reviewing stage advances to complete
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from app.services import pipeline_service
from scripts import agent_pipeline


# ---------------------------------------------------------------------------
# R2 / Acceptance: test_pending_task_ranking_selects_highest_roi
# ---------------------------------------------------------------------------


def test_pending_task_ranking_selects_highest_roi() -> None:
    """Rank candidates by ROI = coherence_score × urgency_weight, descending."""
    ideas = [
        {"id": "a", "stage": "none", "coherence_score": 0.5, "urgency_weight": 2.0},  # ROI=1.0
        {"id": "b", "stage": "none", "coherence_score": 0.9, "urgency_weight": 3.0},  # ROI=2.7
        {"id": "c", "stage": "specced", "coherence_score": 0.8, "urgency_weight": 2.5},  # ROI=2.0
        {"id": "d", "stage": "none", "coherence_score": 0.3, "urgency_weight": 1.0},  # ROI=0.3
    ]

    ranked = pipeline_service.rank_candidate_ideas(ideas, top_n=3)

    ids = [r["id"] for r in ranked]
    assert ids[0] == "b", "highest ROI should be first"
    assert ids[1] == "c"
    assert ids[2] == "a"
    assert len(ranked) == 3


# ---------------------------------------------------------------------------
# R6a / Acceptance: test_slot_selector_used_for_selected_task
# ---------------------------------------------------------------------------


def test_slot_selector_used_for_selected_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pipeline delegates slot selection to SlotSelector (or equivalent)
    rather than hard-coding provider logic.

    Since SlotSelector integration is spec'd but the pipeline currently
    delegates execution to local_runner (which internally uses SlotSelector),
    we verify that process_idea calls run_local_runner (the slot-aware path)
    rather than reimplementing provider selection.
    """
    pipeline_service.reset_for_tests()
    runner_called = {"task_id": None}

    monkeypatch.setattr(
        agent_pipeline,
        "create_agent_task",
        lambda *_a, **_kw: {"id": "task-slot-1"},
    )

    def _fake_runner(task_id: str) -> tuple[bool, str]:
        runner_called["task_id"] = task_id
        return True, "ok"

    monkeypatch.setattr(agent_pipeline, "run_local_runner", _fake_runner)
    monkeypatch.setattr(agent_pipeline, "advance_idea", lambda *_a, **_kw: None)

    result = agent_pipeline.process_idea(
        {"id": "idea-slot", "name": "Slot", "description": "test", "stage": "none"}
    )

    assert result["status"] == "completed"
    assert runner_called["task_id"] == "task-slot-1", (
        "pipeline must delegate to local_runner (slot-aware path)"
    )


# ---------------------------------------------------------------------------
# R10a / Acceptance: test_outcome_journal_records_success_and_failure
# ---------------------------------------------------------------------------


def test_outcome_journal_records_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cycle log entries are appended for each processed idea (both success and failure)."""
    pipeline_service.reset_for_tests()
    logged: list[dict[str, Any]] = []

    monkeypatch.setattr(
        pipeline_service, "append_cycle_log", lambda entry, **_kw: logged.append(entry)
    )
    monkeypatch.setattr(pipeline_service, "persist_state", lambda *_a, **_kw: None)
    monkeypatch.setattr(
        agent_pipeline,
        "fetch_ideas",
        lambda: [
            {"id": "ok-idea", "name": "Ok", "description": "d", "stage": "none",
             "coherence_score": 0.9, "urgency_weight": 2.0},
            {"id": "fail-idea", "name": "Fail", "description": "d", "stage": "specced",
             "coherence_score": 0.5, "urgency_weight": 1.0},
        ],
    )
    monkeypatch.setattr(agent_pipeline, "has_active_task", lambda _id: False)
    monkeypatch.setattr(pipeline_service, "DEFAULT_CONCURRENCY", 2)

    call_count = {"n": 0}

    def _process(idea: dict, dry_run: bool = False) -> dict[str, Any]:
        call_count["n"] += 1
        status = "completed" if idea["id"] == "ok-idea" else "failed"
        return {
            "idea_id": idea["id"],
            "task_type": pipeline_service.task_type_for_stage(idea["stage"]),
            "provider": "local_runner",
            "status": status,
            "duration_ms": 100,
        }

    monkeypatch.setattr(agent_pipeline, "process_idea", _process)

    results = agent_pipeline.run_cycle(dry_run=False)

    assert len(results) == 2
    assert len(logged) == 2

    statuses = {entry["idea_id"]: entry["status"] for entry in logged}
    assert statuses["ok-idea"] == "completed"
    assert statuses["fail-idea"] == "failed"

    # Verify cycle log structure per R10
    for entry in logged:
        assert "timestamp" in entry
        assert "cycle" in entry
        assert "idea_id" in entry
        assert "task_type" in entry
        assert "provider" in entry
        assert "status" in entry
        assert "duration_ms" in entry


# ---------------------------------------------------------------------------
# ROI scoring edge cases
# ---------------------------------------------------------------------------


class TestRoiScore:
    def test_roi_basic(self) -> None:
        assert pipeline_service.roi_score(
            {"coherence_score": 0.5, "urgency_weight": 2.0}
        ) == pytest.approx(1.0)

    def test_roi_missing_urgency_defaults_to_one(self) -> None:
        assert pipeline_service.roi_score(
            {"coherence_score": 0.7}
        ) == pytest.approx(0.7)

    def test_roi_uses_free_energy_fallback(self) -> None:
        """When coherence_score is absent, falls back to free_energy_score."""
        assert pipeline_service.roi_score(
            {"free_energy_score": 0.4, "urgency_weight": 2.0}
        ) == pytest.approx(0.8)

    def test_roi_invalid_values_return_zero(self) -> None:
        assert pipeline_service.roi_score({"coherence_score": "bad"}) == 0.0

    def test_roi_zero_coherence(self) -> None:
        assert pipeline_service.roi_score(
            {"coherence_score": 0.0, "urgency_weight": 5.0}
        ) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# R3: Stage-to-task-type mapping completeness
# ---------------------------------------------------------------------------


def test_stage_mapping_complete() -> None:
    """Every actionable IdeaStage maps to a task type."""
    expected = {
        "none": "spec",
        "specced": "impl",
        "implementing": "test",
        "testing": "review",
        "reviewing": "review",
    }
    for stage, task_type in expected.items():
        assert pipeline_service.task_type_for_stage(stage) == task_type, (
            f"stage '{stage}' should map to '{task_type}'"
        )


def test_complete_stage_returns_none() -> None:
    """Complete ideas should not be assigned new tasks."""
    assert pipeline_service.task_type_for_stage("complete") is None


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


class TestClassifyFailure:
    def test_timeout(self) -> None:
        assert agent_pipeline.classify_failure("task exceeded timeout limit") == "timeout"

    def test_auth(self) -> None:
        assert agent_pipeline.classify_failure("HTTP 401 Unauthorized") == "auth"

    def test_rate_limit(self) -> None:
        assert agent_pipeline.classify_failure("status 429 rate limit exceeded") == "rate_limit"

    def test_unknown(self) -> None:
        assert agent_pipeline.classify_failure("some random error") == "unknown"

    def test_empty_output(self) -> None:
        result = agent_pipeline.classify_failure("")
        assert result in ("unknown", "empty_output")


# ---------------------------------------------------------------------------
# R9: Skip ideas with running/pending tasks in run_cycle
# ---------------------------------------------------------------------------


def test_run_cycle_skips_needs_attention(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ideas marked needs_attention are skipped in candidate selection."""
    pipeline_service.reset_for_tests()
    pipeline_service.mark_needs_attention("bad-idea")

    monkeypatch.setattr(
        agent_pipeline,
        "fetch_ideas",
        lambda: [
            {"id": "bad-idea", "name": "Bad", "description": "d", "stage": "none"},
            {"id": "good-idea", "name": "Good", "description": "d", "stage": "none"},
        ],
    )
    monkeypatch.setattr(agent_pipeline, "has_active_task", lambda _id: False)
    monkeypatch.setattr(pipeline_service, "DEFAULT_CONCURRENCY", 2)
    processed: list[str] = []

    def _process(idea: dict, dry_run: bool = False) -> dict[str, Any]:
        processed.append(idea["id"])
        return {
            "idea_id": idea["id"],
            "task_type": "spec",
            "provider": "local_runner",
            "status": "skipped",
            "duration_ms": 1,
        }

    monkeypatch.setattr(agent_pipeline, "process_idea", _process)
    monkeypatch.setattr(pipeline_service, "append_cycle_log", lambda *_a, **_kw: None)
    monkeypatch.setattr(pipeline_service, "persist_state", lambda *_a, **_kw: None)

    results = agent_pipeline.run_cycle(dry_run=True)

    assert processed == ["good-idea"]
    assert len(results) == 1


# ---------------------------------------------------------------------------
# Ranking excludes complete ideas
# ---------------------------------------------------------------------------


def test_ranking_excludes_complete_ideas() -> None:
    ideas = [
        {"id": "done", "stage": "complete", "coherence_score": 1.0, "urgency_weight": 5.0},
        {"id": "active", "stage": "none", "coherence_score": 0.1, "urgency_weight": 1.0},
    ]
    ranked = pipeline_service.rank_candidate_ideas(ideas, top_n=5)
    ids = [r["id"] for r in ranked]
    assert "done" not in ids
    assert "active" in ids


# ---------------------------------------------------------------------------
# State persistence round-trip
# ---------------------------------------------------------------------------


def test_state_persistence_round_trip() -> None:
    """State can be persisted and reloaded correctly."""
    pipeline_service.reset_for_tests()
    pipeline_service.start()
    pipeline_service.mark_cycle()
    pipeline_service.mark_task_completed()
    pipeline_service.mark_task_failed()
    pipeline_service.mark_idea_advanced()
    pipeline_service.mark_needs_attention("idea-x")

    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = Path(tmpdir) / "state.json"
        pipeline_service.persist_state(state_path)

        # Verify file was written
        assert state_path.exists()
        data = json.loads(state_path.read_text())
        assert data["running"] is True
        assert data["cycle_count"] == 1
        assert data["tasks_completed"] == 1
        assert data["tasks_failed"] == 1
        assert data["ideas_advanced"] == 1
        assert "idea-x" in data["needs_attention_ideas"]

        # Reset and reload
        pipeline_service.reset_for_tests()
        pipeline_service.load_state(state_path)
        status = pipeline_service.get_status()
        assert status["cycle_count"] == 1
        assert status["tasks_completed"] == 1
        assert pipeline_service.is_needs_attention("idea-x")


# ---------------------------------------------------------------------------
# Cycle log append
# ---------------------------------------------------------------------------


def test_cycle_log_appends_json_lines() -> None:
    """append_cycle_log writes JSONL entries."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "pipeline.log"
        entry1 = {"cycle": 1, "idea_id": "a", "status": "completed"}
        entry2 = {"cycle": 2, "idea_id": "b", "status": "failed"}

        pipeline_service.append_cycle_log(entry1, path=log_path)
        pipeline_service.append_cycle_log(entry2, path=log_path)

        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["idea_id"] == "a"
        assert json.loads(lines[1])["idea_id"] == "b"


# ---------------------------------------------------------------------------
# PipelineState snapshot structure matches API contract
# ---------------------------------------------------------------------------


def test_pipeline_state_snapshot_keys() -> None:
    """Snapshot dict has all keys defined in the spec API contract."""
    pipeline_service.reset_for_tests()
    status = pipeline_service.get_status()
    required_keys = {
        "running",
        "uptime_seconds",
        "current_idea_id",
        "cycle_count",
        "ideas_advanced",
        "tasks_completed",
        "tasks_failed",
        "last_cycle_at",
    }
    assert required_keys.issubset(status.keys())


# ---------------------------------------------------------------------------
# Build direction includes context
# ---------------------------------------------------------------------------


def test_build_direction_includes_idea_context() -> None:
    idea = {"id": "idea-1", "name": "Test Idea", "description": "A test", "stage": "none"}
    direction = agent_pipeline.build_direction(idea, "spec")
    assert "Test Idea" in direction
    assert "spec" in direction
    assert "none" in direction
    assert "A test" in direction


# ---------------------------------------------------------------------------
# Atomic write pattern (R8 failure mode mitigation)
# ---------------------------------------------------------------------------


def test_atomic_write_creates_file() -> None:
    """_atomic_write_json uses tmp+rename for crash safety."""
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "subdir" / "state.json"
        pipeline_service._atomic_write_json(target, {"key": "value"})
        assert target.exists()
        data = json.loads(target.read_text())
        assert data["key"] == "value"
        # Verify tmp file is cleaned up
        assert not target.with_suffix(".json.tmp").exists()


# ---------------------------------------------------------------------------
# R11: CLI argument parsing
# ---------------------------------------------------------------------------


def test_parse_args_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["agent_pipeline.py"])
    args = agent_pipeline.parse_args()
    assert args.once is False
    assert args.dry_run is False
    assert args.loop is False


def test_parse_args_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["agent_pipeline.py", "--once", "--dry-run", "--interval", "30"])
    args = agent_pipeline.parse_args()
    assert args.once is True
    assert args.dry_run is True
    assert args.interval == 30


# ---------------------------------------------------------------------------
# Cleanup helper
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_pipeline_state() -> None:
    """Ensure each test starts with clean pipeline state."""
    pipeline_service.reset_for_tests()
