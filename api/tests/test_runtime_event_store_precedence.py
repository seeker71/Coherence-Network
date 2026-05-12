"""Regression tests for runtime telemetry DB precedence.

The runtime-telemetry-db-precedence spec exists because the public
deploy contract once turned amber when a database was configured but
the runtime events path was *also* set: the dual-config made the
runtime backend route to a JSON file even though a DB was available,
and `GET /api/health/persistence` flagged the file-routing as a
contract miss.

The fix is precedence: when ``database_overrides.runtime`` is set,
the DB wins over ``runtime.events_path``. These tests pin the
precedence directly against the surface that decides it
(``runtime_event_store.enabled()`` and ``backend_info()``), so a
future config change can't silently re-flip the order without a
failing test.

Source under test:
    api/app/services/runtime_event_store.py::enabled, backend_info
Spec: specs/runtime-telemetry-db-precedence.md
"""

from __future__ import annotations

import pytest

from app.services import runtime_event_store


@pytest.fixture(autouse=True)
def _reset_engine_cache():
    """Wipe the module-level engine cache so each test starts clean.

    runtime_event_store caches the engine + sessionmaker between calls,
    keyed by the resolved database URL. When config changes between
    tests, the cache could otherwise hand back a stale engine pointed
    at the wrong URL. We don't actually need the engine to *work*
    (these tests only exercise enabled/backend_info, which read config
    directly), but clearing the cache keeps the precedence assertion
    pure to the config-resolution path.
    """
    runtime_event_store._ENGINE_CACHE["engine"] = None
    runtime_event_store._ENGINE_CACHE["sessionmaker"] = None
    runtime_event_store._ENGINE_CACHE["url"] = ""
    runtime_event_store._SCHEMA_INITIALIZED = False
    runtime_event_store._SCHEMA_INITIALIZED_URL = ""
    yield
    runtime_event_store._ENGINE_CACHE["engine"] = None
    runtime_event_store._ENGINE_CACHE["sessionmaker"] = None
    runtime_event_store._ENGINE_CACHE["url"] = ""
    runtime_event_store._SCHEMA_INITIALIZED = False
    runtime_event_store._SCHEMA_INITIALIZED_URL = ""


def _clear_telemetry_config(set_config):
    """Default-empty state for the keys this spec touches."""
    set_config("database_overrides", "runtime", "")
    set_config("runtime", "events_path", "")
    set_config("database", "url", "")


# ── enabled() — the precedence gate ──────────────────────────────


def test_enabled_db_override_wins_when_events_path_also_set(set_config):
    """Spec R1: when a runtime DB URL is configured, telemetry events
    must land in the database even if events_path is *also* set."""
    _clear_telemetry_config(set_config)
    set_config("database_overrides", "runtime", "sqlite:///tmp/runtime-prec.db")
    set_config("runtime", "events_path", "/tmp/runtime-prec.json")

    assert runtime_event_store.enabled() is True, (
        "DB override must take precedence over events_path"
    )


def test_enabled_events_path_only_routes_to_file(set_config):
    """When only events_path is set (no DB override, no fallback URL),
    the file backend is the chosen path — enabled() returns False."""
    _clear_telemetry_config(set_config)
    set_config("runtime", "events_path", "/tmp/runtime-events-only.json")

    assert runtime_event_store.enabled() is False, (
        "No DB anywhere, file path set: store must report disabled"
    )


def test_enabled_db_override_only(set_config):
    """DB override set, no events_path — enabled() returns True."""
    _clear_telemetry_config(set_config)
    set_config("database_overrides", "runtime", "sqlite:///tmp/runtime-only.db")

    assert runtime_event_store.enabled() is True


def test_enabled_neither_set(set_config):
    """Nothing configured for runtime persistence — enabled() False."""
    _clear_telemetry_config(set_config)

    assert runtime_event_store.enabled() is False


# ── backend_info() — what the health contract sees ────────────────


def test_backend_info_db_override_reports_sqlite_not_file(set_config):
    """When the DB wins precedence, backend_info must say so honestly.

    This is the surface GET /api/health/persistence reads. The
    previous bug surfaced here: backend reported "file" because the
    file branch ran before the override check. Pin "sqlite" / "postgresql"
    (depending on URL scheme) — never "file" — when an override URL
    is set, regardless of events_path also being set.
    """
    _clear_telemetry_config(set_config)
    set_config("database_overrides", "runtime", "sqlite:///tmp/runtime-info.db")
    set_config("runtime", "events_path", "/tmp/runtime-info.json")

    info = runtime_event_store.backend_info()
    assert info["enabled"] is True
    assert info["backend"] == "sqlite", (
        f"backend must report 'sqlite' when DB override wins, got {info['backend']!r}"
    )
    # The URL shows up redacted but non-empty for the contract.
    assert info["database_url"], "DB URL must be present in backend_info when override is set"
    # The events_path is noted but does not change the backend choice.
    assert info["events_file_override"] is True


def test_backend_info_db_override_reports_postgresql(set_config):
    """Same precedence, postgres URL scheme — backend reports 'postgresql'."""
    _clear_telemetry_config(set_config)
    set_config(
        "database_overrides",
        "runtime",
        "postgresql://user:pass@host:5432/coherence_runtime",
    )
    set_config("runtime", "events_path", "/tmp/runtime-pg-info.json")

    info = runtime_event_store.backend_info()
    assert info["enabled"] is True
    assert info["backend"] == "postgresql"


def test_backend_info_events_path_only_reports_file(set_config):
    """When file path wins (no DB anywhere), backend says 'file'."""
    _clear_telemetry_config(set_config)
    set_config("runtime", "events_path", "/tmp/runtime-file-only.json")

    info = runtime_event_store.backend_info()
    assert info["enabled"] is False
    assert info["backend"] == "file"
    assert info["events_file_override"] is True


def test_backend_info_nothing_set_reports_none(set_config):
    """No DB, no events_path — backend is honest: 'none'."""
    _clear_telemetry_config(set_config)

    info = runtime_event_store.backend_info()
    assert info["enabled"] is False
    assert info["backend"] == "none"
    assert info["database_url"] == ""
    assert info["events_file_override"] is False
