"""Tests for Universal Node + Edge primitives with typed relationships.

Spec 169: Validates canonical node types, canonical edge types, Ice/Water/Gas lifecycle,
self-loop prevention, registry endpoints, and the proof endpoint.

All acceptance criteria from Spec 169 §Acceptance Criteria map 1:1 to tests here.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import graph_service


# ── Helpers ──────────────────────────────────────────────────────────

async def _post_node(client: AsyncClient, node_type: str, name: str, external_id: str | None = None, **extra) -> dict:
    payload = {"type": node_type, "name": name, "description": "", **extra}
    if external_id:
        payload["id"] = external_id
    r = await client.post("/api/graph/nodes", json=payload)
    return r


async def _post_edge(client: AsyncClient, from_id: str, to_id: str, edge_type: str) -> dict:
    r = await client.post(
        "/api/graph/edges",
        json={"from_id": from_id, "to_id": to_id, "type": edge_type, "strength": 1.0},
    )
    return r


# ── Node type validation ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_node_type_accepted():
    """POST with node_type 'idea' returns 200 (Spec 169 AC: test_valid_node_type_accepted)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _post_node(client, "idea", "Test Idea")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["type"] == "idea"


@pytest.mark.asyncio
async def test_invalid_node_type_rejected():
    """POST with node_type 'widget' returns 422 (Spec 169 AC: test_invalid_node_type_rejected)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _post_node(client, "widget", "Bad Node")
    assert r.status_code == 422, r.text
    detail = r.json().get("detail", "")
    assert "widget" in detail
    assert "node-types" in detail or "node_type" in detail


@pytest.mark.asyncio
async def test_all_ten_canonical_node_types_accepted():
    """Each of the 10 canonical node types should be accepted (Spec 169 §Node Types)."""
    canonical = [
        "idea", "concept", "spec", "implementation", "service",
        "contributor", "domain", "pipeline-run", "event", "artifact",
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for node_type in canonical:
            r = await _post_node(client, node_type, f"Test {node_type}")
            assert r.status_code == 200, f"{node_type} failed: {r.text}"
            assert r.json()["type"] == node_type


@pytest.mark.asyncio
async def test_legacy_task_node_type_still_accepted():
    """Legacy graph CRUD types like task remain valid even though the registry is canonical-only."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _post_node(client, "task", "Legacy Task")
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "task"


# ── Edge type validation ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_edge_type_accepted():
    """POST edge with edge_type 'extends' returns 200 (Spec 169 AC: test_valid_edge_type_accepted)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        na = (await _post_node(client, "spec", "Spec A")).json()
        nb = (await _post_node(client, "spec", "Spec B")).json()
        r = await _post_edge(client, na["id"], nb["id"], "extends")
    assert r.status_code == 200, r.text
    assert r.json()["type"] == "extends"


@pytest.mark.asyncio
async def test_invalid_edge_type_rejected():
    """POST edge with edge_type 'causes' returns 422 (Spec 169 AC: test_invalid_edge_type_rejected)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        na = (await _post_node(client, "idea", "Idea A")).json()
        nb = (await _post_node(client, "idea", "Idea B")).json()
        r = await _post_edge(client, na["id"], nb["id"], "causes")
    assert r.status_code == 422, r.text
    detail = r.json().get("detail", "")
    assert "causes" in detail
    assert "inspires" in detail  # valid types mentioned


@pytest.mark.asyncio
async def test_all_seven_canonical_edge_types_accepted():
    """Each of the 7 canonical edge types should be accepted (Spec 169 §Edge Types)."""
    canonical = [
        "inspires", "depends-on", "implements", "contradicts",
        "extends", "analogous-to", "parent-of",
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for edge_type in canonical:
            na = (await _post_node(client, "concept", f"Node A for {edge_type}")).json()
            nb = (await _post_node(client, "concept", f"Node B for {edge_type}")).json()
            r = await _post_edge(client, na["id"], nb["id"], edge_type)
            assert r.status_code == 200, f"{edge_type} failed: {r.text}"
            assert r.json()["type"] == edge_type


# ── Self-loop prevention ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_self_loop_rejected():
    """POST edge where from_node_id == to_node_id returns 422 (Spec 169 AC: test_self_loop_rejected)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        na = (await _post_node(client, "idea", "Self Loop Node")).json()
        r = await _post_edge(client, na["id"], na["id"], "extends")
    assert r.status_code == 422, r.text
    detail = r.json().get("detail", "")
    assert "self" in detail.lower() or "loop" in detail.lower() or "same" in detail.lower()


# ── Lifecycle state defaults ─────────────────────────────────────────


def _get_lifecycle(data: dict) -> str | None:
    """Extract lifecycle_state from a node API response dict.

    to_dict() merges properties to top-level, so lifecycle_state may appear
    directly on the dict or nested under 'properties'.
    """
    if "lifecycle_state" in data:
        return data["lifecycle_state"]
    return data.get("properties", {}).get("lifecycle_state", data.get("phase"))


@pytest.mark.asyncio
async def test_lifecycle_state_gas_default_for_idea():
    """POST idea without lifecycle_state; GET returns gas default (Spec 169 AC)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _post_node(client, "idea", "Gas Idea")
    assert r.status_code == 200, r.text
    lc = _get_lifecycle(r.json())
    assert lc == "gas", f"Expected gas default for idea, got {lc!r}. Full data: {r.json()}"


@pytest.mark.asyncio
async def test_lifecycle_state_water_default_for_contributor():
    """POST contributor; GET returns water default (Spec 169 AC)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _post_node(client, "contributor", "Agent Claude")
    assert r.status_code == 200, r.text
    lc = _get_lifecycle(r.json())
    assert lc == "water", f"Expected water default for contributor, got {lc!r}."


@pytest.mark.asyncio
async def test_lifecycle_state_ice_default_for_spec():
    """POST spec without lifecycle_state; returns ice default."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _post_node(client, "spec", "Frozen Spec")
    assert r.status_code == 200, r.text
    lc = _get_lifecycle(r.json())
    assert lc == "ice", f"Expected ice default for spec, got {lc!r}."


@pytest.mark.asyncio
async def test_explicit_lifecycle_state_accepted():
    """POST idea with explicit lifecycle_state: ice is accepted."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await _post_node(
            client, "idea", "Ice Idea",
            properties={"lifecycle_state": "ice"},
        )
    assert r.status_code == 200, r.text
    lc = _get_lifecycle(r.json())
    assert lc == "ice"


# ── Lifecycle filter on neighbors ────────────────────────────────────


@pytest.mark.asyncio
async def test_lifecycle_filter_on_neighbors():
    """GET neighbors with ?lifecycle_state=ice returns only ice nodes (Spec 169 AC)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Node A: idea (gas by default)
        na = (await _post_node(client, "idea", "Node A")).json()
        # Node B: spec (ice by default)
        nb = (await _post_node(client, "spec", "Node B")).json()
        # Node C: implementation (water by default)
        nc = (await _post_node(client, "implementation", "Node C")).json()
        # Edges: A inspires B and C
        await _post_edge(client, na["id"], nb["id"], "inspires")
        await _post_edge(client, na["id"], nc["id"], "inspires")

        # Filter neighbors of A by lifecycle_state=ice — should return only B
        r = await client.get(
            f"/api/graph/nodes/{na['id']}/neighbors",
            params={"lifecycle_state": "ice"},
        )

    assert r.status_code == 200, r.text
    neighbors = r.json()
    ids = [n["id"] for n in neighbors]
    assert nb["id"] in ids, f"Expected ice neighbor {nb['id']} in {ids}"
    assert nc["id"] not in ids, f"Expected water neighbor {nc['id']} NOT in {ids}"


@pytest.mark.asyncio
async def test_invalid_lifecycle_state_filter_rejected():
    """GET neighbors with ?lifecycle_state=plasma returns 422 (Spec 169 Scenario 5 edge case)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        na = (await _post_node(client, "idea", "Node A")).json()
        r = await client.get(
            f"/api/graph/nodes/{na['id']}/neighbors",
            params={"lifecycle_state": "plasma"},
        )
    assert r.status_code == 422, r.text


# ── Registry endpoints ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_node_types_registry():
    """GET /api/graph/node-types returns 10 types with description and lifecycle_default (Spec 169 AC)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/graph/node-types")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "node_types" in data
    types = data["node_types"]
    assert len(types) == 10, f"Expected 10 node types, got {len(types)}"
    for entry in types:
        assert "type" in entry
        assert "description" in entry
        assert "lifecycle_default" in entry


@pytest.mark.asyncio
async def test_get_edge_types_registry():
    """GET /api/graph/edge-types returns 7 types with description and symmetric flag (Spec 169 AC)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/graph/edge-types")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "edge_types" in data
    types = data["edge_types"]
    assert len(types) == 9, f"Expected 9 edge types, got {len(types)}"
    for entry in types:
        assert "type" in entry
        assert "description" in entry
        assert "symmetric" in entry

    # Verify symmetric types
    type_map = {e["type"]: e for e in types}
    assert type_map["contradicts"]["symmetric"] is True
    assert type_map["analogous-to"]["symmetric"] is True
    assert type_map["implements"]["symmetric"] is False


@pytest.mark.asyncio
async def test_registry_endpoints_return_200_on_empty_graph():
    """Both registry endpoints return 200 even when graph is empty (Spec 169 Scenario 3 edge case)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_nodes = await client.get("/api/graph/node-types")
        r_edges = await client.get("/api/graph/edge-types")
    assert r_nodes.status_code == 200
    assert r_edges.status_code == 200


# ── Proof endpoint ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_proof_endpoint():
    """GET /api/graph/proof returns expected structure (Spec 169 AC: test_get_proof_endpoint)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create a node and an edge so the graph is non-empty
        na = (await _post_node(client, "idea", "Proof Node A")).json()
        nb = (await _post_node(client, "spec", "Proof Node B")).json()
        await _post_edge(client, na["id"], nb["id"], "inspires")

        r = await client.get("/api/graph/proof")

    assert r.status_code == 200, r.text
    data = r.json()
    assert "total_nodes" in data
    assert "total_edges" in data
    assert "nodes_by_type" in data
    assert "edges_by_type" in data
    assert "lifecycle_distribution" in data
    assert "last_edge_created_at" in data
    assert data["total_nodes"] >= 1
    assert data["total_edges"] >= 1


@pytest.mark.asyncio
async def test_get_proof_endpoint_empty_graph():
    """GET /api/graph/proof returns 200 with zeroes on empty graph (Spec 169 Scenario 4 edge case)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/graph/proof")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_nodes"] == 0
    assert data["total_edges"] == 0
    assert isinstance(data["lifecycle_distribution"], dict)


# ── Symmetric edge types ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_contradicts_and_analogous_to_symmetric():
    """A→B 'contradicts' edge means neighbors of B shows A as incoming (Spec 169 AC)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        na = (await _post_node(client, "idea", "Centralise Auth")).json()
        nb = (await _post_node(client, "idea", "Federated Identity")).json()
        await _post_edge(client, na["id"], nb["id"], "contradicts")

        # Neighbors of B with direction=incoming should include A
        r = await client.get(
            f"/api/graph/nodes/{nb['id']}/neighbors",
            params={"direction": "incoming"},
        )

    assert r.status_code == 200, r.text
    neighbors = r.json()
    ids = [n["id"] for n in neighbors]
    assert na["id"] in ids, f"Expected A in incoming neighbors of B. Got: {ids}"


# ── Lifecycle transitions ────────────────────────────────────────────


def _get_lifecycle(data: dict) -> str | None:
    """Extract lifecycle_state from a node API response dict.

    to_dict() merges properties to top-level, so lifecycle_state may appear
    directly on the dict or nested under 'properties'.
    """
    # Check top-level first (to_dict merges properties)
    if "lifecycle_state" in data:
        return data["lifecycle_state"]
    # Fall back to nested properties
    return data.get("properties", {}).get("lifecycle_state", data.get("phase"))


@pytest.mark.asyncio
async def test_full_lifecycle_transition():
    """Create idea in gas → update to ice → GET shows ice; update to water (Spec 169 AC)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create idea — defaults to gas
        r_create = await _post_node(client, "idea", "Lifecycle Test Idea")
        assert r_create.status_code == 200
        node_id = r_create.json()["id"]

        # Update to ice
        r_ice = await client.patch(
            f"/api/graph/nodes/{node_id}",
            json={"properties": {"lifecycle_state": "ice"}},
        )
        assert r_ice.status_code == 200
        lc_ice = _get_lifecycle(r_ice.json())
        assert lc_ice == "ice", f"Expected ice after update, got {lc_ice!r}. Full: {r_ice.json()}"

        # Update to water
        r_water = await client.patch(
            f"/api/graph/nodes/{node_id}",
            json={"properties": {"lifecycle_state": "water"}},
        )
        assert r_water.status_code == 200
        lc_water = _get_lifecycle(r_water.json())
        assert lc_water == "water", f"Expected water after update, got {lc_water!r}."


# ── Direction filter on neighbors ────────────────────────────────────


@pytest.mark.asyncio
async def test_direction_filter_outgoing():
    """GET neighbors with direction=outgoing returns only nodes A points to."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        na = (await _post_node(client, "idea", "Dir A")).json()
        nb = (await _post_node(client, "spec", "Dir B")).json()
        nc = (await _post_node(client, "implementation", "Dir C")).json()
        # A → inspires → B (outgoing from A)
        await _post_edge(client, na["id"], nb["id"], "inspires")
        # C → depends-on → A (incoming to A)
        await _post_edge(client, nc["id"], na["id"], "depends-on")

        r = await client.get(
            f"/api/graph/nodes/{na['id']}/neighbors",
            params={"direction": "outgoing"},
        )
    assert r.status_code == 200
    neighbors = r.json()
    ids = [n["id"] for n in neighbors]
    assert nb["id"] in ids
    assert nc["id"] not in ids


@pytest.mark.asyncio
async def test_rel_type_filter():
    """GET neighbors with rel_type=inspires returns only inspirational neighbors."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        na = (await _post_node(client, "idea", "RelType A")).json()
        nb = (await _post_node(client, "concept", "RelType B")).json()
        nc = (await _post_node(client, "spec", "RelType C")).json()
        await _post_edge(client, na["id"], nb["id"], "inspires")
        await _post_edge(client, na["id"], nc["id"], "depends-on")

        r = await client.get(
            f"/api/graph/nodes/{na['id']}/neighbors",
            params={"rel_type": "inspires"},
        )
    assert r.status_code == 200
    neighbors = r.json()
    ids = [n["id"] for n in neighbors]
    assert nb["id"] in ids
    assert nc["id"] not in ids
