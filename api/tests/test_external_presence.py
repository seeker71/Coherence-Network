"""Acceptance tests for spec: external-presence-bots-and-news (idea: external-presence).

Covers done_when criteria:
  - GET /api/news/feed returns cached news items
  - GET /api/news/resonance matches news to ideas with scores
  - POST /api/news/sources adds configurable feed
  - GET /api/news/sources returns list
"""

from __future__ import annotations

from uuid import uuid4
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app import config_loader
from app.main import app
from app.services import news_ingestion_service

AUTH = {"X-API-Key": "dev-key"}
BASE = "http://test"


def _uid(prefix: str = "ep") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# 1. GET /api/news/feed returns items (may be empty list)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_news_feed_returns_items():
    """News feed endpoint returns a count and items list."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/news/feed", params={"limit": 10})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "count" in body
        assert isinstance(body["items"], list)
        assert body["count"] == len(body["items"])


# ---------------------------------------------------------------------------
# 2. GET /api/news/sources returns list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_news_sources_returns_list():
    """News sources endpoint returns count and sources array."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/news/sources")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "count" in body
        assert isinstance(body["sources"], list)


def test_news_sources_load_from_config_path(tmp_path):
    """News source data lives in configured JSON, not hidden service defaults."""
    source_path = tmp_path / "news_sources.json"
    source_path.write_text(
        json.dumps([
            {
                "id": "configured-feed",
                "name": "Configured Feed",
                "type": "rss",
                "url": "https://example.com/feed.xml",
                "is_active": True,
            }
        ]),
        encoding="utf-8",
    )
    config_loader.set_config_value("news", "sources_path", str(source_path))

    loaded = news_ingestion_service._load_sources()

    assert [row["id"] for row in loaded] == ["configured-feed"]


def test_news_default_source_config_is_packaged_with_api():
    """Default relative source path resolves inside api/config for deployment."""
    config_loader.set_config_value("news", "sources_path", "config/news-sources.json")

    path = news_ingestion_service._config_path()

    assert path.name == "news-sources.json"
    assert path.parent.name == "config"
    assert path.parent.parent.name == "api"
    assert path.exists()


def test_missing_news_sources_config_returns_empty_list(tmp_path):
    """Missing source config should be visible as empty, not a hard-coded feed list."""
    config_loader.set_config_value("news", "sources_path", str(tmp_path / "missing.json"))

    assert news_ingestion_service._load_sources() == []


# ---------------------------------------------------------------------------
# 3. POST /api/news/sources adds configurable feed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_add_news_source():
    """Adding a news source via POST persists and appears in list."""
    source_id = _uid("src")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.post(
            "/api/news/sources",
            json={
                "id": source_id,
                "name": f"Test Feed {source_id}",
                "type": "rss",
                "url": f"https://example.com/feed/{source_id}.xml",
                "categories": ["tech"],
                "is_active": True,
            },
            headers=AUTH,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["id"] == source_id

        # Verify it appears in the list
        r2 = await c.get("/api/news/sources")
        assert r2.status_code == 200
        source_ids = [s["id"] for s in r2.json()["sources"]]
        assert source_id in source_ids


# ---------------------------------------------------------------------------
# 4. GET /api/news/resonance returns structure
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_news_resonance_returns_structure():
    """News resonance endpoint returns news_count, idea_count, and results."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/news/resonance", params={"top_n": 3, "limit": 10})
        assert r.status_code == 200, r.text
        body = r.json()
        assert "news_count" in body
        assert "idea_count" in body
        assert isinstance(body["results"], list)


# ---------------------------------------------------------------------------
# 5. GET /api/news/sources/{source_id} returns a single source
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_single_news_source():
    """Retrieving a source by ID returns the correct record."""
    source_id = _uid("single")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Create it
        await c.post(
            "/api/news/sources",
            json={
                "id": source_id,
                "name": f"Single {source_id}",
                "type": "rss",
                "url": f"https://example.com/{source_id}.xml",
            },
            headers=AUTH,
        )

        r = await c.get(f"/api/news/sources/{source_id}")
        assert r.status_code == 200, r.text
        assert r.json()["id"] == source_id


@pytest.mark.asyncio
async def test_get_nonexistent_source_returns_404():
    """Requesting a non-existent source returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/news/sources/does-not-exist-zzz")
        assert r.status_code == 404
