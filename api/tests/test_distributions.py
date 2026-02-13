from __future__ import annotations

import pytest
from decimal import Decimal
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app


@pytest.mark.asyncio
async def test_distribution_weighted_by_coherence() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp1 = await client.post("/v1/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        alice_id = resp1.json()["id"]

        resp2 = await client.post("/v1/contributors", json={"type": "HUMAN", "name": "Bob", "email": "bob@example.com"})
        bob_id = resp2.json()["id"]

        resp3 = await client.post("/v1/assets", json={"type": "CODE", "description": "Test asset"})
        asset_id = resp3.json()["id"]

        await client.post(
            "/v1/contributions",
            json={"contributor_id": alice_id, "asset_id": asset_id, "cost_amount": "100.00", "metadata": {"has_tests": True, "has_docs": True}},
        )
        await client.post(
            "/v1/contributions",
            json={"contributor_id": bob_id, "asset_id": asset_id, "cost_amount": "100.00", "metadata": {}},
        )

        resp = await client.post("/v1/distributions", json={"asset_id": asset_id, "value_amount": "1000.00"})
        assert resp.status_code == 201
        data = resp.json()

        payouts = {p["contributor_id"]: Decimal(p["amount"]) for p in data["payouts"]}
        assert abs(payouts[alice_id] - Decimal("583.33")) < Decimal("0.01")
        assert abs(payouts[bob_id] - Decimal("416.67")) < Decimal("0.01")


@pytest.mark.asyncio
async def test_distribution_asset_not_found_404() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/distributions", json={"asset_id": "00000000-0000-0000-0000-000000000000", "value_amount": "1.00"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Asset not found"


@pytest.mark.asyncio
async def test_distribution_no_contributions_returns_empty_payouts() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        a = await client.post("/v1/assets", json={"type": "CODE", "description": "Empty asset"})
        asset_id = a.json()["id"]

        resp = await client.post("/v1/distributions", json={"asset_id": asset_id, "value_amount": "10.00"})
        assert resp.status_code == 201
        assert resp.json()["payouts"] == []


@pytest.mark.asyncio
async def test_distribution_422() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/v1/distributions", json={"asset_id": "00000000-0000-0000-0000-000000000000", "value_amount": "x"})
        assert resp.status_code == 422
