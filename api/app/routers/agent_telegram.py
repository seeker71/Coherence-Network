"""Telegram webhook routes for agent operations."""

import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Body

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_service

router = APIRouter()
logger = logging.getLogger(__name__)


_RUNNER_CONTEXT_KEYS = {
    "active_run_id",
    "active_worker_id",
    "last_worker_id",
    "retry_not_before",
    "runner_metrics",
}
_ROI_KEYS = (
    "potential_roi",
    "roi_estimate",
    "estimated_roi",
    "answer_roi",
    "question_roi",
)
_MEASURED_VALUE_KEYS = (
    "measured_value_total",
    "measured_value",
    "actual_value",
    "measured_delta",
)
_WEB_BASE_ENV_KEYS = (
    "AGENT_WEB_UI_BASE_URL",
    "WEB_UI_BASE_URL",
    "PUBLIC_APP_URL",
    "NEXT_PUBLIC_APP_URL",
    "NEXT_PUBLIC_WEB_URL",
)
_DEFAULT_WEB_BASE_URL = "https://coherence-web-production.up.railway.app"


def _escape_markdown(text: str) -> str:
    out = text or ""
    for ch in ("\\", "`", "*", "_", "[", "]"):
        out = out.replace(ch, f"\\{ch}")
    return out


def _normalize_base_url(raw_value: Any) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")):
        return value.rstrip("/")
    if value.startswith("/"):
        return ""
    return f"https://{value.rstrip('/')}"


def _coerce_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if value is None:
        return None
    try:
        parsed = float(str(value).strip())
    except Exception:
        return None
    if parsed != parsed:  # NaN check
        return None
    return parsed


def _task_context(task: dict[str, Any]) -> dict[str, Any]:
    context = task.get("context")
    return context if isinstance(context, dict) else {}


def _idea_id_from_context(context: dict[str, Any]) -> str:
    idea_id = str(context.get("idea_id") or "").strip()
    if idea_id:
        return idea_id
    idea_ids = context.get("idea_ids")
    if isinstance(idea_ids, list):
        for raw in idea_ids:
            candidate = str(raw or "").strip()
            if candidate:
                return candidate
    return ""


def _find_numeric(context: dict[str, Any], keys: tuple[str, ...]) -> tuple[float | None, str | None]:
    for key in keys:
        value = _coerce_float(context.get(key))
        if value is not None:
            return value, key
    return None, None


def _resolve_idea_values(idea_id: str) -> dict[str, float]:
    if not idea_id:
        return {}
    try:
        from app.services import idea_service

        idea = idea_service.get_idea(idea_id)
    except Exception:
        return {}
    if idea is None:
        return {}
    return {
        "potential_value": float(idea.potential_value),
        "actual_value": float(idea.actual_value),
        "estimated_cost": float(idea.estimated_cost),
    }


def _resolve_potential_roi(
    context: dict[str, Any],
    idea_values: dict[str, float],
) -> tuple[float | None, str | None]:
    direct, direct_key = _find_numeric(context, _ROI_KEYS)
    if direct is not None:
        return direct, f"context.{direct_key}"

    value = _coerce_float(context.get("estimated_unblock_value"))
    cost = _coerce_float(context.get("estimated_unblock_cost"))
    if value is not None and cost is not None and cost > 0:
        return value / cost, "context.estimated_unblock_value/estimated_unblock_cost"

    value = _coerce_float(context.get("value_to_whole"))
    cost = _coerce_float(context.get("estimated_cost"))
    if value is not None and cost is not None and cost > 0:
        return value / cost, "context.value_to_whole/estimated_cost"

    value = _coerce_float(idea_values.get("potential_value"))
    cost = _coerce_float(idea_values.get("estimated_cost"))
    if value is not None and cost is not None and cost > 0:
        return value / cost, "idea.potential_value/estimated_cost"
    return None, None


def _resolve_measured_value(
    context: dict[str, Any],
    idea_values: dict[str, float],
) -> tuple[float | None, str | None]:
    direct, direct_key = _find_numeric(context, _MEASURED_VALUE_KEYS)
    if direct is not None and direct > 0:
        return direct, f"context.{direct_key}"

    actual_value = _coerce_float(idea_values.get("actual_value"))
    if actual_value is not None and actual_value > 0:
        return actual_value, "idea.actual_value"
    return None, None


def _base_web_url(context: dict[str, Any]) -> str:
    for context_key in ("web_ui_base_url", "web_base_url", "web_url"):
        context_value = _normalize_base_url(context.get(context_key))
        if context_value:
            return context_value
    for env_key in _WEB_BASE_ENV_KEYS:
        value = _normalize_base_url(os.getenv(env_key))
        if value:
            return value
    return _DEFAULT_WEB_BASE_URL


def _tasks_web_url(context: dict[str, Any]) -> str:
    return f"{_base_web_url(context).rstrip('/')}/tasks"


def _task_web_url(task_id: str, context: dict[str, Any]) -> str:
    task_path = f"/tasks?task_id={quote(task_id, safe='')}"
    base = _base_web_url(context)
    if "/tasks?" in base and "task_id=" in base:
        return base
    if base.rstrip("/").endswith("/tasks"):
        return f"{base}?task_id={quote(task_id, safe='')}"
    return f"{base.rstrip('/')}{task_path}"


def is_runner_task_update(worker_id: str | None = None, context_patch: dict[str, Any] | None = None) -> bool:
    if str(worker_id or "").strip():
        return True
    if not isinstance(context_patch, dict):
        return False
    for key in context_patch:
        normalized = str(key or "").strip().lower()
        if not normalized:
            continue
        if normalized.startswith("runner_") or normalized in _RUNNER_CONTEXT_KEYS:
            return True
    return False


def format_task_alert(task: dict, *, runner_update: bool = False) -> str:
    """Format a telegram task alert with routing/context/value metadata."""
    status = task.get("status", "?")
    status_str = status.value if hasattr(status, "value") else str(status)
    status_norm = status_str.strip().lower()
    context = _task_context(task)
    task_id = str(task.get("id") or "").strip()
    direction = _escape_markdown(str(task.get("direction") or "").strip()[:220] or "(no direction)")
    current_step = _escape_markdown(str(task.get("current_step") or "").strip()[:180])

    idea_id = _idea_id_from_context(context)
    idea_values = _resolve_idea_values(idea_id)
    potential_roi, potential_roi_source = _resolve_potential_roi(context, idea_values)
    measured_value, measured_value_source = _resolve_measured_value(context, idea_values)
    task_url = _task_web_url(task_id, context)
    tasks_url = _tasks_web_url(context)

    icon = "⚠️"
    if runner_update:
        icon = "🔄"
    elif status_norm == TaskStatus.FAILED.value:
        icon = "❌"
    elif status_norm == TaskStatus.NEEDS_DECISION.value:
        icon = "🟡"
    title = "runner_update" if runner_update else status_norm
    msg = (
        f"{icon} *{_escape_markdown(title)}*\n"
        f"Task: {direction}\n"
        f"Status: `{status_str}`\n"
        f"Task ID: `{task_id}`\n"
        f"Web UI: [open task]({task_url}) | [all tasks]({tasks_url})"
    )
    updated_at = str(task.get("updated_at") or task.get("created_at") or "").strip()
    if updated_at:
        msg += f"\nUpdated: `{updated_at}`"
    progress_pct = task.get("progress_pct")
    if progress_pct is not None:
        msg += f"\nProgress: `{progress_pct}%`"
    if current_step:
        msg += f"\nStep: {current_step}"
    if idea_id:
        msg += f"\nIdea: `{idea_id}`"
    if potential_roi is not None:
        source = _escape_markdown(potential_roi_source or "derived")
        msg += f"\nPotential ROI: `{potential_roi:.3f}x` ({source})"
    else:
        msg += "\nPotential ROI: `n/a`"
    if measured_value is not None:
        source = _escape_markdown(measured_value_source or "derived")
        msg += f"\nMeasured value: `{measured_value:.3f}` ({source})"
    else:
        msg += "\nMeasured value: `unavailable`"
    if status_norm == TaskStatus.NEEDS_DECISION.value and task_id:
        msg += f"\nAction: `/reply {task_id} <decision>`"
    elif status_norm == TaskStatus.FAILED.value and task_id:
        msg += f"\nAction: `/task {task_id}` then `/direction Retry task {task_id}`"
    if task.get("decision_prompt"):
        prompt = _escape_markdown(str(task.get("decision_prompt") or "")[:500])
        msg += f"\n\n{prompt}"
    return msg[:3800]


def _now_utc_label() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _help_reply() -> str:
    return (
        "Commands: /status, /tasks [status], /task {id}, /reply {id} {decision}, "
        "/attention, /usage, /direction \"...\", /railway ..., or just type your direction"
    )


def _format_agent_status_reply(summary: dict[str, Any]) -> str:
    by_status = summary.get("by_status") if isinstance(summary.get("by_status"), dict) else {}
    needs = summary.get("needs_attention") if isinstance(summary.get("needs_attention"), list) else []
    reply = (
        "*Agent status*\n"
        f"Checked: `{_now_utc_label()}`\n"
        f"Total tasks: `{int(summary.get('total') or 0)}`"
    )
    if by_status:
        for key in sorted(by_status):
            reply += f"\n`{key}`: `{int(by_status.get(key) or 0)}`"
    if needs:
        reply += f"\nAttention: `{len(needs)}` (use `/attention`)"
    else:
        reply += "\nAttention: `0`"
    reply += f"\nWeb UI: [open tasks]({_tasks_web_url({})})"
    return reply


def _format_usage_reply(usage: dict[str, Any]) -> str:
    reply = f"*Usage by model*\nChecked: `{_now_utc_label()}`"
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


def _format_tasks_reply(
    items: list[dict[str, Any]],
    total: int,
    *,
    status_filter: str | None,
) -> str:
    reply = (
        f"*Tasks* ({total} total)\n"
        f"Checked: `{_now_utc_label()}`"
    )
    if status_filter:
        reply += f"\nFilter: `{status_filter}`"
    if not items:
        return reply + f"\nNo matching tasks.\nWeb UI: [open tasks]({_tasks_web_url({})})"
    for task in items:
        task_id = str(task.get("id") or "").strip()
        status_obj = task.get("status")
        status = (
            str(status_obj.value).strip()
            if hasattr(status_obj, "value")
            else str(status_obj or "unknown").strip()
        )
        direction = _escape_markdown(str(task.get("direction") or "").strip())
        if len(direction) > 70:
            direction = f"{direction[:67]}..."
        task_url = _task_web_url(task_id, _task_context(task))
        reply += f"\n`{task_id}` `{status}` {direction} [open]({task_url})"
    reply += f"\nWeb UI: [open tasks]({_tasks_web_url({})})"
    return reply


def _format_task_snapshot_reply(task: dict[str, Any]) -> str:
    task_id = str(task.get("id") or "").strip()
    context = _task_context(task)
    task_url = _task_web_url(task_id, context)
    tasks_url = _tasks_web_url(context)
    status = task.get("status", "unknown")
    status_str = status.value if hasattr(status, "value") else str(status)
    direction = _escape_markdown(str(task.get("direction") or "").strip())
    updated = task.get("updated_at") or task.get("created_at")
    if hasattr(updated, "isoformat"):
        updated_at = str(updated.isoformat()).strip()
    else:
        updated_at = str(updated or "").strip()
    reply = (
        f"*Task* `{task_id}`\n"
        f"Status: `{status_str}`"
    )
    if updated_at:
        reply += f"\nUpdated: `{updated_at}`"
    if direction:
        reply += f"\nDirection: {direction[:220]}"
    reply += f"\nWeb UI: [open task]({task_url}) | [all tasks]({tasks_url})"
    reply += f"\nNext: `/task {task_id}`"
    return reply


def _format_attention_reply(items: list[dict[str, Any]], total: int) -> str:
    reply = (
        f"*Attention* ({total} need action)\n"
        f"Checked: `{_now_utc_label()}`"
    )
    if not items:
        return reply + f"\nNo attention tasks right now.\nWeb UI: [open tasks]({_tasks_web_url({})})"
    for task in items:
        task_id = str(task.get("id") or "").strip()
        status = str(task.get("status") or "unknown").strip()
        direction = _escape_markdown(str(task.get("direction") or "").strip())
        if len(direction) > 60:
            direction = f"{direction[:57]}..."
        task_url = _task_web_url(task_id, _task_context(task))
        reply += f"\n`{task_id}` `{status}` {direction} [open]({task_url})"
        if task.get("decision_prompt"):
            prompt = _escape_markdown(str(task.get("decision_prompt") or "").strip())
            reply += f"\nPrompt: _{prompt[:100]}_"
    reply += f"\nWeb UI: [open tasks]({_tasks_web_url({})})"
    return reply


def _extract_status_filter(arg: str) -> str | None:
    candidate = str(arg or "").strip().lower()
    if candidate in ("pending", "running", "completed", "failed", "needs_decision"):
        return candidate
    return None


@router.post("/agent/telegram/webhook")
async def telegram_webhook(update: dict = Body(...)) -> dict:
    """Receive Telegram updates and run command handlers.

    Commands: /status, /tasks [status], /task {id}, /reply {id} {decision},
    /attention, /usage, /direction \"...\", /railway ..., or plain text.
    """
    from app.services import telegram_adapter
    from app.services import telegram_diagnostics

    telegram_diagnostics.record_webhook(update)
    logger.info("Telegram webhook received: %s", list(update.keys()))
    if not telegram_adapter.has_token():
        logger.warning("Telegram webhook: no token configured")
        return {"ok": True}

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        logger.info("Telegram webhook: no message in update")
        return {"ok": True}

    chat_id = msg.get("chat", {}).get("id")
    text = msg.get("text", "").strip()
    user_id = (msg.get("from") or {}).get("id")
    logger.info("Telegram webhook: user_id=%s chat_id=%s text=%r", user_id, chat_id, text[:50])

    if not telegram_adapter.is_user_allowed(user_id):
        if user_id is None:
            logger.warning(
                "Telegram webhook: message has no 'from' (reject when TELEGRAM_ALLOWED_USER_IDS set)"
            )
        else:
            logger.warning(
                "Telegram webhook: user %s not allowed (check TELEGRAM_ALLOWED_USER_IDS)",
                user_id,
            )
        return {"ok": True}

    cmd, arg = telegram_adapter.parse_command(text)
    reply = ""

    if cmd == "status":
        summary = agent_service.get_review_summary()
        reply = _format_agent_status_reply(summary if isinstance(summary, dict) else {})
    elif cmd == "usage":
        usage = agent_service.get_usage_summary()
        reply = _format_usage_reply(usage if isinstance(usage, dict) else {})
    elif cmd == "tasks":
        status_filter = _extract_status_filter(arg)
        status_enum = TaskStatus(status_filter) if status_filter else None
        items, total = agent_service.list_tasks(status=status_enum, limit=10)
        reply = _format_tasks_reply(items, total, status_filter=status_filter)
    elif cmd == "task":
        if not arg:
            reply = "Usage: /task {id}"
        else:
            task = agent_service.get_task(arg.strip())
            if not task:
                reply = f"Task `{arg}` not found"
            else:
                reply = (
                    format_task_alert(task)
                    if task.get("status")
                    in (agent_service.TaskStatus.NEEDS_DECISION, agent_service.TaskStatus.FAILED)
                    else _format_task_snapshot_reply(task)
                )
    elif cmd == "reply":
        parts = (arg or "").split(maxsplit=1)
        task_id = (parts[0] or "").strip()
        decision = (parts[1] or "").strip() if len(parts) > 1 else ""
        if not task_id or not decision:
            reply = "Usage: /reply {task_id} {decision}"
        else:
            task = agent_service.update_task(task_id, decision=decision)
            if not task:
                reply = f"Task `{task_id}` not found"
            else:
                reply = f"Decision recorded for `{task_id}`"
    elif cmd == "attention":
        items, total = agent_service.get_attention_tasks(limit=10)
        reply = _format_attention_reply(items, total)
    elif cmd in {"railway", "deploy"}:
        from app.services import telegram_railway_service

        reply = await telegram_railway_service.handle_railway_command(arg)
    elif cmd == "direction" or (not cmd and text):
        direction = arg if cmd == "direction" else text
        if not direction:
            reply = "Send a direction: e.g. /direction Add GET /api/projects"
        else:
            created = agent_service.create_task(
                AgentTaskCreate(direction=direction, task_type=TaskType.IMPL)
            )
            created_id = str(created.get("id") or "").strip()
            created_context = created.get("context")
            task_url = _task_web_url(
                created_id,
                created_context if isinstance(created_context, dict) else {},
            )
            reply = (
                f"✅ Task `{created_id}`\n"
                f"Web UI: [open task]({task_url})\n\n"
                f"Run:\n`{created['command']}`"
            )
    else:
        reply = _help_reply()

    if reply:
        logger.info(
            "Telegram reply prepared: cmd=%s chat_id=%s preview=%r",
            cmd,
            chat_id,
            reply[:200],
        )
        ok = await telegram_adapter.send_reply(chat_id, reply)
        logger.info("Telegram reply sent: %s", ok)
        if not ok:
            logger.warning("Telegram send_reply failed — check bot token and that user has /start with bot")

    return {"ok": True}
