"""Flow tests for read_tracking_service — story-protocol-integration R5 + R6.

Exercises the three named functions the spec's `source:` block claims:
record_read, get_daily_aggregates, compute_cc_flow. The service holds
its event log in a module-level dict; each test starts fresh via the
autouse reset fixture.

The DB-backed counter path is exercised by test_views_and_wallets.py and
test_verification.py; the tests here cover the pure-logic R5+R6 surface.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import pytest

from app.services import read_tracking_service


@pytest.fixture(autouse=True)
def _reset():
    read_tracking_service._reset_for_tests()
    yield
    read_tracking_service._reset_for_tests()


# ---------------------------------------------------------------------------
# record_read
# ---------------------------------------------------------------------------

def test_record_read_returns_event():
    event = read_tracking_service.record_read(
        "asset-001", reader_id="reader-a", read_type="free"
    )
    assert event["asset_id"] == "asset-001"
    assert event["reader_id"] == "reader-a"
    assert event["read_type"] == "free"
    assert event["cc_amount"] == 0.0
    assert event["payment_token"] is None
    assert event["concept_resonance_snapshot"] is None
    assert isinstance(event["timestamp"], datetime)


def test_record_paid_read_includes_payment_token():
    event = read_tracking_service.record_read(
        "asset-002",
        reader_id="reader-b",
        read_type="paid",
        payment_token="x402:token:abc123",
    )
    assert event["read_type"] == "paid"
    assert event["payment_token"] == "x402:token:abc123"
    # Paid reads carry cc_amount = base_cc by default (1.0 placeholder).
    assert event["cc_amount"] == read_tracking_service.DEFAULT_BASE_CC


def test_record_read_carries_concept_resonance_snapshot():
    snapshot = {"lc-space": 0.8, "lc-energy": 0.4}
    event = read_tracking_service.record_read(
        "asset-003",
        reader_id="reader-c",
        concept_resonance_snapshot=snapshot,
    )
    assert event["concept_resonance_snapshot"] == snapshot
    # Returned snapshot is a copy — caller mutations don't leak through.
    snapshot["lc-space"] = 0.1
    log = read_tracking_service.get_read_events("asset-003")
    assert log[0]["concept_resonance_snapshot"]["lc-space"] == 0.8


def test_record_read_back_compat_positional_concept_id():
    # Existing middleware passes (asset_id, concept_id, contributor_id=...).
    event = read_tracking_service.record_read(
        "asset-legacy", "lc-space", contributor_id="reader-d"
    )
    assert event["asset_id"] == "asset-legacy"
    assert event["concept_id"] == "lc-space"
    assert event["reader_id"] == "reader-d"  # contributor_id fell through


# ---------------------------------------------------------------------------
# get_daily_aggregates
# ---------------------------------------------------------------------------

def test_get_daily_aggregates_empty():
    agg = read_tracking_service.get_daily_aggregates()
    assert agg["total"] == 0
    assert agg["unique_readers"] == 0
    assert agg["paid_reads"] == 0
    assert agg["free_reads"] == 0
    assert agg["per_asset"] == {}


def test_get_daily_aggregates_after_reads():
    for i in range(5):
        reader = f"reader-{i % 3}"  # 3 unique readers across 5 reads
        read_tracking_service.record_read(
            "asset-x", reader_id=reader, read_type="free"
        )
    agg = read_tracking_service.get_daily_aggregates()
    assert agg["total"] == 5
    assert agg["unique_readers"] == 3
    assert agg["free_reads"] == 5
    assert agg["paid_reads"] == 0
    assert agg["per_asset"]["asset-x"]["total"] == 5
    assert agg["per_asset"]["asset-x"]["unique_readers"] == 3


def test_get_daily_aggregates_counts_paid_and_free_separately():
    read_tracking_service.record_read("asset-mix", reader_id="r1", read_type="paid")
    read_tracking_service.record_read("asset-mix", reader_id="r2", read_type="free")
    read_tracking_service.record_read("asset-mix", reader_id="r3", read_type="paid")
    agg = read_tracking_service.get_daily_aggregates()
    assert agg["paid_reads"] == 2
    assert agg["free_reads"] == 1
    assert agg["total"] == 3


def test_get_daily_aggregates_filters_by_date():
    read_tracking_service.record_read("asset-y", reader_id="r1")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
    agg = read_tracking_service.get_daily_aggregates(date=yesterday)
    assert agg["total"] == 0
    assert agg["unique_readers"] == 0


def test_get_daily_aggregates_filters_by_asset():
    read_tracking_service.record_read("asset-a", reader_id="r1")
    read_tracking_service.record_read("asset-a", reader_id="r2")
    read_tracking_service.record_read("asset-b", reader_id="r1")
    agg = read_tracking_service.get_daily_aggregates(asset_id="asset-a")
    assert agg["total"] == 2
    assert set(agg["per_asset"].keys()) == {"asset-a"}
    assert agg["per_asset"]["asset-a"]["unique_readers"] == 2


def test_get_daily_aggregates_asset_filter_returns_zero_entry_when_unknown():
    agg = read_tracking_service.get_daily_aggregates(asset_id="never-seen")
    assert agg["total"] == 0
    assert agg["per_asset"]["never-seen"]["total"] == 0


# ---------------------------------------------------------------------------
# compute_cc_flow
# ---------------------------------------------------------------------------

def test_compute_cc_flow_distributes_by_concept_weight():
    # Asset tagged with two concepts; one reader with a resonance profile.
    asset_weights = {"c1": 0.8, "c2": 0.2}
    reader_weights = {"reader-1": {"c1": 1.0, "c2": 0.5}}
    reads = [{"reader_id": "reader-1"}]

    flow = read_tracking_service.compute_cc_flow(
        "asset-1", reads, asset_weights, reader_weights, base_cc=1.0
    )
    assert flow["asset_id"] == "asset-1"
    assert flow["reader_count"] == 1
    # c1: 1.0 * 0.8 * 1.0 = 0.8 ; c2: 1.0 * 0.2 * 0.5 = 0.1
    assert flow["per_concept"]["c1"] == pytest.approx(0.8)
    assert flow["per_concept"]["c2"] == pytest.approx(0.1)
    assert flow["total_cc"] == pytest.approx(0.9)


def test_compute_cc_flow_multiple_readers_sums():
    asset_weights = {"c1": 0.5}
    reader_weights = {
        "r1": {"c1": 1.0},
        "r2": {"c1": 1.0},
        "r3": {"c1": 1.0},
    }
    reads = [{"reader_id": "r1"}, {"reader_id": "r2"}, {"reader_id": "r3"}]
    flow = read_tracking_service.compute_cc_flow(
        "asset-2", reads, asset_weights, reader_weights, base_cc=1.0
    )
    # Single reader would contribute 0.5; three readers → 1.5.
    assert flow["per_concept"]["c1"] == pytest.approx(1.5)
    assert flow["reader_count"] == 3


def test_compute_cc_flow_handles_zero_reader_weight():
    asset_weights = {"c1": 1.0}
    # Reader has no resonance for the asset's concepts.
    reader_weights = {"r1": {"c-other": 1.0}}
    reads = [{"reader_id": "r1"}]
    flow = read_tracking_service.compute_cc_flow(
        "asset-3", reads, asset_weights, reader_weights
    )
    assert flow["total_cc"] == 0.0
    assert flow["per_concept"]["c1"] == 0.0


def test_compute_cc_flow_dedupes_repeat_reads_by_reader():
    # The same reader visiting twice should count once for CC weighting —
    # multi-read CC scaling is settlement's job, not this function's.
    asset_weights = {"c1": 1.0}
    reader_weights = {"r1": {"c1": 1.0}}
    reads = [{"reader_id": "r1"}, {"reader_id": "r1"}, {"reader_id": "r1"}]
    flow = read_tracking_service.compute_cc_flow(
        "asset-4", reads, asset_weights, reader_weights, base_cc=1.0
    )
    assert flow["reader_count"] == 1
    assert flow["per_concept"]["c1"] == pytest.approx(1.0)


def test_compute_cc_flow_skips_anonymous_readers():
    asset_weights = {"c1": 1.0}
    reader_weights = {"r1": {"c1": 1.0}}
    reads = [
        {"reader_id": "r1"},
        {"reader_id": None},
        {"reader_id": None},
    ]
    flow = read_tracking_service.compute_cc_flow(
        "asset-5", reads, asset_weights, reader_weights, base_cc=1.0
    )
    assert flow["reader_count"] == 1
    assert flow["per_concept"]["c1"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# non-blocking budget — spec constraint <50ms per read
# ---------------------------------------------------------------------------

def test_record_read_is_non_blocking():
    # 200 reads back-to-back should land well under a second on any
    # reasonable machine. The spec constraint is per-read <50ms; this
    # exercises the aggregate to catch accidental O(n^2) regressions.
    start = time.perf_counter()
    for i in range(200):
        read_tracking_service.record_read(
            f"asset-{i % 10}",
            reader_id=f"reader-{i % 50}",
            read_type="free",
        )
    elapsed = time.perf_counter() - start
    # 200 reads in under 2 seconds is the loose ceiling; real budget is
    # tighter but DB-backed best-effort writes can add overhead in CI.
    assert elapsed < 2.0
