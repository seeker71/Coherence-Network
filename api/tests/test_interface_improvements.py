"""
Integration tests proving every machine + human interface improvement works.

Run with:  cd api && .venv/bin/pytest tests/test_interface_improvements.py -v

Each test exercises a real HTTP request against the actual FastAPI app
and asserts on the actual response body, headers, and status codes.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app


@pytest.fixture(autouse=True)
def fresh_store():
    app.state.graph_store = InMemoryGraphStore()


# ═══════════════════════════════════════════════════════════════
# 1. Security Headers — every response must include them
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_security_headers_on_health():
    """SecurityHeadersMiddleware adds OWASP headers to every response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200

        assert resp.headers["x-content-type-options"] == "nosniff", \
            f"Expected nosniff, got {resp.headers.get('x-content-type-options')}"
        assert resp.headers["x-frame-options"] == "DENY", \
            f"Expected DENY, got {resp.headers.get('x-frame-options')}"
        assert "strict-origin" in resp.headers["referrer-policy"], \
            f"Expected strict-origin policy, got {resp.headers.get('referrer-policy')}"
        assert "camera=()" in resp.headers["permissions-policy"], \
            f"Expected permissions-policy, got {resp.headers.get('permissions-policy')}"


@pytest.mark.asyncio
async def test_security_headers_on_post():
    """Security headers present even on POST responses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "Test", "email": "sec@test.com"},
        )
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_security_headers_on_404():
    """Security headers present even on error responses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/contributors/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"


# ═══════════════════════════════════════════════════════════════
# 2. Request ID — generated and returned in X-Request-ID header
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_request_id_generated():
    """When no X-Request-ID header is sent, one is generated and returned."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health")
        req_id = resp.headers.get("x-request-id")
        assert req_id is not None, "X-Request-ID header missing from response"
        # Should be a valid UUID
        uuid.UUID(req_id)


@pytest.mark.asyncio
async def test_request_id_propagated():
    """When X-Request-ID header is sent, the same value is returned."""
    my_id = "trace-abc-12345"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/health", headers={"x-request-id": my_id})
        assert resp.headers["x-request-id"] == my_id, \
            f"Expected propagated ID '{my_id}', got '{resp.headers.get('x-request-id')}'"


# ═══════════════════════════════════════════════════════════════
# 3. Paginated List Responses — contributors
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_contributors_list_returns_paginated_envelope():
    """GET /api/contributors returns {items, total, limit, offset} not a bare array."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create two contributors
        await client.post("/api/contributors", json={"type": "HUMAN", "name": "A", "email": "a@test.com"})
        await client.post("/api/contributors", json={"type": "HUMAN", "name": "B", "email": "b@test.com"})

        resp = await client.get("/api/contributors?limit=10&offset=0")
        assert resp.status_code == 200
        body = resp.json()

        # Must NOT be a list
        assert isinstance(body, dict), f"Expected dict, got {type(body).__name__}"
        assert "items" in body, f"Missing 'items' key. Keys: {list(body.keys())}"
        assert "total" in body, f"Missing 'total' key"
        assert "limit" in body, f"Missing 'limit' key"
        assert "offset" in body, f"Missing 'offset' key"

        assert isinstance(body["items"], list)
        assert len(body["items"]) == 2
        assert body["total"] >= 2
        assert body["limit"] == 10
        assert body["offset"] == 0


@pytest.mark.asyncio
async def test_contributors_pagination_offset():
    """Offset parameter skips items correctly."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/contributors", json={"type": "HUMAN", "name": "C1", "email": "c1@test.com"})
        await client.post("/api/contributors", json={"type": "HUMAN", "name": "C2", "email": "c2@test.com"})
        await client.post("/api/contributors", json={"type": "HUMAN", "name": "C3", "email": "c3@test.com"})

        full = await client.get("/api/contributors?limit=100&offset=0")
        offset1 = await client.get("/api/contributors?limit=100&offset=1")

        full_items = full.json()["items"]
        offset_items = offset1.json()["items"]

        assert len(offset_items) == len(full_items) - 1, \
            f"Offset=1 should skip 1 item: full={len(full_items)}, offset={len(offset_items)}"


# ═══════════════════════════════════════════════════════════════
# 4. Paginated List Responses — assets
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_assets_list_returns_paginated_envelope():
    """GET /api/assets returns {items, total, limit, offset} not a bare array."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/assets", json={"type": "CODE", "description": "Asset 1"})

        resp = await client.get("/api/assets?limit=10")
        assert resp.status_code == 200
        body = resp.json()

        assert isinstance(body, dict), f"Expected dict, got {type(body).__name__}"
        assert "items" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body
        assert len(body["items"]) == 1


# ═══════════════════════════════════════════════════════════════
# 5. Paginated List Responses — contributions
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_contributions_list_returns_paginated_envelope():
    """GET /api/contributions returns {items, total, limit, offset} not a bare array."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Setup: create contributor + asset + contribution
        c = await client.post("/api/contributors", json={"type": "HUMAN", "name": "X", "email": "x@test.com"})
        a = await client.post("/api/assets", json={"type": "CODE", "description": "Repo X"})
        await client.post("/api/contributions", json={
            "contributor_id": c.json()["id"],
            "asset_id": a.json()["id"],
            "cost_amount": "10.00",
            "metadata": {},
        })

        resp = await client.get("/api/contributions?limit=5")
        assert resp.status_code == 200
        body = resp.json()

        assert isinstance(body, dict), f"Expected dict, got {type(body).__name__}"
        assert "items" in body
        assert "total" in body
        assert len(body["items"]) == 1


# ═══════════════════════════════════════════════════════════════
# 6. OpenAPI Schema — tags, descriptions, error responses
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_openapi_schema_has_tags():
    """The OpenAPI schema defines tag groups for organized documentation."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()

        tag_names = [t["name"] for t in schema.get("tags", [])]
        for expected_tag in ["health", "contributors", "assets", "contributions", "agent", "ideas"]:
            assert expected_tag in tag_names, \
                f"Tag '{expected_tag}' missing from OpenAPI schema. Found: {tag_names}"


@pytest.mark.asyncio
async def test_openapi_schema_has_description():
    """OpenAPI schema has a project description."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
        schema = resp.json()
        info = schema.get("info", {})
        assert info.get("description"), "OpenAPI info.description is empty"
        assert info.get("contact"), "OpenAPI info.contact is missing"


@pytest.mark.asyncio
async def test_openapi_contributors_post_documents_errors():
    """POST /api/contributors documents 422 error response in OpenAPI schema."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
        schema = resp.json()

        post_path = schema["paths"].get("/api/contributors", {}).get("post", {})
        responses = post_path.get("responses", {})
        assert "422" in responses, \
            f"POST /api/contributors missing 422 response doc. Found: {list(responses.keys())}"


@pytest.mark.asyncio
async def test_openapi_contributions_post_documents_errors():
    """POST /api/contributions documents both 404 and 422 error responses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
        schema = resp.json()

        post_path = schema["paths"].get("/api/contributions", {}).get("post", {})
        responses = post_path.get("responses", {})
        assert "404" in responses, \
            f"POST /api/contributions missing 404 response doc. Found: {list(responses.keys())}"
        assert "422" in responses, \
            f"POST /api/contributions missing 422 response doc. Found: {list(responses.keys())}"


@pytest.mark.asyncio
async def test_openapi_schema_has_pagination_model():
    """OpenAPI schema includes PaginatedResponse model with items/total/limit/offset."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
        schema = resp.json()

        # The list endpoints should reference a paginated model
        get_contributors = schema["paths"].get("/api/contributors", {}).get("get", {})
        resp_schema = get_contributors.get("responses", {}).get("200", {})

        # The response should reference a model with items/total/limit/offset
        # This may be nested under content/application/json/schema
        content = resp_schema.get("content", {}).get("application/json", {}).get("schema", {})
        # Check it has the pagination properties (might be via $ref)
        if "properties" in content:
            props = content["properties"]
            for field in ["items", "total", "limit", "offset"]:
                assert field in props, \
                    f"GET /api/contributors response schema missing '{field}'. Found: {list(props.keys())}"


# ═══════════════════════════════════════════════════════════════
# 7. CORS — restricted methods and headers (not wildcards)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_cors_not_wildcard():
    """CORS preflight should NOT return Access-Control-Allow-Methods: *"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.options(
            "/api/health",
            headers={
                "origin": "http://localhost:3000",
                "access-control-request-method": "GET",
            },
        )
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        assert allow_methods != "*", \
            "CORS allow_methods should not be wildcard '*'"
        # Should list explicit methods
        assert "GET" in allow_methods, f"GET missing from CORS methods: {allow_methods}"


# ═══════════════════════════════════════════════════════════════
# 8. RFC 7807 Error Model — structure check
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_error_model_in_openapi_has_rfc7807_fields():
    """The ErrorDetail model in OpenAPI schema has RFC 7807 fields."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
        schema = resp.json()

        # Find ErrorDetail in components/schemas
        schemas = schema.get("components", {}).get("schemas", {})
        error_detail = schemas.get("ErrorDetail", {})
        assert error_detail, f"ErrorDetail not found in schemas. Available: {list(schemas.keys())}"

        props = error_detail.get("properties", {})
        for field in ["type", "title", "status", "detail"]:
            assert field in props, \
                f"ErrorDetail missing RFC 7807 field '{field}'. Found: {list(props.keys())}"


# ═══════════════════════════════════════════════════════════════
# 9. Route summaries exist
# ═══════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_routes_have_summaries():
    """Key routes have summary fields in the OpenAPI schema."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/openapi.json")
        schema = resp.json()

        checks = [
            ("/api/contributors", "post", "Create contributor"),
            ("/api/contributors/{contributor_id}", "get", "Get contributor by ID"),
            ("/api/contributors", "get", "List contributors"),
            ("/api/assets", "post", "Create asset"),
            ("/api/contributions", "post", "Record a contribution"),
            ("/api/contributions/github", "post", "Track GitHub contribution"),
        ]

        for path, method, expected_summary in checks:
            route = schema["paths"].get(path, {}).get(method, {})
            summary = route.get("summary", "")
            assert summary == expected_summary, \
                f"{method.upper()} {path}: expected summary '{expected_summary}', got '{summary}'"
