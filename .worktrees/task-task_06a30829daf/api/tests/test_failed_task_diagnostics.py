"""Tests for failed-task diagnostics completeness contract (spec 113)."""

from __future__ import annotations


def test_classify_error_timeout() -> None:
    from app.services.failed_task_diagnostics_service import classify_error

    summary, category = classify_error("Task exceeded timeout after 300 seconds")
    assert category == "timeout"
    assert len(summary) > 0

    summary2, category2 = classify_error("Error: timed out waiting for response")
    assert category2 == "timeout"


def test_classify_error_crash() -> None:
    from app.services.failed_task_diagnostics_service import classify_error

    summary, category = classify_error("Traceback (most recent call last):\n  File 'x.py'\nRuntimeError: boom")
    assert category == "executor_crash"

    summary2, category2 = classify_error("Process exited with code 137 (SIGKILL)")
    assert category2 == "executor_crash"

    summary3, category3 = classify_error("fatal error: segfault in worker")
    assert category3 == "executor_crash"


def test_classify_error_provider() -> None:
    from app.services.failed_task_diagnostics_service import classify_error

    summary, category = classify_error("HTTP 429 Too Many Requests: rate limit exceeded")
    assert category == "provider_error"

    summary2, category2 = classify_error("billing quota exhausted for openai account")
    assert category2 == "provider_error"

    summary3, category3 = classify_error("Error: API rate_limit reached, retry after 60s")
    assert category3 == "provider_error"


def test_classify_error_validation() -> None:
    from app.services.failed_task_diagnostics_service import classify_error

    summary, category = classify_error("AssertionError: expected 200, got 404")
    assert category == "validation_failure"

    summary2, category2 = classify_error("ValidationError: field 'name' is required")
    assert category2 == "validation_failure"


def test_classify_error_unknown() -> None:
    from app.services.failed_task_diagnostics_service import classify_error

    summary, category = classify_error("something went wrong")
    assert category == "unknown"
    assert len(summary) > 0

    # None input
    summary2, category2 = classify_error(None)
    assert category2 == "unknown"
    assert summary2 == "No diagnostics provided"

    # Empty string
    summary3, category3 = classify_error("")
    assert category3 == "unknown"
    assert summary3 == "No diagnostics provided"


def test_auto_populate_on_missing_diagnostics() -> None:
    from app.services.failed_task_diagnostics_service import ensure_diagnostics

    # When error_summary is already provided, don't overwrite
    result = ensure_diagnostics(
        error_summary="Manual error note",
        error_category="timeout",
        output="some output",
    )
    assert result["error_summary"] == "Manual error note"
    assert result["error_category"] == "timeout"

    # When error_summary is None but output has signal, auto-classify
    result2 = ensure_diagnostics(
        error_summary=None,
        error_category=None,
        output="Traceback (most recent call last):\nKeyError: 'missing'",
    )
    assert result2["error_summary"] is not None
    assert result2["error_category"] == "executor_crash"

    # When both are None, fallback
    result3 = ensure_diagnostics(
        error_summary=None,
        error_category=None,
        output=None,
    )
    assert result3["error_summary"] == "No diagnostics provided"
    assert result3["error_category"] == "unknown"


def test_diagnostics_completeness_shape() -> None:
    from app.services.failed_task_diagnostics_service import compute_diagnostics_completeness

    # Simulate task records
    tasks = [
        {"status": "failed", "error_summary": "timeout hit", "error_category": "timeout"},
        {"status": "failed", "error_summary": None, "error_category": None},
        {"status": "failed", "error_summary": "crash", "error_category": "executor_crash"},
        {"status": "failed", "error_summary": "No diagnostics provided", "error_category": "unknown"},
        {"status": "completed", "error_summary": None, "error_category": None},
    ]
    result = compute_diagnostics_completeness(tasks)

    assert result["total_failed"] == 4
    assert result["with_diagnostics"] == 2  # sentinel doesn't count
    assert result["missing_pct"] == 50.0
    assert "by_category" in result
    assert result["by_category"]["timeout"] == 1
    assert result["by_category"]["executor_crash"] == 1


def test_model_fields_present() -> None:
    from app.models.agent import AgentTask, AgentTaskListItem, AgentTaskUpdate

    # AgentTask should have error_summary and error_category
    task_fields = AgentTask.model_fields
    assert "error_summary" in task_fields
    assert "error_category" in task_fields

    # AgentTaskListItem should have error_summary and error_category
    list_fields = AgentTaskListItem.model_fields
    assert "error_summary" in list_fields
    assert "error_category" in list_fields

    # AgentTaskUpdate should accept error_summary and error_category
    update_fields = AgentTaskUpdate.model_fields
    assert "error_summary" in update_fields
    assert "error_category" in update_fields
