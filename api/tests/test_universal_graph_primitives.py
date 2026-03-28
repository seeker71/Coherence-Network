"""Pytest contract for Universal Node + Edge primitives (typed relationships + lifecycle).

Specification (contract summary)
================================
Goal
----
Prove that the data layer treats every entity as a graph node, every relationship as a
typed edge, and that nodes carry Ice / Water / Gas lifecycle phases. This enables the
fractal graph model described in project principles.

Files under test (behavioral surface)
-------------------------------------
- ``app/models/graph.py`` — ``Node``, ``Edge``, ``NodePhase``, ``NodeType``
- ``app/services/graph_service.py`` — CRUD + path/subgraph queries
- ``app/routers/graph.py`` — HTTP API under prefix ``/api`` (see main.py)

API endpoints (must exist for production verification)
----------------------------------------------------
- ``GET|POST  /api/graph/nodes`` — list / create nodes
- ``GET       /api/graph/nodes/count`` — counts
- ``GET       /api/graph/stats`` — aggregate stats
- ``GET|PATCH|DELETE /api/graph/nodes/{node_id}`` — read / update / delete
- ``GET       /api/graph/nodes/{node_id}/edges`` — typed edges for a node
- ``POST      /api/graph/edges`` — create edge
- ``DELETE    /api/graph/edges/{edge_id}`` — delete edge
- ``GET       /api/graph/nodes/{node_id}/neighbors`` — 1-hop neighbors
- ``GET       /api/graph/nodes/{node_id}/subgraph`` — bounded subgraph
- ``GET       /api/graph/path`` — shortest path query

Minimal ontology edge types (task framing — stored as strings, not enum-locked)
-------------------------------------------------------------------------------
``inspires``, ``depends-on``, ``implements``, ``contradicts``, ``extends``,
``analogous-to``, ``parent-of``

Acceptance criteria
-------------------
- Nodes persist ``type``, ``name``, ``phase`` (ice | water | gas), and optional JSON
  ``properties``; API returns them on read.
- Edges persist ``type`` (relationship label), ``from_id``, ``to_id``, ``strength``.
- Listing edges respects ``direction`` (incoming | outgoing | both) and optional
  ``type`` filter.
- Deleting a node removes attached edges (no orphan edges).
- Path/subgraph queries return structured JSON without 500 for valid inputs.

Open questions (tracked in tests via documentation, not assertions)
---------------------------------------------------------------------
- *Minimal edge-type set*: the seven types above cover semantic + hierarchical
  links; operational edges (e.g. ``contributes_to``) remain valid additional labels.
- *Proof over time*: ``GET /api/graph/stats`` exposes counts by node/edge type for
  dashboards; increase coverage by adding integration tests as new routers adopt
  ``graph_service``.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.graph import NodePhase
from app.services import graph_service

# Canonical semantic edge types (Living-Codex-style); service stores arbitrary strings.
CANONICAL_EDGE_TYPES = (
    "inspires",
    "depends-on",
    "implements",
    "contradicts",
    "extends",
    "analogous-to",
    "parent-of",
)


@pytest.mark.asyncio
async def test_node_lifecycle_phases_persist_via_api() -> None:
    """Ice / Water / Gas phases round-trip through POST + GET + PATCH."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/graph/nodes",
            json={
                "id": "phase-spec-a",
                "type": "concept",
                "name": "Lifecycle concept",
                "description": "Phase transitions",
                "phase": NodePhase.ICE.value,
                "properties": {"domain": "test"},
            },
        )
        assert created.status_code == 200
        body = created.json()
        assert body["phase"] == "ice"
        assert body["domain"] == "test"

        g = await client.get("/api/graph/nodes/phase-spec-a")
        assert g.status_code == 200
        assert g.json()["phase"] == "ice"

        u = await client.patch(
            "/api/graph/nodes/phase-spec-a",
            json={"phase": NodePhase.GAS.value},
        )
        assert u.status_code == 200
        assert u.json()["phase"] == "gas"

        w = await client.patch(
            "/api/graph/nodes/phase-spec-a",
            json={"phase": NodePhase.WATER.value},
        )
        assert w.status_code == 200
        assert w.json()["phase"] == "water"


@pytest.mark.asyncio
async def test_typed_edges_full_matrix_create_list_delete() -> None:
    """Each canonical edge type can be created between two nodes and listed by type."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        a = await client.post(
            "/api/graph/nodes",
            json={
                "id": "edge-src",
                "type": "idea",
                "name": "Source",
                "description": "from",
                "phase": "water",
            },
        )
        b = await client.post(
            "/api/graph/nodes",
            json={
                "id": "edge-dst",
                "type": "spec",
                "name": "Target",
                "description": "to",
                "phase": "water",
            },
        )
        assert a.status_code == 200 and b.status_code == 200

        edge_ids: list[str] = []
        for rel in CANONICAL_EDGE_TYPES:
            r = await client.post(
                "/api/graph/edges",
                json={
                    "from_id": "edge-src",
                    "to_id": "edge-dst",
                    "type": rel,
                    "strength": 0.9,
                    "created_by": "pytest",
                },
            )
            assert r.status_code == 200, rel
            data = r.json()
            assert data["type"] == rel
            assert data["from_id"] == "edge-src"
            assert data["to_id"] == "edge-dst"
            edge_ids.append(data["id"])

        for rel in CANONICAL_EDGE_TYPES:
            listed = await client.get(
                "/api/graph/nodes/edge-src/edges",
                params={"direction": "outgoing", "type": rel},
            )
            assert listed.status_code == 200
            arr = listed.json()
            assert len(arr) >= 1
            assert any(e["type"] == rel for e in arr)

        for eid in edge_ids:
            d = await client.delete(f"/api/graph/edges/{eid}")
            assert d.status_code == 200
            assert d.json()["deleted"] == eid


@pytest.mark.asyncio
async def test_crud_cycle_create_read_update_delete_node() -> None:
    """Create → read → update → delete for a service-type node."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post(
            "/api/graph/nodes",
            json={
                "id": "svc-crud-1",
                "type": "service",
                "name": "Auth",
                "description": "v1",
                "phase": "gas",
            },
        )
        assert c.status_code == 200
        assert c.json()["name"] == "Auth"

        r = await client.get("/api/graph/nodes/svc-crud-1")
        assert r.status_code == 200
        assert r.json()["type"] == "service"

        p = await client.patch(
            "/api/graph/nodes/svc-crud-1",
            json={"name": "Auth v2", "description": "updated", "properties": {"port": 443}},
        )
        assert p.status_code == 200
        merged = p.json()
        assert merged["name"] == "Auth v2"
        assert merged["port"] == 443

        dl = await client.delete("/api/graph/nodes/svc-crud-1")
        assert dl.status_code == 200
        assert dl.json()["deleted"] == "svc-crud-1"

        missing = await client.get("/api/graph/nodes/svc-crud-1")
        assert missing.status_code == 404


@pytest.mark.asyncio
async def test_error_missing_node_returns_404_not_500() -> None:
    """GET/PATCH/DELETE unknown node yields 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        g = await client.get("/api/graph/nodes/does-not-exist-zzzz")
        assert g.status_code == 404

        p = await client.patch("/api/graph/nodes/does-not-exist-zzzz", json={"name": "x"})
        assert p.status_code == 404

        d = await client.delete("/api/graph/nodes/does-not-exist-zzzz")
        assert d.status_code == 404


@pytest.mark.asyncio
async def test_error_invalid_edge_direction_rejected() -> None:
    """Invalid ``direction`` query must not succeed silently."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/graph/nodes",
            json={
                "id": "edge-dir-node",
                "type": "concept",
                "name": "n",
                "description": "d",
                "phase": "water",
            },
        )
        bad = await client.get(
            "/api/graph/nodes/edge-dir-node/edges",
            params={"direction": "sideways"},
        )
        assert bad.status_code == 422


@pytest.mark.asyncio
async def test_path_and_subgraph_queries() -> None:
    """Path between two linked nodes; subgraph includes both endpoints."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/graph/nodes",
            json={
                "id": "path-a",
                "type": "domain",
                "name": "A",
                "description": "",
                "phase": "ice",
            },
        )
        await client.post(
            "/api/graph/nodes",
            json={
                "id": "path-b",
                "type": "domain",
                "name": "B",
                "description": "",
                "phase": "ice",
            },
        )
        e = await client.post(
            "/api/graph/edges",
            json={
                "from_id": "path-a",
                "to_id": "path-b",
                "type": "extends",
                "strength": 1.0,
            },
        )
        assert e.status_code == 200

        path_resp = await client.get("/api/graph/path", params={"from_id": "path-a", "to_id": "path-b"})
        assert path_resp.status_code == 200
        pdata = path_resp.json()
        assert pdata.get("length") == 1
        assert isinstance(pdata.get("path"), list)

        sub = await client.get("/api/graph/nodes/path-a/subgraph", params={"depth": 2})
        assert sub.status_code == 200
        sdata = sub.json()
        ids = {n["id"] for n in sdata["nodes"]}
        assert "path-a" in ids and "path-b" in ids
        assert any(ed["type"] == "extends" for ed in sdata["edges"])


def test_duplicate_edge_updates_strength_via_service() -> None:
    """Same (from, to, type) edge coalesces to one row; strength refreshes."""
    graph_service.create_node(id="dup-x", type="idea", name="X", description="", phase="water")
    graph_service.create_node(id="dup-y", type="idea", name="Y", description="", phase="water")
    first = graph_service.create_edge(
        from_id="dup-x", to_id="dup-y", type="depends-on", strength=0.3,
    )
    second = graph_service.create_edge(
        from_id="dup-x", to_id="dup-y", type="depends-on", strength=0.95,
    )
    assert first["id"] == second["id"]
    assert second["strength"] == 0.95
    edges = graph_service.get_edges("dup-x", direction="outgoing", edge_type="depends-on")
    assert len(edges) == 1
    graph_service.delete_node("dup-x")
    graph_service.delete_node("dup-y")


@pytest.mark.asyncio
async def test_delete_node_removes_edges() -> None:
    """Deleting a node removes incident edges (no orphan query results)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/graph/nodes",
            json={
                "id": "cascade-a",
                "type": "contributor",
                "name": "A",
                "description": "",
                "phase": "water",
            },
        )
        await client.post(
            "/api/graph/nodes",
            json={
                "id": "cascade-b",
                "type": "contributor",
                "name": "B",
                "description": "",
                "phase": "water",
            },
        )
        await client.post(
            "/api/graph/edges",
            json={"from_id": "cascade-a", "to_id": "cascade-b", "type": "parent-of"},
        )
        await client.delete("/api/graph/nodes/cascade-a")

        # Former neighbor should have no edges involving cascade-a
        edges_b = await client.get("/api/graph/nodes/cascade-b/edges")
        assert edges_b.status_code == 200
        for e in edges_b.json():
            assert e["from_id"] != "cascade-a"
            assert e["to_id"] != "cascade-a"


@pytest.mark.asyncio
async def test_graph_stats_reflects_node_and_edge_types() -> None:
    """Stats endpoint aggregates by node type and edge type (observability hook)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/graph/nodes",
            json={
                "id": "stat-a",
                "type": "measurement",
                "name": "m1",
                "description": "",
                "phase": "gas",
            },
        )
        await client.post(
            "/api/graph/nodes",
            json={
                "id": "stat-b",
                "type": "measurement",
                "name": "m2",
                "description": "",
                "phase": "ice",
            },
        )
        await client.post(
            "/api/graph/edges",
            json={
                "from_id": "stat-a",
                "to_id": "stat-b",
                "type": "analogous-to",
                "strength": 0.5,
            },
        )
        st = await client.get("/api/graph/stats")
        assert st.status_code == 200
        data = st.json()
        assert "nodes_by_type" in data
        assert "edges_by_type" in data
        assert data["total_nodes"] >= 2
        assert data["total_edges"] >= 1
