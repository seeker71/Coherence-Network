from __future__ import annotations

import pytest

from app.services import telegram_adapter


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = '{"ok": true}') -> None:
        self.status_code = status_code
        self.text = text


@pytest.mark.asyncio
async def test_send_alert_rate_limits_repeated_failed_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", "111")
    monkeypatch.setenv("TELEGRAM_FAILED_ALERT_WINDOW_SECONDS", "3600")
    monkeypatch.setenv("TELEGRAM_FAILED_ALERT_MAX_PER_WINDOW", "1")
    telegram_adapter._FAILED_ALERT_TIMESTAMPS.clear()

    sent_payloads: list[dict] = []

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict) -> _FakeResponse:
            sent_payloads.append(json)
            return _FakeResponse()

    monkeypatch.setattr("app.services.telegram_adapter.httpx.AsyncClient", _FakeAsyncClient)

    failed_message = "Status: `failed`\nTask: test"
    first = await telegram_adapter.send_alert(failed_message)
    second = await telegram_adapter.send_alert(failed_message)

    assert first is True
    assert second is True
    assert len(sent_payloads) == 1


@pytest.mark.asyncio
async def test_send_alert_does_not_rate_limit_non_failed_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_IDS", "111")
    monkeypatch.setenv("TELEGRAM_FAILED_ALERT_WINDOW_SECONDS", "3600")
    monkeypatch.setenv("TELEGRAM_FAILED_ALERT_MAX_PER_WINDOW", "1")
    telegram_adapter._FAILED_ALERT_TIMESTAMPS.clear()

    sent_payloads: list[dict] = []

    class _FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict) -> _FakeResponse:
            sent_payloads.append(json)
            return _FakeResponse()

    monkeypatch.setattr("app.services.telegram_adapter.httpx.AsyncClient", _FakeAsyncClient)

    message = "Status: `needs_decision`\nTask: test"
    first = await telegram_adapter.send_alert(message)
    second = await telegram_adapter.send_alert(message)

    assert first is True
    assert second is True
    assert len(sent_payloads) == 2
