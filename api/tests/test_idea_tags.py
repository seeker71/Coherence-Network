"""Tests for idea tagging system (spec 129)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import idea_service

AUTH_HEADERS = {"X-API-Key": "dev-key"}

_BASE_IDEA = {
    "potential_value": 50.0,
    "estimated_cost": 10.0,
    "confidence": 0.7,
}


@pytest.mark.asyncio
async def test_create_idea_normalizes_and_returns_tags() -> None:
    """POST /api/ideas with tags normalizes and returns them on the response."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas",
            json={
                "id": "tag-test-create",
                "name": "Tag Test Create",
                "description": "Test idea for tag normalization.",
                "tags": ["  Ideas  ", "SEARCH", "governance", "ideas"],
                **_BASE_IDEA,
            },
        )
    assert resp.status_code == 201
    data = resp.json()
    # Normalized: trim, lowercase, deduplicate, sort
    assert data["tags"] == ["governance", "ideas", "search"]


@pytest.mark.asyncio
async def test_create_idea_without_tags_defaults_to_empty() -> None:
    """POST /api/ideas without tags field returns empty list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/ideas",
            json={
                "id": "tag-test-no-tags",
                "name": "No Tags Idea",
                "description": "Idea without any tags.",
                **_BASE_IDEA,
            },
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["tags"] == []


@pytest.mark.asyncio
async def test_get_idea_returns_tags() -> None:
    """GET /api/ideas/{id} returns normalized tags."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "tag-test-get",
                "name": "Tag Get Test",
                "description": "Get idea returns tags.",
                "tags": ["alpha", "beta"],
                **_BASE_IDEA,
            },
        )
        resp = await client.get("/api/ideas/tag-test-get")
    assert resp.status_code == 200
    assert resp.json()["tags"] == ["alpha", "beta"]


@pytest.mark.asyncio
async def test_list_ideas_filters_by_all_requested_tags() -> None:
    """GET /api/ideas?tags=X,Y returns only ideas carrying both X and Y."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Idea with both tags
        await client.post(
            "/api/ideas",
            json={
                "id": "filter-both",
                "name": "Has Both Tags",
                "description": "Carries ideas and search.",
                "tags": ["ideas", "search"],
                **_BASE_IDEA,
            },
        )
        # Idea with only one tag
        await client.post(
            "/api/ideas",
            json={
                "id": "filter-one",
                "name": "Has One Tag",
                "description": "Carries only ideas tag.",
                "tags": ["ideas"],
                **_BASE_IDEA,
            },
        )
        # Idea with no tags
        await client.post(
            "/api/ideas",
            json={
                "id": "filter-none",
                "name": "No Tags",
                "description": "No tags at all.",
                **_BASE_IDEA,
            },
        )

        resp = await client.get("/api/ideas?tags=ideas,search")

    assert resp.status_code == 200
    data = resp.json()
    returned_ids = {i["id"] for i in data["ideas"]}
    assert "filter-both" in returned_ids
    assert "filter-one" not in returned_ids
    assert "filter-none" not in returned_ids


@pytest.mark.asyncio
async def test_list_ideas_tag_filter_normalizes_request() -> None:
    """Tags in the query param are normalized before matching."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "filter-normalize",
                "name": "Filter Normalize",
                "description": "Tag normalization in filter.",
                "tags": ["ideas"],
                **_BASE_IDEA,
            },
        )
        # Request with uppercase / spaces — should normalize to "ideas"
        resp = await client.get("/api/ideas?tags=IDEAS")

    assert resp.status_code == 200
    data = resp.json()
    returned_ids = {i["id"] for i in data["ideas"]}
    assert "filter-normalize" in returned_ids


@pytest.mark.asyncio
async def test_put_idea_tags_replaces_existing_tags() -> None:
    """PUT /api/ideas/{id}/tags replaces the full tag set."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "tag-test-put",
                "name": "Tag Put Test",
                "description": "Test tag replacement.",
                "tags": ["old-tag"],
                **_BASE_IDEA,
            },
        )
        # Replace tags
        resp = await client.put(
            "/api/ideas/tag-test-put/tags",
            json={"tags": ["new-tag", "  Another Tag  ", "new-tag"]},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "tag-test-put"
    assert data["tags"] == ["another-tag", "new-tag"]


@pytest.mark.asyncio
async def test_put_idea_tags_clears_all_tags_when_empty() -> None:
    """PUT /api/ideas/{id}/tags with empty array clears all tags."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "tag-test-clear",
                "name": "Clear Tags",
                "description": "Test clearing tags.",
                "tags": ["keep-me"],
                **_BASE_IDEA,
            },
        )
        resp = await client.put(
            "/api/ideas/tag-test-clear/tags",
            json={"tags": []},
        )

    assert resp.status_code == 200
    assert resp.json()["tags"] == []


@pytest.mark.asyncio
async def test_put_idea_tags_returns_404_for_unknown_idea() -> None:
    """PUT /api/ideas/{id}/tags returns 404 for non-existent idea."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.put(
            "/api/ideas/does-not-exist-xyz/tags",
            json={"tags": ["some-tag"]},
        )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_put_idea_tags_returns_422_for_invalid_tag() -> None:
    """PUT /api/ideas/{id}/tags with a non-empty tag that normalizes to empty returns 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "tag-test-invalid",
                "name": "Invalid Tag",
                "description": "Test invalid tag rejection.",
                **_BASE_IDEA,
            },
        )
        # "!!!" normalizes to empty string — should be rejected
        resp = await client.put(
            "/api/ideas/tag-test-invalid/tags",
            json={"tags": ["valid-tag", "!!!"]},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_idea_tags_catalog_returns_counts() -> None:
    """GET /api/ideas/tags returns a catalog of tags with idea counts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "catalog-a",
                "name": "Catalog A",
                "description": "First idea for catalog test.",
                "tags": ["governance", "ideas"],
                **_BASE_IDEA,
            },
        )
        await client.post(
            "/api/ideas",
            json={
                "id": "catalog-b",
                "name": "Catalog B",
                "description": "Second idea for catalog test.",
                "tags": ["ideas", "search"],
                **_BASE_IDEA,
            },
        )

        resp = await client.get("/api/ideas/tags")

    assert resp.status_code == 200
    data = resp.json()
    assert "tags" in data
    tag_map = {entry["tag"]: entry["idea_count"] for entry in data["tags"]}
    assert tag_map.get("ideas", 0) == 2
    assert tag_map.get("governance", 0) == 1
    assert tag_map.get("search", 0) == 1


@pytest.mark.asyncio
async def test_get_idea_tags_catalog_empty_when_no_tags() -> None:
    """GET /api/ideas/tags returns empty list when no tags exist."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/ideas/tags")
    assert resp.status_code == 200
    assert resp.json() == {"tags": []}


@pytest.mark.asyncio
async def test_list_ideas_no_tag_filter_returns_all() -> None:
    """GET /api/ideas without tags param returns all ideas (no regression)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "no-filter-a",
                "name": "No Filter A",
                "description": "Should appear in unfiltered list.",
                "tags": ["alpha"],
                **_BASE_IDEA,
            },
        )
        await client.post(
            "/api/ideas",
            json={
                "id": "no-filter-b",
                "name": "No Filter B",
                "description": "Also appears in unfiltered list.",
                **_BASE_IDEA,
            },
        )
        resp = await client.get("/api/ideas")

    assert resp.status_code == 200
    data = resp.json()
    returned_ids = {i["id"] for i in data["ideas"]}
    assert "no-filter-a" in returned_ids
    assert "no-filter-b" in returned_ids


@pytest.mark.asyncio
async def test_normalize_tags_unit() -> None:
    """Unit test: normalize_tags handles various edge cases correctly."""
    assert idea_service.normalize_tags([]) == []
    assert idea_service.normalize_tags(["  Ideas  ", "SEARCH", "governance", "ideas"]) == [
        "governance", "ideas", "search"
    ]
    assert idea_service.normalize_tags(["hello world"]) == ["hello-world"]
    assert idea_service.normalize_tags(["!!!", "   "]) == []
    assert idea_service.normalize_tags(["a", "A", "a"]) == ["a"]  # deduplicate
