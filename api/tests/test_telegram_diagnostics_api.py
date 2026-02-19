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
