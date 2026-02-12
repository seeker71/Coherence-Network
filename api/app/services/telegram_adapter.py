"""Telegram adapter — outbound alerts and inbound webhook handling.

Borrows from OpenClaw: bot token, allowed users, sendMessage.
Config: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS (comma-separated), TELEGRAM_ALLOWED_USER_IDS.
"""

import logging
import os
from typing import Optional, Union

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"


def _get_token() -> Optional[str]:
    return os.environ.get("TELEGRAM_BOT_TOKEN") or None


def _get_chat_ids() -> list[str]:
    raw = os.environ.get("TELEGRAM_CHAT_IDS", "")
    return [s.strip() for s in raw.split(",") if s.strip()]


def _get_allowed_user_ids() -> set[str]:
    raw = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
    return {s.strip() for s in raw.split(",") if s.strip()}


def is_configured() -> bool:
    """True if Telegram is configured for outbound alerts."""
    return bool(_get_token() and _get_chat_ids())


def has_token() -> bool:
    """True if bot token is set (for webhook replies)."""
    return bool(_get_token())


def is_user_allowed(user_id: int) -> bool:
    """True if user_id is allowed to send commands (empty = allow all)."""
    allowed = _get_allowed_user_ids()
    if not allowed:
        return True
    return str(user_id) in allowed


async def send_alert(message: str, parse_mode: str = "Markdown") -> bool:
    """Send message to configured chat IDs. Returns True if sent, False if not configured."""
    token = _get_token()
    chat_ids = _get_chat_ids()
    if not token or not chat_ids:
        return False
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    ok = True
    async with httpx.AsyncClient(timeout=10.0) as client:
        for chat_id in chat_ids:
            try:
                r = await client.post(
                    url,
                    json={
                        "chat_id": chat_id.strip(),
                        "text": message[:4096],  # Telegram limit
                        "parse_mode": parse_mode,
                    },
                )
                if r.status_code != 200:
                    ok = False
            except Exception:
                ok = False
    return ok


async def send_reply(chat_id: Union[int, str], message: str, parse_mode: str = "Markdown") -> bool:
    """Send message to a specific chat (for webhook replies)."""
    from app.services import telegram_diagnostics

    token = _get_token()
    if not token:
        telegram_diagnostics.record_send(chat_id, False, None, "no token")
        return False
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": message[:4096],
                    "parse_mode": parse_mode,
                },
            )
            if r.status_code == 200:
                telegram_diagnostics.record_send(chat_id, True, 200, r.text)
                return True
            # Retry without parse_mode if Telegram rejects Markdown
            if parse_mode and "parse" in (r.text or "").lower():
                r2 = await client.post(
                    url,
                    json={"chat_id": chat_id, "text": message[:4096]},
                )
                if r2.status_code == 200:
                    telegram_diagnostics.record_send(chat_id, True, 200, r2.text)
                    return True
            logger.warning("Telegram sendMessage failed: %s %s", r.status_code, (r.text or "")[:200])
            telegram_diagnostics.record_send(chat_id, False, r.status_code, r.text)
            return False
        except Exception as e:
            logger.warning("Telegram sendMessage error: %s", e)
            telegram_diagnostics.record_send(chat_id, False, None, str(e))
            return False


def parse_command(text: str) -> tuple[str, str]:
    """Parse /cmd or /cmd arg into (cmd, arg)."""
    text = (text or "").strip()
    if not text:
        return ("", "")
    if text.startswith("/"):
        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""
        return (cmd, arg)
    # No slash: treat as direction for new task
    return ("direction", text)
