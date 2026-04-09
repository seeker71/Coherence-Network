"""Flow-centric tests for the Constellation View API.

Tests the constellation endpoint as a user would experience it:
HTTP requests in, JSON out.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


async def _seed_idea(c: AsyncClient, idea_id: str, name: str) -> dict:
    """Seed an idea via the ideas API."""
    r = await c.post(
        "/api/ideas",
        json={
            "id": idea_id,
            "name": name,
            "description": f"Test idea: {name}",
            "potential_value": 100.0,
            "estimated_cost": 10.0,
        },
    )
    assert r.status_code in (200, 201, 409), r.text
    return r.json()


async def _seed_contributor(c: AsyncClient, contrib_id: str, name: str) -> dict:
    """Seed a contributor via the graph API."""
    r = await c.post(
        "/api/graph/nodes",
        json={
            "id": contrib_id,
            "type": "contributor",
            "name": name,
            "description": f"Test contributor: {name}",
        },
    )
    assert r.status_code in (200, 201, 409), r.text
    return r.json()


# ---------------------------------------------------------------------------
# Test 1: Constellation returns nodes and edges
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_constellation_returns_nodes_and_edges():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _seed_idea(c, "const-idea-1", "Alpha Idea")
        await _seed_idea(c, "const-idea-2", "Beta Idea")
        await _seed_contributor(c, "const-contrib-1", "Alice")

        r = await c.get("/api/constellation")
        assert r.status_code == 200, r.text
        body = r.json()

        assert "nodes" in body
        assert "edges" in body
        assert "stats" in body
        assert isinstance(body["nodes"], list)
        assert isinstance(body["edges"], list)
        assert len(body["nodes"]) >= 2  # at least the seeded ideas

        # Each node has required fields
        for node in body["nodes"]:
            assert "id" in node
            assert "type" in node
            assert "name" in node
            assert "brightness" in node
            assert "size" in node
            assert "color" in node
            assert "x" in node
            assert "y" in node
            assert isinstance(node["brightness"], (int, float))
            assert isinstance(node["x"], (int, float))
            assert isinstance(node["y"], (int, float))


# ---------------------------------------------------------------------------
# Test 2: Node types include idea and contributor
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_node_types_include_idea_and_contributor():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _seed_idea(c, "const-idea-3", "Gamma Idea")
        await _seed_contributor(c, "const-contrib-2", "Bob")

        r = await c.get("/api/constellation")
        assert r.status_code == 200, r.text
        body = r.json()

        types = {n["type"] for n in body["nodes"]}
        assert "idea" in types
        assert "contributor" in types


# ---------------------------------------------------------------------------
# Test 3: Stats present with correct fields
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stats_present():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        await _seed_idea(c, "const-idea-4", "Delta Idea")

        r = await c.get("/api/constellation")
        assert r.status_code == 200, r.text
        body = r.json()

        stats = body["stats"]
        assert "total_nodes" in stats
        assert "total_edges" in stats
        assert "clusters" in stats
        assert isinstance(stats["total_nodes"], int)
        assert isinstance(stats["total_edges"], int)
        assert isinstance(stats["clusters"], int)
        assert stats["total_nodes"] >= 1
