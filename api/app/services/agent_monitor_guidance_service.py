"""Guidance text helpers for agent monitor issues."""

from typing import Any


def low_success_rate_suggested_action(
    diagnostics: dict[str, Any],
    fallback_task_type: str,
) -> str:
    rows = diagnostics.get("recent_failed_reasons") if isinstance(diagnostics.get("recent_failed_reasons"), list) else []
    top_reason = ""
    for row in rows:
        count = row.get("count") if isinstance(row, dict) else 0
        try:
            normalized_count = int(count or 0)
        except (TypeError, ValueError):
            normalized_count = 0
        if isinstance(row, dict) and str(row.get("reason") or "").strip() and normalized_count > 0:
            top_reason = str(row.get("reason") or "").strip()
            break

    reason_actions = {
        "context_compaction": "Fix recent context_compaction failures first: retry from persisted task cards with a fresh context budget and require artifact/test evidence.",
        "spec_gate": "Fix recent spec_gate failures first: stop unspecced implementation work, create or activate the required specs, and requeue only scoped work with evidence.",
        "no_code": "Fix recent no-artifact failures first: reject progress-only or empty completions, then retry with exact files_allowed and done_when verification.",
        "empty_output": "Fix recent no-artifact failures first: reject progress-only or empty completions, then retry with exact files_allowed and done_when verification.",
        "done_spec_gate": "Fix recent done_spec_gate failures first: verify existing artifacts or select unfinished specs instead of retrying completed specs.",
    }
    if top_reason in reason_actions:
        return reason_actions[top_reason]
    if top_reason:
        return (
            f"Digest recent {top_reason} failures first: inspect failure signatures, "
            "then tighten routing/task-card gates or requeue only scoped work with evidence."
        )
    return (
        f"Digest recent {fallback_task_type} failures first: inspect failure signatures, "
        "then tighten routing/task-card gates or requeue only scoped work with evidence."
    )
