"""Analysis tests — silence derivation, daily rollup, uptime %."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pulse_app.analysis import (
    latency_percentiles,
    overall_status,
    reconcile_silences,
    rollup_daily,
    status_from_last_sample,
    uptime_percent,
)
from pulse_app.storage import Sample, Store, iso_utc


def _s(organ: str, ok: bool, minutes_ago: int) -> Sample:
    dt = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return Sample(
        ts=iso_utc(dt),
        organ=organ,
        ok=ok,
        latency_ms=10,
        detail=None if ok else "fail",
    )


# --- uptime percent -------------------------------------------------------

def test_uptime_percent_all_ok():
    samples = [_s("api", True, m) for m in (5, 4, 3, 2, 1)]
    assert uptime_percent(samples) == 100.0


def test_uptime_percent_all_bad():
    samples = [_s("api", False, m) for m in (5, 4, 3, 2, 1)]
    assert uptime_percent(samples) == 0.0


def test_uptime_percent_mixed():
    samples = [_s("api", True, 5), _s("api", True, 4), _s("api", False, 3), _s("api", True, 2)]
    assert uptime_percent(samples) == 75.0


def test_uptime_percent_empty():
    assert uptime_percent([]) == 0.0


# --- status_from_last_sample ---------------------------------------------

def test_status_last_sample_none_is_unknown():
    assert status_from_last_sample(None) == "unknown"


def test_status_last_sample_ok():
    assert status_from_last_sample(_s("api", True, 0)) == "breathing"


def test_status_last_sample_bad():
    assert status_from_last_sample(_s("api", False, 0)) == "silent"


# --- overall_status -------------------------------------------------------

def test_overall_all_breathing():
    assert overall_status(["breathing", "breathing", "breathing"]) == "breathing"


def test_overall_one_silent():
    assert overall_status(["breathing", "silent", "breathing"]) == "silent"


def test_overall_one_strained_no_silent():
    assert overall_status(["breathing", "strained", "breathing"]) == "strained"


def test_overall_all_unknown():
    assert overall_status(["unknown", "unknown"]) == "unknown"


def test_overall_empty():
    assert overall_status([]) == "unknown"


# --- daily rollup ---------------------------------------------------------

def test_rollup_produces_requested_day_count():
    now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
    samples: list[Sample] = []
    buckets = rollup_daily(samples, days=7, now=now)
    assert len(buckets) == 7
    # Dates are chronological, ending on today.
    dates = [b.date for b in buckets]
    assert dates == sorted(dates)
    assert dates[-1] == "2026-04-15"


def test_rollup_counts_samples_and_failures():
    now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
    # Today: 2 ok, 1 bad. Yesterday: 1 ok.
    samples = [
        Sample(ts="2026-04-15T10:00:00Z", organ="api", ok=True, latency_ms=10, detail=None),
        Sample(ts="2026-04-15T11:00:00Z", organ="api", ok=True, latency_ms=10, detail=None),
        Sample(ts="2026-04-15T11:30:00Z", organ="api", ok=False, latency_ms=10, detail="x"),
        Sample(ts="2026-04-14T09:00:00Z", organ="api", ok=True, latency_ms=10, detail=None),
    ]
    buckets = rollup_daily(samples, days=2, now=now)
    by_date = {b.date: b for b in buckets}
    assert by_date["2026-04-14"].samples == 1
    assert by_date["2026-04-14"].failures == 0
    assert by_date["2026-04-14"].status == "breathing"
    assert by_date["2026-04-15"].samples == 3
    assert by_date["2026-04-15"].failures == 1
    # 1/3 failures < half, so strained not silent.
    assert by_date["2026-04-15"].status == "strained"


def test_rollup_empty_days_are_unknown():
    now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
    buckets = rollup_daily([], days=3, now=now)
    for b in buckets:
        assert b.status == "unknown"
        assert b.samples == 0


def test_rollup_half_or_more_failures_is_silent():
    now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
    samples = [
        Sample(ts="2026-04-15T09:00:00Z", organ="api", ok=False, latency_ms=10, detail="x"),
        Sample(ts="2026-04-15T10:00:00Z", organ="api", ok=False, latency_ms=10, detail="x"),
        Sample(ts="2026-04-15T11:00:00Z", organ="api", ok=True, latency_ms=10, detail=None),
    ]
    buckets = rollup_daily(samples, days=1, now=now)
    assert buckets[0].status == "silent"


# --- latency aggregation -------------------------------------------------

def test_rollup_computes_latency_percentiles_on_successful_samples():
    now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
    # 10 successful samples today with latencies 10..100 (step 10)
    samples = [
        Sample(ts=f"2026-04-15T{hour:02d}:00:00Z", organ="api", ok=True,
               latency_ms=(hour + 1) * 10, detail=None)
        for hour in range(10)
    ]
    buckets = rollup_daily(samples, days=1, now=now)
    b = buckets[0]
    assert b.samples == 10
    assert b.failures == 0
    # Nearest-rank p50 on a sorted 10-element list = 5th element (10, 20, 30, 40, 50)
    assert b.latency_p50_ms == 50
    # p95 on a 10-element list = ceil(.95*10)=10th element = 100
    assert b.latency_p95_ms == 100


def test_rollup_latency_ignores_failed_samples():
    now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
    # 3 ok latencies (100, 200, 300), 2 failed with very high latencies
    samples = [
        Sample(ts="2026-04-15T09:00:00Z", organ="api", ok=True, latency_ms=100, detail=None),
        Sample(ts="2026-04-15T10:00:00Z", organ="api", ok=True, latency_ms=200, detail=None),
        Sample(ts="2026-04-15T11:00:00Z", organ="api", ok=True, latency_ms=300, detail=None),
        Sample(ts="2026-04-15T12:00:00Z", organ="api", ok=False, latency_ms=9999, detail="timeout"),
        Sample(ts="2026-04-15T13:00:00Z", organ="api", ok=False, latency_ms=9999, detail="timeout"),
    ]
    buckets = rollup_daily(samples, days=1, now=now)
    b = buckets[0]
    # Percentiles come from the ok samples only, not the failures
    assert b.latency_p50_ms == 200
    assert b.latency_p95_ms == 300


def test_rollup_latency_none_when_no_successes():
    now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
    samples = [
        Sample(ts="2026-04-15T09:00:00Z", organ="api", ok=False, latency_ms=10, detail="x"),
    ]
    buckets = rollup_daily(samples, days=1, now=now)
    assert buckets[0].latency_p50_ms is None
    assert buckets[0].latency_p95_ms is None


def test_rollup_latency_none_for_empty_day():
    now = datetime(2026, 4, 15, 12, 0, tzinfo=timezone.utc)
    buckets = rollup_daily([], days=3, now=now)
    for b in buckets:
        assert b.latency_p50_ms is None
        assert b.latency_p95_ms is None


def test_latency_percentiles_window():
    samples = [
        Sample(ts="2026-04-15T09:00:00Z", organ="api", ok=True, latency_ms=100, detail=None),
        Sample(ts="2026-04-15T10:00:00Z", organ="api", ok=True, latency_ms=200, detail=None),
        Sample(ts="2026-04-15T11:00:00Z", organ="api", ok=True, latency_ms=300, detail=None),
        Sample(ts="2026-04-15T12:00:00Z", organ="api", ok=True, latency_ms=400, detail=None),
    ]
    p50, p95 = latency_percentiles(samples)
    assert p50 == 200  # ceil(.5*4)=2nd element = 200
    assert p95 == 400  # ceil(.95*4)=4th element = 400


def test_latency_percentiles_empty():
    assert latency_percentiles([]) == (None, None)


# --- reconcile_silences ---------------------------------------------------

def test_reconcile_opens_silence_after_three_failures(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    # Insert 3 consecutive failures, no prior history.
    for m in (3, 2, 1):
        store.insert_sample(_s("api", False, m))
    reconcile_silences(store, "api")
    ongoing = store.ongoing_silence_for_organ("api")
    assert ongoing is not None
    assert ongoing.severity == "strained"


def test_reconcile_does_not_open_on_two_failures(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    for m in (2, 1):
        store.insert_sample(_s("api", False, m))
    reconcile_silences(store, "api")
    assert store.ongoing_silence_for_organ("api") is None


def test_reconcile_closes_silence_after_three_successes(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    # First open a silence.
    for m in (10, 9, 8):
        store.insert_sample(_s("api", False, m))
    reconcile_silences(store, "api")
    assert store.ongoing_silence_for_organ("api") is not None
    # Now a clean run.
    for m in (3, 2, 1):
        store.insert_sample(_s("api", True, m))
    reconcile_silences(store, "api")
    assert store.ongoing_silence_for_organ("api") is None


def test_reconcile_single_success_does_not_close(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    for m in (10, 9, 8):
        store.insert_sample(_s("api", False, m))
    reconcile_silences(store, "api")
    # Only one success — not enough.
    store.insert_sample(_s("api", True, 1))
    reconcile_silences(store, "api")
    assert store.ongoing_silence_for_organ("api") is not None
