"""Tests for the coherence-network-agent-pipeline spec
(specs/coherence-network-agent-pipeline.md).

Exercises pipeline_service state-machine: running flag, cycle counts,
task completed/failed counters, current_idea, needs_attention set.
The state is global+threadsafe; reset_for_tests is the body's idiom
for test isolation.
"""
from __future__ import annotations

import pytest

from app.services import pipeline_service


@pytest.fixture(autouse=True)
def reset_pipeline_state():
    pipeline_service.reset_for_tests()
    yield
    pipeline_service.reset_for_tests()


def test_pipeline_starts_in_stopped_state():
    status = pipeline_service.get_status()
    assert status["running"] is False
    assert status["current_idea_id"] is None


def test_start_marks_pipeline_running():
    pipeline_service.start()
    status = pipeline_service.get_status()
    assert status["running"] is True
    # uptime is in the snapshot (0+ once started); started_at isn't surfaced
    assert "uptime_seconds" in status


def test_stop_clears_current_idea():
    pipeline_service.start()
    pipeline_service.set_current_idea("idea-foo")
    pipeline_service.stop()
    status = pipeline_service.get_status()
    assert status["running"] is False
    assert status["current_idea_id"] is None


def test_mark_cycle_increments_counter():
    pipeline_service.mark_cycle()
    pipeline_service.mark_cycle()
    pipeline_service.mark_cycle()
    assert pipeline_service.get_status()["cycle_count"] == 3


def test_mark_task_completed_and_failed_count_independently():
    for _ in range(5):
        pipeline_service.mark_task_completed()
    for _ in range(2):
        pipeline_service.mark_task_failed()
    status = pipeline_service.get_status()
    assert status["tasks_completed"] == 5
    assert status["tasks_failed"] == 2


def test_mark_idea_advanced_increments_counter():
    pipeline_service.mark_idea_advanced()
    pipeline_service.mark_idea_advanced()
    assert pipeline_service.get_status()["ideas_advanced"] == 2


def test_needs_attention_set_is_idempotent():
    pipeline_service.mark_needs_attention("idea-1")
    pipeline_service.mark_needs_attention("idea-2")
    pipeline_service.mark_needs_attention("idea-1")  # duplicate
    assert pipeline_service.is_needs_attention("idea-1")
    assert pipeline_service.is_needs_attention("idea-2")
    assert not pipeline_service.is_needs_attention("idea-3")


def test_reset_for_tests_returns_to_clean_state():
    pipeline_service.start()
    pipeline_service.mark_cycle()
    pipeline_service.mark_task_completed()
    pipeline_service.mark_needs_attention("idea-x")
    pipeline_service.reset_for_tests()
    status = pipeline_service.get_status()
    assert status["running"] is False
    assert status["cycle_count"] == 0
    assert status["tasks_completed"] == 0
    assert not pipeline_service.is_needs_attention("idea-x")
