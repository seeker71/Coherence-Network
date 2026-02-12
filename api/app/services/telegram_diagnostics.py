"""In-memory diagnostics for Telegram webhook and send_reply — inspect via GET /api/agent/telegram/diagnostics."""

import time
from collections import deque
from typing import Any, Optional

# Last 50 webhook payloads (sanitized)
_webhook_events: deque = deque(maxlen=50)

# Last 50 send_reply attempts: {chat_id, ok, status_code, response_text, ts}
_send_results: deque = deque(maxlen=50)


def record_webhook(update: dict, sanitize: bool = True) -> None:
    """Record incoming webhook payload."""
    if sanitize:
        # Deep copy, remove message.text if sensitive
        copy = {}
        for k, v in update.items():
            if k == "message" and isinstance(v, dict):
                msg_copy = dict(v)
                msg_copy.pop("photo", None)
                msg_copy.pop("document", None)
                copy[k] = msg_copy
            else:
                copy[k] = v
    else:
        copy = dict(update)
    _webhook_events.append({"ts": time.time(), "update": copy})


def record_send(chat_id: Any, ok: bool, status_code: Optional[int] = None, response_text: Optional[str] = None) -> None:
    """Record send_reply attempt."""
    _send_results.append({
        "ts": time.time(),
        "chat_id": chat_id,
        "ok": ok,
        "status_code": status_code,
        "response_text": (response_text or "")[:500],
    })


def get_webhook_events() -> list:
    return list(_webhook_events)


def get_send_results() -> list:
    return list(_send_results)
