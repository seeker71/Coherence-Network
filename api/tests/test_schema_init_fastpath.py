from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    ("module_name", "table_name", "ensure_fn_name"),
    [
        ("runtime_event_store", "runtime_events", "ensure_schema"),
        ("agent_task_store_service", "agent_tasks", "ensure_schema"),
        ("agent_runner_registry_service", "agent_runners", "_ensure_schema"),
    ],
)
def test_ensure_schema_short_circuits_after_first_init(
    monkeypatch: pytest.MonkeyPatch, module_name: str, table_name: str, ensure_fn_name: str
) -> None:
    module = importlib.import_module(f"app.services.{module_name}")
    ensure_schema = getattr(module, ensure_fn_name)
    sentinel_engine = object()
    calls = {"table_exists": 0, "create_all": 0}

    monkeypatch.setattr(module, "_SCHEMA_INITIALIZED", False)
    monkeypatch.setattr(module, "_SCHEMA_INITIALIZED_URL", "")
    monkeypatch.setattr(module, "_database_url", lambda: "postgresql://example")
    monkeypatch.setattr(module, "_engine", lambda: sentinel_engine)

    def _fake_table_exists(engine, name: str) -> bool:
        assert engine is sentinel_engine
        assert name == table_name
        calls["table_exists"] += 1
        return True

    def _fake_create_all(*, bind) -> None:
        calls["create_all"] += 1

    monkeypatch.setattr(module, "_table_exists", _fake_table_exists)
    monkeypatch.setattr(module.Base.metadata, "create_all", _fake_create_all)

    ensure_schema()
    ensure_schema()

    assert calls["create_all"] == 0
    assert calls["table_exists"] == 1
