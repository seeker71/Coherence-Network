"""Spec 113: Failed-Task Diagnostics Completeness Contract — acceptance tests (task task_6e23d770446).

Covers acceptance tests listed in specs/113-failed-task-diagnostics-contract.md.
"""

from __future__ import annotations


def test_113_classify_error_timeout() -> None:
    from app.services.failed_task_diagnostics_service import classify_error

    summary, category = classify_error("Task exceeded timeout after 300 seconds")
    assert category == "timeout"
    assert len(summary) > 0

    _summary2, category2 = classify_error("Error: timed out waiting for response")
    assert category2 == "timeout"


def test_113_classify_error_crash() -> None:
    from app.services.failed_task_diagnostics_service import classify_error

    _summary, category = classify_error(
        "Traceback (most recent call last):\n  File 'x.py'\nRuntimeError: boom"
    )
    assert category == "executor_crash"

    _summary2, category2 = classify_error("Process exited with code 137 (SIGKILL)")
    assert category2 == "executor_crash"

    _summary3, category3 = classify_error("fatal error: segfault in worker")
    assert category3 == "executor_crash"


def test_113_classify_error_provider() -> None:
    from app.services.failed_task_diagnostics_service import classify_error

    _summary, category = classify_error("HTTP 429 Too Many Requests: rate limit exceeded")
    assert category == "provider_error"

    _summary2, category2 = classify_error("billing quota exhausted for openai account")
    assert category2 == "provider_error"

    _summary3, category3 = classify_error("Error: API rate_limit reached, retry after 60s")
    assert category3 == "provider_error"


def test_113_classify_error_validation() -> None:
    from app.services.failed_task_diagnostics_service import classify_error

    _summary, category = classify_error("AssertionError: expected 200, got 404")
    assert category == "validation_failure"

    _summary2, category2 = classify_error("ValidationError: field 'name' is required")
    assert category2 == "validation_failure"


def test_113_classify_error_unknown() -> None:
    from app.services.failed_task_diagnostics_service import classify_error

    summary, category = classify_error("something went wrong")
    assert category == "unknown"
    assert len(summary) > 0

    summary2, category2 = classify_error(None)
    assert category2 == "unknown"
    assert summary2 == "No diagnostics provided"

    summary3, category3 = classify_error("")
    assert category3 == "unknown"
    assert summary3 == "No diagnostics provided"


def test_113_auto_populate_on_missing_diagnostics() -> None:
    from app.services.failed_task_diagnostics_service import ensure_diagnostics

    result = ensure_diagnostics(
        error_summary="Manual error note",
        error_category="timeout",
        output="some output",
    )
    assert result["error_summary"] == "Manual error note"
    assert result["error_category"] == "timeout"

    result2 = ensure_diagnostics(
        error_summary=None,
        error_category=None,
        output="Traceback (most recent call last):\nKeyError: 'missing'",
    )
    assert result2["error_summary"] is not None
    assert result2["error_category"] == "executor_crash"

    result3 = ensure_diagnostics(
        error_summary=None,
        error_category=None,
        output=None,
    )
    assert result3["error_summary"] == "No diagnostics provided"
    assert result3["error_category"] == "unknown"


def test_113_diagnostics_completeness_shape() -> None:
    from app.services.failed_task_diagnostics_service import compute_diagnostics_completeness

    tasks = [
        {"status": "failed", "error_summary": "timeout hit", "error_category": "timeout"},
        {"status": "failed", "error_summary": None, "error_category": None},
        {"status": "failed", "error_summary": "crash", "error_category": "executor_crash"},
        {"status": "failed", "error_summary": "No diagnostics provided", "error_category": "unknown"},
        {"status": "completed", "error_summary": None, "error_category": None},
    ]
    result = compute_diagnostics_completeness(tasks)

    assert result["total_failed"] == 4
    assert result["with_diagnostics"] == 2
    assert result["missing_pct"] == 50.0
    assert "by_category" in result
    assert result["by_category"]["timeout"] == 1
    assert result["by_category"]["executor_crash"] == 1
    assert set(result.keys()) == {"total_failed", "with_diagnostics", "missing_pct", "by_category"}


def test_113_model_fields_present() -> None:
    from app.models.agent import AgentTask, AgentTaskListItem, AgentTaskUpdate

    task_fields = AgentTask.model_fields
    assert "error_summary" in task_fields
    assert "error_category" in task_fields

    list_fields = AgentTaskListItem.model_fields
    assert "error_summary" in list_fields
    assert "error_category" in list_fields

    update_fields = AgentTaskUpdate.model_fields
    assert "error_summary" in update_fields
    assert "error_category" in update_fields


def test_113_agent_task_record_has_error_columns() -> None:
    from app.services.agent_task_store_service import AgentTaskRecord

    assert hasattr(AgentTaskRecord, "error_summary")
    assert hasattr(AgentTaskRecord, "error_category")


def test_113_valid_categories_five_defined() -> None:
    from app.services.failed_task_diagnostics_service import VALID_CATEGORIES

    assert VALID_CATEGORIES == {
        "executor_crash",
        "timeout",
        "validation_failure",
        "provider_error",
        "unknown",
    }
