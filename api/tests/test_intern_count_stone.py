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
    assert sqlite.dialect.name == "sqlite"
    # sqlite connect_args are {check_same_thread}, never the postgres options
    args = sqlite.dialect.create_connect_args(sqlite.url)
    for part in args:
        if isinstance(part, dict):
            assert "options" not in part
