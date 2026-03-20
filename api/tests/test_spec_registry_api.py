from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.mark.asyncio
async def test_spec_registry_create_list_update(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/spec-registry",
            json={
                "spec_id": "spec-xyz",
                "title": "Contributor spec",
                "summary": "Initial summary",
                "idea_id": "portfolio-governance",
                "potential_value": 55.0,
                "estimated_cost": 10.0,
                "actual_value": 12.5,
                "actual_cost": 4.0,
                "created_by_contributor_id": "user-1",
            },
            headers=AUTH_HEADERS,
        )
        assert created.status_code == 201
        created_payload = created.json()
        assert created_payload["spec_id"] == "spec-xyz"
        assert created_payload["potential_value"] == 55.0
        assert created_payload["estimated_cost"] == 10.0
        assert created_payload["actual_value"] == 12.5
        assert created_payload["actual_cost"] == 4.0
        assert created_payload["value_gap"] == 42.5
        assert created_payload["cost_gap"] == -6.0
        assert created_payload["estimated_roi"] == 5.5
        assert created_payload["actual_roi"] == 3.125

        conflict = await client.post(
            "/api/spec-registry",
            json={
                "spec_id": "spec-xyz",
                "title": "Duplicate",
                "summary": "Duplicate summary",
            },
            headers=AUTH_HEADERS,
        )
        assert conflict.status_code == 409

        listed = await client.get("/api/spec-registry")
        assert listed.status_code == 200
        assert any(row["spec_id"] == "spec-xyz" for row in listed.json())

        updated = await client.patch(
            "/api/spec-registry/spec-xyz",
            json={
                "summary": "Updated summary",
                "actual_value": 30.0,
                "actual_cost": 7.5,
                "updated_by_contributor_id": "user-2",
            },
            headers=AUTH_HEADERS,
        )
        assert updated.status_code == 200
        payload = updated.json()
        assert payload["summary"] == "Updated summary"
        assert payload["actual_value"] == 30.0
        assert payload["actual_cost"] == 7.5
        assert payload["value_gap"] == 25.0
        assert payload["cost_gap"] == -2.5
        assert payload["estimated_roi"] == 5.5
        assert payload["actual_roi"] == 4.0
        assert payload["updated_by_contributor_id"] == "user-2"


@pytest.mark.asyncio
async def test_spec_registry_uses_database_url_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'governance.db'}")
    monkeypatch.delenv("GOVERNANCE_DATABASE_URL", raising=False)
    monkeypatch.delenv("GOVERNANCE_DB_URL", raising=False)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/spec-registry",
            json={
                "spec_id": "spec-db-fallback",
                "title": "DB fallback",
                "summary": "Spec persists through DATABASE_URL.",
            },
            headers=AUTH_HEADERS,
        )
        assert created.status_code == 201
        listed = await client.get("/api/spec-registry")
        assert listed.status_code == 200
        assert any(row["spec_id"] == "spec-db-fallback" for row in listed.json())


@pytest.mark.asyncio
async def test_spec_registry_cards_endpoint_supports_filters_and_sort(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for payload in (
            {
                "spec_id": "spec-alpha",
                "title": "Alpha Unlinked",
                "summary": "No idea linked yet.",
                "potential_value": 20.0,
                "estimated_cost": 4.0,
                "actual_value": 0.0,
                "actual_cost": 0.0,
            },
            {
                "spec_id": "spec-beta",
                "title": "Beta In Progress",
                "summary": "Implementation pending.",
                "idea_id": "idea-beta",
                "process_summary": "Draft process exists.",
                "potential_value": 30.0,
                "estimated_cost": 6.0,
                "actual_value": 0.0,
                "actual_cost": 0.0,
            },
            {
                "spec_id": "spec-gamma",
                "title": "Gamma Measured",
                "summary": "Measured results available.",
                "idea_id": "idea-gamma",
                "implementation_summary": "Shipped rollout complete.",
                "potential_value": 50.0,
                "estimated_cost": 10.0,
                "actual_value": 40.0,
                "actual_cost": 5.0,
            },
        ):
            created = await client.post("/api/spec-registry", json=payload, headers=AUTH_HEADERS)
            assert created.status_code == 201

        linked = await client.get("/api/spec-registry/cards", params={"linked": "linked", "sort": "roi_desc", "limit": 10})
        assert linked.status_code == 200
        linked_payload = linked.json()
        assert linked_payload["summary"]["total"] == 2
        assert linked_payload["items"][0]["spec_id"] == "spec-gamma"
        assert linked_payload["items"][0]["state"] == "measured"
        assert linked_payload["items"][0]["attention_level"] in {"none", "low", "medium", "high"}
        assert linked_payload["items"][0]["links"]["web_detail_path"] == "/specs/spec-gamma"
        assert linked_payload["items"][0]["links"]["web_idea_path"] == "/ideas/idea-gamma"

        unlinked = await client.get("/api/spec-registry/cards", params={"state": "unlinked", "limit": 10})
        assert unlinked.status_code == 200
        unlinked_payload = unlinked.json()
        assert unlinked_payload["summary"]["total"] == 1
        assert unlinked_payload["items"][0]["spec_id"] == "spec-alpha"
        assert unlinked_payload["items"][0]["state"] == "unlinked"
        assert unlinked_payload["items"][0]["attention_level"] == "high"

        min_roi = await client.get("/api/spec-registry/cards", params={"min_roi": 6, "limit": 10})
        assert min_roi.status_code == 200
        min_roi_payload = min_roi.json()
        assert min_roi_payload["summary"]["total"] == 1
        assert min_roi_payload["items"][0]["spec_id"] == "spec-gamma"


@pytest.mark.asyncio
async def test_spec_registry_cards_endpoint_uses_cursor_pagination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for index in range(1, 5):
            created = await client.post(
                "/api/spec-registry",
                json={
                    "spec_id": f"spec-{index}",
                    "title": f"Spec {index}",
                    "summary": "Cursor pagination sample.",
                    "idea_id": f"idea-{index}",
                    "potential_value": float(10 + index),
                    "estimated_cost": 2.0,
                    "actual_value": 0.0,
                    "actual_cost": 0.0,
                },
                headers=AUTH_HEADERS,
            )
            assert created.status_code == 201

        first = await client.get("/api/spec-registry/cards", params={"sort": "name_asc", "limit": 2})
        assert first.status_code == 200
        first_payload = first.json()
        assert first_payload["pagination"]["returned"] == 2
        assert first_payload["pagination"]["has_more"] is True
        next_cursor = first_payload["pagination"]["next_cursor"]
        assert isinstance(next_cursor, str) and next_cursor
        first_ids = [row["spec_id"] for row in first_payload["items"]]

        second = await client.get("/api/spec-registry/cards", params={"sort": "name_asc", "limit": 2, "cursor": next_cursor})
        assert second.status_code == 200
        second_payload = second.json()
        second_ids = [row["spec_id"] for row in second_payload["items"]]
        assert len(set(first_ids).intersection(set(second_ids))) == 0
        assert second_payload["query"]["cursor"] == 2
