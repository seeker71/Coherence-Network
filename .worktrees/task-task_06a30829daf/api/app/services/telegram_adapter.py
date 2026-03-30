"""Telegram adapter — outbound alerts and inbound webhook handling.

Borrows from OpenClaw: bot token, allowed users, sendMessage.
Config: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS (comma-separated), TELEGRAM_ALLOWED_USER_IDS.
"""

import logging
import os
import re
import time
from collections import deque
from threading import Lock
from typing import Optional, Union

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
_FAILED_ALERT_TIMESTAMPS: deque[float] = deque()
_FAILED_ALERT_LOCK = Lock()
_FAILED_STATUS_PATTERN = re.compile(r"(?im)^status:\s*`?failed`?\b")


def _failed_alert_window_seconds() -> int:
    raw = (os.environ.get("TELEGRAM_FAILED_ALERT_WINDOW_SECONDS") or "1800").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 1800
    return max(60, min(value, 86400))


def _failed_alert_max_per_window() -> int:
    raw = (os.environ.get("TELEGRAM_FAILED_ALERT_MAX_PER_WINDOW") or "1").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 1
    return max(0, min(value, 100))


def _is_failed_alert_message(message: str) -> bool:
    return bool(_FAILED_STATUS_PATTERN.search(message or ""))


def _should_suppress_failed_alert(message: str) -> bool:
    if not _is_failed_alert_message(message):
        return False
    max_per_window = _failed_alert_max_per_window()
    if max_per_window <= 0:
        return True
    window_seconds = _failed_alert_window_seconds()
    now = time.time()
    with _FAILED_ALERT_LOCK:
        while _FAILED_ALERT_TIMESTAMPS and (now - _FAILED_ALERT_TIMESTAMPS[0]) > window_seconds:
            _FAILED_ALERT_TIMESTAMPS.popleft()
        if len(_FAILED_ALERT_TIMESTAMPS) >= max_per_window:
            return True
        _FAILED_ALERT_TIMESTAMPS.append(now)
    return False


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
    from app.services import telegram_diagnostics

    token = _get_token()
    chat_ids = _get_chat_ids()
    if not token or not chat_ids:
        return False
    if _should_suppress_failed_alert(message):
        for chat_id in chat_ids:
            telegram_diagnostics.record_report("alert_suppressed", chat_id.strip(), message)
        logger.warning("Telegram failed alert suppressed by rate limit window")
        return True
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    ok = True
    async with httpx.AsyncClient(timeout=10.0) as client:
        for chat_id in chat_ids:
            try:
                telegram_diagnostics.record_report("alert", chat_id.strip(), message)
                r = await client.post(
                    url,
                    json={
                        "chat_id": chat_id.strip(),
                        "text": message[:4096],  # Telegram limit
                        "parse_mode": parse_mode,
                    },
                )
                if r.status_code == 200:
                    telegram_diagnostics.record_send(chat_id.strip(), True, 200, r.text)
                else:
                    telegram_diagnostics.record_send(chat_id.strip(), False, r.status_code, r.text)
                    ok = False
            except Exception as e:
                telegram_diagnostics.record_send(chat_id.strip(), False, None, str(e))
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
            telegram_diagnostics.record_report("reply", chat_id, message)
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
