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
                "created_by_contributor_id": "user-1",
            },
        )
        assert created.status_code == 201
        assert created.json()["spec_id"] == "spec-xyz"

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
                "updated_by_contributor_id": "user-2",
            },
        )
        assert updated.status_code == 200
        payload = updated.json()
        assert payload["summary"] == "Updated summary"
        assert payload["updated_by_contributor_id"] == "user-2"
