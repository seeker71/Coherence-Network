"""Tests for the canonical-route-registry-and-runtime-mapping spec
(specs/canonical-route-registry-and-runtime-mapping.md).

The body's API exposes a canonical route registry (one source of truth
for tooling that needs to enumerate API + web routes) and a runtime
mapping endpoint that prefers `/api`, `/v1`, and `/` over the
`unmapped` default for standard surfaces.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_canonical_routes_endpoint_returns_200(client):
    response = client.get("/api/inventory/routes/canonical")
    assert response.status_code == 200


def test_canonical_routes_response_carries_required_keys(client):
    body = client.get("/api/inventory/routes/canonical").json()
    for key in ("generated_at", "version", "api_routes", "web_routes"):
        assert key in body, f"missing canonical-route key {key!r}"


def test_canonical_routes_returns_lists_for_route_collections(client):
    body = client.get("/api/inventory/routes/canonical").json()
    assert isinstance(body["api_routes"], list)
    assert isinstance(body["web_routes"], list)


def test_canonical_routes_generated_at_is_iso_string(client):
    body = client.get("/api/inventory/routes/canonical").json()
    # Just verify it parses as an ISO-8601-ish string
    assert isinstance(body["generated_at"], str)
    assert "T" in body["generated_at"]


def test_canonical_routes_service_returns_dict_directly():
    """Unit-test the service layer the router wraps."""
    from app.services import route_registry_service
    routes = route_registry_service.get_canonical_routes()
    assert isinstance(routes, dict)
    assert "api_routes" in routes
    assert "web_routes" in routes
    assert isinstance(routes["api_routes"], list)


def test_canonical_routes_milestone_field_present(client):
    """The registry exposes milestone metadata for tooling that wants
    to gate on shipped milestones."""
    body = client.get("/api/inventory/routes/canonical").json()
    assert "milestone" in body
