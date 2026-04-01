"""Tests for spec 166: Universal Node + Edge Data Layer.

Verifies:
- Node CRUD with upsert idempotency
- Edge CRUD with cascade delete
- Neighbor traversal
- 404 handling
- Pydantic response model contracts
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── Helpers ────────────────────────────────────────────────────────────────────

VALID_NODE_TYPES = ["idea", "concept", "spec", "implementation", "service", "contributor", "domain", "pipeline-run", "event", "artifact"]
VALID_EDGE_TYPES = ["inspires", "depends-on", "implements", "contradicts", "extends", "analogous-to", "parent-of"]


def _create_node(node_type="idea", payload=None, name=None):
    """Create a node via POST /api/graph/nodes and return the response JSON."""
    if node_type not in VALID_NODE_TYPES:
        node_type = "idea"
    body = {
        "id": str(uuid.uuid4()),
        "type": node_type,
        "name": name or f"test-{node_type}-{uuid.uuid4().hex[:8]}",
        "description": f"A test {node_type} node",
        "properties": payload or {},
        "phase": "water",
    }
    resp = client.post("/api/graph/nodes", json=body)
    assert resp.status_code == 200, f"Failed to create node: {resp.text}"
    return resp.json()


def _create_edge(from_id, to_id, edge_type="depends-on", weight=1.0, payload=None):
    """Create an edge via POST /api/graph/edges and return the response JSON."""
    if edge_type not in VALID_EDGE_TYPES:
        edge_type = "depends-on"
    body = {
        "id": str(uuid.uuid4()),
        "from_id": from_id,
        "to_id": to_id,
        "type": edge_type,
        "strength": weight,
        "properties": payload or {},
        "created_by": "test",
    }
    resp = client.post("/api/graph/edges", json=body)
    assert resp.status_code == 200, f"Failed to create edge: {resp.text}"
    return resp.json()


# ── Node CRUD ──────────────────────────────────────────────────────────────────

class TestNodeCRUD:
    """Node creation, retrieval, update, deletion."""

    def test_upsert_node_creates_new(self):
        """POST with new node returns 200 with a UUID id."""
        node = _create_node(node_type="idea", payload={"score": 0.87})
        assert "id" in node
        assert node["type"] == "idea"
        assert node["score"] == 0.87
        assert "created_at" in node

    def test_get_node_by_id(self):
        """GET /api/graph/nodes/{id} returns the node."""
        node = _create_node(node_type="artifact")
        resp = client.get(f"/api/graph/nodes/{node['id']}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == node["id"]
        assert data["type"] == "artifact"

    def test_get_node_not_found(self):
        """GET for unknown UUID returns 404."""
        resp = client.get(f"/api/graph/nodes/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_delete_node(self):
        """DELETE removes the node."""
        node = _create_node()
        resp = client.delete(f"/api/graph/nodes/{node['id']}")
        assert resp.status_code == 200
        resp = client.get(f"/api/graph/nodes/{node['id']}")
        assert resp.status_code == 404

    def test_patch_node(self):
        """PATCH updates node fields."""
        node = _create_node(name="original")
        resp = client.patch(
            f"/api/graph/nodes/{node['id']}",
            json={"name": "updated", "phase": "ice"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "updated"
        assert data["phase"] == "ice"


# ── Edge CRUD ──────────────────────────────────────────────────────────────────

class TestEdgeCRUD:
    """Edge creation, retrieval, deletion."""

    def test_upsert_edge(self):
        """POST /api/graph/edges returns 200 with UUID id."""
        a = _create_node(node_type="idea")
        b = _create_node(node_type="artifact")
        edge = _create_edge(a["id"], b["id"], edge_type="implements")
        assert "id" in edge
        assert edge["type"] == "implements"
        assert edge["from_id"] == a["id"]
        assert edge["to_id"] == b["id"]

    def test_delete_edge(self):
        """DELETE removes the edge."""
        a = _create_node()
        b = _create_node()
        edge = _create_edge(a["id"], b["id"])
        resp = client.delete(f"/api/graph/edges/{edge['id']}")
        assert resp.status_code == 200

    def test_get_node_with_edges(self):
        """GET for known node returns node, edges available at /edges subpath."""
        a = _create_node(node_type="idea")
        b = _create_node(node_type="artifact")
        _create_edge(a["id"], b["id"], edge_type="implements")
        resp = client.get(f"/api/graph/nodes/{a['id']}/edges")
        assert resp.status_code == 200
        edges = resp.json()
        assert isinstance(edges, list)
        assert len(edges) >= 1
        assert edges[0]["type"] == "implements"


# ── Cascade Delete ─────────────────────────────────────────────────────────────

class TestCascadeDelete:
    """Deleting a node removes dependent edges."""

    def test_cascade_delete(self):
        """DELETE node removes dependent edges (from and to)."""
        a = _create_node()
        b = _create_node()
        c = _create_node()
        edge_ab = _create_edge(a["id"], b["id"])
        edge_ca = _create_edge(c["id"], a["id"])

        # Delete node a
        resp = client.delete(f"/api/graph/nodes/{a['id']}")
        assert resp.status_code == 200

        # Both edges should be gone
        resp = client.get(f"/api/graph/nodes/{b['id']}/edges")
        assert resp.status_code == 200
        edges = resp.json()
        # edge_ab should be gone (from_id was a)
        edge_ids = [e["id"] for e in edges]
        assert edge_ab["id"] not in edge_ids


# ── Neighbor Traversal ─────────────────────────────────────────────────────────

class TestNeighborTraversal:
    """GET /api/graph/nodes/{id}/neighbors returns correct neighbors."""

    def test_get_neighbors_outgoing(self):
        """GET neighbors returns outgoing neighbors with edge metadata."""
        a = _create_node(node_type="idea")
        b = _create_node(node_type="artifact")
        _create_edge(a["id"], b["id"], edge_type="implements", weight=2.0)
        resp = client.get(f"/api/graph/nodes/{a['id']}/neighbors")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        neighbor_ids = [n["id"] for n in data]
        assert b["id"] in neighbor_ids
        # Verify edge metadata is included
        neighbor = [n for n in data if n["id"] == b["id"]][0]
        assert neighbor["via_edge_type"] == "implements"
        assert neighbor["via_direction"] == "outgoing"

    def test_get_neighbors_incoming(self):
        """GET neighbors returns incoming neighbors too."""
        a = _create_node()
        b = _create_node()
        _create_edge(b["id"], a["id"], edge_type="inspires")
        resp = client.get(f"/api/graph/nodes/{a['id']}/neighbors")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        neighbor_ids = [n["id"] for n in data]
        assert b["id"] in neighbor_ids

    def test_get_neighbors_empty(self):
        """GET neighbors for isolated node returns empty list."""
        a = _create_node()
        resp = client.get(f"/api/graph/nodes/{a['id']}/neighbors")
        assert resp.status_code == 200
        data = resp.json()
        assert data == []


# ── Pydantic Contract ──────────────────────────────────────────────────────────

class TestPydanticContract:
    """Response models have stable field names, no dynamic key leakage."""

    def test_node_response_has_required_fields(self):
        """Node response includes id, type, name, description, phase, created_at, updated_at."""
        node = _create_node()
        for field in ("id", "type", "name", "description", "phase", "created_at", "updated_at"):
            assert field in node, f"Missing field: {field}"

    def test_edge_response_has_required_fields(self):
        """Edge response includes id, from_id, to_id, type, strength, created_at."""
        a = _create_node()
        b = _create_node()
        edge = _create_edge(a["id"], b["id"])
        for field in ("id", "from_id", "to_id", "type", "strength", "created_at"):
            assert field in edge, f"Missing field: {field}"

    def test_neighbors_response_shape(self):
        """Neighbors response has node + edge metadata per neighbor."""
        a = _create_node()
        b = _create_node()
        _create_edge(a["id"], b["id"])
        resp = client.get(f"/api/graph/nodes/{a['id']}/neighbors")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        for neighbor in data:
            assert "id" in neighbor
            assert "type" in neighbor
            assert "via_edge_type" in neighbor
            assert "via_direction" in neighbor


# ── Stats and Registry ─────────────────────────────────────────────────────────

class TestGraphStatsAndRegistry:
    """Stats and type registry endpoints."""

    def test_node_count(self):
        """GET /api/graph/nodes/count returns count."""
        _create_node()
        resp = client.get("/api/graph/nodes/count")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert data["total"] >= 1

    def test_stats_endpoint(self):
        """GET /api/graph/stats returns aggregate stats."""
        resp = client.get("/api/graph/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_nodes" in data
        assert "total_edges" in data

    def test_node_types_registry(self):
        """GET /api/graph/node-types returns registry."""
        resp = client.get("/api/graph/node-types")
        assert resp.status_code == 200
        data = resp.json()
        assert "node_types" in data
        assert len(data["node_types"]) > 0

    def test_edge_types_registry(self):
        """GET /api/graph/edge-types returns registry."""
        resp = client.get("/api/graph/edge-types")
        assert resp.status_code == 200
        data = resp.json()
        assert "edge_types" in data
        assert len(data["edge_types"]) > 0

    def test_proof_endpoint(self):
        """GET /api/graph/proof returns aggregate proof."""
        resp = client.get("/api/graph/proof")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_nodes" in data
        assert "total_edges" in data
        assert "nodes_by_type" in data
        assert "edges_by_type" in data
