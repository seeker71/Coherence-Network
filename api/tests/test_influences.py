"""Flow-centric tests for the influence resolver and /api/influences.

The resolver is exercised through the FastAPI app. External HTTP is
patched: we never reach out to the real internet from tests.
"""
from __future__ import annotations

from uuid import uuid4
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import graph_service, influence_resolver_service as resolver

BASE = "http://test"

ARTIST_HTML = """
<html><head>
<meta property="og:site_name" content="Liquid Bloom">
<meta property="og:title" content="Liquid Bloom — Bandcamp">
<meta property="og:description" content="Downtempo and bass for ceremony.">
<meta property="og:image" content="https://example.com/lb.jpg">
<link rel="canonical" href="https://liquidbloom.bandcamp.com/">
<title>Liquid Bloom on Bandcamp</title>
</head><body></body></html>
"""

EVENT_HTML = """
<html><head>
<meta property="og:title" content="Unison Festival 2026">
<meta property="og:description" content="A field where music meets ceremony.">
<title>Unison Festival</title>
</head></html>
"""


def _fake_fetch(html: str, final_url: str):
    return lambda url: (final_url, html)


async def _create_source(c: AsyncClient, suffix: str = "") -> str:
    """Create a source contributor via /api/graph/nodes and return its id."""
    cid = f"contributor:test-source-{uuid4().hex[:8]}{suffix}"
    payload = {
        "id": cid,
        "type": "contributor",
        "name": cid.split(":", 1)[1],
        "description": "Test source contributor",
        "properties": {
            "contributor_type": "HUMAN",
            "email": f"{cid.split(':', 1)[1]}@test.local",
        },
    }
    r = await c.post("/api/graph/nodes", json=payload)
    assert r.status_code == 200, r.text
    return cid


@pytest.mark.asyncio
async def test_resolve_url_creates_node_and_edge():
    """Posting an artist URL fetches metadata, creates a contributor node
    keyed to its canonical URL, and links the source via inspired-by."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(resolver, "_fetch", _fake_fetch(ARTIST_HTML, "https://liquidbloom.bandcamp.com/")):
            r = await c.post("/api/influences", json={
                "input": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": source,
            })
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["node_created"] is True
        assert body["edge_existed"] is False
        node = body["node"]
        assert node["type"] == "contributor"
        assert node["name"] == "Liquid Bloom"
        assert node["canonical_url"] == "https://liquidbloom.bandcamp.com"
        assert node["provider"] == "bandcamp"
        assert node["claimable"] is True


@pytest.mark.asyncio
async def test_resolve_is_idempotent_on_canonical_url():
    """Re-importing the same URL reuses the node and reports edge_existed."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(resolver, "_fetch", _fake_fetch(ARTIST_HTML, "https://liquidbloom.bandcamp.com/")):
            first = await c.post("/api/influences", json={
                "input": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": source,
            })
            second = await c.post("/api/influences", json={
                "input": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": source,
            })
        assert first.status_code == 201
        assert second.status_code == 201
        assert second.json()["node_created"] is False
        assert second.json()["edge_existed"] is True
        # Same node id both times.
        assert first.json()["node"]["id"] == second.json()["node"]["id"]


@pytest.mark.asyncio
async def test_bare_name_uses_search_then_resolves_url():
    """A bare name routes through DuckDuckGo, then through the URL fetch path."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(resolver, "_ddg_first_result", lambda q: "https://eventbrite.com/e/unison-festival"), \
             patch.object(resolver, "_fetch", _fake_fetch(EVENT_HTML, "https://eventbrite.com/e/unison-festival")):
            r = await c.post("/api/influences", json={
                "input": "Unison Festival",
                "source_contributor_id": source,
            })
        assert r.status_code == 201, r.text
        node = r.json()["node"]
        assert node["type"] == "community"
        assert node["provider"] == "eventbrite"


@pytest.mark.asyncio
async def test_unresolvable_input_returns_422():
    """A name we cannot find anywhere is a soft failure (422), not a 500."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(resolver, "_ddg_first_result", lambda q: None):
            r = await c.post("/api/influences", json={
                "input": "definitely not a real influence xyz123",
                "source_contributor_id": source,
            })
        assert r.status_code == 422


@pytest.mark.asyncio
async def test_list_and_delete_influence_edge():
    """List returns the imported influence; delete removes the edge but
    leaves the node in place so it stays claimable."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        source = await _create_source(c)
        with patch.object(resolver, "_fetch", _fake_fetch(ARTIST_HTML, "https://liquidbloom.bandcamp.com/")):
            created = await c.post("/api/influences", json={
                "input": "https://liquidbloom.bandcamp.com",
                "source_contributor_id": source,
            })
        node_id = created.json()["node"]["id"]

        listed = await c.get(f"/api/influences?contributor_id={source}")
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert len(items) == 1
        edge_id = items[0]["edge_id"]
        assert items[0]["node"]["id"] == node_id

        deleted = await c.delete(f"/api/influences/{edge_id}")
        assert deleted.status_code == 200

        # Node still exists, edge gone.
        relisted = await c.get(f"/api/influences?contributor_id={source}")
        assert relisted.json()["count"] == 0
        assert graph_service.get_node(node_id) is not None
