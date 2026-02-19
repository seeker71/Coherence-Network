"""In-memory diagnostics for Telegram webhook and send_reply — inspect via GET /api/agent/telegram/diagnostics."""

import time
from collections import deque
from typing import Any, Optional

# Last 50 webhook payloads (sanitized)
_webhook_events: deque = deque(maxlen=50)

# Last 50 send_reply attempts: {chat_id, ok, status_code, response_text, ts}
_send_results: deque = deque(maxlen=50)

# Last 100 rendered Telegram reports: {kind, chat_id, text_preview, ts}
_report_log: deque = deque(maxlen=100)


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


def record_report(kind: str, chat_id: Any, text: str) -> None:
    """Record generated Telegram report text preview for inspection."""
    _report_log.append({
        "ts": time.time(),
        "kind": str(kind or "unknown").strip() or "unknown",
        "chat_id": chat_id,
        "text_preview": (text or "")[:1200],
        "text_len": len(text or ""),
    })


def get_webhook_events() -> list:
    return list(_webhook_events)


def get_send_results() -> list:
    return list(_send_results)


def get_report_log() -> list:
    return list(_report_log)


def clear() -> None:
    """Clear webhook_events and send_results. For test isolation (spec 003 diagnostic test)."""
    _webhook_events.clear()
    _send_results.clear()
    _report_log.clear()
