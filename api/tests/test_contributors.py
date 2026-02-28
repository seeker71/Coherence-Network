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


@pytest.mark.asyncio
async def test_create_contributor_conflict_when_email_already_exists_after_normalization() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "Owner", "email": "urs-muff@coherence.network"},
        )
        assert first.status_code == 201

        second = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "Alias", "email": "urs-muff+run1@coherence.network"},
        )
        assert second.status_code == 409
        assert second.json()["detail"] == "Contributor email already exists"


@pytest.mark.asyncio
async def test_list_contributors_can_exclude_system_rows() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        human = await client.post(
            "/api/contributors",
            json={"type": "HUMAN", "name": "Human", "email": "human@coherence.network"},
        )
        assert human.status_code == 201
        system = await client.post(
            "/api/contributors",
            json={"type": "SYSTEM", "name": "System", "email": "system@coherence.network"},
        )
        assert system.status_code == 201

        all_rows = await client.get("/api/contributors?limit=10")
        assert all_rows.status_code == 200
        assert len(all_rows.json()) == 2

        human_only = await client.get("/api/contributors?limit=10&include_system=false")
        assert human_only.status_code == 200
        payload = human_only.json()
        assert len(payload) == 1
        assert payload[0]["type"] == "HUMAN"
