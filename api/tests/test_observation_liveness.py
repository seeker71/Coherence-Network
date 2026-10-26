"""Concurrent liveness while the compatibility carrier observes a request."""
from __future__ import annotations

import asyncio
import threading

import pytest

from app.middleware.serialized_observation import SerializedObservation
import httpx
from fastapi import FastAPI


def _run_while_blocked(app, path, entered, release):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            observed = asyncio.create_task(client.get(path))
            try:
                assert await asyncio.to_thread(entered.wait, 3), "observer did not enter"
                assert not observed.done(), "observer blocked the event loop until its wait expired"
                ping = await asyncio.wait_for(client.get("/api/ping"), 1)
                assert ping.status_code == 200
                assert not release.is_set()
                assert not observed.done(), "observation must still be awaited"
            finally:
                release.set()
                response = await asyncio.wait_for(observed, 3)
            assert response.status_code == 200
    asyncio.run(run())


def _app():
    app = FastAPI()
    @app.get("/api/ping")
    async def ping():
        return {"pong": True}
    @app.get("/api/concepts/lc-synthetic")
    async def concept():
        return {"id": "lc-synthetic"}
    return app


def test_slow_read_promotion_yields_and_preserves_the_view(monkeypatch):
    from app.middleware import read_tracking as sensing
    from app.services import read_tracking_service
    entered, release = threading.Event(), threading.Event()
    writes = []
    def promote(asset_id):
        entered.set()
        release.wait(3)
    monkeypatch.setattr(sensing, "_maybe_promote", promote)
    monkeypatch.setattr(sensing, "_SENSING_WORK", SerializedObservation())
    monkeypatch.setattr(sensing, "_asset_tiers", {})
    monkeypatch.setattr(read_tracking_service, "record_view", lambda **row: writes.append(row))
    app = _app()
    app.add_middleware(sensing.ReadTrackingMiddleware)
    _run_while_blocked(app, "/api/concepts/lc-synthetic", entered, release)
    assert len(writes) == 1
    assert writes[0]["asset_id"] == "lc-synthetic"


def test_slow_runtime_write_yields_and_keeps_ping_independent(monkeypatch, set_config):
    from app import main
    entered, release = threading.Event(), threading.Event()
    writes = []
    def record(payload):
        entered.set()
        release.wait(3)
        writes.append(payload)
    set_config("runtime", "telemetry_enabled", True)
    monkeypatch.setattr(main, "_RUNTIME_CAPTURE_WORK", SerializedObservation())
    monkeypatch.setattr(main, "_record_or_aggregate_runtime_event", lambda payload: [payload])
    monkeypatch.setattr(main.runtime_service, "record_event", record)
    app = _app()
    app.middleware("http")(main.capture_runtime_metrics)
    _run_while_blocked(app, "/api/concepts/lc-synthetic", entered, release)
    assert len(writes) == 1
    assert writes[0].endpoint == "/api/concepts/lc-synthetic"


def test_read_observers_remain_serialized(monkeypatch):
    from app.middleware import read_tracking as sensing
    entered, release = threading.Event(), threading.Event()
    calls = []
    def sense(*args):
        calls.append(threading.get_ident())
        entered.set()
        release.wait(3)
    monkeypatch.setattr(sensing, "_sense_read", sense)
    monkeypatch.setattr(sensing, "_SENSING_WORK", SerializedObservation())
    app = _app()
    app.add_middleware(sensing.ReadTrackingMiddleware)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            tasks = [asyncio.create_task(client.get("/api/concepts/lc-synthetic")) for _ in range(2)]
            try:
                assert await asyncio.to_thread(entered.wait, 3)
                assert (await asyncio.wait_for(client.get("/api/ping"), 1)).status_code == 200
                assert len(calls) == 1
            finally:
                release.set()
                responses = await asyncio.gather(*tasks)
            assert all(response.status_code == 200 for response in responses)
            assert len(calls) == 2
    asyncio.run(run())


def test_raw_request_cancellation_keeps_worker_admission_until_completion():
    entered, release = threading.Event(), threading.Event()
    calls = []
    owner = SerializedObservation()
    def observe(label):
        calls.append(label)
        if label == "first":
            entered.set()
            release.wait(3)
        return label
    async def run():
        first = asyncio.create_task(owner.run(observe, "first"))
        second = None
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            second = asyncio.create_task(owner.run(observe, "second"))
            # A queued waiter proves it reached the admission boundary.
            for _ in range(100):
                if owner._limiter.statistics().tasks_waiting:
                    break
                await asyncio.sleep(0)
            assert owner._limiter.statistics().tasks_waiting == 1
            assert calls == ["first"]
        finally:
            release.set()
            if second is not None:
                assert await asyncio.wait_for(second, 3) == "second"
        assert calls == ["first", "second"]
    asyncio.run(run())


def test_graceful_drain_waits_for_admitted_work_after_request_cancellation():
    entered, release = threading.Event(), threading.Event()
    completed = []
    owner = SerializedObservation()
    def observe():
        entered.set()
        release.wait(3)
        completed.append(True)
    async def run():
        request = asyncio.create_task(owner.run(observe))
        drain = None
        try:
            assert await asyncio.to_thread(entered.wait, 3)
            request.cancel()
            with pytest.raises(asyncio.CancelledError):
                await request
            drain = asyncio.create_task(owner.drain())
            await asyncio.sleep(0)
            assert not drain.done()
            assert not completed
        finally:
            release.set()
            if drain is not None:
                await asyncio.wait_for(drain, 3)
        assert completed == [True]
        assert not owner._pending
    asyncio.run(run())
