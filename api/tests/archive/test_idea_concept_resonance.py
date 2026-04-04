"""Tests for idea-level concept resonance across domains."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.mark.asyncio
async def test_concept_resonance_surfaces_cross_domain_match_first(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for payload in (
            {
                "id": "bio-feedback-loops",
                "name": "Biology Feedback Loops",
                "description": "Map adaptive feedback loops in living systems.",
                "potential_value": 60.0,
                "estimated_cost": 12.0,
                "confidence": 0.8,
                "tags": ["biology", "feedback", "adaptation"],
                "interfaces": ["domain:science"],
            },
            {
                "id": "logistics-feedback-routing",
                "name": "Logistics Feedback Routing",
                "description": "Use adaptive feedback loops to improve warehouse routing.",
                "potential_value": 55.0,
                "estimated_cost": 11.0,
                "confidence": 0.75,
                "tags": ["logistics", "feedback", "routing"],
                "interfaces": ["domain:operations"],
            },
            {
                "id": "music-harmony-archive",
                "name": "Music Harmony Archive",
                "description": "Catalog regional harmony patterns for live performance.",
                "potential_value": 20.0,
                "estimated_cost": 5.0,
                "confidence": 0.6,
                "tags": ["music", "archive"],
                "interfaces": ["domain:arts"],
            },
        ):
            created = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
            assert created.status_code == 201, created.text

        response = await client.get(
            "/api/ideas/bio-feedback-loops/concept-resonance",
            params={"limit": 3, "min_score": 0.05},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["idea_id"] == "bio-feedback-loops"
    assert body["total"] >= 1
    assert body["matches"][0]["idea_id"] == "logistics-feedback-routing"
    assert body["matches"][0]["cross_domain"] is True
    assert "feedback" in body["matches"][0]["shared_concepts"]
    assert "biology" in body["matches"][0]["source_domains"]
    assert "logistics" in body["matches"][0]["candidate_domains"]


@pytest.mark.asyncio
async def test_concept_resonance_404_for_unknown_idea(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/ideas/missing-idea/concept-resonance")

    assert response.status_code == 404
