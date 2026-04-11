"""Acceptance tests for spec: portfolio-governance-health (idea: portfolio-governance).

Covers done_when criteria:
  - GET /api/coherence returns score with signal breakdown
      (actual endpoint: GET /api/coherence/score)
  - GET /api/ideas/right-sizing returns health counts and suggestions
  - GET /api/workspaces/{id}/vitality returns 6 health signals
  - GET /api/cc/supply returns coherence score
  - POST /api/cc/stake creates staking position
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _uid(prefix: str = "pg") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _mint_for_user(user_id: str, amount_cc: float, deposit_usd: float) -> None:
    from app.services import cc_treasury_service
    cc_treasury_service.mint(user_id, amount_cc, deposit_usd, 333.33)


def _reset_services() -> None:
    from app.services import cc_treasury_service, cc_oracle_service
    cc_treasury_service.reset_treasury()
    cc_oracle_service.reset_cache()


async def _create_idea(c: AsyncClient, idea_id: str | None = None) -> dict:
    iid = idea_id or _uid("idea")
    r = await c.post("/api/ideas", json={
        "id": iid,
        "name": f"Idea {iid}",
        "description": f"Portfolio governance test idea {iid}",
        "potential_value": 100.0,
        "estimated_cost": 10.0,
        "confidence": 0.8,
    })
    assert r.status_code == 201, r.text
    return r.json()


async def _create_workspace(c: AsyncClient, ws_id: str | None = None) -> dict:
    wid = ws_id or _uid("ws")
    r = await c.post("/api/workspaces", json={"id": wid, "name": f"Workspace {wid}"})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# 1. GET /api/coherence/score returns score with signal breakdown
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_coherence_score_returns_signals():
    """Coherence score endpoint returns aggregate score and per-signal breakdown."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/coherence/score")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "score" in body
        assert isinstance(body["score"], (int, float))
        assert 0.0 <= body["score"] <= 1.0
        assert "signals" in body
        assert isinstance(body["signals"], dict)
        assert body["total_signals"] > 0
        assert "computed_at" in body


# ---------------------------------------------------------------------------
# 2. GET /api/ideas/right-sizing returns health counts and suggestions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_right_sizing_returns_health():
    """Right-sizing report returns portfolio health counts and suggestions."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/right-sizing")
        assert r.status_code == 200, r.text
        body = r.json()

        health = body["portfolio_health"]
        assert "total" in health
        assert "healthy" in health
        assert "too_large" in health
        assert "too_small" in health

        assert isinstance(body["suggestions"], list)
        assert "generated_at" in body


# ---------------------------------------------------------------------------
# 3. GET /api/workspaces/{id}/vitality returns 6 health signals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vitality_returns_six_signals():
    """Workspace vitality returns all 6 living-system health signals."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        ws = await _create_workspace(c)
        ws_id = ws["id"]

        r = await c.get(f"/api/workspaces/{ws_id}/vitality")
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["workspace_id"] == ws_id
        assert "vitality_score" in body
        assert 0.0 <= body["vitality_score"] <= 1.0

        signals = body["signals"]
        assert "diversity_index" in signals
        assert "resonance_density" in signals
        assert "flow_rate" in signals
        assert "breath_rhythm" in signals
        assert "connection_strength" in signals
        assert "activity_pulse" in signals


# ---------------------------------------------------------------------------
# 4. GET /api/cc/supply returns coherence score
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cc_supply_returns_coherence():
    """CC supply endpoint returns supply data including coherence score."""
    _reset_services()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/cc/supply")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "total_minted" in data
        assert "total_burned" in data
        assert "outstanding" in data
        assert "coherence_score" in data
        assert "exchange_rate" in data
        assert "as_of" in data


# ---------------------------------------------------------------------------
# 5. POST /api/cc/stake creates staking position
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stake_creates_position():
    """Staking CC into an idea creates an active position."""
    _reset_services()
    user_id = _uid("user")
    idea_id = _uid("idea")
    _mint_for_user(user_id, 1000.0, 10.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _create_idea(c, idea_id)
        r = await c.post("/api/cc/stake", json={
            "user_id": user_id,
            "idea_id": idea_id,
            "amount_cc": 500.0,
        })
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["stake_id"]
        assert data["user_id"] == user_id
        assert data["idea_id"] == idea_id
        assert data["amount_cc"] == 500.0
        assert data["status"] == "active"


# ---------------------------------------------------------------------------
# 6. GET /api/ideas/portfolio-summary returns curated super-idea rollup
# ---------------------------------------------------------------------------


def _seed_curated_idea(
    *,
    idea_id: str,
    pillar: str,
    actual_value: float = 0.0,
    last_activity_at: str | None = None,
) -> None:
    """Seed a curated super-idea node directly via graph_service.

    The public POST /api/ideas does not expose is_curated, so curated fixtures
    must be created at the graph layer.
    """
    from app.services import graph_service, unified_db
    unified_db.ensure_schema()
    graph_service.create_node(
        id=idea_id,
        type="idea",
        name=f"Curated {idea_id}",
        description=f"Curated super-idea {idea_id} for portfolio summary tests",
        phase="gas",
        properties={
            "potential_value": 100.0,
            "estimated_cost": 10.0,
            "actual_value": actual_value,
            "actual_cost": 0.5,
            "confidence": 0.8,
            "manifestation_status": "none",
            "stage": "active",
            "idea_type": "standalone",
            "interfaces": [],
            "open_questions": [],
            "is_curated": True,
            "pillar": pillar,
            "last_activity_at": last_activity_at,
        },
    )


def _seed_spec_for_idea(spec_id: str, idea_id: str, *, actual_value: float = 0.0) -> None:
    """Seed a spec node linked to the given idea via idea_id property."""
    from app.services import graph_service
    graph_service.create_node(
        id=spec_id,
        type="spec",
        name=spec_id,
        description=f"Spec {spec_id} for idea {idea_id}",
        phase="gas",
        properties={
            "idea_id": idea_id,
            "actual_value": actual_value,
            "potential_value": 50.0,
            "estimated_cost": 5.0,
            "status": "done" if actual_value > 0 else "active",
        },
    )


@pytest.mark.asyncio
async def test_portfolio_summary_returns_envelope():
    """Endpoint returns the canonical envelope shape even when no curated ideas exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/portfolio-summary")
        assert r.status_code == 200, r.text
        body = r.json()
        for key in ("total_ideas", "total_specs", "total_done_specs", "pillars", "ideas", "snapshot_at"):
            assert key in body, f"missing key: {key}"
        assert isinstance(body["pillars"], list)
        assert isinstance(body["ideas"], list)


@pytest.mark.asyncio
async def test_portfolio_summary_red_when_no_specs_linked():
    """A curated idea with no linked specs reports health=red."""
    iid = _uid("curated-red")
    _seed_curated_idea(idea_id=iid, pillar="realization")

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/portfolio-summary")
        assert r.status_code == 200, r.text
        body = r.json()
        match = next((i for i in body["ideas"] if i["idea_id"] == iid), None)
        assert match is not None, f"seeded idea {iid} not in summary"
        assert match["pillar"] == "realization"
        assert match["spec_count"] == 0
        assert match["health_status"] == "red"


@pytest.mark.asyncio
async def test_portfolio_summary_green_when_active_specs_present():
    """A curated idea with at least one undelivered spec reports health=green."""
    iid = _uid("curated-green")
    _seed_curated_idea(idea_id=iid, pillar="pipeline")
    _seed_spec_for_idea(_uid("spec-active"), iid, actual_value=0.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/portfolio-summary")
        body = r.json()
        match = next((i for i in body["ideas"] if i["idea_id"] == iid), None)
        assert match is not None
        assert match["spec_count"] == 1
        assert match["active_spec_count"] == 1
        assert match["done_spec_count"] == 0
        assert match["health_status"] == "green"


@pytest.mark.asyncio
async def test_portfolio_summary_yellow_when_all_specs_done_no_value():
    """A curated idea whose specs are all delivered but with no recorded value or recent activity is yellow."""
    iid = _uid("curated-yellow")
    _seed_curated_idea(idea_id=iid, pillar="economics", actual_value=0.0, last_activity_at=None)
    _seed_spec_for_idea(_uid("spec-done"), iid, actual_value=42.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/portfolio-summary")
        body = r.json()
        match = next((i for i in body["ideas"] if i["idea_id"] == iid), None)
        assert match is not None
        assert match["done_spec_count"] == 1
        assert match["active_spec_count"] == 0
        assert match["health_status"] == "yellow"


@pytest.mark.asyncio
async def test_portfolio_summary_pillar_grouping_aggregates():
    """Per-pillar stats correctly aggregate spec counts across multiple curated ideas."""
    iid_a = _uid("curated-pillar-a")
    iid_b = _uid("curated-pillar-b")
    _seed_curated_idea(idea_id=iid_a, pillar="surfaces")
    _seed_curated_idea(idea_id=iid_b, pillar="surfaces")
    _seed_spec_for_idea(_uid("spec-a1"), iid_a, actual_value=0.0)
    _seed_spec_for_idea(_uid("spec-b1"), iid_b, actual_value=10.0)
    _seed_spec_for_idea(_uid("spec-b2"), iid_b, actual_value=0.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/ideas/portfolio-summary")
        body = r.json()
        surfaces = next((p for p in body["pillars"] if p["pillar"] == "surfaces"), None)
        assert surfaces is not None, "surfaces pillar missing from rollup"
        assert surfaces["idea_count"] >= 2
        assert surfaces["total_specs"] >= 3
        assert surfaces["done_specs"] >= 1
        assert surfaces["active_specs"] >= 2
