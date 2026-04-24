from __future__ import annotations

from app.services import automation_usage_service, friction_service, persistence_contract_service
from app.services.telemetry_persistence_service import db as telemetry_service_db


def test_persistence_contract_auto_ignores_dev_sqlite(set_config) -> None:
    set_config("persistence_contract", "required", "auto")
    set_config("database", "url", "sqlite:///data/coherence.db")

    assert persistence_contract_service.contract_required() is False


def test_persistence_contract_auto_requires_service_database(set_config) -> None:
    set_config("persistence_contract", "required", "auto")
    set_config("database", "url", "postgresql://user:pass@example.test/coherence")

    assert persistence_contract_service.contract_required() is True


def test_persistence_contract_required_comes_from_config_not_env(set_config, monkeypatch) -> None:
    monkeypatch.setenv("GLOBAL_PERSISTENCE_REQUIRED", "1")
    set_config("persistence_contract", "required", False)
    set_config("database", "url", "sqlite:///data/coherence.db")

    assert persistence_contract_service.contract_required() is False


def test_automation_usage_snapshot_path_comes_from_config(set_config, tmp_path) -> None:
    snapshots_path = tmp_path / "usage_snapshots.json"
    set_config("automation_usage", "snapshots_path", str(snapshots_path))
    set_config("automation_usage", "use_db", True)

    assert automation_usage_service._snapshots_path() == snapshots_path
    assert automation_usage_service._use_db_snapshots() is False


def test_automation_usage_use_db_comes_from_config(set_config) -> None:
    set_config("automation_usage", "snapshots_path", None)
    set_config("automation_usage", "use_db", False)

    assert automation_usage_service._use_db_snapshots() is False


def test_friction_paths_come_from_config(set_config, tmp_path) -> None:
    friction_path = tmp_path / "friction.jsonl"
    monitor_path = tmp_path / "monitor.json"
    github_path = tmp_path / "github.json"
    set_config("friction", "events_path", str(friction_path))
    set_config("monitor", "issues_path", str(monitor_path))
    set_config("github_actions", "health_path", str(github_path))

    assert friction_service.friction_file_path() == friction_path
    assert friction_service.monitor_issues_file_path() == monitor_path
    assert friction_service.github_actions_health_file_path() == github_path
    assert friction_service.report_window_limit_days() == 365
    assert friction_service._use_db_events() is False


def test_friction_use_db_comes_from_config(set_config) -> None:
    set_config("friction", "events_path", None)
    set_config("friction", "use_db", False)

    assert friction_service._use_db_events() is False


def test_telemetry_persistence_service_uses_unified_database_url(set_config, monkeypatch) -> None:
    monkeypatch.setenv("TELEMETRY_DATABASE_URL", "sqlite+pysqlite:///tmp/legacy-telemetry.db")
    set_config("database", "url", "postgresql://user:pass@example.test/coherence")

    assert telemetry_service_db.database_url() == "postgresql://user:pass@example.test/coherence"
