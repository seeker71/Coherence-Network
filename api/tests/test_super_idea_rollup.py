"""Tests for super-idea rollup criteria (spec: super-idea-rollup-criteria).

Validates:
  R1: Each super-idea has a rollup_condition field in DB
  R2: validate_super_idea(idea_id) checks all children validated + rollup condition
  R3: Super-idea manifestation_status auto-updates when rollup criteria met
  R4: Dashboard shows rollup progress (children validated / total children)
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


def _uid(prefix: str = "rollup") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_idea(c: AsyncClient, idea_id: str | None = None, **overrides) -> dict:
    iid = idea_id or _uid()
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
    return r.json()


# ---------------------------------------------------------------------------
# R1: rollup_condition field stored and returned
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r1_rollup_condition_stored_on_create():
    """Super-idea created with rollup_condition has it persisted and returned."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        sid = _uid("super")
        parent = await _create_idea(
            c,
            idea_id=sid,
            idea_type="super",
            rollup_condition="All child specs pass parity tests",
        )
        assert parent["rollup_condition"] == "All child specs pass parity tests"

        # Verify GET returns the field too
        r = await c.get(f"/api/ideas/{sid}")
        assert r.status_code == 200
        assert r.json()["rollup_condition"] == "All child specs pass parity tests"


@pytest.mark.asyncio
async def test_r1_rollup_condition_defaults_to_none():
    """Ideas without rollup_condition default to null."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        idea = await _create_idea(c)
        assert idea.get("rollup_condition") is None


# ---------------------------------------------------------------------------
# R4: GET /api/ideas/{idea_id}/rollup returns progress
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r4_rollup_endpoint_returns_progress():
    """GET /api/ideas/{id}/rollup returns rollup progress with child counts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        sid = _uid("super")
        await _create_idea(c, idea_id=sid, idea_type="super", rollup_condition="All tests pass")

        cid1 = _uid("child")
        cid2 = _uid("child")
        await _create_idea(c, idea_id=cid1, parent_idea_id=sid, idea_type="child")
        await _create_idea(c, idea_id=cid2, parent_idea_id=sid, idea_type="child")

        r = await c.get(f"/api/ideas/{sid}/rollup")
        assert r.status_code == 200
        body = r.json()
        assert body["idea_id"] == sid
        assert body["children_total"] == 2
        assert body["children_validated"] == 0
        assert body["progress_pct"] == 0.0
        assert body["all_children_validated"] is False
        assert body["rollup_met"] is False
        assert body["rollup_condition"] == "All tests pass"
        assert len(body["children"]) == 2


@pytest.mark.asyncio
async def test_r4_rollup_progress_partial():
    """Rollup shows partial progress when some children are validated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        sid = _uid("super")
        await _create_idea(c, idea_id=sid, idea_type="super")

        cid1 = _uid("child")
        cid2 = _uid("child")
        await _create_idea(c, idea_id=cid1, parent_idea_id=sid, idea_type="child")
        await _create_idea(
            c, idea_id=cid2, parent_idea_id=sid, idea_type="child",
            manifestation_status="validated",
        )

        r = await c.get(f"/api/ideas/{sid}/rollup")
        body = r.json()
        assert body["children_total"] == 2
        assert body["children_validated"] == 1
        assert body["progress_pct"] == 50.0
        assert body["all_children_validated"] is False
        assert body["rollup_met"] is False


@pytest.mark.asyncio
async def test_r4_rollup_404_for_missing_idea():
    """GET /api/ideas/{nonexistent}/rollup returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/nonexistent-idea/rollup")
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# R2 + R3: validate_super_idea checks children + auto-updates status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_r2_r3_validate_auto_updates_to_validated():
    """When all children validated, POST validate-rollup sets parent to validated."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        sid = _uid("super")
        await _create_idea(
            c, idea_id=sid, idea_type="super",
            rollup_condition="All children validated",
        )

        cid1 = _uid("child")
        cid2 = _uid("child")
        await _create_idea(
            c, idea_id=cid1, parent_idea_id=sid, idea_type="child",
            manifestation_status="validated",
        )
        await _create_idea(
            c, idea_id=cid2, parent_idea_id=sid, idea_type="child",
            manifestation_status="validated",
        )

        r = await c.post(f"/api/ideas/{sid}/validate-rollup", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["rollup_met"] is True
        assert body["all_children_validated"] is True
        assert body["manifestation_status"] == "validated"

        # Verify the idea's manifestation_status was actually updated
        r2 = await c.get(f"/api/ideas/{sid}")
        assert r2.json()["manifestation_status"] == "validated"


@pytest.mark.asyncio
async def test_r2_r3_validate_sets_partial_when_some_validated():
    """When some (but not all) children are validated, parent becomes partial."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        sid = _uid("super")
        await _create_idea(c, idea_id=sid, idea_type="super")

        cid1 = _uid("child")
        cid2 = _uid("child")
        await _create_idea(
            c, idea_id=cid1, parent_idea_id=sid, idea_type="child",
            manifestation_status="validated",
        )
        await _create_idea(
            c, idea_id=cid2, parent_idea_id=sid, idea_type="child",
            manifestation_status="none",
        )

        r = await c.post(f"/api/ideas/{sid}/validate-rollup", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["rollup_met"] is False
        assert body["manifestation_status"] == "partial"


@pytest.mark.asyncio
async def test_r3_validate_downgrades_on_regression():
    """If a child regresses after parent was validated, validate-rollup downgrades parent."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        sid = _uid("super")
        await _create_idea(
            c, idea_id=sid, idea_type="super",
            manifestation_status="validated",
        )

        cid1 = _uid("child")
        cid2 = _uid("child")
        await _create_idea(
            c, idea_id=cid1, parent_idea_id=sid, idea_type="child",
            manifestation_status="validated",
        )
        # This child has regressed to partial
        await _create_idea(
            c, idea_id=cid2, parent_idea_id=sid, idea_type="child",
            manifestation_status="partial",
        )

        r = await c.post(f"/api/ideas/{sid}/validate-rollup", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["rollup_met"] is False
        assert body["manifestation_status"] == "partial"

        # Verify the actual idea was downgraded
        r2 = await c.get(f"/api/ideas/{sid}")
        assert r2.json()["manifestation_status"] == "partial"


@pytest.mark.asyncio
async def test_r2_validate_rejects_non_super():
    """validate-rollup returns 422 for non-super ideas."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        iid = _uid("standalone")
        await _create_idea(c, idea_id=iid, idea_type="standalone")

        r = await c.post(f"/api/ideas/{iid}/validate-rollup", headers=AUTH)
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_r2_validate_404_for_missing():
    """validate-rollup returns 404 for nonexistent idea."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post("/api/ideas/nonexistent-id/validate-rollup", headers=AUTH)
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_r3_validate_no_children_stays_none():
    """Super-idea with no children stays at 'none' status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        sid = _uid("super")
        await _create_idea(c, idea_id=sid, idea_type="super")

        r = await c.post(f"/api/ideas/{sid}/validate-rollup", headers=AUTH)
        assert r.status_code == 200
        body = r.json()
        assert body["children_total"] == 0
        assert body["rollup_met"] is False
        assert body["manifestation_status"] == "none"
