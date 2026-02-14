from __future__ import annotations

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_list_ideas_returns_ranked_scores_and_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas")

    assert resp.status_code == 200
    data = resp.json()
    assert "ideas" in data
    assert "summary" in data
    assert data["summary"]["total_ideas"] >= 1
    assert all("free_energy_score" in idea for idea in data["ideas"])

    scores = [idea["free_energy_score"] for idea in data["ideas"]]
    assert scores == sorted(scores, reverse=True)
    assert portfolio_path.exists()


@pytest.mark.asyncio
async def test_get_idea_by_id_and_404(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")
        idea_id = listed.json()["ideas"][0]["id"]

        found = await client.get(f"/api/ideas/{idea_id}")
        missing = await client.get("/api/ideas/does-not-exist")

    assert found.status_code == 200
    assert found.json()["id"] == idea_id
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_patch_idea_updates_fields(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    portfolio_path = tmp_path / "idea_portfolio.json"
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(portfolio_path))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        listed = await client.get("/api/ideas")
        idea_id = listed.json()["ideas"][0]["id"]

        patched = await client.patch(
            f"/api/ideas/{idea_id}",
            json={
                "actual_value": 34.5,
                "actual_cost": 8.0,
                "confidence": 0.75,
                "manifestation_status": "validated",
            },
        )

        refetched = await client.get(f"/api/ideas/{idea_id}")

    assert patched.status_code == 200
    payload = refetched.json()
    assert payload["actual_value"] == 34.5
    assert payload["actual_cost"] == 8.0
    assert payload["confidence"] == 0.75
    assert payload["manifestation_status"] == "validated"

    raw = json.loads(portfolio_path.read_text(encoding="utf-8"))
    assert any(item["id"] == idea_id and item["manifestation_status"] == "validated" for item in raw["ideas"])
