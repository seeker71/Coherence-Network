"""Telegram webhook routes for agent operations."""

import logging
import os
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


def _escape_markdown(text: str) -> str:
    out = text or ""
    for ch in ("\\", "`", "*", "_", "[", "]"):
        out = out.replace(ch, f"\\{ch}")
    return out


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
    context_value = str(context.get("web_ui_base_url") or "").strip()
    if context_value:
        return context_value
    for env_key in _WEB_BASE_ENV_KEYS:
        value = str(os.getenv(env_key) or "").strip()
        if value:
            return value
    return ""


def _task_web_url(task_id: str, context: dict[str, Any]) -> str:
    task_path = f"/tasks?task_id={quote(task_id, safe='')}"
    base = _base_web_url(context)
    if not base:
        return task_path
    if "/tasks?" in base and "task_id=" in base:
        return base
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
    context = _task_context(task)
    task_id = str(task.get("id") or "").strip()
    direction = _escape_markdown(str(task.get("direction") or "").strip()[:220] or "(no direction)")
    current_step = _escape_markdown(str(task.get("current_step") or "").strip()[:180])

    idea_id = _idea_id_from_context(context)
    idea_values = _resolve_idea_values(idea_id)
    potential_roi, potential_roi_source = _resolve_potential_roi(context, idea_values)
    measured_value, measured_value_source = _resolve_measured_value(context, idea_values)
    task_url = _task_web_url(task_id, context)

    title = "runner_update" if runner_update else status_str
    msg = (
        f"⚠️ *{_escape_markdown(title)}*\n"
        f"Task: {direction}\n"
        f"Status: `{status_str}`\n"
        f"Task ID: `{task_id}`\n"
        f"Web UI: [open task]({task_url})"
    )
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
    if task.get("decision_prompt"):
        prompt = _escape_markdown(str(task.get("decision_prompt") or "")[:500])
        msg += f"\n\n{prompt}"
    return msg[:3800]


@router.post("/agent/telegram/webhook")
async def telegram_webhook(update: dict = Body(...)) -> dict:
    """Receive Telegram updates and run command handlers.

    Commands: /status, /tasks [status], /task {id}, /reply {id} {decision},
    /attention, /usage, /direction \"...\" or plain text.
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
        needs = summary["needs_attention"]
        reply = f"*Agent status*\nTasks: {summary['total']}\n"
        reply += "\n".join(f"  {k}: {v}" for k, v in summary["by_status"].items())
        if needs:
            reply += f"\n\n⚠️ *{len(needs)} need attention*"
    elif cmd == "usage":
        usage = agent_service.get_usage_summary()
        reply = "*Usage by model*\n"
        for model, u in usage.get("by_model", {}).items():
            reply += f"\n`{model}`: {u.get('count', 0)} tasks"
            if u.get("by_status"):
                reply += " " + ", ".join(f"{k}:{v}" for k, v in u["by_status"].items())
        reply += "\n\n*Routing*: " + ", ".join(
            f"{t}={d['model']}" for t, d in usage.get("routing", {}).items()
        )
    elif cmd == "tasks":
        status_filter = (
            arg if arg in ("pending", "running", "completed", "failed", "needs_decision") else None
        )
        status_enum = TaskStatus(status_filter) if status_filter else None
        items, total = agent_service.list_tasks(status=status_enum, limit=10)
        reply = f"*Tasks* ({total} total)\n"
        for t in items:
            reply += f"\n`{t['id']}` {t['status']} — {str(t['direction'])[:50]}..."
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
                    else f"*Task* `{task['id']}`\n{task['status']}\n{task.get('direction', '')[:200]}"
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
        reply = f"*Attention* ({total} need action)\n"
        for t in items:
            reply += f"\n`{t['id']}` {t['status']} — {str(t.get('direction', ''))[:40]}..."
            if t.get("decision_prompt"):
                reply += f"\n  _{t['decision_prompt'][:60]}_"
    elif cmd == "direction" or (not cmd and text):
        direction = arg if cmd == "direction" else text
        if not direction:
            reply = "Send a direction: e.g. /direction Add GET /api/projects"
        else:
            created = agent_service.create_task(
                AgentTaskCreate(direction=direction, task_type=TaskType.IMPL)
            )
            reply = f"✅ Task `{created['id']}`\n\nRun:\n`{created['command']}`"
    else:
        reply = (
            "Commands: /status, /tasks [status], /task {id}, /reply {id} {decision}, "
            "/attention, /usage, /direction \"...\" or just type your direction"
        )

    if reply:
        ok = await telegram_adapter.send_reply(chat_id, reply)
        logger.info("Telegram reply sent: %s", ok)
        if not ok:
            logger.warning("Telegram send_reply failed — check bot token and that user has /start with bot")

    return {"ok": True}
