"""Stones for the substrate write-lane wedge (2026-07-02).

The public write lane wedged three times, each on a long-held
`UPDATE substrate_nodes SET count = ...` — a per-intern read-modify-write of a
hot bookkeeping row that could stall the whole lane for hours. Two stones close
the outage class:

1. DB timeouts (lock_timeout / idle_in_transaction_session_timeout /
   statement_timeout) so no writer hangs — unified_db.POSTGRES_STARTUP_OPTIONS,
   applied to the Postgres engine in _create_engine.
2. An atomic `SET count = count + 1` so the hot row's lock is held for one
   statement, not a Python round-trip — kernel._bump_seen_count. Its correctness
   (count still increments to 2 on re-intern) is already witnessed by
   tests/test_substrate.py::test_intern_node_dedup_returns_same_id.

This file witnesses stone 1: the Postgres engine carries the three GUCs.
"""

from __future__ import annotations

import pytest

from app import main
from app.services import unified_db as udb


def test_postgres_startup_options_carry_the_three_gucs():
    opts = udb.POSTGRES_STARTUP_OPTIONS
    assert "lock_timeout=5000" in opts
    assert "idle_in_transaction_session_timeout=30000" in opts
    assert "statement_timeout=60000" in opts


def test_postgres_branch_passes_the_options_sqlite_does_not(monkeypatch):
    """The Postgres branch of _create_engine passes our GUCs via connect_args;
    the sqlite branch does not (would be invalid). Driver-free: we capture the
    kwargs _create_engine hands to create_engine rather than open a connection
    (psycopg isn't installed in every environment)."""
    captured: dict = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()  # never used; we only inspect the kwargs

    monkeypatch.setattr(udb, "create_engine", fake_create_engine)
    udb._create_engine("postgresql+psycopg://u:p@localhost:5432/db")
    assert captured["kwargs"]["connect_args"]["options"] == udb.POSTGRES_STARTUP_OPTIONS


def test_sqlite_engine_gets_no_postgres_options():
    """The real sqlite engine (driver always present) must not carry the
    Postgres `options` GUCs, which sqlite would reject."""
    sqlite = udb._create_engine("sqlite:///:memory:")
    try:
        assert sqlite.dialect.name == "sqlite"
        # sqlite connect_args are {check_same_thread}, never the postgres options
        args = sqlite.dialect.create_connect_args(sqlite.url)
        for part in args:
            if isinstance(part, dict):
                assert "options" not in part
    finally:
        sqlite.dispose()


def test_postgres_schema_replaces_unbounded_serialized_unique_constraint(monkeypatch):
    """Schema setup migrates the old full-text btree key before ingestion."""
    calls: list[str] = []

    class _Result:
        def mappings(self):
            return self

        def one(self):
            return {"legacy_constraint": True, "digest_index": False}

    class _Connection:
        def execute(self, statement):
            calls.append(str(statement))
            return _Result()

    class _Begin:
        def __enter__(self):
            return _Connection()

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Bind:
        def begin(self):
            return _Begin()

    monkeypatch.setattr(udb.Base.metadata, "create_all", lambda **_kwargs: None)
    udb._create_all_idempotent(bind=_Bind(), url="postgresql://db")

    assert calls[0].strip() == udb.POSTGRES_SUBSTRATE_UNIQUENESS_STATE_SQL.strip()
    assert calls[1:] == list(udb.POSTGRES_SUBSTRATE_UNIQUENESS_DDL)
    assert "DROP CONSTRAINT IF EXISTS uq_substrate_serialized" in calls[1]
    assert "md5(serialized)" in calls[2]


def test_postgres_schema_skips_locking_ddl_after_migration(monkeypatch):
    calls: list[str] = []

    class _Result:
        def mappings(self):
            return self

        def one(self):
            return {"legacy_constraint": False, "digest_index": True}

    class _Connection:
        def execute(self, statement):
            calls.append(str(statement))
            return _Result()

    class _Begin:
        def __enter__(self):
            return _Connection()

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Bind:
        def begin(self):
            return _Begin()

    monkeypatch.setattr(udb.Base.metadata, "create_all", lambda **_kwargs: None)
    udb._create_all_idempotent(bind=_Bind(), url="postgresql://db")

    assert calls == [udb.POSTGRES_SUBSTRATE_UNIQUENESS_STATE_SQL]


def test_sqlite_schema_does_not_run_postgres_substrate_migration(monkeypatch):
    class _Bind:
        def begin(self):
            raise AssertionError("Postgres migration must not run on SQLite")

    monkeypatch.setattr(udb.Base.metadata, "create_all", lambda **_kwargs: None)
    udb._create_all_idempotent(bind=_Bind(), url="sqlite:///:memory:")


def test_postgres_schema_migration_failure_blocks_startup_and_clears_cache(monkeypatch):
    cache = {"url": None, "engine": None, "sessionmaker": None}

    class _Engine:
        disposed = False

        def dispose(self):
            self.disposed = True

    eng = _Engine()
    monkeypatch.setattr(udb, "database_url", lambda: "postgresql://db")
    monkeypatch.setattr(udb, "_normalize_engine_cache", lambda: cache)
    monkeypatch.setattr(udb, "_create_engine", lambda _url: eng)
    monkeypatch.setattr(udb, "sessionmaker", lambda **_kwargs: object())

    def fail_schema(**_kwargs):
        raise RuntimeError("migration lock timeout")

    monkeypatch.setattr(udb, "_create_all_idempotent", fail_schema)

    with pytest.raises(RuntimeError, match="migration lock timeout"):
        udb.engine()

    assert cache == {"url": None, "engine": None, "sessionmaker": None}
    assert eng.disposed is True


def test_lifespan_table_gate_propagates_schema_failure(monkeypatch):
    """The outer startup carrier must not swallow the engine's migration error."""
    def fail_engine():
        raise RuntimeError("migration lock timeout")

    monkeypatch.setattr(udb, "engine", fail_engine)
    with pytest.raises(RuntimeError, match="migration lock timeout"):
        main._ensure_db_tables()
