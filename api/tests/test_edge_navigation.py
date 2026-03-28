"""Tests for edge navigation — 46 typed relationships.

Covers:
  GET  /api/edges/types          — canonical type registry
  GET  /api/edges                — list edges with filters
  GET  /api/edges/{id}           — single edge by ID
  POST /api/edges                — create typed edge
  DELETE /api/edges/{id}         — delete edge
  GET  /api/entities/{id}/edges  — entity-scoped edge listing
  GET  /api/entities/{id}/neighbors — 1-hop neighbors
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH = {"X-API-Key": "dev-key"}
CANONICAL_COUNT = 46


# ── helpers ───────────────────────────────────────────────────────────────────

async def _create_node(client: AsyncClient, node_id: str, name: str, node_type: str = "idea") -> dict:
    r = await client.post(
        "/api/graph/nodes",
        json={"id": node_id, "type": node_type, "name": name},
        headers=AUTH,
    )
    assert r.status_code in (200, 201, 409), f"create_node failed: {r.text}"
    return r.json()


async def _create_edge(client: AsyncClient, from_id: str, edge_type: str, to_id: str, strength: float = 1.0) -> dict:
    r = await client.post(
        "/api/edges",
        json={"from_id": from_id, "to_id": to_id, "type": edge_type, "strength": strength},
        headers=AUTH,
    )
    assert r.status_code in (200, 201), f"create_edge failed: {r.text}"
    return r.json()


# ── Type registry ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edge_types_returns_46_canonical_types() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edges/types")

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == CANONICAL_COUNT, f"Expected {CANONICAL_COUNT} types, got {data['total']}"
    assert len(data["families"]) == 7  # 7 families in the Living Codex ontology


@pytest.mark.asyncio
async def test_edge_types_family_filter() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edges/types", params={"family": "ontological"})

    assert r.status_code == 200
    data = r.json()
    assert len(data["families"]) == 1
    assert data["families"][0]["slug"] == "ontological"
    assert data["total"] == 6  # ontological family has 6 types


@pytest.mark.asyncio
async def test_edge_types_unknown_family_returns_empty() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edges/types", params={"family": "nonexistent"})

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["families"] == []


@pytest.mark.asyncio
async def test_edge_types_contain_expected_slugs() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edges/types")

    all_slugs = {t["slug"] for f in r.json()["families"] for t in f["types"]}
    required = {
        "resonates-with", "emerges-from", "transforms-into", "enables",
        "implements", "extends", "contradicts", "precedes", "follows",
        "tension-with", "bridges", "contributes-to", "depends-on",
        "analogous-to", "validates", "invalidates",
    }
    assert required <= all_slugs, f"Missing canonical types: {required - all_slugs}"


# ── Edge CRUD ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_and_retrieve_canonical_edge() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-src-1", "Source Node")
        await _create_node(c, "nav-dst-1", "Dest Node")

        created = await _create_edge(c, "nav-src-1", "resonates-with", "nav-dst-1", strength=0.8)
        assert created["canonical"] is True
        assert created["from_node"]["id"] == "nav-src-1"
        assert created["to_node"]["id"] == "nav-dst-1"
        assert created["type"] == "resonates-with"
        assert abs(created["strength"] - 0.8) < 0.001

        edge_id = created["id"]
        r = await c.get(f"/api/edges/{edge_id}")
        assert r.status_code == 200
        fetched = r.json()
        assert fetched["id"] == edge_id
        assert fetched["type"] == "resonates-with"


@pytest.mark.asyncio
async def test_create_edge_marks_non_canonical_correctly() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-src-2", "Src2")
        await _create_node(c, "nav-dst-2", "Dst2")

        r = await c.post(
            "/api/edges",
            json={"from_id": "nav-src-2", "to_id": "nav-dst-2", "type": "custom-non-canonical"},
            headers=AUTH,
        )
        assert r.status_code in (200, 201)
        assert r.json()["canonical"] is False


@pytest.mark.asyncio
async def test_create_edge_strict_rejects_non_canonical() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-src-3", "Src3")
        await _create_node(c, "nav-dst-3", "Dst3")

        r = await c.post(
            "/api/edges",
            params={"strict": "true"},
            json={"from_id": "nav-src-3", "to_id": "nav-dst-3", "type": "made-up-type"},
            headers=AUTH,
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_duplicate_edge_returns_409() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-dup-a", "DupA")
        await _create_node(c, "nav-dup-b", "DupB")

        await _create_edge(c, "nav-dup-a", "enables", "nav-dup-b")

        r2 = await c.post(
            "/api/edges",
            json={"from_id": "nav-dup-a", "to_id": "nav-dup-b", "type": "enables"},
            headers=AUTH,
        )
        assert r2.status_code == 409


@pytest.mark.asyncio
async def test_create_edge_missing_node_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-exists", "Exists")

        r = await c.post(
            "/api/edges",
            json={"from_id": "nav-exists", "to_id": "node-does-not-exist-xyz", "type": "enables"},
            headers=AUTH,
        )
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_edge() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-del-a", "DelA")
        await _create_node(c, "nav-del-b", "DelB")

        edge = await _create_edge(c, "nav-del-a", "triggers", "nav-del-b")
        edge_id = edge["id"]

        r_del = await c.delete(f"/api/edges/{edge_id}")
        assert r_del.status_code == 200
        assert r_del.json()["deleted"] == edge_id

        r_get = await c.get(f"/api/edges/{edge_id}")
        assert r_get.status_code == 404


@pytest.mark.asyncio
async def test_get_edge_not_found() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/edges/edge-definitely-does-not-exist-xyz")
    assert r.status_code == 404


# ── List edges with filters ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_edges_filter_by_type() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-lt-a", "LtA")
        await _create_node(c, "nav-lt-b", "LtB")
        await _create_node(c, "nav-lt-c", "LtC")

        await _create_edge(c, "nav-lt-a", "catalyzes", "nav-lt-b")
        await _create_edge(c, "nav-lt-a", "blocks", "nav-lt-c")

        r = await c.get("/api/edges", params={"type": "catalyzes"})
        assert r.status_code == 200
        data = r.json()
        assert all(e["type"] == "catalyzes" for e in data["items"])


@pytest.mark.asyncio
async def test_list_edges_filter_by_from_id() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-from-a", "FromA")
        await _create_node(c, "nav-from-b", "FromB")
        await _create_node(c, "nav-from-c", "FromC")

        await _create_edge(c, "nav-from-a", "complements", "nav-from-b")
        await _create_edge(c, "nav-from-a", "complements", "nav-from-c")

        r = await c.get("/api/edges", params={"from_id": "nav-from-a"})
        assert r.status_code == 200
        data = r.json()
        assert all(e["from_id"] == "nav-from-a" for e in data["items"])


# ── Entity-scoped edge navigation ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_entity_edges_returns_all_directions() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-hub", "Hub")
        await _create_node(c, "nav-spoke-1", "Spoke1")
        await _create_node(c, "nav-spoke-2", "Spoke2")

        await _create_edge(c, "nav-hub", "extends", "nav-spoke-1")
        await _create_edge(c, "nav-spoke-2", "extends", "nav-hub")

        r = await c.get("/api/entities/nav-hub/edges")
        assert r.status_code == 200
        data = r.json()
        edge_ids = {e["from_id"] for e in data["items"]} | {e["to_id"] for e in data["items"]}
        assert "nav-hub" in edge_ids
        assert data["total"] >= 2


@pytest.mark.asyncio
async def test_entity_edges_direction_outgoing() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-dir-hub", "DirHub")
        await _create_node(c, "nav-dir-out", "DirOut")
        await _create_node(c, "nav-dir-in", "DirIn")

        await _create_edge(c, "nav-dir-hub", "refines", "nav-dir-out")
        await _create_edge(c, "nav-dir-in", "refines", "nav-dir-hub")

        r = await c.get("/api/entities/nav-dir-hub/edges", params={"direction": "outgoing"})
        assert r.status_code == 200
        data = r.json()
        assert all(e["from_id"] == "nav-dir-hub" for e in data["items"])


@pytest.mark.asyncio
async def test_entity_edges_direction_incoming() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-inc-hub", "IncHub")
        await _create_node(c, "nav-inc-src", "IncSrc")

        await _create_edge(c, "nav-inc-src", "inspired-by", "nav-inc-hub")

        r = await c.get("/api/entities/nav-inc-hub/edges", params={"direction": "incoming"})
        assert r.status_code == 200
        data = r.json()
        assert all(e["to_id"] == "nav-inc-hub" for e in data["items"])


@pytest.mark.asyncio
async def test_entity_edges_unknown_entity_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/entities/no-such-entity-xyz/edges")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_entity_edges_type_filter() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-ef-hub", "EFHub")
        await _create_node(c, "nav-ef-a", "EFA")
        await _create_node(c, "nav-ef-b", "EFB")

        await _create_edge(c, "nav-ef-hub", "subsumes", "nav-ef-a")
        await _create_edge(c, "nav-ef-hub", "contradicts", "nav-ef-b")

        r = await c.get("/api/entities/nav-ef-hub/edges", params={"type": "subsumes"})
        assert r.status_code == 200
        data = r.json()
        assert all(e["type"] == "subsumes" for e in data["items"])


# ── Neighbor navigation ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_neighbors_returns_adjacent_nodes() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-nbr-hub", "NbrHub")
        await _create_node(c, "nav-nbr-1", "Nbr1")
        await _create_node(c, "nav-nbr-2", "Nbr2")

        await _create_edge(c, "nav-nbr-hub", "generalises", "nav-nbr-1")
        await _create_edge(c, "nav-nbr-hub", "specialises", "nav-nbr-2")

        r = await c.get("/api/entities/nav-nbr-hub/neighbors")
        assert r.status_code == 200
        data = r.json()
        assert data["entity_id"] == "nav-nbr-hub"
        assert data["total"] >= 2
        assert len(data["neighbors"]) >= 2


@pytest.mark.asyncio
async def test_neighbors_includes_edge_context() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-nbr-ctx", "NbrCtx")
        await _create_node(c, "nav-nbr-peer", "NbrPeer")

        await _create_edge(c, "nav-nbr-ctx", "co-occurs-with", "nav-nbr-peer")

        r = await c.get("/api/entities/nav-nbr-ctx/neighbors")
        assert r.status_code == 200
        neighbors = r.json()["neighbors"]
        assert len(neighbors) >= 1
        via = neighbors[0]["via_edge"]
        assert "type" in via
        assert "direction" in via
        assert "strength" in via


@pytest.mark.asyncio
async def test_neighbors_unknown_entity_returns_404() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/entities/no-such-entity-neighbors/neighbors")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_neighbors_type_filter() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-tf-hub", "TFHub")
        await _create_node(c, "nav-tf-a", "TFA", node_type="concept")
        await _create_node(c, "nav-tf-b", "TFB", node_type="spec")

        await _create_edge(c, "nav-tf-hub", "fractal-scaling", "nav-tf-a")
        await _create_edge(c, "nav-tf-hub", "aggregates", "nav-tf-b")

        r = await c.get(
            "/api/entities/nav-tf-hub/neighbors",
            params={"type": "fractal-scaling"},
        )
        assert r.status_code == 200
        data = r.json()
        assert all(n["via_edge"]["type"] == "fractal-scaling" for n in data["neighbors"])


# ── Edge canonical flag in list responses ─────────────────────────────────────


@pytest.mark.asyncio
async def test_list_edges_includes_canonical_flag() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await _create_node(c, "nav-cf-a", "CFA")
        await _create_node(c, "nav-cf-b", "CFB")

        # canonical
        c1 = await _create_edge(c, "nav-cf-a", "resolves", "nav-cf-b")
        assert c1["canonical"] is True

        # non-canonical
        r2 = await c.post(
            "/api/edges",
            json={"from_id": "nav-cf-a", "to_id": "nav-cf-b", "type": "custom-type-xyz"},
            headers=AUTH,
        )
        assert r2.status_code in (200, 201)
        assert r2.json()["canonical"] is False

        # list should carry canonical flag on each item
        r = await c.get("/api/edges", params={"from_id": "nav-cf-a"})
        assert r.status_code == 200
        items = r.json()["items"]
        for item in items:
            assert "canonical" in item
