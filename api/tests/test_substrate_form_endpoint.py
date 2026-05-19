"""Smoke tests for POST /api/substrate/form — the substrate-native query DSL
exposed as REST so outside agents can ask the lattice in its own language."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_form_endpoint_evaluates_empty_query_against_substrate() -> None:
    """A well-formed Form expression returns a discriminated result.

    Asking for cells in a domain that has no entries should still parse,
    evaluate, and return kind="cells" with an empty list — proving the
    endpoint is live, not just registered.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/form",
            json={"expression": '?cells where domain == "no_such_domain_for_test"'},
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "cells"
    assert body["cells"] == []


@pytest.mark.asyncio
async def test_form_endpoint_streaming_mode_emits_same_recipe_node() -> None:
    """Streaming mode exposes the direct Recipe emitter through the same API."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        ast_response = await client.post(
            "/api/substrate/form",
            json={"expression": "1 + 2 * 3"},
        )
        streaming_response = await client.post(
            "/api/substrate/form",
            json={"expression": "1 + 2 * 3", "mode": "streaming"},
        )

    assert ast_response.status_code == 200, ast_response.text
    assert streaming_response.status_code == 200, streaming_response.text
    ast_body = ast_response.json()
    streaming_body = streaming_response.json()
    assert ast_body["kind"] == "recipe"
    assert streaming_body["kind"] == "recipe"
    assert streaming_body["node_id"] == ast_body["node_id"]


@pytest.mark.asyncio
async def test_form_endpoint_rejects_unknown_mode() -> None:
    """Mode stays explicit so callers know which parser path they exercised."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/form",
            json={"expression": "1 + 2", "mode": "direct"},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_form_endpoint_rejects_syntactically_broken_expression() -> None:
    """Parse / eval failures return HTTP 400 with the failure reason.

    The substrate stays read-only; bad expressions never silently succeed.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/substrate/form",
            json={"expression": "?? this is not Form notation @@@"},
        )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "form parse/eval failed" in detail


@pytest.mark.asyncio
async def test_form_endpoint_requires_expression() -> None:
    """Empty payload returns 422 from Pydantic validation; not 500."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/substrate/form", json={})

    assert response.status_code == 422
