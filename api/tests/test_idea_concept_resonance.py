"""Tests for idea-level concept resonance across domains.

Contract (spec): resonance surfaces ideas that share *derived concept tokens* from
metadata (tags, interfaces, name, description, questions). The MVP scorer treats
these token sets as a proxy for structural similarity; cross-domain matches are
boosted when domain tags/interfaces differ — e.g. biology symbiosis ↔ software
microservices can resonate via shared *problem-structure* tokens (coupling,
boundary, dependency) without copying each other's domain vocabulary.
"""

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


@pytest.mark.asyncio
async def test_symbiosis_microservices_analogous_resonance_cross_domain(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Biology symbiosis ↔ software microservices: shared structural tokens, different domains.

    Neither idea name-drops the other's domain keyword; overlap comes from analogous
    problem framing (coupling, boundary, dependency) encoded in descriptions/tags.
    """
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    bio_payload = {
        "id": "symbiosis-biology-membrane",
        "name": "Symbiosis and membrane exchange",
        "description": (
            "Model mutual dependency, coupling, and resource exchange at organism "
            "boundaries; symbiotic partners negotiate stable interfaces."
        ),
        "potential_value": 62.0,
        "estimated_cost": 12.0,
        "confidence": 0.82,
        "tags": ["ecology", "coupling", "boundary"],
        "interfaces": ["domain:life-sciences"],
    }
    sw_payload = {
        "id": "microservices-architecture-fractal",
        "name": "Microservices decomposition",
        "description": (
            "Decompose capability into loosely coupled processes with explicit boundary "
            "contracts, dependency inversion, and stable interchange between contexts."
        ),
        "potential_value": 58.0,
        "estimated_cost": 11.0,
        "confidence": 0.78,
        "tags": ["architecture", "coupling", "boundary"],
        "interfaces": ["domain:engineering"],
    }
    noise_payload = {
        "id": "music-harmony-archive-2",
        "name": "Music Harmony Archive",
        "description": "Catalog regional harmony patterns for live performance.",
        "potential_value": 18.0,
        "estimated_cost": 4.0,
        "confidence": 0.55,
        "tags": ["music", "archive"],
        "interfaces": ["domain:arts"],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for payload in (bio_payload, sw_payload, noise_payload):
            created = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
            assert created.status_code == 201, created.text

        response = await client.get(
            "/api/ideas/symbiosis-biology-membrane/concept-resonance",
            params={"limit": 5, "min_score": 0.05},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["idea_id"] == "symbiosis-biology-membrane"
    assert body["total"] >= 1
    top = body["matches"][0]
    assert top["idea_id"] == "microservices-architecture-fractal"
    assert top["cross_domain"] is True
    sw_lower = sw_payload["description"].lower() + sw_payload["name"].lower()
    bio_lower = bio_payload["description"].lower() + bio_payload["name"].lower()
    assert "symbiosis" not in sw_lower
    assert "microservice" not in bio_lower and "microservices" not in bio_lower
    shared = set(top["shared_concepts"])
    assert {"coupling", "boundary"} <= shared
    assert "dependency" in shared or "exchange" in shared


@pytest.mark.asyncio
async def test_concept_resonance_invalid_min_score_returns_422(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "cr-validation-seed",
                "name": "Validation seed",
                "description": "Seed idea for query validation.",
                "potential_value": 40.0,
                "estimated_cost": 8.0,
                "confidence": 0.7,
                "tags": ["alpha"],
                "interfaces": ["domain:test"],
            },
            headers=AUTH_HEADERS,
        )
        too_high = await client.get(
            "/api/ideas/cr-validation-seed/concept-resonance",
            params={"min_score": 1.5},
        )
        not_a_float = await client.get(
            "/api/ideas/cr-validation-seed/concept-resonance",
            params={"min_score": "nope"},
        )

    assert too_high.status_code == 422
    assert not_a_float.status_code == 422


@pytest.mark.asyncio
async def test_post_duplicate_idea_returns_409(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))
    payload = {
        "id": "duplicate-cr-test",
        "name": "First",
        "description": "Once.",
        "potential_value": 40.0,
        "estimated_cost": 8.0,
        "confidence": 0.7,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)
        second = await client.post("/api/ideas", json=payload, headers=AUTH_HEADERS)

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["detail"] == "Idea already exists"


@pytest.mark.asyncio
async def test_put_tags_updates_concept_resonance_signals(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """After replacing tags, GET concept-resonance must reflect new shared tokens."""
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "ideas.json"))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "cr-update-alpha",
                "name": "Alpha",
                "description": "Alpha uses token alphaonly for isolation.",
                "potential_value": 40.0,
                "estimated_cost": 8.0,
                "confidence": 0.7,
                "tags": ["alphaonly", "zeta"],
                "interfaces": ["domain:cr-a"],
            },
            headers=AUTH_HEADERS,
        )
        await client.post(
            "/api/ideas",
            json={
                "id": "cr-update-beta",
                "name": "Beta",
                "description": "Beta shares structuraltoken after tag edit.",
                "potential_value": 41.0,
                "estimated_cost": 8.0,
                "confidence": 0.71,
                "tags": ["betaonly"],
                "interfaces": ["domain:cr-b"],
            },
            headers=AUTH_HEADERS,
        )
        before = await client.get(
            "/api/ideas/cr-update-alpha/concept-resonance",
            params={"min_score": 0.01},
        )
        assert before.status_code == 200
        assert before.json()["total"] == 0

        await client.put(
            "/api/ideas/cr-update-alpha/tags",
            json={"tags": ["structuraltoken", "alphaonly"]},
        )
        after = await client.get(
            "/api/ideas/cr-update-alpha/concept-resonance",
            params={"min_score": 0.01},
        )

    assert after.status_code == 200
    body = after.json()
    assert body["total"] >= 1
    match = next(m for m in body["matches"] if m["idea_id"] == "cr-update-beta")
    assert "structuraltoken" in set(match.get("shared_concepts", []))
