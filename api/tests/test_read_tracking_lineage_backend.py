"""Lineage-backend tests for read_tracking_service — story-protocol-integration R5.

The default backend in test is ``memory`` (fast, isolated). This file
exercises the persistent ``lineage`` backend: each read is written as a
UsageEventRecord row via ``value_lineage_service.add_usage_event``, and
``get_daily_aggregates`` reads back from the same persisted store.

The proof that reads survive a restart: we record events, then dispose
the SQLAlchemy engine (which is what a process restart would do for the
session-side state), re-issue the schema, and confirm the aggregates
still report the same totals from disk.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services import read_tracking_service, value_lineage_service


@pytest.fixture
def _lineage_backend():
    prev = read_tracking_service.current_backend()
    read_tracking_service.use_backend("lineage")
    read_tracking_service._reset_for_tests()
    yield
    read_tracking_service._reset_for_tests()
    read_tracking_service.use_backend(prev)


# ---------------------------------------------------------------------------
# record_read against the lineage backend
# ---------------------------------------------------------------------------

def test_lineage_record_read_persists_to_usage_event(_lineage_backend):
    event = read_tracking_service.record_read(
        "asset-lineage-1", reader_id="reader-a", read_type="free"
    )
    assert event["asset_id"] == "asset-lineage-1"
    # Read back through the persistence layer directly to prove the row exists.
    persisted = value_lineage_service.query_read_events(asset_id="asset-lineage-1")
    assert len(persisted) == 1
    assert persisted[0].asset_id == "asset-lineage-1"
    assert persisted[0].reader_id == "reader-a"
    assert persisted[0].read_type == "free"
    assert persisted[0].source == "read"
    assert persisted[0].lineage_id == "asset:asset-lineage-1"


def test_lineage_record_read_carries_concept_resonance_snapshot(_lineage_backend):
    snapshot = {"lc-space": 0.8, "lc-energy": 0.4}
    read_tracking_service.record_read(
        "asset-lineage-2", reader_id="reader-b", concept_resonance_snapshot=snapshot
    )
    persisted = value_lineage_service.query_read_events(asset_id="asset-lineage-2")
    assert len(persisted) == 1
    assert persisted[0].concept_resonance_snapshot == snapshot


def test_lineage_record_read_carries_paid_payment_token(_lineage_backend):
    read_tracking_service.record_read(
        "asset-lineage-3",
        reader_id="reader-c",
        read_type="paid",
        payment_token="x402:token:xyz",
    )
    persisted = value_lineage_service.query_read_events(asset_id="asset-lineage-3")
    assert persisted[0].read_type == "paid"
    assert persisted[0].payment_token == "x402:token:xyz"
    assert persisted[0].cc_amount == read_tracking_service.DEFAULT_BASE_CC


# ---------------------------------------------------------------------------
# get_daily_aggregates against the lineage backend
# ---------------------------------------------------------------------------

def test_lineage_aggregates_round_trip(_lineage_backend):
    for i in range(4):
        read_tracking_service.record_read(
            "asset-lineage-agg",
            reader_id=f"reader-{i % 2}",
            read_type="free",
        )
    agg = read_tracking_service.get_daily_aggregates()
    assert agg["total"] == 4
    assert agg["unique_readers"] == 2
    assert agg["free_reads"] == 4
    assert agg["paid_reads"] == 0
    assert agg["per_asset"]["asset-lineage-agg"]["total"] == 4


def test_lineage_aggregates_paid_and_free(_lineage_backend):
    read_tracking_service.record_read("asset-mix-lineage", reader_id="r1", read_type="paid")
    read_tracking_service.record_read("asset-mix-lineage", reader_id="r2", read_type="free")
    read_tracking_service.record_read("asset-mix-lineage", reader_id="r3", read_type="paid")
    agg = read_tracking_service.get_daily_aggregates()
    assert agg["paid_reads"] == 2
    assert agg["free_reads"] == 1
    assert agg["total"] == 3


def test_lineage_aggregates_filter_by_asset(_lineage_backend):
    read_tracking_service.record_read("asset-l-a", reader_id="r1")
    read_tracking_service.record_read("asset-l-a", reader_id="r2")
    read_tracking_service.record_read("asset-l-b", reader_id="r1")
    agg = read_tracking_service.get_daily_aggregates(asset_id="asset-l-a")
    assert agg["total"] == 2
    assert set(agg["per_asset"].keys()) == {"asset-l-a"}


# ---------------------------------------------------------------------------
# get_read_events against the lineage backend
# ---------------------------------------------------------------------------

def test_lineage_get_read_events_returns_dicts(_lineage_backend):
    read_tracking_service.record_read("asset-l-evt", reader_id="r1", read_type="free")
    read_tracking_service.record_read("asset-l-evt", reader_id="r2", read_type="paid")
    events = read_tracking_service.get_read_events("asset-l-evt")
    assert len(events) == 2
    # Ordered by capture time (oldest first from the lineage query).
    assert events[0]["reader_id"] == "r1"
    assert events[1]["reader_id"] == "r2"
    assert events[1]["read_type"] == "paid"
    assert isinstance(events[0]["timestamp"], datetime)


# ---------------------------------------------------------------------------
# Restart survival — the load-bearing test for this PR
# ---------------------------------------------------------------------------

def test_lineage_reads_survive_engine_dispose(_lineage_backend):
    """Simulate a process restart by tearing down and rebuilding the SQLA
    engine. Disk state (sqlite file) persists; the lineage-backed event
    log must still surface the events recorded before the dispose.
    """
    from app.services import unified_db

    # Record three reads.
    for i in range(3):
        read_tracking_service.record_read(
            "asset-restart-test",
            reader_id=f"reader-{i}",
            read_type="free",
        )

    pre_agg = read_tracking_service.get_daily_aggregates(asset_id="asset-restart-test")
    assert pre_agg["total"] == 3
    assert pre_agg["unique_readers"] == 3

    # Simulate restart: dispose engine + sessionmaker. The next call to
    # session() rebuilds them against the same database URL.
    unified_db.reset_engine()
    value_lineage_service._R5_COLUMNS_INSTALLED = False  # re-run column probe

    # Fresh engine, same disk. Aggregates must still see the three reads.
    post_agg = read_tracking_service.get_daily_aggregates(asset_id="asset-restart-test")
    assert post_agg["total"] == 3
    assert post_agg["unique_readers"] == 3

    # And direct query of the persistence layer agrees.
    persisted = value_lineage_service.query_read_events(asset_id="asset-restart-test")
    assert len(persisted) == 3


# ---------------------------------------------------------------------------
# Backend toggle plumbing
# ---------------------------------------------------------------------------

def test_use_backend_rejects_unknown():
    with pytest.raises(ValueError):
        read_tracking_service.use_backend("nonsense")


def test_current_backend_reports_state(_lineage_backend):
    assert read_tracking_service.current_backend() == "lineage"
