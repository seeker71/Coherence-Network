"""Tests for failed_task_diagnostics_service (spec: failed-task-diagnostics-contract).

Three pure functions:
  classify_error(output)            -> (summary, category)
  ensure_diagnostics(sum, cat, out) -> dict with summary + category
  compute_diagnostics_completeness(tasks) -> stats dict

Covers the spec's named requirements:
  - classify_error correctly categorizes timeout, crash, provider, validation
  - ensure_diagnostics preserves provided summary; auto-classifies otherwise
  - completeness counts failed tasks with/without diagnostics, by category
  - error_category must be one of the 5 defined categories
  - backward compatible: empty/null inputs return "unknown" gracefully
"""
from __future__ import annotations

from app.services.failed_task_diagnostics_service import (
    VALID_CATEGORIES,
    classify_error,
    compute_diagnostics_completeness,
    ensure_diagnostics,
)


# ---------------------------------------------------------------------------
# classify_error
# ---------------------------------------------------------------------------


def test_classify_error_empty_input_is_unknown():
    """Empty / None / whitespace-only input → ("No diagnostics provided", "unknown")."""
    for inp in [None, "", "   ", "\n\n"]:
        summary, category = classify_error(inp)
        assert summary == "No diagnostics provided"
        assert category == "unknown"


def test_classify_error_timeout_patterns():
    """Timeout keywords → category "timeout"."""
    for output in [
        "Task timed out after 300s",
        "deadline exceeded",
        "Operation exceeded timeout limit",
        "TimeoutError: connection timeout",
    ]:
        _, category = classify_error(output)
        assert category == "timeout", f"expected timeout for {output!r}, got {category}"


def test_classify_error_crash_patterns():
    """Crash / traceback / signal patterns → category "executor_crash"."""
    for output in [
        "Traceback (most recent call last):\n  File ...",
        "Exit code 139 (SIGSEGV)",
        "RuntimeError: something blew up",
        "Process crashed with signal 9",
        "Fatal error: out of memory",
        "MemoryError: cannot allocate",
    ]:
        _, category = classify_error(output)
        assert category == "executor_crash", f"expected executor_crash for {output!r}, got {category}"


def test_classify_error_provider_patterns():
    """Rate-limit / 429 / quota / api-error patterns → category "provider_error"."""
    for output in [
        "HTTP 429 Too Many Requests",
        "Rate limit exceeded",
        "API quota exhausted",
        "Provider error: billing issue",
    ]:
        _, category = classify_error(output)
        assert category == "provider_error", f"expected provider_error for {output!r}, got {category}"


def test_classify_error_validation_patterns():
    """Validation / assertion / schema patterns → category "validation_failure"."""
    for output in [
        "AssertionError: expected True got False",
        "validation error: missing required field",
        "expected 5 got 3",
        "Schema validation failed",
    ]:
        _, category = classify_error(output)
        assert category == "validation_failure", f"expected validation_failure for {output!r}, got {category}"


def test_classify_error_unknown_when_no_pattern_matches():
    """Generic error text with no matching pattern → category "unknown"."""
    _, category = classify_error("Something went wrong somewhere")
    assert category == "unknown"


def test_classify_error_summary_uses_first_meaningful_line():
    """Summary is the first non-empty line, not the whole text."""
    output = "\n\n  Connection refused\nstack frame 1\nstack frame 2"
    summary, _ = classify_error(output)
    assert summary == "Connection refused"


def test_classify_error_summary_capped_at_500_chars():
    """Long first lines are truncated to 500 chars to keep the field bounded."""
    long_line = "x" * 1000
    summary, _ = classify_error(long_line)
    assert len(summary) == 500


def test_classify_error_returns_valid_category():
    """Every category returned by classify_error is in VALID_CATEGORIES (the contract)."""
    samples = [
        "timeout exceeded",
        "Traceback",
        "rate limit",
        "AssertionError",
        "random text",
        "",
        None,
    ]
    for output in samples:
        _, category = classify_error(output)
        assert category in VALID_CATEGORIES, f"category {category!r} not in VALID_CATEGORIES"


# ---------------------------------------------------------------------------
# ensure_diagnostics
# ---------------------------------------------------------------------------


def test_ensure_diagnostics_preserves_provided_summary():
    """When error_summary is given, it's returned unchanged (just stripped)."""
    result = ensure_diagnostics(
        error_summary="  My custom summary  ",
        error_category="timeout",
        output="some output",
    )
    assert result["error_summary"] == "My custom summary"
    assert result["error_category"] == "timeout"


def test_ensure_diagnostics_invalid_category_falls_back_to_unknown():
    """A provided category outside VALID_CATEGORIES is coerced to 'unknown'."""
    result = ensure_diagnostics(
        error_summary="something",
        error_category="not-a-real-category",
        output=None,
    )
    assert result["error_category"] == "unknown"


def test_ensure_diagnostics_auto_classifies_when_no_summary():
    """When summary is missing, classify from output."""
    result = ensure_diagnostics(
        error_summary=None,
        error_category=None,
        output="Traceback (most recent call last)",
    )
    assert result["error_category"] == "executor_crash"
    assert result["error_summary"]  # non-empty


def test_ensure_diagnostics_empty_summary_triggers_auto_classify():
    """Whitespace-only summary is treated as missing — auto-classifies."""
    result = ensure_diagnostics(
        error_summary="   ",
        error_category=None,
        output="rate limit exceeded",
    )
    assert result["error_category"] == "provider_error"


# ---------------------------------------------------------------------------
# compute_diagnostics_completeness
# ---------------------------------------------------------------------------


def test_completeness_empty_list_returns_zeros():
    """No tasks → all zero counts, no division-by-zero."""
    result = compute_diagnostics_completeness([])
    assert result["total_failed"] == 0
    assert result["with_diagnostics"] == 0
    assert result["missing_pct"] == 0.0
    assert result["by_category"] == {}


def test_completeness_ignores_non_failed_tasks():
    """Only tasks with status='failed' are counted in total_failed."""
    tasks = [
        {"status": "completed", "error_summary": None, "error_category": None},
        {"status": "running", "error_summary": None, "error_category": None},
        {"status": "failed", "error_summary": "Boom", "error_category": "executor_crash"},
    ]
    result = compute_diagnostics_completeness(tasks)
    assert result["total_failed"] == 1
    assert result["with_diagnostics"] == 1


def test_completeness_counts_missing_diagnostics():
    """Failed tasks with no real summary count as missing diagnostics."""
    tasks = [
        {"status": "failed", "error_summary": "real summary", "error_category": "timeout"},
        {"status": "failed", "error_summary": None, "error_category": None},
        {"status": "failed", "error_summary": "No diagnostics provided", "error_category": "unknown"},
    ]
    result = compute_diagnostics_completeness(tasks)
    assert result["total_failed"] == 3
    assert result["with_diagnostics"] == 1  # only the first
    assert result["missing_pct"] == round((2 / 3) * 100, 2)


def test_completeness_aggregates_by_category():
    """by_category counts how many failed tasks fall into each category."""
    tasks = [
        {"status": "failed", "error_summary": "a", "error_category": "timeout"},
        {"status": "failed", "error_summary": "b", "error_category": "timeout"},
        {"status": "failed", "error_summary": "c", "error_category": "executor_crash"},
        {"status": "failed", "error_summary": "d", "error_category": "provider_error"},
    ]
    result = compute_diagnostics_completeness(tasks)
    assert result["by_category"] == {
        "timeout": 2,
        "executor_crash": 1,
        "provider_error": 1,
    }
