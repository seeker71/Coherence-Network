"""Tests for the Concept Layer Foundation spec.

Verifies:
- GET /api/concepts — list concepts with pagination (184 total)
- GET /api/concepts/{id} — get concept by ID, 404 for unknown
- GET /api/concepts/search?q= — full-text search
- GET /api/concepts/{concept_id}/edges — get edges for concept
- POST /api/concepts/{concept_id}/edges — create a typed edge
- GET /api/concepts/relationships — 46 relationship types
- GET /api/concepts/axes — 53 ontology axes
- GET /api/concepts/stats — counts for ontology
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.mark.asyncio
async def test_list_concepts_returns_184_total() -> None:
    """GET /api/concepts should expose all 184 Living Codex concepts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/concepts", params={"limit": 50, "offset": 0})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 184
    assert len(body["items"]) == 50
    assert body["limit"] == 50
    assert body["offset"] == 0


@pytest.mark.asyncio
async def test_list_concepts_pagination() -> None:
    """Pagination offset and limit are respected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r1 = await client.get("/api/concepts", params={"limit": 10, "offset": 0})
        r2 = await client.get("/api/concepts", params={"limit": 10, "offset": 10})

    assert r1.status_code == 200
    assert r2.status_code == 200
    ids1 = [c["id"] for c in r1.json()["items"]]
    ids2 = [c["id"] for c in r2.json()["items"]]
    # Pages must not overlap
    assert set(ids1).isdisjoint(set(ids2))
    assert len(ids1) == 10
    assert len(ids2) == 10


@pytest.mark.asyncio
async def test_list_concepts_all_have_required_fields() -> None:
    """Every concept must have id, name, description."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/concepts", params={"limit": 200})

    body = response.json()
    for concept in body["items"]:
        assert "id" in concept, f"Missing id: {concept}"
        assert "name" in concept, f"Missing name: {concept}"
        assert "description" in concept, f"Missing description: {concept}"


@pytest.mark.asyncio
async def test_get_concept_by_id_returns_concept() -> None:
    """GET /api/concepts/{id} should return a known concept by its ID."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 'activity' is the first concept in core-concepts.json
        response = await client.get("/api/concepts/activity")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "activity"
    assert body["name"] == "Activity"
    assert "description" in body


@pytest.mark.asyncio
async def test_get_concept_unknown_returns_404() -> None:
    """GET /api/concepts/{id} for a non-existent concept returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/concepts/non-existent-concept-xyz")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_search_concepts_returns_matches() -> None:
    """GET /api/concepts/search?q= should return concepts matching the query."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/concepts/search", params={"q": "activity"})

    assert response.status_code == 200
    results = response.json()
    assert isinstance(results, list)
    assert len(results) >= 1
    # The 'activity' concept must be in the results
    ids = [r["id"] for r in results]
    assert "activity" in ids


@pytest.mark.asyncio
async def test_search_concepts_no_match_returns_empty_list() -> None:
    """GET /api/concepts/search?q= with a nonsense query returns empty list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/concepts/search", params={"q": "zzznomatchxxx999"})

    assert response.status_code == 200
    results = response.json()
    assert results == []


@pytest.mark.asyncio
async def test_search_concepts_respects_limit() -> None:
    """Search limit parameter caps returned results."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/concepts/search", params={"q": "e", "limit": 3})

    assert response.status_code == 200
    results = response.json()
    assert len(results) <= 3


@pytest.mark.asyncio
async def test_list_relationships_returns_46_types() -> None:
    """GET /api/concepts/relationships should expose all 46 relationship types."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/concepts/relationships")

    assert response.status_code == 200
    rels = response.json()
    assert isinstance(rels, list)
    assert len(rels) == 46
    # Each relationship should have id and name
    for rel in rels:
        assert "id" in rel
        assert "name" in rel


@pytest.mark.asyncio
async def test_list_axes_returns_53_axes() -> None:
    """GET /api/concepts/axes should expose all 53 ontology axes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/concepts/axes")

    assert response.status_code == 200
    axes = response.json()
    assert isinstance(axes, list)
    assert len(axes) == 53
    for axis in axes:
        assert "id" in axis
        assert "name" in axis


@pytest.mark.asyncio
async def test_concept_stats_reports_correct_counts() -> None:
    """GET /api/concepts/stats should report the full ontology counts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/concepts/stats")

    assert response.status_code == 200
    stats = response.json()
    assert stats["concepts"] == 184
    assert stats["relationship_types"] == 46
    assert stats["axes"] == 53
    assert "user_edges" in stats


@pytest.mark.asyncio
async def test_get_concept_edges_returns_list_for_known_concept() -> None:
    """GET /api/concepts/{id}/edges returns an empty or populated list for a known concept."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/concepts/activity/edges")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_get_concept_edges_404_for_unknown_concept() -> None:
    """GET /api/concepts/{id}/edges returns 404 for unknown concept."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/concepts/totally-unknown-xyz/edges")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_edge_between_two_concepts() -> None:
    """POST /api/concepts/{id}/edges creates a typed relationship between two concepts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/concepts/activity/edges",
            json={
                "from_id": "activity",
                "to_id": "entity",
                "relationship_type": "resonates-with",
                "created_by": "test-agent",
            },
        )

    assert response.status_code == 200
    edge = response.json()
    assert edge["from"] == "activity"
    assert edge["to"] == "entity"
    assert edge["type"] == "resonates-with"
    assert edge["created_by"] == "test-agent"
    assert "id" in edge
    assert "created_at" in edge


@pytest.mark.asyncio
async def test_create_edge_unknown_source_returns_404() -> None:
    """POST /api/concepts/{id}/edges returns 404 if source concept does not exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/concepts/unknown-concept-xyz/edges",
            json={
                "from_id": "unknown-concept-xyz",
                "to_id": "activity",
                "relationship_type": "resonates-with",
            },
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_edge_unknown_target_returns_404() -> None:
    """POST /api/concepts/{id}/edges returns 404 if target concept does not exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/concepts/activity/edges",
            json={
                "from_id": "activity",
                "to_id": "totally-unknown-target-xyz",
                "relationship_type": "resonates-with",
            },
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_edge_appears_in_concept_edges_after_creation() -> None:
    """A created edge is retrievable via GET /api/concepts/{id}/edges."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create edge
        create_r = await client.post(
            "/api/concepts/activity/edges",
            json={
                "from_id": "activity",
                "to_id": "entity",
                "relationship_type": "resonates-with",
                "created_by": "test",
            },
        )
        assert create_r.status_code == 200
        edge_id = create_r.json()["id"]

        # Retrieve edges for concept
        edges_r = await client.get("/api/concepts/activity/edges")

    assert edges_r.status_code == 200
    edge_ids = [e["id"] for e in edges_r.json()]
    assert edge_id in edge_ids
