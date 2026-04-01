"""Agent route (routing) and Telegram diagnostics routes."""

import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query

from app.models.agent import RouteResponse, TaskType

from app.services import agent_service
from app.services.config_service import get_config

router = APIRouter()


def _get_telegram_config() -> dict:
    """Get telegram configuration from config."""
    config = get_config()
    telegram = config.get("telegram", {})
    
    bot_token = telegram.get("bot_token") if isinstance(telegram, dict) else None
    if not bot_token:
        bot_token = config.get("telegram_bot_token")
    
    chat_ids = telegram.get("chat_ids") if isinstance(telegram, dict) else None
    if chat_ids is None:
        chat_ids = []
    
    allowed_user_ids = telegram.get("allowed_user_ids") if isinstance(telegram, dict) else None
    if allowed_user_ids is None:
        allowed_user_ids = []
    
    return {
        "bot_token": bot_token,
        "chat_ids": chat_ids,
        "allowed_user_ids": allowed_user_ids,
    }


@router.get("/route", response_model=RouteResponse)
async def route(
    task_type: TaskType = Query(...),
    executor: Optional[str] = Query(
        "auto",
        description="Executor: auto (default policy), or canonical claude, cursor, codex, gemini, openrouter.",
    ),
) -> RouteResponse:
    """Get routing for a task type (no persistence). Canonical executors only."""
    return RouteResponse(**agent_service.get_route(task_type, executor=executor or "auto"))


@router.get("/telegram/diagnostics")
async def telegram_diagnostics() -> dict:
    """Diagnostics: last webhook events, send results, config (masked). For debugging."""
    from app.services import telegram_adapter
    from app.services import telegram_diagnostics as diag

    def _iso_ts(raw: object) -> str | None:
        try:
            ts = float(raw)  # type: ignore[arg-type]
        except Exception:
            return None
        if ts <= 0:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")

    webhook_events = diag.get_webhook_events()
    send_results = diag.get_send_results()
    report_log = diag.get_report_log()

    webhook_events_out = []
    for row in webhook_events:
        if isinstance(row, dict):
            out = dict(row)
            out["ts_iso"] = _iso_ts(out.get("ts"))
            webhook_events_out.append(out)
        else:
            webhook_events_out.append(row)

    send_results_out = []
    for row in send_results:
        if isinstance(row, dict):
            out = dict(row)
            out["ts_iso"] = _iso_ts(out.get("ts"))
            send_results_out.append(out)
        else:
            send_results_out.append(row)

    report_log_out = []
    for row in report_log:
        if isinstance(row, dict):
            out = dict(row)
            out["ts_iso"] = _iso_ts(out.get("ts"))
            report_log_out.append(out)
        else:
            report_log_out.append(row)

    send_success = sum(1 for item in send_results if isinstance(item, dict) and bool(item.get("ok")))
    send_failures = sum(1 for item in send_results if isinstance(item, dict) and not bool(item.get("ok")))

    telegram_config = _get_telegram_config()
    token = telegram_config["bot_token"]
    token_prefix = (token[:8] + "...") if token else None
    return {
        "config": {
            "has_token": telegram_adapter.has_token(),
            "token_prefix": token_prefix,
            "chat_ids": telegram_config["chat_ids"],
            "allowed_user_ids": telegram_config["allowed_user_ids"],
        },
        "summary": {
            "webhook_event_count": len(webhook_events),
            "send_count": len(send_results),
            "send_success_count": send_success,
            "send_failure_count": send_failures,
            "report_count": len(report_log),
            "last_webhook_at": _iso_ts(webhook_events[-1].get("ts")) if webhook_events and isinstance(webhook_events[-1], dict) else None,
            "last_send_at": _iso_ts(send_results[-1].get("ts")) if send_results and isinstance(send_results[-1], dict) else None,
            "last_report_at": _iso_ts(report_log[-1].get("ts")) if report_log and isinstance(report_log[-1], dict) else None,
        },
        "webhook_events": webhook_events_out,
        "send_results": send_results_out,
        "report_log": report_log_out,
    }


@router.post("/telegram/test-send")
async def telegram_test_send(
    text: Optional[str] = Query(None, description="Optional message text"),
) -> dict:
    """Send a test message to configured chat IDs. Returns raw Telegram API response for debugging."""
    import httpx
    from app.services import telegram_diagnostics as diag

    message_text = text or "Test from diagnostics"
    telegram_config = _get_telegram_config()
    token = telegram_config["bot_token"]
    chat_ids = telegram_config["chat_ids"]
    if not token or not chat_ids:
        return {"ok": False, "error": "telegram bot_token or chat_ids not configured"}

    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        for cid in chat_ids[:3]:
            r = await client.post(url, json={"chat_id": cid, "text": message_text})
            response_text = (
                r.text[:500]
                if not r.headers.get("content-type", "").startswith("application/json")
                else str(r.json())[:500]
            )
            diag.record_send(cid, r.status_code == 200, r.status_code, response_text)
            results.append({
                "chat_id": cid,
                "status_code": r.status_code,
                "response": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:500],
            })
    return {"ok": all(r["status_code"] == 200 for r in results), "results": results}
