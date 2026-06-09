"""Analysis tests — silence derivation, daily rollup, uptime %."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pulse_app.analysis import (
    BOUNDARY_REPAIR_PROTOCOL,
    latency_percentiles,
    overall_status,
    overall_status_with_open_silences,
    reconcile_all_silences,
    reconcile_silences,
    rollup_daily,
    status_from_last_sample,
    uptime_percent,
)
from pulse_app.storage import Sample, SilenceRow, Store, iso_utc


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


def test_status_last_sample_slow_is_strained():
    slow_sample = Sample(
        ts=iso_utc(),
        organ="api",
        ok=True,
        latency_ms=3500,
        detail="slow: 3500ms > 2000ms threshold",
    )
    assert status_from_last_sample(slow_sample) == "strained"


def test_status_last_sample_detail_other_than_slow_is_still_breathing():
    weird_sample = Sample(
        ts=iso_utc(),
        organ="api",
        ok=True,
        latency_ms=100,
        detail="some other detail",
    )
    assert status_from_last_sample(weird_sample) == "breathing"


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


def test_rollup_handful_of_failures_in_high_volume_day_is_breathing():
    """A single failure across nearly three thousand probes is honest
    noise, not strain. The witness should not cry wolf when 99.5%+ of
    the day's probes succeeded — the live silence detector already
    surfaces clustered failures via the silences table.
    """
    now = datetime(2026, 4, 15, 23, 59, tzinfo=timezone.utc)
    # 2879 successful samples, 1 failure → 99.965% success.
    samples = [
        Sample(
            ts=f"2026-04-15T{(i // 120) % 24:02d}:{(i % 120) // 2:02d}:{(i % 2) * 30:02d}Z",
            organ="api",
            ok=(i != 1000),
            latency_ms=10,
            detail=None if i != 1000 else "x",
        )
        for i in range(2880)
    ]
    buckets = rollup_daily(samples, days=1, now=now)
    assert buckets[0].samples == 2880
    assert buckets[0].failures == 1
    assert buckets[0].status == "breathing"


def test_rollup_sustained_low_failure_rate_is_still_strained():
    """A 1% failure rate sustained across a high-volume day is real
    strain — it sits above the noise floor.
    """
    now = datetime(2026, 4, 15, 23, 59, tzinfo=timezone.utc)
    # 100 samples, 5 failures = 95% success → below 99.5% breathing floor,
    # well below 50% silent threshold → strained.
    samples = [
        Sample(
            ts=f"2026-04-15T{i // 60:02d}:{i % 60:02d}:00Z",
            organ="api",
            ok=(i % 20 != 0),  # every 20th sample fails → 5/100
            latency_ms=10,
            detail=None,
        )
        for i in range(100)
    ]
    buckets = rollup_daily(samples, days=1, now=now)
    assert buckets[0].samples == 100
    assert buckets[0].failures == 5
    assert buckets[0].status == "strained"


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


def test_reconcile_closes_with_boundary_repair_receipt(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    sid = store.open_silence("api", "2026-04-15T12:00:00Z", "silent")
    for ts in (
        "2026-04-15T12:05:00Z",
        "2026-04-15T12:05:30Z",
        "2026-04-15T12:06:00Z",
    ):
        store.insert_sample(
            Sample(ts=ts, organ="api", ok=True, latency_ms=10, detail=None)
        )

    receipt = reconcile_silences(store, "api")

    assert receipt is not None
    assert receipt.silence_id == sid
    assert receipt.protocol == BOUNDARY_REPAIR_PROTOCOL
    assert receipt.choice == "re_enter"
    assert receipt.ended_at == "2026-04-15T12:05:00Z"
    closed = store.silences_since("2026-04-15T00:00:00Z")[0]
    assert closed.ended_at == "2026-04-15T12:05:00Z"
    assert closed.note is not None
    assert closed.note.startswith(f"{BOUNDARY_REPAIR_PROTOCOL}:")
    assert "3 consecutive breathing samples" in closed.note


def test_reconcile_all_repairs_stale_open_silence_from_samples(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    store.open_silence("api", "2026-04-15T12:00:00Z", "strained")
    for ts in (
        "2026-04-15T12:05:00Z",
        "2026-04-15T12:05:30Z",
        "2026-04-15T12:06:00Z",
    ):
        store.insert_sample(
            Sample(ts=ts, organ="api", ok=True, latency_ms=10, detail=None)
        )

    receipts = reconcile_all_silences(store, ["api", "web"])

    assert [r.organ for r in receipts] == ["api"]
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


def test_reconcile_all_keeps_silence_open_without_enough_reentry_evidence(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    store.open_silence("api", "2026-04-15T12:00:00Z", "strained")
    for ts in ("2026-04-15T12:05:00Z", "2026-04-15T12:05:30Z"):
        store.insert_sample(
            Sample(ts=ts, organ="api", ok=True, latency_ms=10, detail=None)
        )

    receipts = reconcile_all_silences(store, ["api"])

    assert receipts == []
    assert store.ongoing_silence_for_organ("api") is not None


def test_overall_status_with_open_silences_refuses_breathing_contradiction():
    strained = SilenceRow(
        id=1,
        organ="api",
        started_at="2026-04-15T12:00:00Z",
        ended_at=None,
        severity="strained",
        note=None,
    )
    silent = SilenceRow(
        id=2,
        organ="web",
        started_at="2026-04-15T12:01:00Z",
        ended_at=None,
        severity="silent",
        note=None,
    )

    assert overall_status_with_open_silences(["breathing"], []) == "breathing"
    assert overall_status_with_open_silences(["breathing"], [strained]) == "strained"
    assert overall_status_with_open_silences(["breathing"], [silent]) == "silent"
