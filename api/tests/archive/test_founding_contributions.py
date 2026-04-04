"""Tests for founding contributions in the ledger."""

from __future__ import annotations

import pytest
from app.services import contribution_ledger_service, unified_db


def _isolate_db(tmp_path, monkeypatch):
    """Point unified_db at a temp SQLite database for test isolation."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'test_founding.db'}")
    unified_db.reset_engine()
    unified_db.ensure_schema()


def test_record_founding_contributions_first_time(tmp_path, monkeypatch):
    """Verify founding contributions are recorded the first time."""
    _isolate_db(tmp_path, monkeypatch)
    
    results = contribution_ledger_service.record_founding_contributions("tester")
    assert len(results) == 4
    
    balance = contribution_ledger_service.get_contributor_balance("tester")
    assert balance["grand_total"] == 170.0 # 28 + 50 + 62 + 30
    assert balance["totals_by_type"]["compute"] == 28.0
    assert balance["totals_by_type"]["direction"] == 50.0
    assert balance["totals_by_type"]["code"] == 62.0
    assert balance["totals_by_type"]["infrastructure"] == 30.0


def test_record_founding_contributions_idempotency(tmp_path, monkeypatch):
    """Verify founding contributions are not recorded twice (idempotency)."""
    _isolate_db(tmp_path, monkeypatch)
    
    # First call
    results1 = contribution_ledger_service.record_founding_contributions("tester")
    assert len(results1) == 4
    
    # Second call
    results2 = contribution_ledger_service.record_founding_contributions("tester")
    assert len(results2) == 0
    
    balance = contribution_ledger_service.get_contributor_balance("tester")
    assert balance["grand_total"] == 170.0 # Remains unchanged
