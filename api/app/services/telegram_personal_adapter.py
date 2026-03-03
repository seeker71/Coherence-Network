"""Telegram personal-assistant adapter.

Uses a dedicated bot token/user allowlist so personal assistant traffic is isolated
from the agent operations Telegram bot.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Union

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"



def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on", "y"}



def _get_token() -> Optional[str]:
    return os.environ.get("TELEGRAM_PERSONAL_BOT_TOKEN") or None



def _get_allowed_user_ids() -> set[str]:
    raw = os.environ.get("TELEGRAM_PERSONAL_ALLOWED_USER_IDS", "")
    return {s.strip() for s in raw.split(",") if s.strip()}



def has_token() -> bool:
    return bool(_get_token())



def is_user_allowed(user_id: int | None) -> bool:
    allowed = _get_allowed_user_ids()
    if not allowed:
        return True
    return str(user_id) in allowed



def auto_execute_enabled() -> bool:
    # Default-on for assistant bot background behavior. Disable with TELEGRAM_PERSONAL_AUTO_EXECUTE=0.
    return _truthy(os.environ.get("TELEGRAM_PERSONAL_AUTO_EXECUTE", "1"))



async def send_reply(chat_id: Union[int, str], message: str, parse_mode: str = "Markdown") -> bool:
    token = _get_token()
    if not token:
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
                return True
            if parse_mode and "parse" in (r.text or "").lower():
                r2 = await client.post(
                    url,
                    json={"chat_id": chat_id, "text": message[:4096]},
                )
                return r2.status_code == 200
            logger.warning("Personal Telegram sendMessage failed: %s %s", r.status_code, (r.text or "")[:200])
            return False
        except Exception as exc:
            logger.warning("Personal Telegram sendMessage error: %s", exc)
            return False



def parse_command(text: str) -> tuple[str, str]:
    """Parse assistant commands from Telegram text."""
    text = (text or "").strip()
    if not text:
        return ("", "")

    if text.startswith("/"):
        parts = text[1:].split(maxsplit=1)
        cmd = (parts[0] if parts else "").lower().strip()
        arg = parts[1].strip() if len(parts) > 1 else ""
        if cmd == "action":
            cmd = "do"
        return (cmd, arg)

    # Plain-text help shortcuts.
    if text.lower() in {"help", "start", "?", "commands"}:
        return ("help", "")

    return ("do", text)
