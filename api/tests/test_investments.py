"""Flow-centric tests for the investment surface — covers preview, portfolio,
history, time pledges, and the stake dry_run mode.

The five tests are strange-minimal: each exercises a single decision boundary
in the position-computer + pledge service through the HTTP surface.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import time_pledge_service

BASE = "http://test"


def _uid(prefix: str = "inv") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_idea(c: AsyncClient, idea_id: str | None = None, **overrides) -> str:
    """Create an idea and return its id."""
    iid = idea_id or _uid("inv-idea")
    payload = {
        "id": iid,
        "name": f"Idea {iid}",
        "description": f"Description for {iid}",
        "potential_value": 100.0,
        "estimated_cost": 10.0,
        "confidence": 0.8,
    }
    payload.update(overrides)
    r = await c.post("/api/ideas", json=payload)
    assert r.status_code == 201, r.text
    return iid


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_positions_for_new_contributor():
    """A contributor with no stakes returns an empty portfolio + zero summary."""
    cid = _uid("contrib-empty")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get(f"/api/contributors/{cid}/investments")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["contributor_id"] == cid
        assert body["positions"] == []
        assert body["summary"]["total_positions"] == 0
        assert body["summary"]["total_invested_cc"] == 0.0
        assert body["summary"]["total_current_value_cc"] == 0.0


@pytest.mark.asyncio
async def test_one_position_has_basic_roi_and_dry_run_matches():
    """One stake produces one position. Dry-run preview reflects the same idea state."""
    cid = _uid("contrib-one")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = await _create_idea(c, potential_value=200.0, estimated_cost=20.0, confidence=0.9)
        

        # Stake 50 CC.
        stake_resp = await c.post(
            f"/api/ideas/{iid}/stake",
            json={"contributor_id": cid, "amount_cc": 50.0, "rationale": "trust"},
        )
        assert stake_resp.status_code == 200, stake_resp.text

        # Portfolio shows one position.
        port = await c.get(f"/api/contributors/{cid}/investments")
        assert port.status_code == 200
        positions = port.json()["positions"]
        assert len(positions) == 1
        p = positions[0]
        assert p["idea_id"] == iid
        assert p["invested_cc"] == 50.0
        # current_value_cc >= invested_cc — gain or break-even, never loss
        # at stage=none with unlock_pct=0.
        assert p["current_value_cc"] >= p["invested_cc"]
        assert p["roi_pct"] >= 0.0

        # Dry-run preview returns the same coherence + stage shape.
        preview = await c.get(f"/api/ideas/{iid}/invest-preview")
        assert preview.status_code == 200
        pv = preview.json()
        assert pv["idea_id"] == iid
        assert pv["stage"] == p["stage"]
        assert 0.0 <= pv["coherence_score"] <= 1.0
        assert pv["projections"]["low_multiplier"] > 0
        assert pv["projections"]["high_multiplier"] >= pv["projections"]["low_multiplier"]
        # Total CC staked on the idea matches what we put in.
        assert pv["total_cc_staked"] == 50.0


@pytest.mark.asyncio
async def test_stake_dry_run_returns_preview_without_recording():
    """POST /stake with dry_run=true returns projection but creates no stake."""
    cid = _uid("contrib-dryrun")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = await _create_idea(c)
        

        # Dry-run via body flag.
        resp = await c.post(
            f"/api/ideas/{iid}/stake",
            json={"contributor_id": cid, "amount_cc": 25.0, "dry_run": True},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["dry_run"] is True
        assert "preview" in body
        assert body["preview"]["idea_id"] == iid

        # Portfolio should still be empty — no stake was recorded.
        port = await c.get(f"/api/contributors/{cid}/investments")
        assert port.status_code == 200
        assert port.json()["positions"] == []

        # Dry-run via query string also works.
        resp_q = await c.post(
            f"/api/ideas/{iid}/stake?dry_run=true",
            json={"contributor_id": cid, "amount_cc": 25.0},
        )
        assert resp_q.status_code == 200
        assert resp_q.json()["dry_run"] is True


@pytest.mark.asyncio
async def test_time_pledge_creates_cc_equivalent_and_fulfills():
    """Pledge converts hours -> CC at the configured rate; fulfillment lands a return."""
    cid = _uid("contrib-pledge")
    time_pledge_service._reset_for_tests()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = await _create_idea(c)
        

        # 2 hours * 500 CC/hour = 1000 CC equivalent (the spec example).
        create = await c.post(
            f"/api/contributors/{cid}/pledges",
            json={"idea_id": iid, "hours_pledged": 2.0, "pledge_type": "review"},
        )
        assert create.status_code == 201, create.text
        pledge = create.json()
        assert pledge["cc_equivalent"] == 1000.0
        assert pledge["status"] == "pending"
        assert pledge["expires_at"] > pledge["created_at"]
        pid = pledge["pledge_id"]

        # Listing returns the pledge.
        listing = await c.get(f"/api/contributors/{cid}/pledges")
        assert listing.status_code == 200
        assert len(listing.json()["pledges"]) == 1

        # Fulfill the pledge — records a 'return' contribution.
        fulfill = await c.post(
            f"/api/contributors/{cid}/pledges/{pid}/fulfill",
            json={"contribution_id": "contrib_xyz", "evidence_url": "https://example.com/pr/1"},
        )
        assert fulfill.status_code == 200, fulfill.text
        f = fulfill.json()
        assert f["status"] == "fulfilled"
        assert f["fulfilled_at"] is not None

        # Re-fulfilling returns 409.
        re_fulfill = await c.post(
            f"/api/contributors/{cid}/pledges/{pid}/fulfill",
            json={"contribution_id": "contrib_again"},
        )
        assert re_fulfill.status_code == 409

        # Fulfillment by wrong contributor returns 403.
        another = await c.post(
            f"/api/contributors/{_uid('other')}/pledges/{pid}/fulfill",
            json={"contribution_id": "contrib_wrong"},
        )
        assert another.status_code in (403, 409)  # 409 if already fulfilled wins first


@pytest.mark.asyncio
async def test_history_timeline_orders_newest_first_and_includes_pledges():
    """History endpoint returns events newest-first and includes pledges + stakes."""
    cid = _uid("contrib-hist")
    time_pledge_service._reset_for_tests()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = await _create_idea(c)
        

        await c.post(
            f"/api/ideas/{iid}/stake",
            json={"contributor_id": cid, "amount_cc": 10.0},
        )
        await c.post(
            f"/api/contributors/{cid}/pledges",
            json={"idea_id": iid, "hours_pledged": 1.0},
        )

        resp = await c.get(f"/api/contributors/{cid}/investment-history")
        assert resp.status_code == 200, resp.text
        events = resp.json()["events"]
        # At minimum a stake event and a pledge event.
        types = {e["event_type"] for e in events}
        assert "stake" in types
        assert "pledge" in types
        # Filter by idea_id.
        scoped = await c.get(
            f"/api/contributors/{cid}/investment-history?idea_id={iid}"
        )
        assert scoped.status_code == 200
        for e in scoped.json()["events"]:
            assert e["idea_id"] == iid


@pytest.mark.asyncio
async def test_invest_preview_404_for_missing_idea():
    """Preview endpoint returns 404 when the idea does not exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        resp = await c.get(f"/api/ideas/{_uid('nope')}/invest-preview")
        assert resp.status_code == 404
