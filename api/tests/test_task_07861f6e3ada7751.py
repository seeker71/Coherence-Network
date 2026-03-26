"""Acceptance tests for Web News Resonance Page task.

These tests validate the web-to-API contract used by `web/app/resonance/page.tsx`
for the News Feed section.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.routers import news as news_router


REPO_ROOT = Path(__file__).resolve().parents[2]
RESONANCE_PAGE_PATH = REPO_ROOT / "web" / "app" / "resonance" / "page.tsx"


class _FakeNewsItem:
    def __init__(self, payload: dict) -> None:
        self.source = payload["source"]
        self._payload = payload

    def to_dict(self) -> dict:
        return dict(self._payload)


def test_resonance_page_news_feed_fetch_contract() -> None:
    """Resonance page fetches the expected feed endpoint and shape."""
    content = RESONANCE_PAGE_PATH.read_text(encoding="utf-8")
    assert "/api/news/feed?limit=10" in content
    assert 'cache: "no-store"' in content
    assert "Array.isArray(data.items) ? data.items : []" in content


def test_resonance_page_news_section_render_contract() -> None:
    """News Feed section renders only with items and links safely."""
    content = RESONANCE_PAGE_PATH.read_text(encoding="utf-8")
    assert "newsItems.length > 0" in content
    assert "News Feed" in content
    assert "Latest headlines from across the network&rsquo;s sources." in content
    assert 'target="_blank"' in content
    assert 'rel="noopener noreferrer"' in content


@pytest.mark.asyncio
async def test_news_feed_api_returns_fields_resonance_page_renders(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/news/feed exposes title/source/url/published_at fields consumed by page."""
    payloads = [
        {
            "title": "Coherence milestone reached",
            "description": "Network update",
            "url": "https://example.com/news/1",
            "published_at": "2026-03-20T10:00:00Z",
            "source": "Example Source",
        },
        {
            "title": "Another update",
            "description": "Second entry",
            "url": "https://example.com/news/2",
            "published_at": None,
            "source": "Example Source 2",
        },
    ]

    async def _fake_fetch_feeds(*, force_refresh: bool = False):  # noqa: ARG001
        return [_FakeNewsItem(item) for item in payloads]

    monkeypatch.setattr(news_router.news_ingestion_service, "fetch_feeds", _fake_fetch_feeds)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/news/feed", params={"limit": 10})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert isinstance(body["items"], list)
    assert len(body["items"]) == 2

    required_fields = {"title", "description", "url", "published_at", "source"}
    for item in body["items"]:
        missing = required_fields - set(item.keys())
        assert not missing, f"News item missing fields consumed by resonance page: {missing}"
        assert isinstance(item["title"], str)
        assert isinstance(item["url"], str)
        assert isinstance(item["source"], str)


@pytest.mark.asyncio
async def test_news_feed_api_respects_limit_for_resonance_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GET /api/news/feed limit bounds item count used by page list rendering."""
    payloads = [
        {
            "title": f"Item {idx}",
            "description": "Desc",
            "url": f"https://example.com/news/{idx}",
            "published_at": "2026-03-20T10:00:00Z",
            "source": "Source",
        }
        for idx in range(5)
    ]

    async def _fake_fetch_feeds(*, force_refresh: bool = False):  # noqa: ARG001
        return [_FakeNewsItem(item) for item in payloads]

    monkeypatch.setattr(news_router.news_ingestion_service, "fetch_feeds", _fake_fetch_feeds)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/news/feed", params={"limit": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 3
    assert len(body["items"]) == 3
