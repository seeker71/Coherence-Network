"""Tests for Metadata Self-Discovery API (spec 162-meta-self-discovery).

Verifies acceptance criteria:
- GET /api/meta/endpoints returns endpoint concept nodes
- GET /api/meta/modules returns module concept nodes with trace coverage
- GET /api/meta/summary returns system coverage overview
- Self-consistency, edge cases, and router registration
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


# ---------------------------------------------------------------------------
# GET /api/meta/endpoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meta_endpoints_returns_200():
    """GET /api/meta/endpoints returns HTTP 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_meta_endpoints_has_required_fields():
    """Response includes total (int) and endpoints (list)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    data = resp.json()
    assert "total" in data
    assert "endpoints" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["endpoints"], list)


@pytest.mark.asyncio
async def test_meta_endpoints_total_matches_endpoints_length():
    """total field matches length of endpoints list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    data = resp.json()
    assert data["total"] == len(data["endpoints"])


@pytest.mark.asyncio
async def test_meta_endpoints_has_at_least_one_route():
    """System has at least one registered route (total > 0)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    data = resp.json()
    assert data["total"] > 0


@pytest.mark.asyncio
async def test_meta_endpoint_nodes_have_required_fields():
    """Each endpoint node has path, method, id, tags, edges."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    endpoints = resp.json()["endpoints"]
    assert endpoints, "Expected at least one endpoint node"
    for ep in endpoints[:5]:  # spot-check first 5
        assert "path" in ep, f"Missing 'path' in {ep}"
        assert "method" in ep, f"Missing 'method' in {ep}"
        assert "id" in ep, f"Missing 'id' in {ep}"
        assert "tags" in ep, f"Missing 'tags' in {ep}"
        assert "edges" in ep, f"Missing 'edges' in {ep}"
        assert isinstance(ep["method"], str)
        assert ep["method"] in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
        assert isinstance(ep["path"], str)
        assert ep["path"].startswith("/")


@pytest.mark.asyncio
async def test_meta_endpoint_node_id_encodes_method_and_path():
    """Endpoint node id has format '<METHOD> <path>'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    endpoints = resp.json()["endpoints"]
    for ep in endpoints[:10]:
        expected_id = f"{ep['method']} {ep['path']}"
        assert ep["id"] == expected_id, f"Unexpected id format: {ep['id']!r}"


@pytest.mark.asyncio
async def test_meta_endpoint_edges_have_type_and_target_id():
    """Each edge has type and target_id fields."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    endpoints = resp.json()["endpoints"]
    for ep in endpoints:
        for edge in ep.get("edges", []):
            assert "type" in edge
            assert "target_id" in edge
            assert edge["type"] in {"implements_spec", "traces_idea", "defined_in_module"}


@pytest.mark.asyncio
async def test_meta_endpoints_sorted_by_path_then_method():
    """Endpoints are sorted by path, then method."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    endpoints = resp.json()["endpoints"]
    keys = [(ep["path"], ep["method"]) for ep in endpoints]
    assert keys == sorted(keys), "Endpoints are not sorted by (path, method)"


@pytest.mark.asyncio
async def test_meta_endpoints_includes_meta_router_itself():
    """The meta endpoints router appears in the list (self-discovery)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    endpoints = resp.json()["endpoints"]
    paths = {ep["path"] for ep in endpoints}
    assert "/api/meta/endpoints" in paths
    assert "/api/meta/modules" in paths


@pytest.mark.asyncio
async def test_meta_endpoints_spec_id_and_idea_id_are_nullable():
    """spec_id and idea_id fields are present and can be None."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    endpoints = resp.json()["endpoints"]
    for ep in endpoints[:10]:
        assert "spec_id" in ep
        assert "idea_id" in ep


@pytest.mark.asyncio
async def test_meta_endpoints_untraced_have_null_spec_and_idea():
    """Endpoints without trace edges have null spec_id and idea_id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    endpoints = resp.json()["endpoints"]
    for ep in endpoints:
        has_spec_edge = any(e["type"] == "implements_spec" for e in ep.get("edges", []))
        has_idea_edge = any(e["type"] == "traces_idea" for e in ep.get("edges", []))
        if not has_spec_edge:
            assert ep["spec_id"] is None, f"Expected null spec_id for untraced {ep['id']}"
        if not has_idea_edge:
            assert ep["idea_id"] is None, f"Expected null idea_id for untraced {ep['id']}"


@pytest.mark.asyncio
async def test_meta_endpoints_no_500_error():
    """GET /api/meta/endpoints never returns 500."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    assert resp.status_code != 500


@pytest.mark.asyncio
async def test_meta_endpoints_do_not_include_admin_reset():
    """Admin reset-database path is excluded from meta endpoint listing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    endpoints = resp.json()["endpoints"]
    paths = {ep["path"] for ep in endpoints}
    assert "/api/admin/reset-database" not in paths


@pytest.mark.asyncio
async def test_meta_endpoints_do_not_include_openapi_docs():
    """Internal docs paths are excluded from meta endpoint listing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    endpoints = resp.json()["endpoints"]
    paths = {ep["path"] for ep in endpoints}
    assert "/openapi.json" not in paths
    assert "/docs" not in paths


@pytest.mark.asyncio
async def test_meta_endpoints_is_idempotent():
    """Two calls to /api/meta/endpoints return the same total."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.get("/api/meta/endpoints")
        r2 = await client.get("/api/meta/endpoints")
    assert r1.json()["total"] == r2.json()["total"]


# ---------------------------------------------------------------------------
# GET /api/meta/modules
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meta_modules_returns_200():
    """GET /api/meta/modules returns HTTP 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_meta_modules_has_required_fields():
    """Response includes total (int) and modules (list)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    data = resp.json()
    assert "total" in data
    assert "modules" in data
    assert isinstance(data["total"], int)
    assert isinstance(data["modules"], list)


@pytest.mark.asyncio
async def test_meta_modules_total_matches_list_length():
    """total field matches length of modules list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    data = resp.json()
    assert data["total"] == len(data["modules"])


@pytest.mark.asyncio
async def test_meta_modules_has_at_least_one_entry():
    """System has at least one module registered (total > 0)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    data = resp.json()
    assert data["total"] > 0


@pytest.mark.asyncio
async def test_meta_module_nodes_have_required_fields():
    """Each module node has id, name, module_type, endpoint_count, edges."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    modules = resp.json()["modules"]
    assert modules, "Expected at least one module node"
    for mod in modules[:5]:
        assert "id" in mod
        assert "name" in mod
        assert "module_type" in mod
        assert "endpoint_count" in mod
        assert "edges" in mod
        assert isinstance(mod["id"], str)
        assert isinstance(mod["endpoint_count"], int)
        assert mod["endpoint_count"] >= 0
        assert mod["module_type"] in {"router", "service", "model", "middleware", "module"}


@pytest.mark.asyncio
async def test_meta_modules_spec_and_idea_ids_are_lists():
    """spec_ids and idea_ids fields are lists (possibly empty)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    modules = resp.json()["modules"]
    for mod in modules:
        assert "spec_ids" in mod
        assert "idea_ids" in mod
        assert isinstance(mod["spec_ids"], list)
        assert isinstance(mod["idea_ids"], list)


@pytest.mark.asyncio
async def test_meta_modules_includes_meta_router():
    """The meta router module itself is listed as a module node."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    modules = resp.json()["modules"]
    module_ids = {m["id"] for m in modules}
    assert "app.routers.meta" in module_ids


@pytest.mark.asyncio
async def test_meta_modules_no_500_error():
    """GET /api/meta/modules never returns 500."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    assert resp.status_code != 500


@pytest.mark.asyncio
async def test_meta_modules_is_idempotent():
    """Two calls to /api/meta/modules return the same total."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.get("/api/meta/modules")
        r2 = await client.get("/api/meta/modules")
    assert r1.json()["total"] == r2.json()["total"]


# ---------------------------------------------------------------------------
# GET /api/meta/summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meta_summary_returns_200():
    """GET /api/meta/summary returns HTTP 200."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/summary")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_meta_summary_has_required_fields():
    """Summary response contains endpoint_count, module_count, traced_count, spec_coverage."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/summary")
    data = resp.json()
    assert "endpoint_count" in data
    assert "module_count" in data
    assert "traced_count" in data
    assert "spec_coverage" in data
    assert isinstance(data["endpoint_count"], int)
    assert isinstance(data["module_count"], int)
    assert isinstance(data["traced_count"], int)
    assert isinstance(data["spec_coverage"], float)


@pytest.mark.asyncio
async def test_meta_summary_coverage_between_0_and_1():
    """spec_coverage is a fraction between 0.0 and 1.0."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/summary")
    data = resp.json()
    assert 0.0 <= data["spec_coverage"] <= 1.0


@pytest.mark.asyncio
async def test_meta_summary_traced_count_le_endpoint_count():
    """traced_count cannot exceed endpoint_count."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/summary")
    data = resp.json()
    assert data["traced_count"] <= data["endpoint_count"]


@pytest.mark.asyncio
async def test_meta_summary_endpoint_count_matches_endpoints_total():
    """endpoint_count in summary matches total from /api/meta/endpoints."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        summary = (await client.get("/api/meta/summary")).json()
        endpoints = (await client.get("/api/meta/endpoints")).json()
    assert summary["endpoint_count"] == endpoints["total"]


@pytest.mark.asyncio
async def test_meta_summary_module_count_matches_modules_total():
    """module_count in summary matches total from /api/meta/modules."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        summary = (await client.get("/api/meta/summary")).json()
        modules = (await client.get("/api/meta/modules")).json()
    assert summary["module_count"] == modules["total"]


@pytest.mark.asyncio
async def test_meta_summary_spec_coverage_is_consistent():
    """spec_coverage = traced_count / endpoint_count (within float tolerance)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/summary")
    data = resp.json()
    total = data["endpoint_count"]
    traced = data["traced_count"]
    reported = data["spec_coverage"]
    if total > 0:
        expected = round(traced / total, 4)
        assert abs(reported - expected) < 0.001, (
            f"spec_coverage {reported} does not match {traced}/{total}={expected}"
        )
    else:
        assert reported == 0.0


@pytest.mark.asyncio
async def test_meta_summary_no_500_error():
    """GET /api/meta/summary never returns 500."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/summary")
    assert resp.status_code != 500


# ---------------------------------------------------------------------------
# Meta router registration in OpenAPI
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meta_router_is_registered_with_meta_tag():
    """Meta endpoints appear with the 'meta' tag in the OpenAPI spec."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    paths = spec.get("paths", {})
    meta_tagged = [
        p for p, methods in paths.items()
        if p.startswith("/api/meta")
        and any(
            "meta" in method_info.get("tags", [])
            for method_info in methods.values()
        )
    ]
    assert meta_tagged, "No /api/meta paths with 'meta' tag found in OpenAPI spec"
