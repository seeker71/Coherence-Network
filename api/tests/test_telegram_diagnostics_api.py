from __future__ import annotations

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import telegram_diagnostics


@pytest.mark.asyncio
async def test_telegram_test_send_returns_error_without_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_IDS", raising=False)
    telegram_diagnostics.clear()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/agent/telegram/test-send?text=hello")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "not set" in payload["error"]


@pytest.mark.asyncio
@respx.mock
async def test_telegram_test_send_records_send_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot_token_for_test")
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", "111,222")
    telegram_diagnostics.clear()

    send_url = "https://api.telegram.org/botbot_token_for_test/sendMessage"
    route = respx.post(send_url).mock(return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}}))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/agent/telegram/test-send?text=telegram-proof")
        assert response.status_code == 200
        payload = response.json()
        assert payload["ok"] is True
        assert len(payload["results"]) == 2
        assert all(item["status_code"] == 200 for item in payload["results"])

        diagnostics = await client.get("/api/agent/telegram/diagnostics")
        assert diagnostics.status_code == 200
        diag_payload = diagnostics.json()
        send_results = diag_payload.get("send_results", [])

    assert route.call_count == 2
    assert len(send_results) == 2
    assert all(item["ok"] is True for item in send_results)
    assert {str(item["chat_id"]) for item in send_results} == {"111", "222"}


@pytest.mark.asyncio
async def test_telegram_diagnostics_includes_summary_and_report_log() -> None:
    telegram_diagnostics.clear()
    telegram_diagnostics.record_webhook({"message": {"text": "/status"}})
    telegram_diagnostics.record_send(chat_id="111", ok=True, status_code=200, response_text="ok")
    telegram_diagnostics.record_report("reply", "111", "*Agent status*")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        diagnostics = await client.get("/api/agent/telegram/diagnostics")

    assert diagnostics.status_code == 200
    payload = diagnostics.json()
    summary = payload.get("summary", {})
    assert summary.get("webhook_event_count") == 1
    assert summary.get("send_count") == 1
    assert summary.get("send_success_count") == 1
    assert summary.get("report_count") == 1
    assert isinstance(summary.get("last_webhook_at"), str)
    assert isinstance(summary.get("last_send_at"), str)
    assert isinstance(summary.get("last_report_at"), str)

    webhook_events = payload.get("webhook_events", [])
    send_results = payload.get("send_results", [])
    report_log = payload.get("report_log", [])
    assert webhook_events and isinstance(webhook_events[0].get("ts_iso"), str)
    assert send_results and isinstance(send_results[0].get("ts_iso"), str)
    assert report_log and report_log[0].get("kind") == "reply"
    assert report_log[0].get("text_preview") == "*Agent status*"
