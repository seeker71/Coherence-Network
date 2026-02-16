from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app


@pytest.mark.asyncio
async def test_create_get_list_contributors() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"},
        )
        assert resp.status_code == 201
        created = resp.json()
        cid = created["id"]

        resp2 = await client.get(f"/api/contributors/{cid}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == cid

        resp3 = await client.get("/api/contributors?limit=10")
        assert resp3.status_code == 200
        assert any(x["id"] == cid for x in resp3.json())


@pytest.mark.asyncio
async def test_get_contributor_404() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/contributors/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Contributor not found"


@pytest.mark.asyncio
async def test_create_contributor_422() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/contributors", json={"type": "HUMAN", "name": "NoEmail"})
        assert resp.status_code == 422
