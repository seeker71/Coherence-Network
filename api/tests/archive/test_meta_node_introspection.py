"""Tests for Meta-node system — self-describing code and API introspection.

Verifies that:
- Module nodes expose file_path for code navigation
- Module types are correctly classified (router/service/model/middleware)
- Endpoint nodes carry a module reference for code traceability
- Edge cross-references are internally consistent
- meta_service unit functions produce coherent data
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


# ---------------------------------------------------------------------------
# Module file_path introspection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_module_nodes_have_file_path():
    """Each module node includes a file_path for code navigation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    modules = resp.json()["modules"]
    for mod in modules:
        assert "file_path" in mod, f"Module {mod['id']} missing file_path"


@pytest.mark.asyncio
async def test_module_file_paths_are_python_files():
    """Module file_path values end with .py."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    modules = resp.json()["modules"]
    for mod in modules:
        fp = mod.get("file_path")
        if fp is not None:
            assert fp.endswith(".py"), f"Expected .py file path, got {fp!r} for {mod['id']}"


@pytest.mark.asyncio
async def test_module_file_path_derives_from_dotted_id():
    """file_path mirrors the module id with '.' replaced by '/' and '.py' appended."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    modules = resp.json()["modules"]
    for mod in modules:
        expected = mod["id"].replace(".", "/") + ".py"
        assert mod.get("file_path") == expected, (
            f"file_path {mod.get('file_path')!r} does not match expected {expected!r}"
        )


# ---------------------------------------------------------------------------
# Module type classification
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_router_modules_classified_correctly():
    """Modules under app.routers.* have module_type 'router'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    modules = resp.json()["modules"]
    for mod in modules:
        if ".routers." in mod["id"] or mod["id"].endswith(".routers"):
            assert mod["module_type"] == "router", (
                f"Module {mod['id']} should be 'router', got {mod['module_type']!r}"
            )


@pytest.mark.asyncio
async def test_service_modules_classified_correctly():
    """Modules under app.services.* have module_type 'service'."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    modules = resp.json()["modules"]
    for mod in modules:
        if ".services." in mod["id"] or mod["id"].endswith(".services"):
            assert mod["module_type"] == "service", (
                f"Module {mod['id']} should be 'service', got {mod['module_type']!r}"
            )


@pytest.mark.asyncio
async def test_module_types_are_valid_values():
    """All module_type values are from the allowed set."""
    allowed = {"router", "service", "model", "middleware", "module"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    modules = resp.json()["modules"]
    for mod in modules:
        assert mod["module_type"] in allowed, (
            f"Unknown module_type {mod['module_type']!r} for {mod['id']}"
        )


# ---------------------------------------------------------------------------
# Endpoint-to-module traceability
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_endpoint_nodes_have_module_field():
    """Each endpoint node exposes the implementing module name."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    endpoints = resp.json()["endpoints"]
    for ep in endpoints:
        assert "module" in ep, f"Endpoint {ep['id']} missing module field"


@pytest.mark.asyncio
async def test_endpoint_module_matches_defined_in_module_edge():
    """Endpoint module field is consistent with 'defined_in_module' edge target_id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/endpoints")
    endpoints = resp.json()["endpoints"]
    for ep in endpoints:
        module_edges = [e for e in ep.get("edges", []) if e["type"] == "defined_in_module"]
        if module_edges:
            edge_target = module_edges[0]["target_id"]
            assert ep.get("module") == edge_target, (
                f"Endpoint {ep['id']}: module={ep.get('module')!r} "
                f"but edge target_id={edge_target!r}"
            )


@pytest.mark.asyncio
async def test_endpoint_defined_in_module_targets_known_module():
    """'defined_in_module' edge targets appear in the modules list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ep_resp = await client.get("/api/meta/endpoints")
        mod_resp = await client.get("/api/meta/modules")

    module_ids = {m["id"] for m in mod_resp.json()["modules"]}
    endpoints = ep_resp.json()["endpoints"]
    for ep in endpoints:
        for edge in ep.get("edges", []):
            if edge["type"] == "defined_in_module":
                assert edge["target_id"] in module_ids, (
                    f"Endpoint {ep['id']} references unknown module {edge['target_id']!r}"
                )


# ---------------------------------------------------------------------------
# meta_service unit tests — direct function calls
# ---------------------------------------------------------------------------

def test_meta_service_list_endpoints_returns_response():
    """meta_service.list_endpoints(app) returns a MetaEndpointsResponse."""
    from app.services import meta_service
    from app.models.meta import MetaEndpointsResponse

    result = meta_service.list_endpoints(app)
    assert isinstance(result, MetaEndpointsResponse)
    assert result.total == len(result.endpoints)


def test_meta_service_list_modules_returns_response():
    """meta_service.list_modules(app) returns a MetaModulesResponse."""
    from app.services import meta_service
    from app.models.meta import MetaModulesResponse

    result = meta_service.list_modules(app)
    assert isinstance(result, MetaModulesResponse)
    assert result.total == len(result.modules)


def test_meta_service_get_summary_returns_response():
    """meta_service.get_summary(app) returns a MetaSummaryResponse."""
    from app.services import meta_service
    from app.models.meta import MetaSummaryResponse

    result = meta_service.get_summary(app)
    assert isinstance(result, MetaSummaryResponse)
    assert 0.0 <= result.spec_coverage <= 1.0
    assert result.traced_count <= result.endpoint_count


def test_meta_service_list_endpoints_ids_are_strings():
    """All endpoint node ids are non-empty strings."""
    from app.services import meta_service

    result = meta_service.list_endpoints(app)
    for ep in result.endpoints:
        assert isinstance(ep.id, str) and ep.id, f"Invalid id on endpoint node: {ep.id!r}"


def test_meta_service_list_modules_no_duplicate_ids():
    """No two module nodes share the same id."""
    from app.services import meta_service

    result = meta_service.list_modules(app)
    ids = [m.id for m in result.modules]
    assert len(ids) == len(set(ids)), "Duplicate module node ids found"


# ---------------------------------------------------------------------------
# Cross-resource consistency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_meta_module_endpoint_count_is_nonnegative():
    """endpoint_count on every module node is >= 0."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    for mod in resp.json()["modules"]:
        assert mod["endpoint_count"] >= 0


@pytest.mark.asyncio
async def test_module_name_is_last_segment_of_id():
    """Module name is the last dotted segment of the id."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/meta/modules")
    for mod in resp.json()["modules"]:
        expected_name = mod["id"].split(".")[-1]
        assert mod["name"] == expected_name, (
            f"Module {mod['id']}: name={mod['name']!r}, expected {expected_name!r}"
        )
