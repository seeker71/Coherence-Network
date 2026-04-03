from __future__ import annotations

import json
from pathlib import Path

from app import config_loader


def test_user_config_overrides_repo_config(monkeypatch, tmp_path: Path) -> None:
    repo_config = tmp_path / "api.json"
    user_config = tmp_path / "user-config.json"
    repo_config.write_text(json.dumps({
        "database": {"url": "sqlite:///data/coherence.db"},
        "auth": {"api_key": "repo-key"},
    }))
    user_config.write_text(json.dumps({
        "database": {"url": "postgresql://coherence:pw@db/coherence"},
        "auth": {"api_key": "user-key"},
        "_doc": "ignored",
    }))

    monkeypatch.setattr(config_loader, "_find_config_paths", lambda: [repo_config, user_config])
    config_loader.reload_config()

    assert config_loader.database_url() == "postgresql://coherence:pw@db/coherence"
    assert config_loader.api_config("auth", "api_key") == "user-key"


def test_missing_user_config_falls_back_to_repo(monkeypatch, tmp_path: Path) -> None:
    repo_config = tmp_path / "api.json"
    repo_config.write_text(json.dumps({
        "database": {"url": "sqlite:///data/coherence.db"},
        "auth": {"api_key": "repo-key"},
    }))

    monkeypatch.setattr(config_loader, "_find_config_paths", lambda: [repo_config, tmp_path / "missing.json"])
    config_loader.reload_config()

    assert config_loader.database_url() == "sqlite:///data/coherence.db"
    assert config_loader.api_config("auth", "api_key") == "repo-key"


def test_config_source_report_marks_loaded_sources(monkeypatch, tmp_path: Path) -> None:
    repo_config = tmp_path / "api.json"
    user_config = tmp_path / "user-config.json"
    repo_config.write_text(json.dumps({"database": {"url": "sqlite:///repo.db"}}))
    user_config.write_text(json.dumps({"auth": {"api_key": "user-key"}}))

    monkeypatch.setattr(config_loader, "_find_config_paths", lambda: [repo_config, user_config])

    report = config_loader.config_source_report()

    assert report[0]["source"] == "repo"
    assert report[0]["loaded"] is True
    assert "database" in report[0]["sections"]
    assert report[1]["source"] == "user"
    assert report[1]["loaded"] is True
    assert "auth" in report[1]["sections"]


def test_loader_exposes_web_and_cli_defaults(monkeypatch, tmp_path: Path) -> None:
    repo_config = tmp_path / "api.json"
    repo_config.write_text(json.dumps({}), encoding="utf-8")
    monkeypatch.setattr(config_loader, "_find_config_paths", lambda: [repo_config, tmp_path / "missing.json"])
    config_loader.reload_config()

    assert config_loader.api_config("web", "api_base_url") == "https://api.coherencycoin.com"
    assert config_loader.get_int("live_updates", "poll_ms", 0) == 120000
    assert config_loader.api_config("cli", "provider") == "cli"
