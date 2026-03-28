"""Tests for accessible ontology — non-technical contributors can extend it naturally.

Verification contract:
1. GET /api/concepts returns a paginated list with human-readable names and descriptions
2. GET /api/concepts/search?q=<plain-english> finds concepts by plain-language query
3. GET /api/concepts/relationships returns relationship types with human-readable names
4. POST /api/concepts/{id}/edges creates a connection using a plain string relationship type
5. GET /api/concepts/{id}/edges retrieves the edge a contributor just created
6. A contributor with zero technical knowledge can discover, search, and link concepts
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.mark.asyncio
async def test_list_concepts_returns_human_readable_fields() -> None:
    """Non-technical contributors can browse concepts with meaningful names and descriptions."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/concepts")

    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    items = data["items"]
    assert len(items) > 0

    for concept in items[:5]:
        assert "id" in concept
        assert "name" in concept
        assert isinstance(concept["name"], str)
        assert len(concept["name"]) > 0
        # Description should be present and readable
        assert "description" in concept
        assert isinstance(concept["description"], str)


@pytest.mark.asyncio
async def test_search_concepts_by_plain_language_term() -> None:
    """Non-technical users can find concepts using everyday words."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # "activity" is a plain English word that exists in the ontology
        resp = await client.get("/api/concepts/search", params={"q": "activity"})

    assert resp.status_code == 200
    results = resp.json()
    assert isinstance(results, list)
    # At least one concept should match "activity"
    assert len(results) > 0
    names = [r["name"].lower() for r in results]
    descriptions = [r.get("description", "").lower() for r in results]
    # The result should relate to the search term
    found = any("activity" in n or "activity" in d for n, d in zip(names, descriptions))
    assert found, "Search for 'activity' should return at least one relevant concept"


@pytest.mark.asyncio
async def test_search_concepts_by_another_plain_term() -> None:
    """Search works for multiple plain-language terms, not just edge cases."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/concepts/search", params={"q": "entity"})

    assert resp.status_code == 200
    results = resp.json()
    assert isinstance(results, list)
    assert len(results) > 0


@pytest.mark.asyncio
async def test_relationship_types_have_human_readable_names() -> None:
    """Contributors can pick relationship types by reading plain names, not codes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/concepts/relationships")

    assert resp.status_code == 200
    rels = resp.json()
    assert isinstance(rels, list)
    assert len(rels) > 0

    for rel in rels[:5]:
        assert "id" in rel
        assert "name" in rel
        # Names should be human-readable (contain letters, not just codes)
        assert isinstance(rel["name"], str)
        assert len(rel["name"]) > 0


@pytest.mark.asyncio
async def test_contributor_can_create_edge_between_concepts() -> None:
    """A contributor can connect two concepts using a simple, named relationship."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # First, get two concept IDs from the ontology
        list_resp = await client.get("/api/concepts", params={"limit": 5})
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        assert len(items) >= 2

        from_id = items[0]["id"]
        to_id = items[1]["id"]

        # Create edge using a human-readable relationship type
        edge_resp = await client.post(
            f"/api/concepts/{from_id}/edges",
            json={
                "from_id": from_id,
                "to_id": to_id,
                "relationship_type": "resonates-with",
                "created_by": "non-technical-contributor",
            },
        )

    assert edge_resp.status_code == 200
    edge = edge_resp.json()
    assert edge["from"] == from_id
    assert edge["to"] == to_id
    assert edge["type"] == "resonates-with"
    assert edge["created_by"] == "non-technical-contributor"
    assert "id" in edge


@pytest.mark.asyncio
async def test_contributor_can_retrieve_their_created_edge() -> None:
    """After linking concepts, a contributor can verify the connection exists."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        list_resp = await client.get("/api/concepts", params={"limit": 5})
        items = list_resp.json()["items"]
        from_id = items[0]["id"]
        to_id = items[1]["id"]

        # Create the edge
        await client.post(
            f"/api/concepts/{from_id}/edges",
            json={
                "from_id": from_id,
                "to_id": to_id,
                "relationship_type": "aligns-with",
                "created_by": "curious-contributor",
            },
        )

        # Retrieve edges for the source concept
        edges_resp = await client.get(f"/api/concepts/{from_id}/edges")

    assert edges_resp.status_code == 200
    edges = edges_resp.json()
    assert isinstance(edges, list)
    contributor_edges = [e for e in edges if e.get("created_by") == "curious-contributor"]
    assert len(contributor_edges) >= 1
    assert contributor_edges[0]["type"] == "aligns-with"


@pytest.mark.asyncio
async def test_get_single_concept_by_id() -> None:
    """Contributors can look up a specific concept by its ID to understand it."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # "activity" is a known concept in the ontology
        resp = await client.get("/api/concepts/activity")

    assert resp.status_code == 200
    concept = resp.json()
    assert concept["id"] == "activity"
    assert "name" in concept
    assert "description" in concept


@pytest.mark.asyncio
async def test_unknown_concept_returns_404() -> None:
    """Contributors get a clear error when looking up a concept that does not exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/concepts/this-concept-does-not-exist-xyz")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_concepts_pagination_allows_discovery() -> None:
    """Contributors can paginate through the full ontology to explore concepts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first_page = await client.get("/api/concepts", params={"limit": 5, "offset": 0})
        second_page = await client.get("/api/concepts", params={"limit": 5, "offset": 5})

    assert first_page.status_code == 200
    assert second_page.status_code == 200

    first_ids = {c["id"] for c in first_page.json()["items"]}
    second_ids = {c["id"] for c in second_page.json()["items"]}

    # Pages should not overlap
    assert first_ids.isdisjoint(second_ids), "Paginated pages must return different concepts"
