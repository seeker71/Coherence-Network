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
        assert created["metadata"]["cost_basis"] == "declared_unverified"
        assert created["metadata"]["cost_confidence"] == 0.25

        contrib_id = created["id"]

        g = await client.get(f"/api/contributions/{contrib_id}")
        assert g.status_code == 200
        assert g.json()["id"] == contrib_id

        listed = await client.get("/api/contributions?limit=10")
        assert listed.status_code == 200
        items = listed.json()
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
        assert payload["metadata"]["cost_basis"] == "estimated_from_change_shape"
        assert payload["metadata"]["estimation_used"] is True


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
        assert payload["metadata"]["cost_basis"] == "estimated_from_submitted_cost"
        assert payload["metadata"]["estimation_used"] is True


@pytest.mark.asyncio
async def test_manual_contribution_cost_is_marked_actual_when_evidence_exists() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        c = await client.post("/api/contributors", json={"type": "HUMAN", "name": "Alice", "email": "alice@coherence.network"})
        contributor_id = c.json()["id"]
        a = await client.post("/api/assets", json={"type": "CODE", "description": "Repo"})
        asset_id = a.json()["id"]

        r = await client.post(
            "/api/contributions",
            json={
                "contributor_id": contributor_id,
                "asset_id": asset_id,
                "cost_amount": "9.50",
                "metadata": {"invoice_id": "inv_001"},
            },
        )
        assert r.status_code == 201
        payload = r.json()
        assert payload["metadata"]["cost_basis"] == "actual_verified"
        assert payload["metadata"]["estimation_used"] is False


@pytest.mark.asyncio
async def test_github_contribution_cost_marks_actual_with_verification_keys() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/contributions/github",
            json={
                "contributor_email": "verifier@coherence.network",
                "repository": "seeker71/Coherence-Network",
                "commit_hash": "ghi789",
                "cost_amount": "9.50",
                "metadata": {"invoice_id": "inv_002"},
            },
        )
        assert r.status_code == 201
        payload = r.json()
        assert Decimal(payload["cost_amount"]) == Decimal("9.50")
        assert payload["metadata"]["cost_basis"] == "actual_verified"
        assert payload["metadata"]["estimation_used"] is False


@pytest.mark.asyncio
async def test_github_contribution_marks_internal_emails_as_system_contributors() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/api/contributions/github",
            json={
                "contributor_email": "deploy-test+ci123@coherence.network",
                "repository": "seeker71/Coherence-Network",
                "commit_hash": "sys001",
                "cost_amount": "1.00",
                "metadata": {"files_changed": 1, "lines_added": 1},
            },
        )
        assert r.status_code == 201
        payload = r.json()
        assert payload["metadata"]["contributor_email"] == "deploy-test@coherence.network"
        assert payload["metadata"]["contributor_email_raw"] == "deploy-test+ci123@coherence.network"
        assert payload["metadata"]["contributor_type"] == "SYSTEM"


@pytest.mark.asyncio
async def test_github_debug_endpoint_defaults_to_dry_run_without_writes() -> None:
    app.state.graph_store = InMemoryGraphStore()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        debug = await client.post(
            "/api/contributions/github/debug",
            json={
                "contributor_email": "alice+debug@coherence.network",
                "repository": "seeker71/Coherence-Network",
                "commit_hash": "dbg001",
                "cost_amount": "5.00",
                "metadata": {"files_changed": 2, "lines_added": 10},
            },
        )
        assert debug.status_code == 200
        payload = debug.json()
        assert payload["success"] is True
        assert payload["dry_run"] is True
        assert payload["contributor_lookup"]["found_existing"] is False

        contributors = await client.get("/api/contributors?limit=10")
        contributions = await client.get("/api/contributions?limit=10")
        assert contributors.status_code == 200
        assert contributions.status_code == 200
        assert contributors.json() == []
        assert contributions.json() == []


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
