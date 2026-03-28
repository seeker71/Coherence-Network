"""Tests for spec-168: Universal Node + Edge Primitives with Typed Relationships.

Covers:
- node_type vocabulary validation (10 canonical types)
- edge_type vocabulary validation (7 canonical types)
- self-loop rejection
- lifecycle defaults by node type (idea→gas, spec→ice, contributor→water)
- lifecycle_state filter on neighbors endpoint
- GET /api/graph/node-types registry (10 entries)
- GET /api/graph/edge-types registry (7 entries)
- GET /api/graph/proof — with data and with empty graph
- full create-read cycle with typed nodes and edges
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"
TRANSPORT = ASGITransport(app=app)


# ── Helpers ──────────────────────────────────────────────────────────


async def _post_node(client: AsyncClient, node_type: str, external_id: str, payload: dict | None = None) -> dict:
    resp = await client.post(
        "/api/graph/nodes",
        json={"node_type": node_type, "external_id": external_id, "payload": payload or {}},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    return resp.json()


async def _post_edge(client: AsyncClient, edge_type: str, from_node_id: str, to_node_id: str, weight: float = 1.0) -> dict:
    resp = await client.post(
        "/api/graph/edges",
        json={"edge_type": edge_type, "from_node_id": from_node_id, "to_node_id": to_node_id, "weight": weight},
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    return resp.json()


# ── node_type validation ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_node_type_accepted() -> None:
    """POST with a valid node_type (idea) returns 200."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        resp = await client.post(
            "/api/graph/nodes",
            json={"node_type": "idea", "external_id": "test-valid-node-type", "payload": {"title": "Test idea"}},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["type"] == "idea"


@pytest.mark.asyncio
async def test_invalid_node_type_rejected() -> None:
    """POST with an unrecognized node_type returns 422 with a descriptive message."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        resp = await client.post(
            "/api/graph/nodes",
            json={"node_type": "widget", "external_id": "test-invalid-node-type", "payload": {}},
        )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "widget" in detail
    # Must list valid types
    assert "idea" in detail or "Valid types" in detail


@pytest.mark.asyncio
async def test_all_10_node_types_accepted() -> None:
    """Each of the 10 canonical node types should be accepted without 422."""
    node_types = [
        "idea", "concept", "spec", "implementation", "service",
        "contributor", "domain", "pipeline-run", "event", "artifact",
    ]
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        for nt in node_types:
            resp = await client.post(
                "/api/graph/nodes",
                json={"node_type": nt, "external_id": f"test-{nt}-node", "payload": {"title": nt}},
            )
            assert resp.status_code == 200, f"node_type={nt} returned {resp.status_code}: {resp.text}"


# ── edge_type validation ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_edge_type_accepted() -> None:
    """POST edge with valid edge_type (extends) returns 200."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        node_a = await _post_node(client, "spec", "edge-valid-a", {"title": "Spec A"})
        node_b = await _post_node(client, "spec", "edge-valid-b", {"title": "Spec B"})
        resp = await client.post(
            "/api/graph/edges",
            json={
                "edge_type": "extends",
                "from_node_id": node_a["id"],
                "to_node_id": node_b["id"],
                "weight": 1.0,
            },
        )
    assert resp.status_code == 200
    assert resp.json()["type"] == "extends"


@pytest.mark.asyncio
async def test_invalid_edge_type_rejected() -> None:
    """POST edge with unrecognized edge_type returns 422 with valid types listed."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        node_a = await _post_node(client, "idea", "edge-inv-a", {})
        node_b = await _post_node(client, "idea", "edge-inv-b", {})
        resp = await client.post(
            "/api/graph/edges",
            json={
                "edge_type": "causes",
                "from_node_id": node_a["id"],
                "to_node_id": node_b["id"],
            },
        )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "causes" in detail


@pytest.mark.asyncio
async def test_all_7_edge_types_accepted() -> None:
    """Each of the 7 canonical edge types must be accepted."""
    edge_types = ["inspires", "depends-on", "implements", "contradicts", "extends", "analogous-to", "parent-of"]
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        # Create one node per edge type pair
        nodes = []
        for i in range(len(edge_types) * 2):
            node = await _post_node(client, "idea", f"edge-type-node-{i}", {"title": f"Node {i}"})
            nodes.append(node["id"])
        for idx, et in enumerate(edge_types):
            from_id = nodes[idx * 2]
            to_id = nodes[idx * 2 + 1]
            resp = await client.post(
                "/api/graph/edges",
                json={"edge_type": et, "from_node_id": from_id, "to_node_id": to_id},
            )
            assert resp.status_code == 200, f"edge_type={et} returned {resp.status_code}: {resp.text}"


# ── Self-loop rejection ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_self_loop_rejected() -> None:
    """POST edge where from_node_id == to_node_id returns 422."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        node = await _post_node(client, "idea", "self-loop-node", {})
        resp = await client.post(
            "/api/graph/edges",
            json={
                "edge_type": "extends",
                "from_node_id": node["id"],
                "to_node_id": node["id"],
            },
        )
    assert resp.status_code == 422
    assert "self" in resp.json()["detail"].lower() or "self-loop" in resp.json()["detail"].lower()


# ── Lifecycle defaults ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifecycle_state_gas_default_for_idea() -> None:
    """POST idea node without lifecycle_state → GET returns lifecycle_state=gas."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        created = await _post_node(client, "idea", "lifecycle-idea-gas", {"title": "Idea node"})
        node_id = created["id"]
        resp = await client.get(f"/api/graph/nodes/{node_id}")
    assert resp.status_code == 200
    data = resp.json()
    # lifecycle_state comes from properties merged into top-level, or from phase
    lifecycle = data.get("lifecycle_state") or data.get("phase")
    assert lifecycle == "gas", f"Expected gas, got {lifecycle!r}. Full response: {data}"


@pytest.mark.asyncio
async def test_lifecycle_state_ice_default_for_spec() -> None:
    """POST spec node without lifecycle_state → GET returns lifecycle_state=ice."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        created = await _post_node(client, "spec", "lifecycle-spec-ice", {"title": "Spec node"})
        node_id = created["id"]
        resp = await client.get(f"/api/graph/nodes/{node_id}")
    assert resp.status_code == 200
    data = resp.json()
    lifecycle = data.get("lifecycle_state") or data.get("phase")
    assert lifecycle == "ice", f"Expected ice, got {lifecycle!r}. Full response: {data}"


@pytest.mark.asyncio
async def test_lifecycle_state_water_default_for_contributor() -> None:
    """POST contributor node without lifecycle_state → GET returns lifecycle_state=water."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        created = await _post_node(client, "contributor", "lifecycle-contributor-water", {"name": "Agent X"})
        node_id = created["id"]
        resp = await client.get(f"/api/graph/nodes/{node_id}")
    assert resp.status_code == 200
    data = resp.json()
    lifecycle = data.get("lifecycle_state") or data.get("phase")
    assert lifecycle == "water", f"Expected water, got {lifecycle!r}. Full response: {data}"


@pytest.mark.asyncio
async def test_lifecycle_state_explicit_overrides_default() -> None:
    """When lifecycle_state is explicitly set, the default is overridden."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        created = await _post_node(
            client, "idea", "lifecycle-explicit",
            {"title": "Explicit lifecycle", "lifecycle_state": "ice"},
        )
        node_id = created["id"]
        resp = await client.get(f"/api/graph/nodes/{node_id}")
    assert resp.status_code == 200
    data = resp.json()
    lifecycle = data.get("lifecycle_state") or data.get("phase")
    assert lifecycle == "ice"


# ── Lifecycle filter on neighbors ──────────────────────────────────────


@pytest.mark.asyncio
async def test_lifecycle_filter_on_neighbors() -> None:
    """GET neighbors with ?lifecycle_state=ice returns only ice neighbors."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        # Node A: idea (gas default)
        node_a = await _post_node(client, "idea", "lf-a", {"title": "Idea A"})
        # Node B: spec (ice default)
        node_b = await _post_node(client, "spec", "lf-b", {"title": "Spec B"})
        # Node C: implementation (water default)
        node_c = await _post_node(client, "implementation", "lf-c", {"title": "Impl C"})

        # A inspires B and C
        await _post_edge(client, "inspires", node_a["id"], node_b["id"])
        await _post_edge(client, "inspires", node_a["id"], node_c["id"])

        # Filter neighbors of A for ice only — should return only B
        resp = await client.get(
            f"/api/graph/nodes/{node_a['id']}/neighbors",
            params={"lifecycle_state": "ice"},
        )
    assert resp.status_code == 200
    data = resp.json()
    neighbors = data.get("neighbors", [])
    neighbor_ids = [n["node"]["id"] for n in neighbors]
    assert node_b["id"] in neighbor_ids, f"Expected spec node B in ice neighbors, got {neighbor_ids}"
    assert node_c["id"] not in neighbor_ids, f"Impl node C (water) should not appear in ice neighbors"


@pytest.mark.asyncio
async def test_lifecycle_filter_invalid_state_returns_422() -> None:
    """GET neighbors with unknown lifecycle_state returns 422."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        node = await _post_node(client, "idea", "lf-invalid", {})
        resp = await client.get(
            f"/api/graph/nodes/{node['id']}/neighbors",
            params={"lifecycle_state": "plasma"},
        )
    assert resp.status_code == 422


# ── Registry endpoints ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_node_types_registry() -> None:
    """GET /api/graph/node-types returns list of exactly 10 types with required fields."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        resp = await client.get("/api/graph/node-types")
    assert resp.status_code == 200
    data = resp.json()
    assert "node_types" in data, f"Response missing 'node_types' key: {list(data.keys())}"
    node_types = data["node_types"]
    assert len(node_types) == 10, f"Expected 10 node types, got {len(node_types)}: {[t['type'] for t in node_types]}"

    required_fields = {"type", "description", "lifecycle_default"}
    for entry in node_types:
        missing = required_fields - set(entry.keys())
        assert not missing, f"Entry {entry.get('type')} missing fields: {missing}"

    # Verify the 10 canonical types are present
    type_names = {e["type"] for e in node_types}
    expected = {"idea", "concept", "spec", "implementation", "service", "contributor", "domain", "pipeline-run", "event", "artifact"}
    assert expected == type_names, f"Type mismatch. Got: {type_names}"


@pytest.mark.asyncio
async def test_get_edge_types_registry() -> None:
    """GET /api/graph/edge-types returns list of exactly 7 types with required fields."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        resp = await client.get("/api/graph/edge-types")
    assert resp.status_code == 200
    data = resp.json()
    assert "edge_types" in data, f"Response missing 'edge_types' key: {list(data.keys())}"
    edge_types = data["edge_types"]
    assert len(edge_types) == 7, f"Expected 7 edge types, got {len(edge_types)}: {[t['type'] for t in edge_types]}"

    required_fields = {"type", "description", "is_symmetric"}
    for entry in edge_types:
        missing = required_fields - set(entry.keys())
        assert not missing, f"Entry {entry.get('type')} missing fields: {missing}"

    # Verify symmetric flags
    symmetric_types = {e["type"] for e in edge_types if e["is_symmetric"]}
    assert "contradicts" in symmetric_types
    assert "analogous-to" in symmetric_types
    assert "inspires" not in symmetric_types
    assert "parent-of" not in symmetric_types


# ── Proof endpoint ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_proof_endpoint_empty_graph() -> None:
    """GET /api/graph/proof returns 200 with zero counts on empty graph."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        resp = await client.get("/api/graph/proof")
    assert resp.status_code == 200
    data = resp.json()

    assert "total_nodes" in data
    assert "total_edges" in data
    assert "nodes_by_type" in data
    assert "edges_by_type" in data
    assert "lifecycle_distribution" in data
    assert "coverage_pct" in data

    assert data["total_nodes"] == 0
    assert data["total_edges"] == 0
    assert isinstance(data["nodes_by_type"], dict)
    assert isinstance(data["edges_by_type"], dict)
    assert isinstance(data["lifecycle_distribution"], dict)

    coverage = data["coverage_pct"]
    assert "ideas_with_spec" in coverage
    assert "specs_with_impl" in coverage
    assert "impls_with_test" in coverage
    assert coverage["ideas_with_spec"] == 0.0
    assert coverage["specs_with_impl"] == 0.0
    assert coverage["impls_with_test"] == 0.0


@pytest.mark.asyncio
async def test_get_proof_endpoint() -> None:
    """GET /api/graph/proof returns correct stats with populated graph."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        node_a = await _post_node(client, "idea", "proof-a", {"title": "Idea A"})
        node_b = await _post_node(client, "spec", "proof-b", {"title": "Spec B"})
        await _post_edge(client, "inspires", node_a["id"], node_b["id"])

        resp = await client.get("/api/graph/proof")
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_nodes"] == 2
    assert data["total_edges"] == 1
    assert "idea" in data["nodes_by_type"]
    assert "spec" in data["nodes_by_type"]
    assert "inspires" in data["edges_by_type"]
    assert "gas" in data["lifecycle_distribution"] or "ice" in data["lifecycle_distribution"]


# ── Full lifecycle transition ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_lifecycle_transition() -> None:
    """Create idea in gas, update payload lifecycle_state to ice, GET shows ice; update to water, GET shows water."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        created = await _post_node(client, "idea", "lifecycle-transition", {"title": "Lifecycle test"})
        node_id = created["id"]

        # Initial state should be gas
        resp = await client.get(f"/api/graph/nodes/{node_id}")
        data = resp.json()
        lifecycle = data.get("lifecycle_state") or data.get("phase")
        assert lifecycle == "gas"

        # Transition to ice via PATCH
        patch_resp = await client.patch(
            f"/api/graph/nodes/{node_id}",
            json={"phase": "ice", "properties": {"lifecycle_state": "ice"}},
        )
        assert patch_resp.status_code == 200

        resp2 = await client.get(f"/api/graph/nodes/{node_id}")
        data2 = resp2.json()
        lifecycle2 = data2.get("lifecycle_state") or data2.get("phase")
        assert lifecycle2 == "ice"

        # Transition to water
        patch_resp2 = await client.patch(
            f"/api/graph/nodes/{node_id}",
            json={"phase": "water", "properties": {"lifecycle_state": "water"}},
        )
        assert patch_resp2.status_code == 200

        resp3 = await client.get(f"/api/graph/nodes/{node_id}")
        data3 = resp3.json()
        lifecycle3 = data3.get("lifecycle_state") or data3.get("phase")
        assert lifecycle3 == "water"


# ── Symmetric edge: contradicts ────────────────────────────────────────


@pytest.mark.asyncio
async def test_contradicts_symmetric_both_directions() -> None:
    """Create A→B edge of type contradicts; neighbors of B shows A as incoming."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        node_a = await _post_node(client, "idea", "sym-a", {"title": "Idea A"})
        node_b = await _post_node(client, "idea", "sym-b", {"title": "Idea B"})
        await _post_edge(client, "contradicts", node_a["id"], node_b["id"])

        # Neighbors of B should include A (incoming edge)
        resp = await client.get(
            f"/api/graph/nodes/{node_b['id']}/neighbors",
            params={"direction": "both"},
        )
    assert resp.status_code == 200
    data = resp.json()
    neighbors = data.get("neighbors", [])
    neighbor_ids = [n["node"]["id"] for n in neighbors]
    assert node_a["id"] in neighbor_ids, f"Expected A in B's neighbors, got {neighbor_ids}"

    # Verify direction is 'incoming'
    a_entry = next(n for n in neighbors if n["node"]["id"] == node_a["id"])
    assert a_entry["via_edge"]["direction"] == "incoming"


# ── Full create-read cycle ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_create_read_cycle() -> None:
    """Full create-read cycle: typed nodes, typed edge, neighbor traversal."""
    async with AsyncClient(transport=TRANSPORT, base_url=BASE) as client:
        # Create idea (gas default) and spec (ice default)
        idea = await _post_node(client, "idea", "cycle-idea", {"title": "Cycle Idea"})
        spec = await _post_node(client, "spec", "cycle-spec", {"title": "Cycle Spec"})

        assert (idea.get("lifecycle_state") or idea.get("phase")) == "gas"
        assert (spec.get("lifecycle_state") or spec.get("phase")) == "ice"

        # Create inspires edge: idea → spec
        edge = await _post_edge(client, "inspires", idea["id"], spec["id"])
        assert edge["type"] == "inspires"

        # Read neighbors of idea — should include spec
        resp = await client.get(f"/api/graph/nodes/{idea['id']}/neighbors")
        assert resp.status_code == 200
        data = resp.json()
        neighbor_ids = [n["node"]["id"] for n in data.get("neighbors", [])]
        assert spec["id"] in neighbor_ids

        # Re-POST same node → upsert returns same id
        idea2_resp = await client.post(
            "/api/graph/nodes",
            json={"node_type": "idea", "external_id": "cycle-idea", "payload": {"title": "Cycle Idea"}},
        )
        assert idea2_resp.status_code == 200
        assert idea2_resp.json()["id"] == idea["id"], "Upsert should return same ID"
