from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app import config_loader


@pytest.mark.asyncio
async def test_diagnostics_config_editor_reads_and_updates_user_config(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    user_config = tmp_path / "config.json"
    user_config.write_text(
        json.dumps(
            {
                "server": {"environment": "development"},
                "database": {"url": "sqlite:///data/coherence.db"},
                "agent_executor": {"execute_token_allow_unauth": False},
                "telegram": {"chat_ids": ["111"]},
            }
        ),
        encoding="utf-8",
    )
    repo_config = tmp_path / "api.json"
    repo_config.write_text(json.dumps({"auth": {"admin_key": "dev-admin"}}), encoding="utf-8")

    monkeypatch.setattr(config_loader, "_find_config_paths", lambda: [repo_config, user_config])
    monkeypatch.setattr(config_loader, "user_config_path", lambda: user_config)
    monkeypatch.setattr(config_loader, "_user_config_path", lambda: user_config)
    config_loader.reload_config()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get_response = await client.get(
            "/api/agent/diagnostics/config-editor",
            headers={"X-Admin-Key": "dev-admin"},
        )
        assert get_response.status_code == 200
        assert get_response.json()["fields"]["database_url"] == "sqlite:///data/coherence.db"

        patch_response = await client.patch(
            "/api/agent/diagnostics/config-editor",
            headers={"X-Admin-Key": "dev-admin"},
            json={
                "server_environment": "production",
                "database_url": "postgresql://coherence:pw@db/coherence",
                "cors_allowed_origins": ["https://coherencycoin.com", " http://localhost:3000 "],
                "execute_token": "updated-token",
                "execute_token_allow_unauth": True,
                "telegram_chat_ids": ["111", " 222 "],
                "task_log_dir": "data/task_logs",
                "live_updates_poll_ms": 45000,
                "live_updates_router_refresh_every_ticks": 5,
                "live_updates_global": True,
                "runtime_beacon_sample_rate": 0.4,
                "health_proxy_failure_threshold": 4,
                "health_proxy_cooldown_ms": 45000,
                "cli_provider": "codex",
                "cli_active_task_id": "task_demo",
            },
        )

    assert patch_response.status_code == 200
    payload = patch_response.json()
    assert payload["fields"]["server_environment"] == "production"
    assert payload["fields"]["database_url"] == "postgresql://coherence:pw@db/coherence"
    assert payload["fields"]["execute_token_configured"] is True
    assert payload["fields"]["execute_token_allow_unauth"] is True
    assert payload["fields"]["telegram_chat_ids"] == ["111", "222"]
    assert payload["fields"]["live_updates_poll_ms"] == 45000
    assert payload["fields"]["live_updates_global"] is True
    assert payload["fields"]["runtime_beacon_sample_rate"] == 0.4
    assert payload["fields"]["health_proxy_failure_threshold"] == 4
    assert payload["fields"]["cli_provider"] == "codex"
    assert payload["fields"]["cli_active_task_id"] == "task_demo"

    written = json.loads(user_config.read_text(encoding="utf-8"))
    assert written["server"]["environment"] == "production"
    assert written["database"]["url"] == "postgresql://coherence:pw@db/coherence"
    assert written["agent_executor"]["execute_token"] == "updated-token"
    assert written["agent_executor"]["execute_token_allow_unauth"] is True
    assert written["live_updates"]["poll_ms"] == 45000
    assert written["live_updates"]["router_refresh_every_ticks"] == 5
    assert written["live_updates"]["global"] is True
    assert written["runtime_beacon"]["sample_rate"] == 0.4
    assert written["health_proxy"]["failure_threshold"] == 4
    assert written["health_proxy"]["cooldown_ms"] == 45000
    assert written["cli"]["provider"] == "codex"
    assert written["cli"]["active_task_id"] == "task_demo"


@pytest.mark.asyncio
async def test_diagnostics_config_editor_requires_admin_key() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/agent/diagnostics/config-editor")
    assert response.status_code == 401
