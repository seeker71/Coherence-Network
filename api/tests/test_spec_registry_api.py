from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


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
