from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import idea_service

AUTH_HEADERS = {"X-API-Key": "dev-key"}


@pytest.mark.asyncio
async def test_create_idea_normalizes_and_returns_tags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'ideas.db'}")
    idea_service._invalidate_ideas_cache()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/ideas",
            json={
                "id": "idea-tagging-system",
                "name": "Idea tagging system",
                "description": "Tag normalization contract",
                "potential_value": 50.0,
                "estimated_cost": 10.0,
                "tags": ["Ideas", "search", "  governance  ", "ideas"],
            },
            headers=AUTH_HEADERS,
        )
        assert created.status_code == 201
        payload = created.json()
        assert payload["tags"] == ["governance", "ideas", "search"]

        fetched = await client.get("/api/ideas/idea-tagging-system")
        assert fetched.status_code == 200
        assert fetched.json()["tags"] == ["governance", "ideas", "search"]


@pytest.mark.asyncio
async def test_list_ideas_filters_by_all_requested_tags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'ideas.db'}")
    idea_service._invalidate_ideas_cache()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "idea-a",
                "name": "Idea A",
                "description": "Has both tags",
                "potential_value": 20.0,
                "estimated_cost": 5.0,
                "tags": ["ideas", "search"],
            },
            headers=AUTH_HEADERS,
        )
        await client.post(
            "/api/ideas",
            json={
                "id": "idea-b",
                "name": "Idea B",
                "description": "Missing one tag",
                "potential_value": 20.0,
                "estimated_cost": 5.0,
                "tags": ["ideas"],
            },
            headers=AUTH_HEADERS,
        )
        filtered = await client.get("/api/ideas?tags=ideas,search")
        assert filtered.status_code == 200
        ids = [row["id"] for row in filtered.json()["ideas"]]
        assert "idea-a" in ids
        assert "idea-b" not in ids


@pytest.mark.asyncio
async def test_put_idea_tags_replaces_existing_tags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'ideas.db'}")
    idea_service._invalidate_ideas_cache()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        created = await client.post(
            "/api/ideas",
            json={
                "id": "idea-update-tags",
                "name": "Idea Update Tags",
                "description": "Tag replacement",
                "potential_value": 30.0,
                "estimated_cost": 10.0,
                "tags": ["legacy"],
            },
            headers=AUTH_HEADERS,
        )
        assert created.status_code == 201

        replaced = await client.put(
            "/api/ideas/idea-update-tags/tags",
            json={"tags": [" Ideas ", "delivery", "ideas"]},
            headers=AUTH_HEADERS,
        )
        assert replaced.status_code == 200
        assert replaced.json() == {"id": "idea-update-tags", "tags": ["delivery", "ideas"]}

        fetched = await client.get("/api/ideas/idea-update-tags")
        assert fetched.status_code == 200
        assert fetched.json()["tags"] == ["delivery", "ideas"]


@pytest.mark.asyncio
async def test_get_idea_tags_catalog_returns_counts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("IDEA_PORTFOLIO_PATH", str(tmp_path / "idea_portfolio.json"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'ideas.db'}")
    idea_service._invalidate_ideas_cache()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/ideas",
            json={
                "id": "catalog-1",
                "name": "Catalog 1",
                "description": "Catalog baseline",
                "potential_value": 12.0,
                "estimated_cost": 4.0,
                "tags": ["ideas", "search"],
            },
            headers=AUTH_HEADERS,
        )
        await client.post(
            "/api/ideas",
            json={
                "id": "catalog-2",
                "name": "Catalog 2",
                "description": "Catalog secondary",
                "potential_value": 12.0,
                "estimated_cost": 4.0,
                "tags": ["ideas", "governance"],
            },
            headers=AUTH_HEADERS,
        )

        catalog = await client.get("/api/ideas/tags")
        assert catalog.status_code == 200
        assert catalog.json()["tags"] == [
            {"tag": "governance", "idea_count": 1},
            {"tag": "ideas", "idea_count": 2},
            {"tag": "search", "idea_count": 1},
        ]
