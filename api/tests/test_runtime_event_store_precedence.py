from __future__ import annotations

import pytest

from app.models.runtime import RuntimeEventCreate
from app.services import runtime_event_store, runtime_service


def test_runtime_db_precedence_over_events_path_when_runtime_database_url_set(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # When a runtime DB is configured, we should still use it even if a JSON file path
    # is configured (the file path is treated as optional/legacy storage).
    monkeypatch.setenv("RUNTIME_DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'runtime.db'}")
    monkeypatch.setenv("RUNTIME_EVENTS_PATH", str(tmp_path / "runtime_events.json"))
    monkeypatch.setenv("RUNTIME_IDEA_MAP_PATH", str(tmp_path / "runtime_idea_map.json"))

    event = runtime_service.record_event(
        RuntimeEventCreate(
            source="api",
            endpoint="/api/health",
            method="GET",
            status_code=200,
            runtime_ms=12.5,
        )
    )

    assert runtime_event_store.enabled() is True

    rows = runtime_event_store.list_events(limit=50)
    assert any(row.id == event.id for row in rows)

