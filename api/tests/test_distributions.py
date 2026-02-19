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
        resp1 = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        alice_id = resp1.json()["id"]

        resp2 = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Bob", "email": "bob@example.com"})
        bob_id = resp2.json()["id"]

        resp3 = await client.post("/api/assets", json={"type": "CODE", "description": "Test asset"})
        asset_id = resp3.json()["id"]

        await client.post(
            "/api/contributions",
            json={"contributor_id": alice_id, "asset_id": asset_id, "cost_amount": "100.00", "metadata": {"has_tests": True, "has_docs": True}},
        )
        await client.post(
            "/api/contributions",
            json={"contributor_id": bob_id, "asset_id": asset_id, "cost_amount": "100.00", "metadata": {}},
        )

        resp = await client.post("/api/distributions", json={"asset_id": asset_id, "value_amount": "1000.00"})
        assert resp.status_code == 201
        data = resp.json()

        payouts = {p["contributor_id"]: Decimal(p["amount"]) for p in data["payouts"]}
        assert abs(payouts[alice_id] - Decimal("583.33")) < Decimal("0.01")
        assert abs(payouts[bob_id] - Decimal("416.67")) < Decimal("0.01")


@pytest.mark.asyncio
async def test_distribution_asset_not_found_404() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/distributions", json={"asset_id": "00000000-0000-0000-0000-000000000000", "value_amount": "1.00"})
        assert resp.status_code == 404
        assert resp.json()["detail"] == "Asset not found"


@pytest.mark.asyncio
async def test_distribution_no_contributions_returns_empty_payouts() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        a = await client.post("/api/assets", json={"type": "CODE", "description": "Empty asset"})
        asset_id = a.json()["id"]

        resp = await client.post("/api/distributions", json={"asset_id": asset_id, "value_amount": "10.00"})
        assert resp.status_code == 201
        assert resp.json()["payouts"] == []


@pytest.mark.asyncio
async def test_distribution_422() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/distributions", json={"asset_id": "00000000-0000-0000-0000-000000000000", "value_amount": "x"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_distribution_is_persisted_and_retrievable() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        contributor = await client.post(
            "/api/contributors",
            json={
                "type": "HUMAN",
                "name": "Alice",
                "email": "alice@coherence.network",
                "wallet_address": "0x1111111111111111111111111111111111111111",
            },
        )
        contributor_id = contributor.json()["id"]
        asset = await client.post("/api/assets", json={"type": "CODE", "description": "Persisted distribution asset"})
        asset_id = asset.json()["id"]
        await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_id,
                "asset_id": asset_id,
                "cost_amount": "10.00",
                "metadata": {"has_tests": True},
            },
        )

        created = await client.post("/api/distributions", json={"asset_id": asset_id, "value_amount": "99.00"})
        assert created.status_code == 201
        distribution_id = created.json()["id"]

        fetched = await client.get(f"/api/distributions/{distribution_id}")
        assert fetched.status_code == 200
        assert fetched.json()["id"] == distribution_id

        listed = await client.get("/api/distributions?limit=10")
        assert listed.status_code == 200
        assert any(item.get("id") == distribution_id for item in listed.json())


@pytest.mark.asyncio
async def test_distribution_auto_settlement_adds_tx_hashes_for_wallet_payouts() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        alice = await client.post(
            "/api/contributors",
            json={
                "type": "HUMAN",
                "name": "Alice",
                "email": "alice@example.com",
                "wallet_address": "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            },
        )
        bob = await client.post(
            "/api/contributors",
            json={
                "type": "HUMAN",
                "name": "Bob",
                "email": "bob@example.com",
                "wallet_address": "0xbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            },
        )
        alice_id = alice.json()["id"]
        bob_id = bob.json()["id"]

        asset = await client.post("/api/assets", json={"type": "CODE", "description": "Settlement asset"})
        asset_id = asset.json()["id"]

        await client.post(
            "/api/contributions",
            json={"contributor_id": alice_id, "asset_id": asset_id, "cost_amount": "30.00", "metadata": {"has_tests": True}},
        )
        await client.post(
            "/api/contributions",
            json={"contributor_id": bob_id, "asset_id": asset_id, "cost_amount": "20.00", "metadata": {"has_docs": True}},
        )

        created = await client.post("/api/distributions", json={"asset_id": asset_id, "value_amount": "250.00"})
        assert created.status_code == 201
        payload = created.json()
        assert payload["settlement_status"] == "settled"
        assert payload["settled_at"] is not None

        for payout in payload["payouts"]:
            assert payout["settlement_status"] == "confirmed"
            assert payout["tx_hash"].startswith("0x")
            assert len(payout["tx_hash"]) == 66
            assert payout["settled_at"] is not None
