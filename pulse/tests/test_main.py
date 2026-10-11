"""Pulse route tests for read-time silence repair."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import sys
import types

import pytest


if "apscheduler.schedulers.asyncio" not in sys.modules:
    apscheduler = types.ModuleType("apscheduler")
    schedulers = types.ModuleType("apscheduler.schedulers")
    async_scheduler = types.ModuleType("apscheduler.schedulers.asyncio")
    triggers = types.ModuleType("apscheduler.triggers")
    interval = types.ModuleType("apscheduler.triggers.interval")

    class _AsyncIOScheduler:
        def __init__(self, *args, **kwargs):
            pass

        def add_job(self, *args, **kwargs):
            pass

        def start(self):
            pass

        def shutdown(self, wait=False):
            pass

    class _IntervalTrigger:
        def __init__(self, *args, **kwargs):
            pass

    async_scheduler.AsyncIOScheduler = _AsyncIOScheduler
    interval.IntervalTrigger = _IntervalTrigger
    sys.modules.setdefault("apscheduler", apscheduler)
    sys.modules.setdefault("apscheduler.schedulers", schedulers)
    sys.modules.setdefault("apscheduler.schedulers.asyncio", async_scheduler)
    sys.modules.setdefault("apscheduler.triggers", triggers)
    sys.modules.setdefault("apscheduler.triggers.interval", interval)

from pulse_app.main import app, pulse_history, pulse_now
from pulse_app.storage import Sample, Store, iso_utc


@pytest.mark.asyncio
async def test_pulse_now_repairs_stale_open_silence_before_response(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    now = datetime.now(timezone.utc)
    started_at = iso_utc(now - timedelta(minutes=5))
    sample_times = [
        iso_utc(now - timedelta(seconds=60)),
        iso_utc(now - timedelta(seconds=30)),
        iso_utc(now),
    ]
    store.open_silence("api", started_at, "silent")
    for ts in sample_times:
        store.insert_sample(
            Sample(ts=ts, organ="api", ok=True, latency_ms=10, detail=None)
        )

    app.state.store = store
    app.state.started_at = now - timedelta(minutes=10)

    response = await pulse_now()

    assert response.overall == "breathing"
    assert response.ongoing_silences == []
    closed = store.silences_since("2026-04-15T00:00:00Z")[0]
    assert closed.ended_at == sample_times[0]
    assert closed.note is not None
    assert closed.note.startswith("boundary_repair_protocol:")


@pytest.mark.asyncio
async def test_pulse_now_keeps_open_silence_strained_without_reentry_evidence(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    now = datetime.now(timezone.utc)
    store.open_silence("api", iso_utc(now - timedelta(seconds=60)), "strained")
    for ts in (iso_utc(now - timedelta(seconds=30)), iso_utc(now)):
        store.insert_sample(
            Sample(ts=ts, organ="api", ok=True, latency_ms=10, detail=None)
        )

    app.state.store = store
    app.state.started_at = now - timedelta(minutes=10)

    response = await pulse_now()

    assert response.overall == "strained"
    assert len(response.ongoing_silences) == 1
    assert response.ongoing_silences[0].organ == "api"


@pytest.mark.asyncio
async def test_pulse_now_exposes_successful_strain_detail(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    now = datetime.now(timezone.utc)
    detail = "slow: 4691ms > 2000ms threshold"
    store.insert_sample(
        Sample(
            ts=iso_utc(now),
            organ="web",
            ok=True,
            latency_ms=4691,
            detail=detail,
        )
    )

    app.state.store = store
    app.state.started_at = now - timedelta(minutes=10)

    response = await pulse_now()

    web = next(organ for organ in response.organs if organ.name == "web")
    assert response.overall == "strained"
    assert web.status == "strained"
    assert web.detail == detail


@pytest.mark.asyncio
async def test_pulse_history_omits_unobserved_only_organs_from_overall(tmp_path):
    store = Store(str(tmp_path / "pulse.db"))
    now = datetime.now(timezone.utc)
    timestamp = iso_utc(now)
    store.insert_sample(
        Sample(ts=timestamp, organ="api", ok=True, latency_ms=10, detail=None)
    )
    for organ in ("schema", "audit_integrity"):
        store.insert_sample(
            Sample(
                ts=timestamp,
                organ=organ,
                ok=True,
                latency_ms=10,
                detail="unobserved: bounded proof omitted",
            )
        )

    app.state.store = store

    response = await pulse_history(days=1)

    assert response.overall.uptime_pct == 100.0
    assert response.overall.worst_uptime_pct == 100.0
    assert response.overall.worst_organ is None
