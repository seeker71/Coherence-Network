"""Flow-centric integration tests for the Serendipity Discovery feed.

Tests the discovery API as a user would: HTTP requests in, JSON out.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _uid(prefix: str = "test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _setup_contributor(c: AsyncClient) -> str:
    """Create a contributor with a belief profile so the feed has data."""
    cid = _uid("contrib")
    # Create contributor node via graph API
    await c.post("/api/graph/nodes", json={
        "id": f"contributor:{cid}",
        "type": "contributor",
        "name": f"Test User {cid}",
        "properties": {},
    })
    # Set the belief profile via the proper PATCH endpoint so nested
    # properties (worldview_axes, concept_resonances) are persisted correctly.
    await c.patch(f"/api/contributors/{cid}/beliefs", json={
        "worldview_axes": {
            "scientific": 0.8,
            "pragmatic": 0.6,
            "systemic": 0.7,
            "holistic": 0.3,
            "relational": 0.5,
            "spiritual": 0.2,
        },
        "interest_tags": ["software", "resonance", "ontology"],
        "concept_resonances": [
            {"concept_id": "crk", "weight": 0.9},
            {"concept_id": "ontology", "weight": 0.7},
        ],
    })
    return cid


async def _setup_idea(c: AsyncClient, idea_id: str | None = None, **overrides) -> dict:
    """Create an idea for discovery to find."""
    iid = idea_id or _uid("idea")
    payload = {
        "id": iid,
        "name": f"Idea {iid}",
        "description": f"A resonance-based idea about software and ontology for {iid}",
        "potential_value": 100.0,
        "estimated_cost": 10.0,
        "confidence": 0.8,
        "tags": ["software", "resonance"],
    }
    payload.update(overrides)
    r = await c.post("/api/ideas", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Test 1: Discovery feed returns items for a contributor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discovery_feed_returns_items():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _setup_contributor(c)
        await _setup_idea(c)
        await _setup_idea(c)

        r = await c.get(f"/api/discover/{cid}", params={"limit": 30})
        assert r.status_code == 200, r.text
        data = r.json()

        assert data["contributor_id"] == cid
        assert isinstance(data["items"], list)
        assert data["total"] >= 0
        assert "generated_at" in data
        # Feed should return at least some items (the ideas we created)
        assert data["total"] >= 1


# ---------------------------------------------------------------------------
# Test 2: Feed includes mixed kinds (at least 2 different kinds)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discovery_feed_mixed_kinds():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _setup_contributor(c)
        # Create several ideas with different tags to trigger cross-domain
        await _setup_idea(c, tags=["biology", "symbiosis", "evolution"])
        await _setup_idea(c, tags=["software", "microservice", "api"])
        await _setup_idea(c, tags=["physics", "quantum", "energy"])

        # Also create a second contributor to be found as a peer
        cid2 = _uid("peer")
        await c.post("/api/graph/nodes", json={
            "id": f"contributor:{cid2}",
            "type": "contributor",
            "name": f"Peer User {cid2}",
            "properties": {},
        })
        await c.patch(f"/api/contributors/{cid2}/beliefs", json={
            "worldview_axes": {"scientific": 0.9, "pragmatic": 0.7, "systemic": 0.6,
                               "holistic": 0.2, "relational": 0.4, "spiritual": 0.1},
            "interest_tags": ["software", "resonance"],
        })

        r = await c.get(f"/api/discover/{cid}", params={"limit": 50})
        assert r.status_code == 200
        data = r.json()

        kinds = {item["kind"] for item in data["items"]}
        # Should have at least resonant_idea; peers depend on scoring threshold
        assert "resonant_idea" in kinds
        # With a matching peer, we should see at least 2 kinds
        assert len(kinds) >= 2, f"Expected at least 2 kinds, got {kinds}"


# ---------------------------------------------------------------------------
# Test 3: Each item has required fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discovery_items_have_required_fields():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _setup_contributor(c)
        await _setup_idea(c)

        r = await c.get(f"/api/discover/{cid}")
        assert r.status_code == 200
        data = r.json()

        for item in data["items"]:
            assert "kind" in item, f"Missing 'kind' in item: {item}"
            assert "score" in item, f"Missing 'score' in item: {item}"
            assert "title" in item, f"Missing 'title' in item: {item}"
            assert "entity_id" in item, f"Missing 'entity_id' in item: {item}"
            assert isinstance(item["score"], (int, float))
            assert 0.0 <= item["score"] <= 1.0, f"Score out of range: {item['score']}"
            assert item["kind"] in {
                "resonant_idea", "resonant_peer", "cross_domain",
                "resonant_news", "growth_edge",
            }, f"Unknown kind: {item['kind']}"


# ---------------------------------------------------------------------------
# Test 4: Empty contributor (no profile) still returns feed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_discovery_feed_no_profile_still_returns():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Create a bare contributor with no belief profile
        cid = _uid("bare")
        await c.post("/api/graph/nodes", json={
            "id": f"contributor:{cid}",
            "type": "contributor",
            "name": f"Bare User {cid}",
            "properties": {},
        })
        await _setup_idea(c)

        r = await c.get(f"/api/discover/{cid}")
        assert r.status_code == 200
        data = r.json()

        assert data["contributor_id"] == cid
        assert isinstance(data["items"], list)
        # Feed should still work, possibly with neutral scores
        assert data["total"] >= 0


# ---------------------------------------------------------------------------
# Test 5: Profile endpoint returns worldview axes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_profile_endpoint_returns_axes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _setup_contributor(c)

        r = await c.get(f"/api/discover/{cid}/profile")
        assert r.status_code == 200
        data = r.json()

        assert "worldview_axes" in data
        assert isinstance(data["worldview_axes"], dict)
        # The contributor we created has scientific=0.8
        assert data["worldview_axes"].get("scientific", 0) > 0
        assert "top_axes" in data
        assert isinstance(data["top_axes"], list)
