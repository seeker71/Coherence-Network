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
