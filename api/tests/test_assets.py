from __future__ import annotations

import pytest
from decimal import Decimal
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app


@pytest.mark.asyncio
async def test_create_get_list_assets() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/assets", json={"type": "CODE", "description": "Test asset"})
        assert resp.status_code == 201
        created = resp.json()
        aid = created["id"]

        resp2 = await client.get(f"/api/assets/{aid}")
        assert resp2.status_code == 200
        assert resp2.json()["id"] == aid

        resp3 = await client.get("/api/assets?limit=10")
        assert resp3.status_code == 200
        assert any(x["id"] == aid for x in resp3.json())

        # total_cost default
        got = await client.get(f"/api/assets/{aid}")
        assert Decimal(got.json()["total_cost"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_get_asset_404() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/assets/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Asset not found"


@pytest.mark.asyncio
async def test_create_asset_422() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/assets", json={"type": "CODE"})
        assert resp.status_code == 422
