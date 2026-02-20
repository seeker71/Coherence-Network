"""Telegram webhook routes for the personal assistant bot."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Body

from app.models.agent import AgentTaskCreate, TaskType
from app.services import agent_service

router = APIRouter()
logger = logging.getLogger(__name__)

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



def _base_web_url() -> str:
    for env_key in _WEB_BASE_ENV_KEYS:
        value = _normalize_base_url(os.getenv(env_key))
        if value:
            return value
    return _DEFAULT_WEB_BASE_URL



def _task_web_url(task_id: str) -> str:
    base = _base_web_url().rstrip("/")
    return f"{base}/tasks?task_id={quote(task_id, safe='')}"



def _tasks_web_url() -> str:
    return f"{_base_web_url().rstrip('/')}/tasks"



def _now_utc_label() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")



def _normalize_status(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value).strip()
    return str(value or "unknown").strip()



def _help_reply() -> str:
    return (
        "Commands: /research <request>, /do <request>, /status, /task {id}. "
        "Plain text is treated as /do."
    )



def _assistant_context(task: dict[str, Any]) -> dict[str, Any]:
    context = task.get("context")
    return context if isinstance(context, dict) else {}



def _is_assistant_chat_task(task: dict[str, Any], chat_id: str) -> bool:
    context = _assistant_context(task)
    if str(context.get("source") or "").strip() != "telegram_personal_assistant":
        return False
    return str(context.get("telegram_chat_id") or "").strip() == chat_id



def _assistant_status_reply(chat_id: str) -> str:
    items, _ = agent_service.list_tasks(limit=60, offset=0)
    matched = [task for task in items if _is_assistant_chat_task(task, chat_id)]

    reply = f"*Assistant status*\nChecked: `{_now_utc_label()}`"
    if not matched:
        return reply + "\nNo assistant tasks for this chat yet."

    reply += f"\nRecent tasks: `{len(matched)}`"
    for task in matched[:8]:
        task_id = str(task.get("id") or "").strip()
        status = _normalize_status(task.get("status"))
        direction = _escape_markdown(str(task.get("direction") or "").strip())
        if len(direction) > 70:
            direction = f"{direction[:67]}..."
        reply += f"\n`{task_id}` `{status}` {direction} [open]({_task_web_url(task_id)})"
    reply += f"\nWeb UI: [open tasks]({_tasks_web_url()})"
    return reply



def _assistant_task_reply(task_id: str, chat_id: str) -> str:
    task = agent_service.get_task(task_id)
    if task is None or not _is_assistant_chat_task(task, chat_id):
        return f"Task `{_escape_markdown(task_id)}` not found for this assistant chat"

    status = _normalize_status(task.get("status"))
    direction = _escape_markdown(str(task.get("direction") or "").strip())
    output = _escape_markdown(str(task.get("output") or "").strip())
    if len(output) > 280:
        output = f"{output[:277]}..."

    reply = (
        "*Assistant task*\n"
        f"ID: `{_escape_markdown(task_id)}`\n"
        f"Status: `{_escape_markdown(status)}`\n"
        f"Direction: {direction}\n"
        f"Web UI: [open task]({_task_web_url(task_id)})"
    )
    if output:
        reply += f"\nOutput: {output}"
    return reply



def _create_assistant_task(
    *,
    direction: str,
    request_kind: str,
    user_id: int | None,
    chat_id: int | str | None,
) -> dict[str, Any]:
    task_type = TaskType.SPEC if request_kind == "research" else TaskType.IMPL
    payload = AgentTaskCreate(
        direction=direction,
        task_type=task_type,
        context={
            "source": "telegram_personal_assistant",
            "assistant_request_kind": request_kind,
            "telegram_user_id": str(user_id or "").strip(),
            "telegram_chat_id": str(chat_id or "").strip(),
            # Keep assistant requests on the local/free execution lane unless
            # explicitly changed by operators.
            "executor": "openclaw",
            "model_override": "openrouter/free",
            "force_paid_providers": False,
        },
    )
    return agent_service.create_task(payload)



@router.post("/assistant/telegram/webhook")
async def assistant_telegram_webhook(background_tasks: BackgroundTasks, update: dict = Body(...)) -> dict:
    """Receive Telegram updates for the personal assistant bot."""
    from app.services import telegram_personal_adapter

    logger.info("Assistant Telegram webhook received: %s", list(update.keys()))
    if not telegram_personal_adapter.has_token():
        logger.warning("Assistant Telegram webhook: no TELEGRAM_PERSONAL_BOT_TOKEN configured")
        return {"ok": True}

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return {"ok": True}

    chat_id = msg.get("chat", {}).get("id")
    text = str(msg.get("text") or "").strip()
    user_id = (msg.get("from") or {}).get("id")

    if not telegram_personal_adapter.is_user_allowed(user_id):
        logger.warning("Assistant Telegram webhook: user %s not allowed", user_id)
        return {"ok": True}

    cmd, arg = telegram_personal_adapter.parse_command(text)
    reply = ""

    if cmd in {"help", "start"}:
        reply = _help_reply()
    elif cmd == "status":
        reply = _assistant_status_reply(str(chat_id or "").strip())
    elif cmd == "task":
        task_id = arg.strip()
        if not task_id:
            reply = "Usage: /task {id}"
        else:
            reply = _assistant_task_reply(task_id, str(chat_id or "").strip())
    elif cmd in {"research", "do"}:
        direction = arg.strip()
        if not direction:
            reply = "Usage: /research <request> or /do <request>"
        else:
            request_kind = "research" if cmd == "research" else "action"
            created = _create_assistant_task(
                direction=direction,
                request_kind=request_kind,
                user_id=user_id,
                chat_id=chat_id,
            )
            created_id = str(created.get("id") or "").strip()
            queued = False
            if telegram_personal_adapter.auto_execute_enabled() and created_id:
                from app.services import agent_execution_service

                background_tasks.add_task(agent_execution_service.execute_task, created_id)
                queued = True

            reply = (
                "✅ Assistant task created\n"
                f"Kind: `{request_kind}`\n"
                f"Task ID: `{_escape_markdown(created_id)}`\n"
                f"Web UI: [open task]({_task_web_url(created_id)})\n"
                f"Queued execution: `{'yes' if queued else 'no'}`"
            )
            if not queued:
                command = _escape_markdown(str(created.get("command") or "").strip())
                if command:
                    reply += f"\nCommand: `{command}`"
    elif text:
        # Fallback for unknown slash commands: provide help contract.
        reply = _help_reply()

    if reply and chat_id is not None:
        await telegram_personal_adapter.send_reply(chat_id, reply)

    return {"ok": True}
