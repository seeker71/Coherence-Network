from __future__ import annotations

import pytest
from decimal import Decimal
from httpx import ASGITransport, AsyncClient

from app.adapters.graph_store import InMemoryGraphStore
from app.main import app


@pytest.mark.asyncio
async def test_create_get_contribution_and_asset_rollup_cost() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        contributor_id = c.json()["id"]

        a = await client.post("/api/assets", json={"type": "CODE", "description": "Repo"})
        asset_id = a.json()["id"]

        r = await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_id,
                "asset_id": asset_id,
                "cost_amount": "100.00",
                "metadata": {"has_tests": True, "has_docs": True},
            },
        )
        assert r.status_code == 201
        created = r.json()
        assert Decimal(created["cost_amount"]) == Decimal("100.00")
        assert abs(float(created["coherence_score"]) - 0.9) < 1e-9

        contrib_id = created["id"]

        g = await client.get(f"/api/contributions/{contrib_id}")
        assert g.status_code == 200
        assert g.json()["id"] == contrib_id

        l = await client.get("/api/contributions?limit=10")
        assert l.status_code == 200
        items = l.json()
        assert isinstance(items, list)
        assert any(i.get("id") == contrib_id for i in items)

        asset = await client.get(f"/api/assets/{asset_id}")
        assert Decimal(asset.json()["total_cost"]) == Decimal("100.00")


@pytest.mark.asyncio
async def test_create_contribution_404s() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        a = await client.post("/api/assets", json={"type": "CODE", "description": "Repo"})
        asset_id = a.json()["id"]

        r = await client.post(
            "/api/contributions",
            json={
                "contributor_id": "00000000-0000-0000-0000-000000000000",
                "asset_id": asset_id,
                "cost_amount": "10.00",
                "metadata": {},
            },
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "Contributor not found"

        c = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        contributor_id = c.json()["id"]

        r2 = await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_id,
                "asset_id": "00000000-0000-0000-0000-000000000000",
                "cost_amount": "10.00",
                "metadata": {},
            },
        )
        assert r2.status_code == 404
        assert r2.json()["detail"] == "Asset not found"


@pytest.mark.asyncio
async def test_get_asset_and_contributor_contributions() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        contributor_id = c.json()["id"]

        a = await client.post("/api/assets", json={"type": "CODE", "description": "Repo"})
        asset_id = a.json()["id"]

        await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_id,
                "asset_id": asset_id,
                "cost_amount": "5.00",
                "metadata": {"complexity": "low"},
            },
        )

        ac = await client.get(f"/api/assets/{asset_id}/contributions")
        assert ac.status_code == 200
        assert len(ac.json()) == 1

        cc = await client.get(f"/api/contributors/{contributor_id}/contributions")
        assert cc.status_code == 200
        assert len(cc.json()) == 1


@pytest.mark.asyncio
async def test_bidirectional_asset_contributor_links_and_audit() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c1 = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        contributor_a = c1.json()["id"]
        c2 = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Bob", "email": "bob@example.com"})
        contributor_b = c2.json()["id"]

        a1 = await client.post("/api/assets", json={"type": "CODE", "description": "API service"})
        asset_linked = a1.json()["id"]
        a2 = await client.post("/api/assets", json={"type": "DATA", "description": "Resource catalog"})
        asset_unlinked = a2.json()["id"]

        r = await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_a,
                "asset_id": asset_linked,
                "cost_amount": "12.50",
                "metadata": {"has_docs": True},
            },
        )
        assert r.status_code == 201

        by_asset = await client.get(f"/api/links/assets/{asset_linked}/contributors")
        assert by_asset.status_code == 200
        linked_contributor_ids = {row["id"] for row in by_asset.json()}
        assert contributor_a in linked_contributor_ids

        by_contributor = await client.get(f"/api/links/contributors/{contributor_a}/assets")
        assert by_contributor.status_code == 200
        linked_asset_ids = {row["id"] for row in by_contributor.json()}
        assert asset_linked in linked_asset_ids

        matrix_assets = await client.get("/api/links/assets/with-contributors?limit=10")
        assert matrix_assets.status_code == 200
        matrix_by_asset_id = {row["asset_id"]: row for row in matrix_assets.json()}
        assert matrix_by_asset_id[asset_linked]["contributor_count"] == 1
        assert matrix_by_asset_id[asset_unlinked]["contributor_count"] == 0

        matrix_contributors = await client.get("/api/links/contributors/with-assets?limit=10")
        assert matrix_contributors.status_code == 200
        matrix_by_contributor_id = {row["contributor_id"]: row for row in matrix_contributors.json()}
        assert matrix_by_contributor_id[contributor_a]["asset_count"] == 1
        assert matrix_by_contributor_id[contributor_b]["asset_count"] == 0

        audit = await client.get("/api/links/asset-contributor/audit")
        assert audit.status_code == 200
        body = audit.json()
        assert body["total_assets"] == 2
        assert body["total_contributors"] == 2
        assert body["linked_assets"] == 1
        assert body["linked_contributors"] == 1
        assert body["fully_linked"] is False
        assert asset_unlinked in body["missing_asset_links"]
        assert contributor_b in body["missing_contributor_links"]


@pytest.mark.asyncio
async def test_create_contribution_422() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@example.com"})
        contributor_id = c.json()["id"]
        a = await client.post("/api/assets", json={"type": "CODE", "description": "Repo"})
        asset_id = a.json()["id"]

        r = await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_id,
                "asset_id": asset_id,
                "cost_amount": "not-a-number",
                "metadata": {},
            },
        )
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_github_contribution_cost_is_normalized_from_metadata() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/contributions/github",
            json={
                "contributor_email": "alice@coherence.network",
                "repository": "seeker71/Coherence-Network",
                "commit_hash": "abc123",
                "cost_amount": "342.50",
                "metadata": {"files_changed": 3, "lines_added": 120},
            },
        )
        assert r.status_code == 201
        payload = r.json()
        assert Decimal(payload["cost_amount"]) == Decimal("0.79")
        assert payload["metadata"]["raw_cost_amount"] == "342.50"
        assert payload["metadata"]["normalized_cost_amount"] == "0.79"
        assert payload["metadata"]["cost_estimator_version"] == "v2_normalized"


@pytest.mark.asyncio
async def test_github_contribution_cost_clamps_when_metadata_missing() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/contributions/github",
            json={
                "contributor_email": "bob@coherence.network",
                "repository": "seeker71/Coherence-Network",
                "commit_hash": "def456",
                "cost_amount": "342.50",
                "metadata": {},
            },
        )
        assert r.status_code == 201
        payload = r.json()
        assert Decimal(payload["cost_amount"]) == Decimal("10.00")
        assert payload["metadata"]["raw_cost_amount"] == "342.50"
        assert payload["metadata"]["normalized_cost_amount"] == "10.00"


@pytest.mark.asyncio
async def test_agent_tasks_router_is_exposed() -> None:
    # Validates /api/agent/tasks is publicly mountable (router included in main app).
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/agent/tasks")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, dict)
        assert "tasks" in body
