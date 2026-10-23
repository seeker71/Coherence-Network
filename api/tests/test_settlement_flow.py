"""Tests for the settlement service — story-protocol-integration R8.

Service-level tests exercise the pure aggregation logic in isolation
with crafted RenderEvent fixtures; the read-tracking bridge and the
federation value-flow proofs exercise the stores around it.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from app.models.renderer import RenderEvent
from app.services import settlement_service
from app.services.story_protocol_bridge import AssetConceptTag


def _event(
    asset_id: str,
    *,
    day: date = date(2026, 4, 24),
    duration_ms: int = 10000,
    asset_share: Decimal = Decimal("0.80"),
    renderer_share: Decimal = Decimal("0.15"),
    host_share: Decimal = Decimal("0.05"),
) -> RenderEvent:
    pool = Decimal(duration_ms) * Decimal("0.00001")
    return RenderEvent(
        asset_id=asset_id,
        renderer_id="r1",
        reader_id="u1",
        timestamp=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc),
        duration_ms=duration_ms,
        cc_pool=pool,
        cc_asset_creator=pool * asset_share,
        cc_renderer_creator=pool * renderer_share,
        cc_host_node=pool * host_share,
    )


# ---------- service-level ----------


def test_empty_events_produces_empty_batch():
    batch = settlement_service.run_daily_settlement(
        batch_date=date(2026, 4, 24),
        events=[],
        asset_concept_tags={},
        evidence_multipliers={},
    )
    assert batch.entries == []
    assert batch.total_read_count == 0
    assert batch.total_cc_distributed == Decimal("0")


def test_single_asset_single_event_no_multiplier():
    events = [_event("asset:a1", duration_ms=15000)]
    batch = settlement_service.run_daily_settlement(
        batch_date=date(2026, 4, 24),
        events=events,
        asset_concept_tags={},
        evidence_multipliers={},
    )
    assert len(batch.entries) == 1
    entry = batch.entries[0]
    assert entry.asset_id == "asset:a1"
    assert entry.read_count == 1
    # base_pool = 15000 * 0.00001 = 0.15
    assert entry.base_cc_pool == Decimal("0.15000")
    assert entry.evidence_multiplier == Decimal("1")
    assert entry.effective_cc_pool == Decimal("0.15000")
    # default 80/15/5
    assert entry.cc_to_asset_creator == Decimal("0.120000")
    assert entry.cc_to_renderer_creators == Decimal("0.022500")
    assert entry.cc_to_host_nodes == Decimal("0.007500")


def test_evidence_multiplier_applies():
    events = [_event("asset:a2", duration_ms=10000)]
    batch = settlement_service.run_daily_settlement(
        batch_date=date(2026, 4, 24),
        events=events,
        asset_concept_tags={},
        evidence_multipliers={"asset:a2": Decimal("5")},
    )
    entry = batch.entries[0]
    assert entry.evidence_multiplier == Decimal("5")
    # base pool 0.10 × 5 = 0.50
    assert entry.effective_cc_pool == Decimal("0.50000")
    # asset share: 0.10 × 0.80 × 5 = 0.40
    assert entry.cc_to_asset_creator == Decimal("0.400000")


def test_events_off_batch_date_excluded():
    events = [
        _event("asset:today", day=date(2026, 4, 24)),
        _event("asset:yesterday", day=date(2026, 4, 23)),
    ]
    batch = settlement_service.run_daily_settlement(
        batch_date=date(2026, 4, 24),
        events=events,
        asset_concept_tags={},
        evidence_multipliers={},
    )
    assert [e.asset_id for e in batch.entries] == ["asset:today"]


def test_multiple_events_same_asset_aggregate():
    events = [
        _event("asset:a1", duration_ms=5000),
        _event("asset:a1", duration_ms=5000),
        _event("asset:a1", duration_ms=5000),
    ]
    batch = settlement_service.run_daily_settlement(
        batch_date=date(2026, 4, 24),
        events=events,
        asset_concept_tags={},
        evidence_multipliers={},
    )
    assert len(batch.entries) == 1
    assert batch.entries[0].read_count == 3
    # 3 × 0.05 = 0.15
    assert batch.entries[0].base_cc_pool == Decimal("0.15000")


def test_concept_pools_split_by_weight():
    events = [_event("asset:a1", duration_ms=10000)]
    tags = [
        AssetConceptTag(concept_id="lc-land", weight=0.8),
        AssetConceptTag(concept_id="lc-beauty", weight=0.2),
    ]
    batch = settlement_service.run_daily_settlement(
        batch_date=date(2026, 4, 24),
        events=events,
        asset_concept_tags={"asset:a1": tags},
        evidence_multipliers={},
    )
    entry = batch.entries[0]
    # asset_creator share = 0.10 × 0.80 = 0.08; split 0.8/0.2 by weight_sum 1.0
    # → 0.064 to lc-land, 0.016 to lc-beauty
    pools = {p.concept_id: p.cc_amount for p in entry.concept_pools}
    assert pools["lc-land"] == Decimal("0.064000")
    assert pools["lc-beauty"] == Decimal("0.016000")
    assert sum(pools.values()) == entry.cc_to_asset_creator


def test_no_concept_tags_produces_uncategorized_pool():
    events = [_event("asset:a1", duration_ms=10000)]
    batch = settlement_service.run_daily_settlement(
        batch_date=date(2026, 4, 24),
        events=events,
        asset_concept_tags={},
        evidence_multipliers={},
    )
    entry = batch.entries[0]
    assert len(entry.concept_pools) == 1
    assert entry.concept_pools[0].concept_id == "uncategorized"


def test_totals_roll_up_across_assets():
    events = [
        _event("asset:a", duration_ms=10000),
        _event("asset:b", duration_ms=20000),
    ]
    batch = settlement_service.run_daily_settlement(
        batch_date=date(2026, 4, 24),
        events=events,
        asset_concept_tags={},
        evidence_multipliers={},
    )
    assert batch.total_read_count == 2
    assert batch.total_cc_distributed == Decimal("0.30000")
