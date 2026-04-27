"""Flow test for on-demand attunement.

When a view is missing for the target lang and a translator backend is
registered, the GET endpoint enqueues a background attunement. The current
request serves the anchor with pending_translation=true. A moment later, the
attunement has written a canonical view, and the next request serves it.

Uses a stub backend (no LLM call) so the test is fast and deterministic.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import translator_service, translation_cache_service as _tcache


class _StubBackend:
    """Deterministic attunement: prepends a lang marker to each field."""

    calls: list[dict] = []

    def attune(
        self,
        *,
        source_markdown: str,
        source_title: str,
        source_description: str,
        source_lang: str,
        target_lang: str,
        glossary_prompt: str,
    ) -> tuple[str, str, str]:
        _StubBackend.calls.append({
            "source_lang": source_lang,
            "target_lang": target_lang,
            "glossary_prompt": glossary_prompt,
        })
        marker = f"[{target_lang}] "
        return (marker + source_title, marker + source_description, marker + source_markdown)


@pytest.fixture
def stub_backend():
    """Register the stub backend for the duration of a test."""
    _StubBackend.calls = []
    translator_service.set_backend(_StubBackend())
    yield _StubBackend
    translator_service.set_backend(None)


async def _create_concept(c: AsyncClient) -> str:
    cid = f"on-demand-{uuid4().hex[:6]}"
    await c.post("/api/graph/nodes", json={
        "id": cid,
        "type": "concept",
        "name": f"Test {cid}",
        "description": "A test concept",
        "properties": {"domains": ["living-collective"]},
    })
    return cid


@pytest.mark.asyncio
async def test_missing_view_enqueues_attunement(stub_backend):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        cid = await _create_concept(c)
        # Seed an English view so an anchor exists
        await c.post(f"/api/concepts/{cid}/views", json={
            "lang": "en",
            "content_title": "Anchor Title",
            "content_description": "Anchor description",
            "content_markdown": "# Anchor\n\nAnchor body.",
            "author_type": "original_human",
        })

        # First request for German: no view yet; should serve pending anchor
        # and enqueue a background attunement
        r = await c.get(f"/api/concepts/{cid}?lang=de")
        assert r.status_code == 200
        body = r.json()
        assert body["language_meta"]["lang"] == "de"
        # Either pending is true (no de view) or the background task ran already
        # and set the view. Assert at least that the backend will be / has been called.

    # Give the background task a moment to run
    for _ in range(40):
        if any(c["target_lang"] == "de" for c in stub_backend.calls):
            break
        await asyncio.sleep(0.05)
    assert any(c["target_lang"] == "de" for c in stub_backend.calls), \
        "expected background attunement to run for de"

    # Now the de view should exist
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r2 = await c.get(f"/api/concepts/{cid}?lang=de")
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["language_meta"]["pending"] is False
        assert body2["name"].startswith("[de] ")
        assert body2["story_content"].startswith("[de] ")


@pytest.mark.asyncio
async def test_no_views_creates_anchor_and_returns_attuned_content(stub_backend):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        cid = await _create_concept(c)
        await c.patch(f"/api/concepts/{cid}/story", json={"story_content": "# Anchor\n\nAnchor body."})

        r = await c.get(f"/api/concepts/{cid}?lang=de")
        assert r.status_code == 200
        body = r.json()
        assert body["language_meta"]["lang"] == "de"
        assert body["language_meta"]["pending"] is False
        assert body["name"].startswith("[de] ")
        assert body["story_content"].startswith("[de] ")

        rows = _tcache.all_canonical_views("concept", cid)
        assert {v.lang for v in rows} == {"en", "de"}


@pytest.mark.asyncio
async def test_attunement_carries_glossary(stub_backend):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        cid = await _create_concept(c)
        # Seed a glossary entry
        await c.patch("/api/glossary/de", json={"entries": [
            {"source_term": "tending", "target_term": "hüten", "notes": "Schäferin"},
        ]})
        # Seed an anchor
        await c.post(f"/api/concepts/{cid}/views", json={
            "lang": "en",
            "content_title": "Nourishing",
            "content_description": "Everything that sustains.",
            "content_markdown": "# Nourishing\n\nTending circulates.",
            "author_type": "original_human",
        })
        # Trigger background attunement
        await c.get(f"/api/concepts/{cid}?lang=de")

    # Wait for attunement
    for _ in range(40):
        if any(c["target_lang"] == "de" for c in stub_backend.calls):
            break
        await asyncio.sleep(0.05)

    assert stub_backend.calls, "expected backend to have been invoked"
    call = next(c for c in stub_backend.calls if c["target_lang"] == "de")
    assert "tending" in call["glossary_prompt"]
    assert "hüten" in call["glossary_prompt"]


@pytest.mark.asyncio
async def test_no_backend_no_attunement():
    """With no backend registered, pending views serve anchor and never call anything."""
    translator_service.set_backend(None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        cid = await _create_concept(c)
        await c.post(f"/api/concepts/{cid}/views", json={
            "lang": "en",
            "content_title": "Anchor",
            "content_description": "Anchor desc",
            "content_markdown": "Anchor body",
            "author_type": "original_human",
        })
        r = await c.get(f"/api/concepts/{cid}?lang=de")
        assert r.status_code == 200
        assert r.json()["language_meta"]["pending"] is True
        assert r.json()["story_content"] is None
        # No view was written
        rows = _tcache.all_canonical_views("concept", cid)
        assert all(v.lang != "de" for v in rows)


@pytest.mark.asyncio
async def test_pending_view_uses_title_glossary_without_story():
    """Pending non-English views should not expose English hero title/story."""
    translator_service.set_backend(None)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        cid = f"pending-pulse-{uuid4().hex[:6]}"
        await c.post("/api/graph/nodes", json={
            "id": cid,
            "type": "concept",
            "name": "The Pulse",
            "description": "One truth.",
            "properties": {"domains": ["living-collective"]},
        })
        await c.post(f"/api/concepts/{cid}/views", json={
            "lang": "en",
            "content_title": "The Pulse",
            "content_description": "One truth.",
            "content_markdown": "Close your eyes.",
            "author_type": "original_human",
        })
        r = await c.get(f"/api/concepts/{cid}?lang=de")
        assert r.status_code == 200
        body = r.json()
        assert body["language_meta"]["pending"] is True
        assert body["name"] == "Der Puls"
        assert body["story_content"] is None
