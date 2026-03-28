"""Meta-node system — self-describing code and API introspection (minimal core).

Covers:
- meta_service introspection of the FastAPI app (concept nodes without HTTP)
- OpenAPI document as the standard machine-readable API surface
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import meta_service


def test_meta_service_list_endpoints_self_describes_app():
    """list_endpoints walks registered routes into EndpointNode concept nodes."""
    result = meta_service.list_endpoints(app)
    assert result.total == len(result.endpoints)
    assert result.total > 0
    assert any(ep.path.startswith("/api/meta") for ep in result.endpoints)


def test_meta_service_list_modules_self_describes_code_modules():
    """list_modules aggregates implementation modules linked from routes/registry."""
    result = meta_service.list_modules(app)
    assert result.total == len(result.modules)
    assert result.total > 0
    assert any(m.id == "app.routers.meta" for m in result.modules)


def test_meta_service_get_summary_coherent_with_lists():
    """get_summary derives coverage from endpoint/module concept graphs."""
    summary = meta_service.get_summary(app)
    ep_total = meta_service.list_endpoints(app).total
    mod_total = meta_service.list_modules(app).total
    assert summary.endpoint_count == ep_total
    assert summary.module_count == mod_total
    assert summary.traced_count <= summary.endpoint_count
    assert 0.0 <= summary.spec_coverage <= 1.0


@pytest.mark.asyncio
async def test_openapi_json_api_introspection_surface():
    """GET /openapi.json exposes a non-empty path map for clients and tools."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    spec = resp.json()
    assert "openapi" in spec
    assert "paths" in spec and isinstance(spec["paths"], dict)
    assert len(spec["paths"]) > 0
    assert any(str(p).startswith("/api/meta") for p in spec["paths"])
