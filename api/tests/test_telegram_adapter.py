from __future__ import annotations

import pytest

from app import config_loader
from app.services import telegram_adapter


class _FakeResponse:
    def __init__(self, status_code: int = 200, text: str = '{"ok": true}') -> None:
        self.status_code = status_code
        self.text = text


@pytest.mark.asyncio
async def test_send_alert_rate_limits_repeated_failed_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_token = config_loader.api_config("telegram", "bot_token")
    previous_chat_ids = config_loader.api_config("telegram", "chat_ids")
    previous_window = config_loader.api_config("telegram", "failed_alert_window_seconds")
    previous_max = config_loader.api_config("telegram", "failed_alert_max_per_window")
    config_loader.set_config_value("telegram", "bot_token", "test-token")
    config_loader.set_config_value("telegram", "chat_ids", ["111"])
    config_loader.set_config_value("telegram", "failed_alert_window_seconds", 3600)
    config_loader.set_config_value("telegram", "failed_alert_max_per_window", 1)
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

    try:
        failed_message = "Status: `failed`\nTask: test"
        first = await telegram_adapter.send_alert(failed_message)
        second = await telegram_adapter.send_alert(failed_message)

        assert first is True
        assert second is True
        assert len(sent_payloads) == 1
    finally:
        config_loader.set_config_value("telegram", "bot_token", previous_token)
        config_loader.set_config_value("telegram", "chat_ids", previous_chat_ids)
        config_loader.set_config_value("telegram", "failed_alert_window_seconds", previous_window)
        config_loader.set_config_value("telegram", "failed_alert_max_per_window", previous_max)
        telegram_adapter._FAILED_ALERT_TIMESTAMPS.clear()


@pytest.mark.asyncio
async def test_send_alert_does_not_rate_limit_non_failed_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_token = config_loader.api_config("telegram", "bot_token")
    previous_chat_ids = config_loader.api_config("telegram", "chat_ids")
    previous_window = config_loader.api_config("telegram", "failed_alert_window_seconds")
    previous_max = config_loader.api_config("telegram", "failed_alert_max_per_window")
    config_loader.set_config_value("telegram", "bot_token", "test-token")
    config_loader.set_config_value("telegram", "chat_ids", ["111"])
    config_loader.set_config_value("telegram", "failed_alert_window_seconds", 3600)
    config_loader.set_config_value("telegram", "failed_alert_max_per_window", 1)
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

    try:
        message = "Status: `needs_decision`\nTask: test"
        first = await telegram_adapter.send_alert(message)
        second = await telegram_adapter.send_alert(message)

        assert first is True
        assert second is True
        assert len(sent_payloads) == 2
    finally:
        config_loader.set_config_value("telegram", "bot_token", previous_token)
        config_loader.set_config_value("telegram", "chat_ids", previous_chat_ids)
        config_loader.set_config_value("telegram", "failed_alert_window_seconds", previous_window)
        config_loader.set_config_value("telegram", "failed_alert_max_per_window", previous_max)
        telegram_adapter._FAILED_ALERT_TIMESTAMPS.clear()
