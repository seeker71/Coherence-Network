"""Formatting helpers for Telegram status/task replies."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable


def _escape_markdown(text: str) -> str:
    out = text or ""
    for ch in ("\\", "`", "*", "_", "[", "]"):
        out = out.replace(ch, f"\\{ch}")
    return out


def _task_context(task: dict[str, Any]) -> dict[str, Any]:
    context = task.get("context")
    return context if isinstance(context, dict) else {}


def now_utc_label() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def format_help_reply() -> str:
    return (
        "Commands: /status, /tasks [status], /task {id}, /reply {id} {decision}, "
        "/attention, /usage, /direction \"...\", /railway ..., or just type your direction"
    )


def _stale_running_rows(running: list[dict[str, Any]], threshold_seconds: int) -> list[dict[str, Any]]:
    stale: list[dict[str, Any]] = []
    for row in running:
        if not isinstance(row, dict):
            continue
        try:
            run_seconds = float(row.get("running_seconds"))
        except (TypeError, ValueError):
            continue
        if run_seconds > threshold_seconds:
            stale.append(row)
    return stale


def _join_url(base: str, path: str) -> str:
    return f"{(base or '').rstrip('/')}{path}"


def format_agent_status_reply(
    summary: dict[str, Any],
    pipeline_status: dict[str, Any],
    monitor_issues: dict[str, Any],
    status_report: dict[str, Any],
    *,
    tasks_url: str,
    web_base_url: str,
    api_base_url: str,
    orphan_threshold_seconds: int,
) -> str:
    by_status = summary.get("by_status") if isinstance(summary.get("by_status"), dict) else {}
    needs = summary.get("needs_attention") if isinstance(summary.get("needs_attention"), list) else []
    running = pipeline_status.get("running") if isinstance(pipeline_status.get("running"), list) else []
    pending = pipeline_status.get("pending") if isinstance(pipeline_status.get("pending"), list) else []
    recent_completed = (
        pipeline_status.get("recent_completed")
        if isinstance(pipeline_status.get("recent_completed"), list)
        else []
    )
    attention = pipeline_status.get("attention") if isinstance(pipeline_status.get("attention"), dict) else {}
    attention_flags = attention.get("flags") if isinstance(attention.get("flags"), list) else []
    threshold_minutes = max(1, int(round(orphan_threshold_seconds / 60)))
    stale_running = _stale_running_rows(running, orphan_threshold_seconds)
    issues = monitor_issues.get("issues") if isinstance(monitor_issues.get("issues"), list) else []
    condition_names: list[str] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        cond = str(issue.get("condition") or "").strip()
        if cond and cond not in condition_names:
            condition_names.append(cond)
    condition_preview = ", ".join(condition_names[:3]) if condition_names else "none"
    if len(condition_names) > 3:
        condition_preview += f", +{len(condition_names) - 3} more"
    layer_3 = (
        status_report.get("layer_3_attention")
        if isinstance(status_report.get("layer_3_attention"), dict)
        else {}
    )
    report_attention = str(layer_3.get("status") or "unknown").strip()
    report_generated_at = str(status_report.get("generated_at") or "unknown").strip()
    reply = (
        "*Agent status*\n"
        f"Checked: `{now_utc_label()}`\n"
        f"Total tasks: `{int(summary.get('total') or 0)}`"
    )
    if by_status:
        for key in sorted(by_status):
            reply += f"\n`{key}`: `{int(by_status.get(key) or 0)}`"
    if needs:
        reply += f"\nAttention: `{len(needs)}` (use `/attention`)"
    else:
        reply += "\nAttention: `0`"
    reply += f"\nWeb UI: [open tasks]({tasks_url})"
    reply += (
        f"\nPipeline: running `{len(running)}` pending `{len(pending)}` recent_completed `{len(recent_completed)}`"
    )
    if stale_running:
        stale_ids = ", ".join(
            str(row.get("id") or "").strip()
            for row in stale_running[:3]
            if str(row.get("id") or "").strip()
        )
        if len(stale_running) > 3:
            stale_ids += f", +{len(stale_running) - 3} more"
        reply += f"\nStale running (>{threshold_minutes}m): `{len(stale_running)}`"
        if stale_ids:
            reply += f"\nStale IDs: `{stale_ids}`"
    if attention_flags:
        reply += f"\nPipeline flags: `{', '.join(str(flag) for flag in attention_flags[:6])}`"
    reply += f"\nMonitor issues: `{len(issues)}` ({_escape_markdown(condition_preview)})"
    last_check = str(monitor_issues.get("last_check") or "").strip()
    if last_check:
        reply += f"\nMonitor last check: `{last_check}`"
    reply += f"\nStatus report: `{report_attention}` at `{report_generated_at}`"
    reply += (
        "\n\n*Public UI*"
        f"\n[Tasks]({_join_url(web_base_url, '/tasks')}) · [Friction]({_join_url(web_base_url, '/friction')}) · [Usage]({_join_url(web_base_url, '/usage')}) · [Gates]({_join_url(web_base_url, '/gates')}) · [Agent]({_join_url(web_base_url, '/agent')})"
    )
    reply += (
        "\n*Public API*"
        f"\n[pipeline-status]({_join_url(api_base_url, '/api/agent/pipeline-status')}) · [monitor-issues]({_join_url(api_base_url, '/api/agent/monitor-issues')}) · [status-report]({_join_url(api_base_url, '/api/agent/status-report')}) · [effectiveness]({_join_url(api_base_url, '/api/agent/effectiveness')})"
    )
    return reply


def format_usage_reply(usage: dict[str, Any]) -> str:
    reply = f"*Usage by model*\nChecked: `{now_utc_label()}`"
    by_model = usage.get("by_model") if isinstance(usage.get("by_model"), dict) else {}
    if not by_model:
        reply += "\nNo usage data yet."
    for model, data in by_model.items():
        if not isinstance(data, dict):
            continue
        count = int(data.get("count") or 0)
        line = f"\n`{model}`: `{count}` tasks"
        by_status = data.get("by_status") if isinstance(data.get("by_status"), dict) else {}
        if by_status:
            status_pairs = ", ".join(f"{k}:{int(by_status.get(k) or 0)}" for k in sorted(by_status))
            line += f" ({status_pairs})"
        reply += line
    routing = usage.get("routing") if isinstance(usage.get("routing"), dict) else {}
    if routing:
        pairs = []
        for task_type, route in routing.items():
            if not isinstance(route, dict):
                continue
            pairs.append(f"{task_type}={route.get('model')}")
        if pairs:
            reply += "\n\n*Routing*: " + ", ".join(sorted(pairs))
    return reply


def _normalize_status(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value).strip()
    return str(value or "unknown").strip()


def format_tasks_reply(
    items: list[dict[str, Any]],
    total: int,
    *,
    status_filter: str | None,
    tasks_url_builder: Callable[[dict[str, Any]], str],
    task_url_builder: Callable[[str, dict[str, Any]], str],
) -> str:
    reply = f"*Tasks* ({total} total)\nChecked: `{now_utc_label()}`"
    if status_filter:
        reply += f"\nFilter: `{status_filter}`"
    if not items:
        return reply + f"\nNo matching tasks.\nWeb UI: [open tasks]({tasks_url_builder({})})"
    for task in items:
        task_id = str(task.get("id") or "").strip()
        status = _normalize_status(task.get("status"))
        direction = _escape_markdown(str(task.get("direction") or "").strip())
        if len(direction) > 60:
            direction = f"{direction[:57]}..."
        task_url = task_url_builder(task_id, _task_context(task))
        reply += f"\n`{task_id}` `{status}` {direction} [open]({task_url})"
    reply += f"\nWeb UI: [open tasks]({tasks_url_builder({})})"
    return reply


def format_task_snapshot_reply(
    task: dict[str, Any],
    *,
    tasks_url_builder: Callable[[dict[str, Any]], str],
    task_url_builder: Callable[[str, dict[str, Any]], str],
) -> str:
    task_id = str(task.get("id") or "").strip()
    status = _normalize_status(task.get("status"))
    direction = _escape_markdown(str(task.get("direction") or "").strip())
    created_at = _escape_markdown(str(task.get("created_at") or "").strip())
    updated_at = _escape_markdown(str(task.get("updated_at") or "").strip())
    task_url = task_url_builder(task_id, _task_context(task))
    tasks_url = tasks_url_builder(_task_context(task))
    reply = (
        "*Task snapshot*\n"
        f"ID: `{task_id}`\n"
        f"Status: `{status}`\n"
        f"Direction: {direction}\n"
        f"Created: `{created_at}`\n"
        f"Updated: `{updated_at}`"
    )
    reply += f"\nWeb UI: [open task]({task_url}) | [all tasks]({tasks_url})"
    reply += f"\nNext: `/task {task_id}`"
    return reply


def format_attention_reply(
    items: list[dict[str, Any]],
    total: int,
    *,
    monitor_issues: dict[str, Any],
    pipeline_status: dict[str, Any],
    tasks_url: str,
    web_base_url: str,
    orphan_threshold_seconds: int,
    task_url_builder: Callable[[str, dict[str, Any]], str],
) -> str:
    reply = f"*Attention* ({total} need action)\nChecked: `{now_utc_label()}`"
    running = pipeline_status.get("running") if isinstance(pipeline_status.get("running"), list) else []
    threshold_minutes = max(1, int(round(orphan_threshold_seconds / 60)))
    stale_count = len(_stale_running_rows(running, orphan_threshold_seconds))
    if stale_count:
        reply += f"\nStale running (>{threshold_minutes}m): `{stale_count}`"
    if not items:
        reply += "\nNo attention tasks right now."
    else:
        for task in items:
            task_id = str(task.get("id") or "").strip()
            status = str(task.get("status") or "unknown").strip()
            direction = _escape_markdown(str(task.get("direction") or "").strip())
            if len(direction) > 60:
                direction = f"{direction[:57]}..."
            task_url = task_url_builder(task_id, _task_context(task))
            reply += f"\n`{task_id}` `{status}` {direction} [open]({task_url})"
            if task.get("decision_prompt"):
                prompt = _escape_markdown(str(task.get("decision_prompt") or "").strip())
                reply += f"\nPrompt: _{prompt[:100]}_"

    issues = monitor_issues.get("issues") if isinstance(monitor_issues.get("issues"), list) else []
    if issues:
        reply += f"\n\nMonitor issues: `{len(issues)}`"
        for issue in issues[:3]:
            if not isinstance(issue, dict):
                continue
            condition = str(issue.get("condition") or "unknown").strip()
            severity = str(issue.get("severity") or "unknown").strip()
            message = _escape_markdown(str(issue.get("message") or "").strip())
            if len(message) > 100:
                message = f"{message[:97]}..."
            reply += f"\n`{condition}` `{severity}` {message}"

    reply += f"\nWeb UI: [open tasks]({tasks_url})"
    reply += (
        "\n\n*Public UI*"
        f"\n[Tasks]({_join_url(web_base_url, '/tasks')}) · [Friction]({_join_url(web_base_url, '/friction')}) · [Usage]({_join_url(web_base_url, '/usage')})"
    )
    return reply


def extract_status_filter(arg: str) -> str | None:
    candidate = str(arg or "").strip().lower()
    if candidate in ("pending", "running", "completed", "failed", "needs_decision"):
        return candidate
    return None
