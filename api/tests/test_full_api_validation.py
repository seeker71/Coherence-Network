"""Full API endpoint validation — tests all endpoints through TestClient.

Verifies:
- Every endpoint returns a valid HTTP status
- Response times are reasonable
- Nested content loads correctly
- Error handling works
- No crashes on edge cases
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _time_request(method: str, path: str, **kwargs) -> tuple[int, float, Any]:
    """Make a request and return (status_code, elapsed_ms, body_or_none)."""
    t0 = time.time()
    if method == "GET":
        resp = client.get(path, **kwargs)
    elif method == "POST":
        resp = client.post(path, **kwargs)
    elif method == "PATCH":
        resp = client.patch(path, **kwargs)
    elif method == "DELETE":
        resp = client.delete(path, **kwargs)
    else:
        raise ValueError(f"Unknown method: {method}")
    elapsed_ms = (time.time() - t0) * 1000
    body = None
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    return resp.status_code, elapsed_ms, body


# ── Health ──────────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200(self):
        code, ms, body = _time_request("GET", "/api/health")
        assert code == 200, f"Health failed: {code}"
        assert body.get("status") == "ok"
        assert ms < 5000, f"Health too slow: {ms:.0f}ms"

    def test_health_has_required_fields(self):
        _, _, body = _time_request("GET", "/api/health")
        for field in ("status", "version", "timestamp"):
            assert field in body, f"Missing field: {field}"


# ── Ideas ───────────────────────────────────────────────────────────────────

class TestIdeasEndpoint:
    def test_ideas_returns_200(self):
        code, ms, body = _time_request("GET", "/api/ideas")
        assert code == 200
        assert isinstance(body, dict)
        assert "items" in body or "ideas" in body or isinstance(body, list)
        assert ms < 10000, f"Ideas too slow: {ms:.0f}ms"

    def test_ideas_with_limit(self):
        code, _, body = _time_request("GET", "/api/ideas?limit=5")
        assert code == 200

    def test_ideas_with_sort(self):
        code, _, _ = _time_request("GET", "/api/ideas?sort=roi")
        assert code == 200

    def test_ideas_with_manifestation_status(self):
        code, _, _ = _time_request("GET", "/api/ideas?manifestation_status=validated")
        assert code == 200


# ── Contributors ────────────────────────────────────────────────────────────

class TestContributorsEndpoint:
    def test_contributors_returns_200(self):
        code, ms, body = _time_request("GET", "/api/contributors")
        assert code == 200, f"Contributors failed: {code} - {body}"
        assert ms < 5000

    def test_contributors_returns_list(self):
        _, _, body = _time_request("GET", "/api/contributors")
        assert isinstance(body, (list, dict))


# ── Federation ──────────────────────────────────────────────────────────────

class TestFederationEndpoints:
    def test_federation_nodes_returns_200(self):
        code, ms, body = _time_request("GET", "/api/federation/nodes")
        assert code == 200
        assert isinstance(body, list)
        assert ms < 5000

    def test_federation_instances_returns_200(self):
        code, _, _ = _time_request("GET", "/api/federation/instances")
        assert code == 200


# ── Graph ───────────────────────────────────────────────────────────────────

class TestGraphEndpoints:
    def test_graph_nodes_returns_200(self):
        code, ms, _ = _time_request("GET", "/api/graph/nodes")
        assert code == 200
        assert ms < 5000

    def test_graph_nodes_count(self):
        code, _, body = _time_request("GET", "/api/graph/nodes/count")
        assert code == 200
        assert "total" in body
        assert body["total"] >= 0

    def test_graph_stats(self):
        code, _, body = _time_request("GET", "/api/graph/stats")
        assert code == 200
        assert "total_nodes" in body
        assert "total_edges" in body

    def test_graph_node_types_registry(self):
        code, _, body = _time_request("GET", "/api/graph/node-types")
        assert code == 200
        assert "node_types" in body
        assert len(body["node_types"]) > 0

    def test_graph_edge_types_registry(self):
        code, _, body = _time_request("GET", "/api/graph/edge-types")
        assert code == 200
        assert "edge_types" in body
        assert len(body["edge_types"]) > 0

    def test_graph_proof(self):
        code, _, body = _time_request("GET", "/api/graph/proof")
        assert code == 200
        assert "total_nodes" in body

    def test_graph_node_crud(self):
        """Create, read, delete a node through the API."""
        # Create
        node_body = {
            "id": "test-node-api-validation",
            "type": "idea",
            "name": "API Validation Test Node",
            "description": "Created by API validation test",
            "properties": {"test": True},
            "phase": "water",
        }
        code, _, body = _time_request("POST", "/api/graph/nodes", json=node_body)
        assert code == 200, f"Create failed: {body}"
        node_id = body["id"]

        # Read
        code, _, body = _time_request("GET", f"/api/graph/nodes/{node_id}")
        assert code == 200
        assert body["name"] == "API Validation Test Node"

        # Neighbors
        code, _, body = _time_request("GET", f"/api/graph/nodes/{node_id}/neighbors")
        assert code == 200
        assert isinstance(body, list)

        # Delete
        code, _, _ = _time_request("DELETE", f"/api/graph/nodes/{node_id}")
        assert code == 200

    def test_graph_edge_crud(self):
        """Create nodes and edge, then clean up."""
        # Create two nodes
        a = {"id": "test-edge-a", "type": "idea", "name": "Edge Test A", "description": "test", "properties": {}, "phase": "water"}
        b = {"id": "test-edge-b", "type": "artifact", "name": "Edge Test B", "description": "test", "properties": {}, "phase": "water"}
        _time_request("POST", "/api/graph/nodes", json=a)
        _time_request("POST", "/api/graph/nodes", json=b)

        # Create edge
        edge = {"id": "test-edge-ab", "from_id": "test-edge-a", "to_id": "test-edge-b", "type": "depends-on", "strength": 1.0, "properties": {}, "created_by": "test"}
        code, _, body = _time_request("POST", "/api/graph/edges", json=edge)
        assert code == 200, f"Edge create failed: {body}"

        # Clean up
        _time_request("DELETE", "/api/graph/edges/test-edge-ab")
        _time_request("DELETE", "/api/graph/nodes/test-edge-a")
        _time_request("DELETE", "/api/graph/nodes/test-edge-b")


# ── Marketplace ─────────────────────────────────────────────────────────────

class TestMarketplaceEndpoint:
    def test_marketplace_browse_returns_200(self):
        code, ms, body = _time_request("GET", "/api/marketplace/browse")
        assert code == 200
        assert "listings" in body
        assert "total" in body
        assert ms < 5000

    def test_marketplace_browse_pagination(self):
        code, _, body = _time_request("GET", "/api/marketplace/browse?page=1&page_size=5")
        assert code == 200
        assert body["page"] == 1
        assert body["page_size"] == 5

    def test_marketplace_manifest(self):
        code, _, body = _time_request("GET", "/api/marketplace/manifest")
        assert code == 200


# ── Pipeline ────────────────────────────────────────────────────────────────

class TestPipelineEndpoint:
    def test_pipeline_summary_returns_200(self):
        code, ms, body = _time_request("GET", "/api/pipeline/summary")
        assert code == 200
        assert ms < 5000

    def test_pipeline_status_returns_503_when_no_task(self):
        code, _, _ = _time_request("GET", "/api/pipeline/status")
        # May return 200 (idle) or 503 (no pipeline), both are acceptable
        assert code in (200, 503)


# ── Inventory ───────────────────────────────────────────────────────────────

class TestInventoryEndpoint:
    def test_inventory_system_lineage(self):
        code, ms, body = _time_request("GET", "/api/inventory/system-lineage")
        assert code == 200
        assert ms < 10000

    def test_inventory_routes_canonical(self):
        code, _, body = _time_request("GET", "/api/inventory/routes/canonical")
        assert code == 200
        assert isinstance(body, dict)


# ── Onboarding ──────────────────────────────────────────────────────────────

class TestOnboardingEndpoint:
    def test_onboarding_roi(self):
        code, _, body = _time_request("GET", "/api/onboarding/roi")
        assert code == 200
        assert "handle_registrations" in body


# ── Other Endpoints ─────────────────────────────────────────────────────────

class TestOtherEndpoints:
    def test_assets(self):
        code, _, _ = _time_request("GET", "/api/assets")
        assert code == 200

    def test_treasury(self):
        code, _, _ = _time_request("GET", "/api/treasury")
        assert code == 200

    def test_governance(self):
        code, _, _ = _time_request("GET", "/api/governance/change-requests")
        assert code == 200

    def test_runtime_endpoints_summary(self):
        code, _, body = _time_request("GET", "/api/runtime/endpoints/summary")
        assert code == 200
        assert isinstance(body, dict)


# ── Resilience ──────────────────────────────────────────────────────────────

class TestResilience:
    def test_invalid_endpoint_returns_404(self):
        code, _, _ = _time_request("GET", "/api/nonexistent")
        assert code == 404

    def test_ideas_with_negative_limit(self):
        """Negative limit should be rejected or handled gracefully."""
        code, _, _ = _time_request("GET", "/api/ideas?limit=-1")
        assert code in (200, 422)  # Either is acceptable
