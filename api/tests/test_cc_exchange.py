"""Tests for the CC ↔ External Exchange bridge.

Covers: adapters, quotes, swaps, confirmation, history.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ── Adapters ─────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_list_adapters(client):
    resp = await client.get("/api/cc/exchange/adapters")
    assert resp.status_code == 200
    adapters = resp.json()
    assert isinstance(adapters, list)
    assert len(adapters) >= 2
    names = {a["name"] for a in adapters}
    assert "new_earth" in names
    assert "ces" in names


@pytest.mark.anyio
async def test_adapters_have_required_fields(client):
    resp = await client.get("/api/cc/exchange/adapters")
    for adapter in resp.json():
        assert "name" in adapter
        assert "display_name" in adapter
        assert "currencies" in adapter
        assert "settlement_method" in adapter
        assert "healthy" in adapter
        assert adapter["healthy"] is True


# ── Quotes ───────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_quote_cc_to_new_earth(client):
    resp = await client.post(
        "/api/cc/exchange/quote",
        params={"from_currency": "CC", "to_currency": "NEW_EARTH", "amount": 100},
    )
    assert resp.status_code == 200
    quote = resp.json()
    assert quote["from_currency"] == "CC"
    assert quote["to_currency"] == "NEW_EARTH"
    assert quote["amount_from"] == 100
    assert quote["amount_to"] > 0
    assert quote["rate"] > 0
    assert quote["adapter"] == "new_earth"


@pytest.mark.anyio
async def test_quote_cc_to_ces(client):
    resp = await client.post(
        "/api/cc/exchange/quote",
        params={"from_currency": "CC", "to_currency": "CES", "amount": 100},
    )
    assert resp.status_code == 200
    quote = resp.json()
    assert quote["adapter"] == "ces"
    assert quote["amount_to"] > 0


@pytest.mark.anyio
async def test_quote_invalid_currency(client):
    resp = await client.post(
        "/api/cc/exchange/quote",
        params={"from_currency": "CC", "to_currency": "BITCOIN", "amount": 100},
    )
    assert resp.status_code == 400


# ── Swaps ────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_swap_initiate(client):
    resp = await client.post(
        "/api/cc/exchange/swap",
        json={
            "user_id": "test-user-1",
            "from_currency": "CC",
            "to_currency": "NEW_EARTH",
            "amount": 50,
        },
    )
    assert resp.status_code == 201
    swap = resp.json()
    assert swap["status"] == "pending_confirmation"
    assert swap["amount_from"] == 50
    assert swap["amount_to"] > 0
    assert swap["adapter"] == "new_earth"
    assert swap["settlement_method"] == "manual"
    assert "tx_id" in swap


@pytest.mark.anyio
async def test_swap_status(client):
    # Create a swap
    create = await client.post(
        "/api/cc/exchange/swap",
        json={
            "user_id": "test-user-2",
            "from_currency": "CC",
            "to_currency": "NEW_EARTH",
            "amount": 25,
        },
    )
    tx_id = create.json()["tx_id"]

    # Check status
    resp = await client.get(f"/api/cc/exchange/swap/{tx_id}")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending_confirmation"


@pytest.mark.anyio
async def test_swap_confirm(client):
    # Create a swap
    create = await client.post(
        "/api/cc/exchange/swap",
        json={
            "user_id": "test-user-3",
            "from_currency": "CC",
            "to_currency": "NEW_EARTH",
            "amount": 10,
        },
    )
    tx_id = create.json()["tx_id"]

    # Confirm it
    resp = await client.post(
        f"/api/cc/exchange/swap/{tx_id}/confirm",
        params={"external_tx_ref": "NE-12345", "confirmed_by": "test-user-3"},
    )
    assert resp.status_code == 200
    confirm = resp.json()
    assert confirm["status"] == "confirmed"
    assert confirm["external_tx_ref"] == "NE-12345"


@pytest.mark.anyio
async def test_swap_not_found(client):
    resp = await client.get("/api/cc/exchange/swap/nonexistent")
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_double_confirm_fails(client):
    # Create and confirm
    create = await client.post(
        "/api/cc/exchange/swap",
        json={
            "user_id": "test-user-4",
            "from_currency": "CC",
            "to_currency": "CES",
            "amount": 100,
        },
    )
    tx_id = create.json()["tx_id"]
    await client.post(f"/api/cc/exchange/swap/{tx_id}/confirm")

    # Second confirm should fail
    resp = await client.post(f"/api/cc/exchange/swap/{tx_id}/confirm")
    assert resp.status_code == 400


# ── History ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_swap_history(client):
    user = "test-user-history"
    # Create two swaps
    await client.post(
        "/api/cc/exchange/swap",
        json={"user_id": user, "from_currency": "CC", "to_currency": "NEW_EARTH", "amount": 10},
    )
    await client.post(
        "/api/cc/exchange/swap",
        json={"user_id": user, "from_currency": "CC", "to_currency": "CES", "amount": 20},
    )

    resp = await client.get(f"/api/cc/exchange/history/{user}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["swaps"]) == 2
