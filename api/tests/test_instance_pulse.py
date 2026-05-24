"""Acceptance tests for instance-pulse — per-instance breath sharing.

Federation honors sovereignty: every instance exposes its own breath at
/api/pulse/self (alias /api/pulse/now) without needing a central monitor.
Watched-peer pulses surface at /api/pulse/peers.
"""

from __future__ import annotations

import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import instance_pulse_service

BASE = "http://test"


@pytest.fixture(autouse=True)
def _reset_organ_overrides():
    instance_pulse_service.reset_organ_checks()
    yield
    instance_pulse_service.reset_organ_checks()


# ---------------------------------------------------------------------------
# 1. /api/pulse/self returns overall state with required fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_self_pulse_returns_overall_state():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/pulse/self")
        assert r.status_code == 200, r.text
        body = r.json()
        for field in ("instance_id", "overall", "organs", "silences", "uptime_seconds", "as_of"):
            assert field in body, f"missing field: {field}"
        assert isinstance(body["organs"], list)
        assert len(body["organs"]) >= 1
        for organ in body["organs"]:
            assert {"name", "status", "last_breath_at", "score"} <= set(organ.keys())


# ---------------------------------------------------------------------------
# 2. Overall = breathing when all organs breathe
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_self_pulse_breathing_when_api_healthy():
    instance_pulse_service.set_organ_check("postgres", lambda: ("breathing", 1.0, None))
    instance_pulse_service.set_organ_check("neo4j", lambda: ("breathing", 1.0, None))
    instance_pulse_service.set_organ_check("substrate", lambda: ("breathing", 1.0, None))
    instance_pulse_service.set_organ_check("schema", lambda: ("breathing", 1.0, None))

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/pulse/self")
        assert r.status_code == 200
        body = r.json()
        assert body["overall"] == "breathing"
        assert body["silences"] == 0


# ---------------------------------------------------------------------------
# 3. Strained when a non-core organ goes silent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_self_pulse_strained_when_organ_silent():
    # Core organs still healthy, but neo4j times out / silences
    instance_pulse_service.set_organ_check("postgres", lambda: ("breathing", 1.0, None))
    instance_pulse_service.set_organ_check("neo4j", lambda: ("silent", 0.0, "timeout"))
    instance_pulse_service.set_organ_check("substrate", lambda: ("breathing", 1.0, None))
    instance_pulse_service.set_organ_check("schema", lambda: ("breathing", 1.0, None))

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/pulse/self")
        assert r.status_code == 200
        body = r.json()
        assert body["overall"] == "strained"
        assert body["silences"] >= 1
        silent_names = [o["name"] for o in body["organs"] if o["status"] == "silent"]
        assert "neo4j" in silent_names


# ---------------------------------------------------------------------------
# 4. /api/pulse/now is an alias for /api/pulse/self
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pulse_now_is_alias_for_self():
    instance_pulse_service.set_organ_check("postgres", lambda: ("breathing", 1.0, None))
    instance_pulse_service.set_organ_check("neo4j", lambda: ("breathing", 1.0, None))
    instance_pulse_service.set_organ_check("substrate", lambda: ("breathing", 1.0, None))
    instance_pulse_service.set_organ_check("schema", lambda: ("breathing", 1.0, None))

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r_self = await c.get("/api/pulse/self")
        r_now = await c.get("/api/pulse/now")

    assert r_self.status_code == 200
    assert r_now.status_code == 200
    self_body = r_self.json()
    now_body = r_now.json()

    # Identity-bearing fields share shape and values; sampled-at-the-moment
    # fields (as_of, sample_duration_ms, scores) can differ.
    assert set(self_body.keys()) == set(now_body.keys())
    assert self_body["instance_id"] == now_body["instance_id"]
    assert {o["name"] for o in self_body["organs"]} == {o["name"] for o in now_body["organs"]}


# ---------------------------------------------------------------------------
# 5. /api/pulse/peers returns observed pulses
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pulse_peers_returns_observed_pulses():
    peer_id = "peer-instance-alpha"
    instance_pulse_service.record_peer_pulse(peer_id, {
        "instance_id": peer_id,
        "overall": "breathing",
        "silences": 0,
    })

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/pulse/peers")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["count"] >= 1
        ids = [p["peer_instance_id"] for p in body["peers"]]
        assert peer_id in ids
        match = next(p for p in body["peers"] if p["peer_instance_id"] == peer_id)
        assert match["pulse"]["overall"] == "breathing"


# ---------------------------------------------------------------------------
# 6. /api/pulse/peers returns empty list shape when nothing watched
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pulse_peers_empty_when_no_peers_watched():
    # Clear any rows from prior tests in the same DB.
    from app.services import unified_db
    from app.services.instance_pulse_service import PeerPulseRecord
    with unified_db.session() as sess:
        sess.query(PeerPulseRecord).delete()
        sess.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/pulse/peers")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 0
        assert body["peers"] == []


# ---------------------------------------------------------------------------
# 7. Pulse response stays fast — bounded organ timeouts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pulse_response_under_500ms():
    # Even with one organ hanging, the bounded timeout keeps the endpoint
    # responsive. Budget is generous (500ms) to absorb CI jitter while still
    # proving the timeout fires (a real hang would block forever).
    def _slow():
        time.sleep(2.0)
        return ("breathing", 1.0, None)

    instance_pulse_service.set_organ_check("neo4j", _slow)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        started = time.perf_counter()
        r = await c.get("/api/pulse/self")
        elapsed_ms = (time.perf_counter() - started) * 1000

    assert r.status_code == 200
    # Five organs × ~50ms timeout = ~250ms ceiling; give CI 2x headroom.
    assert elapsed_ms < 500, f"pulse took {elapsed_ms:.0f}ms"
    body = r.json()
    silent_names = [o["name"] for o in body["organs"] if o["status"] == "silent"]
    assert "neo4j" in silent_names
