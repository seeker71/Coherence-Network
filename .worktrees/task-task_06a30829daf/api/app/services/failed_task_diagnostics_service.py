"""Failed-task diagnostics: error classification and completeness tracking. Spec 113."""

from __future__ import annotations

import re

_TIMEOUT_PATTERNS = re.compile(
    r"\btimeout\b|\btimed?\s*out\b|exceeded\s+timeout|deadline\s+exceeded",
    re.IGNORECASE,
)
_CRASH_PATTERNS = re.compile(
    r"\btraceback\b|exit\s+code|segfault|\bfatal\s+error\b|signal\s+\d+|SIGKILL|SIGSEGV|\bcrashed\b|RuntimeError|KeyError|TypeError|ValueError|MemoryError",
    re.IGNORECASE,
)
_PROVIDER_PATTERNS = re.compile(
    r"rate.?limit|\b429\b|billing|quota|Too Many Requests|api\s+error|provider.*error",
    re.IGNORECASE,
)
_VALIDATION_PATTERNS = re.compile(
    r"assert(ion)?error|validation\s*error|expected\s+\d+.*got\s+\d+|schema\s+validation",
    re.IGNORECASE,
)

VALID_CATEGORIES = frozenset({
    "executor_crash",
    "timeout",
    "validation_failure",
    "provider_error",
    "unknown",
})


def classify_error(output: str | None) -> tuple[str, str]:
    """Classify error output into (summary, category).

    Returns a human-readable summary (first meaningful line, max 500 chars)
    and one of the 5 defined categories.
    """
    if not output or not output.strip():
        return "No diagnostics provided", "unknown"

    text = output.strip()

    # Extract summary: first non-empty line, capped at 500 chars
    first_line = ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            first_line = stripped
            break
    summary = (first_line or text)[:500]

    # Pattern match in priority order
    if _TIMEOUT_PATTERNS.search(text):
        return summary, "timeout"
    if _CRASH_PATTERNS.search(text):
        return summary, "executor_crash"
    if _PROVIDER_PATTERNS.search(text):
        return summary, "provider_error"
    if _VALIDATION_PATTERNS.search(text):
        return summary, "validation_failure"

    return summary, "unknown"


def ensure_diagnostics(
    error_summary: str | None,
    error_category: str | None,
    output: str | None,
) -> dict[str, str | None]:
    """Ensure error diagnostics are populated for a failed task.

    If error_summary is already provided, return as-is.
    Otherwise, auto-classify from output.
    """
    if error_summary and error_summary.strip():
        cat = error_category if error_category in VALID_CATEGORIES else "unknown"
        return {"error_summary": error_summary.strip(), "error_category": cat}

    summary, category = classify_error(output)
    return {"error_summary": summary, "error_category": category}


def compute_diagnostics_completeness(tasks: list[dict]) -> dict:
    """Compute diagnostics completeness across a list of task records.

    Each task dict should have: status, error_summary, error_category.
    """
    failed = [t for t in tasks if t.get("status") == "failed"]
    total_failed = len(failed)

    with_diag = 0
    by_category: dict[str, int] = {}

    for t in failed:
        summary = t.get("error_summary")
        category = t.get("error_category")
        if summary and summary.strip() and summary.strip() != "No diagnostics provided":
            with_diag += 1
        if category:
            by_category[category] = by_category.get(category, 0) + 1

    missing_pct = 0.0
    if total_failed > 0:
        missing_pct = round(((total_failed - with_diag) / total_failed) * 100, 2)

    return {
        "total_failed": total_failed,
        "with_diagnostics": with_diag,
        "missing_pct": missing_pct,
        "by_category": by_category,
    }
