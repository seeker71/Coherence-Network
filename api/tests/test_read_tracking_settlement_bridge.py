"""Tests for the read → render-event bridge.

Closes contract gap #3 from PR #1963: ``record_read`` now materializes
a render event via ``render_attribution_service.log_render_event`` so
settlement (which scans ``app.routers.render_events._EVENTS``) sees
every content read without manual seeding. The four tests here cover:

1. A single read seeds an _EVENTS row with the right asset_id + pool.
2. Concept resonance is accepted through the bridge surface.
3. Multiple reads on the same day aggregate through settlement.
4. A failing bridge does not break read recording.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.routers.render_events import _EVENTS, _reset_events_for_tests
from app.services import (
    read_tracking_service,
    render_attribution_service,
    settlement_service,
)


def _utc_today():
    return datetime.now(timezone.utc).date()


@pytest.fixture(autouse=True)
def _reset():
    read_tracking_service._reset_for_tests()
    _reset_events_for_tests()
    settlement_service._reset_for_tests()
    yield
    read_tracking_service._reset_for_tests()
    _reset_events_for_tests()
    settlement_service._reset_for_tests()


def test_record_read_seeds_render_event():
    """A single record_read call lands one event in _EVENTS with the
    matching asset_id and cc_amount as the pool."""
    read_tracking_service.record_read(
        "asset-bridge-1",
        reader_id="reader-a",
        read_type="paid",
        cc_amount=0.25,
    )

    bridged = [e for e in _EVENTS.values() if e.asset_id == "asset-bridge-1"]
    assert len(bridged) == 1
    ev = bridged[0]
    assert ev.reader_id == "reader-a"
    assert ev.cc_pool == Decimal("0.25")
    # Platform default 80/15/5 split reconciles to the pool.
    assert ev.cc_asset_creator + ev.cc_renderer_creator + ev.cc_host_node == Decimal("0.25")
    assert ev.renderer_id == render_attribution_service.CONTENT_DIRECT_RENDERER_ID


def test_record_read_render_event_carries_reader_through_bridge():
    """The reader id survives the bridge for analytics & uniqueness counts.
    The current RenderEvent shape doesn't surface concept_resonance, but
    the bridge accepts it without raising so the surface stays stable."""
    snapshot = {"lc-land": 0.9, "lc-beauty": 0.1}
    read_tracking_service.record_read(
        "asset-bridge-2",
        reader_id="reader-resonant",
        read_type="paid",
        cc_amount=0.10,
        concept_resonance_snapshot=snapshot,
    )

    bridged = [e for e in _EVENTS.values() if e.asset_id == "asset-bridge-2"]
    assert len(bridged) == 1
    assert bridged[0].reader_id == "reader-resonant"
    assert bridged[0].cc_pool == Decimal("0.10")


def test_settlement_aggregates_reads_after_record_read():
    """Multiple paid reads through record_read feed settlement directly —
    no manual _EVENTS seeding required. This is the loop the e2e PR
    flagged as broken."""
    for i in range(3):
        read_tracking_service.record_read(
            "asset-bridge-3",
            reader_id=f"reader-{i}",
            read_type="paid",
            cc_amount=0.10,
        )

    today = _utc_today()
    events = list(_EVENTS.values())
    batch = settlement_service.run_daily_settlement(
        batch_date=today,
        events=events,
        asset_concept_tags={},
        evidence_multipliers={},
    )

    assert batch.total_read_count == 3
    # 3 reads × 0.10 CC pool = 0.30 CC total (no multiplier)
    assert batch.total_cc_distributed == Decimal("0.30")
    entry = next(e for e in batch.entries if e.asset_id == "asset-bridge-3")
    assert entry.read_count == 3
    assert entry.base_cc_pool == Decimal("0.30")


def test_bridge_failure_does_not_break_record_read(monkeypatch):
    """When the bridge raises, record_read still returns the event dict
    and the read is still appended to the in-memory backend."""
    def _boom(**kwargs):
        raise RuntimeError("simulated bridge failure")

    monkeypatch.setattr(
        render_attribution_service, "log_render_event", _boom
    )

    event = read_tracking_service.record_read(
        "asset-bridge-4",
        reader_id="reader-resilient",
        read_type="free",
    )
    assert event["asset_id"] == "asset-bridge-4"
    assert event["reader_id"] == "reader-resilient"
    # The read is still recorded in the memory backend even though the
    # bridge raised — the loop drops one event for settlement but the
    # read itself stays durable.
    persisted = read_tracking_service.get_read_events("asset-bridge-4")
    assert len(persisted) == 1
    # And no event leaked into _EVENTS because the bridge raised before
    # the insert (the function is monkeypatched at the module level).
    assert not any(e.asset_id == "asset-bridge-4" for e in _EVENTS.values())
