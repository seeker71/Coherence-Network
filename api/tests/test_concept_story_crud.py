"""Flow-centric tests for concept story CRUD.

Tests the story update endpoint as a user would: HTTP requests in, JSON out.
Verifies story_content storage, auto-extraction of visuals from inline
markdown, and proper error handling.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _uid(prefix: str = "test-concept") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_concept(c: AsyncClient, concept_id: str | None = None) -> dict:
    """Helper: create a concept via the graph node endpoint."""
    cid = concept_id or _uid()
    payload = {
        "id": cid,
        "type": "concept",
        "name": f"Test {cid}",
        "description": f"Test concept {cid}",
        "properties": {"domains": ["living-collective"]},
    }
    r = await c.post("/api/graph/nodes", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Story CRUD (4 tests)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_story_stores_content():
    """PATCH /api/concepts/{id}/story stores story_content in properties."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = _uid()
        await _create_concept(c, cid)

        story = "## The Feeling\n\nThis is a test story about life."
        r = await c.patch(f"/api/concepts/{cid}/story", json={"story_content": story})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("story_content") == story


@pytest.mark.asyncio
async def test_patch_story_auto_extracts_visuals():
    """Visuals are auto-extracted from inline ![caption](visuals:prompt) entries."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = _uid()
        await _create_concept(c, cid)

        story = (
            "## The Feeling\n\n"
            "A warm morning.\n\n"
            "![Dawn over the valley](visuals:photorealistic dawn over green valley)\n\n"
            "The day begins.\n\n"
            "![People gathering](visuals:photorealistic group of people in circle)"
        )
        r = await c.patch(f"/api/concepts/{cid}/story", json={"story_content": story})
        assert r.status_code == 200, r.text
        body = r.json()
        visuals = body.get("visuals", [])
        assert len(visuals) == 2
        assert visuals[0]["caption"] == "Dawn over the valley"
        assert "valley" in visuals[0]["prompt"]
        assert visuals[1]["caption"] == "People gathering"


@pytest.mark.asyncio
async def test_get_concept_returns_updated_story():
    """GET /api/concepts/{id} reflects story_content after PATCH."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = _uid()
        await _create_concept(c, cid)

        story = "## What We're Building\n\nA place of warmth."
        await c.patch(f"/api/concepts/{cid}/story", json={"story_content": story})

        r = await c.get(f"/api/concepts/{cid}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("story_content") == story


@pytest.mark.asyncio
async def test_patch_story_404_for_unknown_concept():
    """PATCH /api/concepts/{unknown}/story returns 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.patch(
            "/api/concepts/nonexistent-concept/story",
            json={"story_content": "test"},
        )
        assert r.status_code == 404
