"""Telegram webhook routes for agent operations."""

import logging

from fastapi import APIRouter, Body

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_service

router = APIRouter()
logger = logging.getLogger(__name__)


def format_task_alert(task: dict) -> str:
    """Format a telegram task alert with a truncated direction."""
    status = task.get("status", "?")
    status_str = status.value if hasattr(status, "value") else str(status)
    direction = (task.get("direction") or "")[:80]
    msg = f"⚠️ *{status_str}*\n\n{direction}\n\nTask: `{task.get('id', '')}`"
    if task.get("decision_prompt"):
        msg += f"\n\n{task['decision_prompt']}"
    return msg


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
