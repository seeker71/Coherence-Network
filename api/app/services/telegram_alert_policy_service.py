"""Telegram alert policy helpers for task updates.

Routine runner updates are summarized at most once per interval to reduce noise,
while attention statuses are handled directly by the router.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from app.services import agent_service

_WEB_BASE_ENV_KEYS = (
    "AGENT_WEB_UI_BASE_URL",
    "WEB_UI_BASE_URL",
    "PUBLIC_APP_URL",
    "NEXT_PUBLIC_APP_URL",
    "NEXT_PUBLIC_WEB_URL",
)
_DEFAULT_WEB_BASE_URL = "https://coherence-web-production.up.railway.app"
_DEFAULT_INTERVAL_SECONDS = 3600
_MIN_INTERVAL_SECONDS = 60
_STATE_FILE_ENV = "TELEGRAM_RUNNER_SUMMARY_STATE_FILE"
_INTERVAL_ENV = "TELEGRAM_RUNNER_SUMMARY_MIN_INTERVAL_SECONDS"
_STATUS_ORDER = ("pending", "running", "needs_decision", "failed", "completed")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _escape_markdown(text: str) -> str:
    out = text or ""
    for ch in ("\\", "`", "*", "_", "[", "]"):
        out = out.replace(ch, f"\\{ch}")
    return out


def _utc_label(value: datetime) -> str:
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_base_url(raw_value: Any) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value.rstrip("/")
    if value.startswith("/"):
        return ""
    return f"https://{value.rstrip('/')}"


def _task_context(task: dict[str, Any]) -> dict[str, Any]:
    context = task.get("context")
    return context if isinstance(context, dict) else {}


def _base_web_url(context: dict[str, Any]) -> str:
    for context_key in ("web_ui_base_url", "web_base_url", "web_url"):
        context_value = _normalize_base_url(context.get(context_key))
        if context_value:
            return context_value
    for env_key in _WEB_BASE_ENV_KEYS:
        env_value = _normalize_base_url(os.getenv(env_key))
        if env_value:
            return env_value
    return _DEFAULT_WEB_BASE_URL


def _tasks_web_url(context: dict[str, Any]) -> str:
    return f"{_base_web_url(context).rstrip('/')}/tasks"


def _logs_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")


def _state_file_path() -> str:
    override = str(os.environ.get(_STATE_FILE_ENV, "")).strip()
    if override:
        return override
    return os.path.join(_logs_dir(), "telegram_runner_summary_state.json")


def _summary_interval_seconds() -> int:
    raw_value = os.environ.get(_INTERVAL_ENV)
    if raw_value is None:
        return _DEFAULT_INTERVAL_SECONDS
    try:
        parsed = int(str(raw_value).strip())
    except (TypeError, ValueError):
        return _DEFAULT_INTERVAL_SECONDS
    return max(_MIN_INTERVAL_SECONDS, parsed)


def _load_state() -> dict[str, Any]:
    path = _state_file_path()
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return {}
    return {}


def _save_state(payload: dict[str, Any]) -> None:
    path = _state_file_path()
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def _ordered_status_counts(by_status: dict[str, Any]) -> list[tuple[str, int]]:
    counts: dict[str, int] = {}
    for key, value in by_status.items():
        try:
            counts[str(key).strip().lower()] = int(value or 0)
        except (TypeError, ValueError):
            counts[str(key).strip().lower()] = 0

    rows: list[tuple[str, int]] = []
    for key in _STATUS_ORDER:
        rows.append((key, counts.pop(key, 0)))
    for key in sorted(k for k in counts if k):
        rows.append((key, counts[key]))
    return rows


def _attention_count(by_status: dict[str, Any]) -> int:
    failed = int(by_status.get("failed") or 0)
    needs_decision = int(by_status.get("needs_decision") or 0)
    return failed + needs_decision


def build_runner_hourly_summary(task: dict[str, Any]) -> str | None:
    """Return summary text for routine runner updates, throttled by interval."""
    now = _now_utc()
    interval_seconds = _summary_interval_seconds()
    state = _load_state()
    previous_sent_ts = float(state.get("last_summary_ts") or 0.0)
    now_ts = now.timestamp()
    if previous_sent_ts and (now_ts - previous_sent_ts) < interval_seconds:
        return None

    summary = agent_service.get_review_summary()
    by_status = summary.get("by_status") if isinstance(summary.get("by_status"), dict) else {}
    pipeline = agent_service.get_pipeline_status(now_utc=now)
    running = pipeline.get("running") if isinstance(pipeline.get("running"), list) else []
    pending = pipeline.get("pending") if isinstance(pipeline.get("pending"), list) else []
    recent_completed = (
        pipeline.get("recent_completed")
        if isinstance(pipeline.get("recent_completed"), list)
        else []
    )

    context = _task_context(task)
    task_id = str(task.get("id") or "").strip()
    direction = str(task.get("direction") or "").strip()
    current_step = str(task.get("current_step") or "").strip()
    if len(direction) > 180:
        direction = f"{direction[:177]}..."
    if len(current_step) > 180:
        current_step = f"{current_step[:177]}..."

    lines: list[str] = [
        "*Hourly pipeline summary*",
        f"Checked: `{_utc_label(now)}`",
        (
            f"Pipeline: running `{len(running)}` pending `{len(pending)}` "
            f"recent_completed `{len(recent_completed)}`"
        ),
        f"Total tasks: `{int(summary.get('total') or 0)}`",
    ]
    for status_key, count in _ordered_status_counts(by_status):
        lines.append(f"`{status_key}`: `{count}`")

    attention = _attention_count(by_status)
    if attention:
        lines.append(f"Attention: `{attention}` (use `/attention`)")
    else:
        lines.append("Attention: `0`")

    if task_id:
        lines.append(f"Latest task: `{task_id}`")
    if direction:
        lines.append(f"Direction: {_escape_markdown(direction)}")
    if current_step:
        lines.append(f"Step: {_escape_markdown(current_step)}")
    lines.append(f"Web UI: [open tasks]({_tasks_web_url(context)})")

    _save_state(
        {
            "last_summary_ts": now_ts,
            "last_summary_at": now.isoformat(),
            "last_task_id": task_id,
            "interval_seconds": interval_seconds,
        }
    )
    return "\n".join(lines)[:3800]
