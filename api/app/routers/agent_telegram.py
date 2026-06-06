"""Telegram webhook routes for agent operations."""

import logging

from fastapi import APIRouter, Body

from app.models.agent import AgentTaskCreate, TaskStatus, TaskType
from app.services import agent_service
from app.routers.agent_telegram_format import (
    _load_monitor_issues,
    _load_status_report,
    _task_web_url,
    format_task_alert,
    _help_reply,
    _format_agent_status_reply,
    _format_usage_reply,
    _format_tasks_reply,
    _format_task_snapshot_reply,
    _format_attention_reply,
    _extract_status_filter,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/agent/telegram/webhook", summary="Receive Telegram updates and run command handlers")
async def telegram_webhook(update: dict = Body(...)) -> dict:
    """Receive Telegram updates and run command handlers.

    Commands: /status, /tasks [status], /task {id}, /reply {id} {decision},
    /attention, /usage, /direction \"...\", /deploy ..., or plain text.
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
        pipeline_status = agent_service.get_pipeline_status()
        monitor_issues = _load_monitor_issues()
        status_report = _load_status_report()
        reply = _format_agent_status_reply(
            summary if isinstance(summary, dict) else {},
            pipeline_status if isinstance(pipeline_status, dict) else {},
            monitor_issues if isinstance(monitor_issues, dict) else {"issues": [], "last_check": None},
            status_report if isinstance(status_report, dict) else {},
        )
    elif cmd == "usage":
        usage = agent_service.get_usage_summary()
        reply = _format_usage_reply(usage if isinstance(usage, dict) else {})
    elif cmd == "tasks":
        status_filter = _extract_status_filter(arg)
        status_enum = TaskStatus(status_filter) if status_filter else None
        listed = agent_service.list_tasks(status=status_enum, limit=10)
        if isinstance(listed, tuple) and len(listed) == 3:
            items, total, _ = listed
        elif isinstance(listed, tuple) and len(listed) == 2:
            items, total = listed
        else:
            items, total = [], 0
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
        monitor_issues = _load_monitor_issues()
        pipeline_status = agent_service.get_pipeline_status()
        reply = _format_attention_reply(
            items,
            total,
            monitor_issues=monitor_issues if isinstance(monitor_issues, dict) else {"issues": [], "last_check": None},
            pipeline_status=pipeline_status if isinstance(pipeline_status, dict) else {},
        )
    elif cmd == "deploy":
        from app.services import telegram_deploy_service

        reply = await telegram_deploy_service.handle_deploy_command(arg)
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
