"""Context-efficiency heuristics for agent tasks and operator surfaces."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

TOKENS_PER_BYTE = 0.25


def _token_estimate(value: str) -> int:
    text = str(value or "")
    return int(len(text.encode("utf-8")) * TOKENS_PER_BYTE)


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw = [part.strip() for part in value.replace("\n", ",").split(",")]
    elif isinstance(value, list):
        raw = [str(part).strip() for part in value]
    else:
        return []
    seen: set[str] = set()
    items: list[str] = []
    for item in raw:
        if not item or item in seen:
            continue
        seen.add(item)
        items.append(item)
    return items


def _context_dict(task: dict[str, Any]) -> dict[str, Any]:
    context = task.get("context")
    return dict(context) if isinstance(context, dict) else {}


def summarize_task_context(task: dict[str, Any]) -> dict[str, Any]:
    context = _context_dict(task)
    task_card = context.get("task_card") if isinstance(context.get("task_card"), dict) else {}

    files_allowed = _normalize_string_list(context.get("files_allowed") or task_card.get("files_allowed"))
    commands = context.get("commands") or task_card.get("commands") or []
    if not isinstance(commands, list):
        commands = [commands]
    commands = [str(command).strip() for command in commands if str(command).strip()]

    direction = str(task.get("direction") or "")
    output = str(task.get("output") or "")
    context_json = json.dumps(context, sort_keys=True, default=str)
    guard_agents = _normalize_string_list(context.get("guard_agents"))
    task_card_validation = context.get("task_card_validation") if isinstance(context.get("task_card_validation"), dict) else {}
    missing_fields = _normalize_string_list(task_card_validation.get("missing"))

    flags: list[dict[str, str]] = []
    recommendations: list[str] = []

    def add_flag(flag_id: str, severity: str, summary: str, recommendation: str) -> None:
        flags.append({"id": flag_id, "severity": severity, "summary": summary})
        if recommendation not in recommendations:
            recommendations.append(recommendation)

    if len(direction) > 1200:
        add_flag(
            "long_direction",
            "high" if len(direction) > 2400 else "medium",
            f"Direction is {len(direction)} chars; long prompts compound expensive rereads.",
            "start fresh sessions and summarize the task into a shorter task card",
        )
    if len(context_json.encode("utf-8")) > 4000:
        add_flag(
            "large_context",
            "high" if len(context_json.encode("utf-8")) > 12000 else "medium",
            f"Task context is {len(context_json.encode('utf-8'))} bytes; hidden overhead is likely too large.",
            "move stable instructions to compact config/docs and keep task context lean",
        )
    if len(files_allowed) > 12:
        add_flag(
            "broad_file_scope",
            "high" if len(files_allowed) > 24 else "medium",
            f"Task file scope spans {len(files_allowed)} files.",
            "narrow files_allowed to the smallest exact set before execution",
        )
    if commands and not files_allowed:
        add_flag(
            "missing_file_scope",
            "medium",
            "Commands are provided without an explicit file scope.",
            "add exact files_allowed entries to prevent broad repo exploration",
        )
    if len(commands) > 6:
        add_flag(
            "large_command_set",
            "medium",
            f"Task card lists {len(commands)} commands.",
            "trim commands to the minimal deterministic validation loop",
        )
    if len(output) > 2000:
        add_flag(
            "output_bloat",
            "high" if len(output) > 6000 else "medium",
            f"Task output is {len(output)} chars; raw output will bloat follow-up context.",
            "store compact summaries and fetch raw logs only on drilldown",
        )
    if len(guard_agents) > 2:
        add_flag(
            "tool_overhead",
            "medium",
            f"Task activates {len(guard_agents)} guard agents.",
            "disable unused tools or guard agents for narrow tasks",
        )
    if missing_fields:
        add_flag(
            "weak_task_card",
            "medium",
            f"Task card is missing: {', '.join(missing_fields)}.",
            "complete goal/files_allowed/done_when/commands before execution",
        )

    severity_weights = {"high": 18, "medium": 10, "low": 4}
    score = max(0, 100 - sum(severity_weights.get(flag["severity"], 0) for flag in flags))
    return {
        "score": score,
        "direction_chars": len(direction),
        "direction_tokens_estimate": _token_estimate(direction),
        "context_bytes": len(context_json.encode("utf-8")),
        "context_tokens_estimate": _token_estimate(context_json),
        "output_chars": len(output),
        "output_tokens_estimate": _token_estimate(output),
        "file_scope_count": len(files_allowed),
        "command_count": len(commands),
        "guard_agent_count": len(guard_agents),
        "flags": flags,
        "recommendations": recommendations,
    }


def annotate_task_context(task: dict[str, Any]) -> dict[str, Any]:
    context = _context_dict(task)
    context["context_hygiene"] = summarize_task_context(task)
    return context


def summarize_recent_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    inspected = [summarize_task_context(task) for task in tasks]
    if not inspected:
        return {
            "score": 100,
            "flagged_tasks": 0,
            "task_count": 0,
            "average_context_bytes": 0,
            "average_output_chars": 0,
            "average_file_scope_count": 0.0,
            "average_command_count": 0.0,
            "top_flags": [],
            "priority_actions": [],
        }

    flag_counter: Counter[str] = Counter()
    recommendation_counter: Counter[str] = Counter()
    for item in inspected:
        for flag in item["flags"]:
            flag_counter.update([flag["id"]])
        for recommendation in item["recommendations"]:
            recommendation_counter.update([recommendation])

    return {
        "score": round(sum(item["score"] for item in inspected) / len(inspected), 2),
        "flagged_tasks": sum(1 for item in inspected if item["flags"]),
        "task_count": len(inspected),
        "average_context_bytes": round(sum(item["context_bytes"] for item in inspected) / len(inspected), 2),
        "average_output_chars": round(sum(item["output_chars"] for item in inspected) / len(inspected), 2),
        "average_file_scope_count": round(sum(item["file_scope_count"] for item in inspected) / len(inspected), 2),
        "average_command_count": round(sum(item["command_count"] for item in inspected) / len(inspected), 2),
        "top_flags": [
            {"id": flag_id, "count": count}
            for flag_id, count in flag_counter.most_common(5)
        ],
        "priority_actions": [
            {"summary": recommendation, "count": count}
            for recommendation, count in recommendation_counter.most_common(4)
        ],
    }


def generate_output_summary(output: str | None, status: str = "", error_category: str | None = None) -> str | None:
    """Generate a compact summary of task output for list/attention views."""
    if not output:
        return None
    text = str(output).strip()
    if len(text) <= 500:
        return text  # Already compact

    lines = text.splitlines()
    line_count = len(lines)
    char_count = len(text)

    # Find first meaningful line (non-empty, non-separator)
    headline = ""
    for line in lines:
        stripped = line.strip()
        if stripped and not all(c in "-=~#*" for c in stripped):
            headline = stripped[:200]
            break

    # Look for key signal patterns
    key_signal = ""
    signal_patterns = [
        ("passed", lambda l: "pass" in l.lower() and ("test" in l.lower() or "assert" in l.lower())),
        ("error", lambda l: l.strip().startswith(("Error:", "ERROR:", "Traceback", "FAILED:"))),
        ("verify", lambda l: "VERIFY_PASSED" in l or "VERIFY_FAILED" in l or "CODE_REVIEW_PASSED" in l),
    ]
    for _name, matcher in signal_patterns:
        for line in reversed(lines[-30:]):
            if matcher(line):
                key_signal = line.strip()[:300]
                break
        if key_signal:
            break

    # Build summary
    parts = [f"[{status}]" if status else "[task]", f"{char_count} chars, {line_count} lines"]
    if error_category:
        parts.append(f"error: {error_category}")
    if headline:
        parts.append(f"| {headline}")
    if key_signal and key_signal != headline:
        parts.append(f"| {key_signal}")

    # Add tail context
    tail = text[-200:].strip()
    if tail:
        parts.append(f"| ...{tail}")

    summary = " ".join(parts)
    return summary[:800]  # Cap total summary

