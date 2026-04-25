"""Tests for the per-minute request outcomes counter."""

from __future__ import annotations

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.middleware.request_outcomes import (
    RequestOutcomesMiddleware,
    _reset_for_tests,
    recent_outcomes_snapshot,
)


def _build_probe_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestOutcomesMiddleware)

    @app.get("/api/ideas")
    async def ideas():
        return {"ideas": []}

    @app.get("/api/ideas/boom")
    async def ideas_boom():
        raise HTTPException(status_code=500, detail="synthetic")

    @app.get("/api/ideas/notfound")
    async def ideas_notfound():
        raise HTTPException(status_code=404, detail="nope")

    @app.get("/api/health")
    async def health():
        # Health is excluded from the counter — this is the synthetic
        # probe path. If it weren't excluded, the witness's own probes
        # would be the biggest caller.
        return {"status": "ok"}

    return app


async def _client():
    app = _build_probe_app()
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_empty_snapshot_has_zero_counts():
    _reset_for_tests()
    snap = recent_outcomes_snapshot()
    assert snap["last_1m"]["total"] == 0
    assert snap["last_1m"]["5xx"] == 0
    assert snap["last_5m"]["total"] == 0


@pytest.mark.asyncio
async def test_2xx_counted():
    _reset_for_tests()
    async with await _client() as c:
        r = await c.get("/api/ideas")
    assert r.status_code == 200
    snap = recent_outcomes_snapshot()
    assert snap["last_1m"]["2xx"] == 1
    assert snap["last_1m"]["total"] == 1


@pytest.mark.asyncio
async def test_5xx_counted():
    _reset_for_tests()
    async with await _client() as c:
        r = await c.get("/api/ideas/boom")
    assert r.status_code == 500
    snap = recent_outcomes_snapshot()
    assert snap["last_1m"]["5xx"] == 1
    assert snap["last_1m"]["2xx"] == 0


@pytest.mark.asyncio
async def test_4xx_counted():
    _reset_for_tests()
    async with await _client() as c:
        r = await c.get("/api/ideas/notfound")
    assert r.status_code == 404
    snap = recent_outcomes_snapshot()
    assert snap["last_1m"]["4xx"] == 1
    assert snap["last_1m"]["5xx"] == 0


@pytest.mark.asyncio
async def test_health_excluded_from_counter():
    """The witness's own probe path must not pollute the real-user traffic counter."""
    _reset_for_tests()
    async with await _client() as c:
        for _ in range(10):
            await c.get("/api/health")
    snap = recent_outcomes_snapshot()
    assert snap["last_1m"]["total"] == 0
    assert snap["last_1m"]["2xx"] == 0


@pytest.mark.asyncio
async def test_mixed_traffic():
    _reset_for_tests()
    async with await _client() as c:
        for _ in range(3):
            await c.get("/api/ideas")
        await c.get("/api/ideas/boom")
        await c.get("/api/ideas/notfound")
        await c.get("/api/health")  # excluded
    snap = recent_outcomes_snapshot()
    assert snap["last_1m"]["2xx"] == 3
    assert snap["last_1m"]["4xx"] == 1
    assert snap["last_1m"]["5xx"] == 1
    assert snap["last_1m"]["total"] == 5  # health excluded


@pytest.mark.asyncio
async def test_snapshot_shape_stable():
    """The snapshot shape is the contract pulse's extract_api reads against."""
    _reset_for_tests()
    snap = recent_outcomes_snapshot()
    assert set(snap.keys()) == {"last_1m", "last_5m", "as_of_minute"}
    for window in ("last_1m", "last_5m"):
        assert set(snap[window].keys()) == {"2xx", "3xx", "4xx", "5xx", "total"}
