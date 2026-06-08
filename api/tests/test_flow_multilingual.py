"""Flow-centric tests for the multilingual platform.

One file covers the whole content-in-any-voice flow:

1. View CRUD, anchor discovery, staleness (language views as first-class
   records; anchor is the freshest human-touched view; stale views emerge
   from hash mismatches, not hardcoded "source is English" rules).
2. On-demand attunement (when a view is missing and a backend is registered,
   the endpoint enqueues background attunement; the current request still
   serves the anchor).
3. LibreTranslate backend glossary post-substitution (free, no key; carries
   frequency anchors like tending→hüten even though LibreTranslate isn't
   prompt-aware).

Covers the full flow a German-speaking visitor walks from first visit to
human-translated view. Uses stub backends to stay fast and deterministic.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import (
    translation_cache_service as _cache,
    translator_service,
)
from app.services.translator_backends import (
    LibreTranslateBackend,
    _apply_glossary,
    register_default_backend,
)

BASE = "http://test"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _installed_locale_codes() -> set[str]:
    return {
        path.stem
        for path in (REPO_ROOT / "web" / "messages").glob("*.json")
        if path.stem
    }


def _uid(prefix: str = "view-test") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


async def _create_concept(c: AsyncClient, suffix: str = "view-test") -> str:
    cid = _uid(suffix)
    payload = {
        "id": cid,
        "type": "concept",
        "name": f"Test {cid}",
        "description": "A test concept",
        "properties": {"domains": ["living-collective"]},
    }
    r = await c.post("/api/graph/nodes", json=payload)
    assert r.status_code == 200, r.text
    return cid


async def _post_view(c: AsyncClient, cid: str, **body) -> dict:
    r = await c.post(f"/api/concepts/{cid}/views", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Locale listing + glossary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_locales_matches_installed_message_bundles():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/locales")
        assert r.status_code == 200
        codes = {loc["code"] for loc in r.json()["locales"]}
        assert _installed_locale_codes().issubset(codes)
        assert r.json()["default"] == "en"


@pytest.mark.asyncio
async def test_glossary_upsert_and_read():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.patch(
            "/api/glossary/de",
            json={"entries": [
                {"source_term": "tending", "target_term": "hüten", "notes": "Schäferin-Frequenz"},
                {"source_term": "ripening", "target_term": "reifen", "notes": None},
            ]},
        )
        assert r.status_code == 200
        assert r.json()["upserted"] == 2

        r = await c.get("/api/glossary/de")
        assert r.status_code == 200
        entries = {e["source_term"]: e["target_term"] for e in r.json()["entries"]}
        assert entries["tending"] == "hüten"
        assert entries["ripening"] == "reifen"


@pytest.mark.asyncio
async def test_glossary_rejects_unsupported_locale():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.patch(
            "/api/glossary/zz",
            json={"entries": [{"source_term": "x", "target_term": "y"}]},
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# View CRUD, anchor discovery, staleness
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concept_with_only_original_view_is_anchor():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c)

        await _post_view(
            c, cid,
            lang="en",
            content_title="Nourishing",
            content_description="Everything that sustains circulates.",
            content_markdown="# Nourishing\n\nA living story...",
            author_type="original_human",
        )

        r = await c.get(f"/api/concepts/{cid}?lang=en")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == "Nourishing"
        meta = body["language_meta"]
        assert meta["is_anchor"] is True
        assert meta["stale"] is False
        assert meta["anchor"]["lang"] == "en"


@pytest.mark.asyncio
async def test_human_translation_references_source_hash_and_is_fresh():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c)

        en_resp = await _post_view(
            c, cid,
            lang="en",
            content_title="Nourishing",
            content_description="EN desc",
            content_markdown="# Nourishing\n\nEN body",
            author_type="original_human",
        )
        en_hash = en_resp["content_hash"]

        await _post_view(
            c, cid,
            lang="de",
            content_title="Nährend",
            content_description="DE Beschreibung",
            content_markdown="# Nährend\n\nDE Text",
            author_type="translation_human",
            translated_from_lang="en",
            translated_from_hash=en_hash,
        )

        r = await c.get(f"/api/concepts/{cid}?lang=de")
        meta = r.json()["language_meta"]
        assert r.json()["name"] == "Nährend"
        assert meta["lang"] == "de"
        assert meta["stale"] is False


@pytest.mark.asyncio
async def test_editing_anchor_stales_attuned_views():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c)

        en1 = await _post_view(
            c, cid,
            lang="en",
            content_title="Nourishing",
            content_description="EN v1",
            content_markdown="# Nourishing\n\nEN v1 body",
            author_type="original_human",
        )
        await _post_view(
            c, cid,
            lang="de",
            content_title="Nährend",
            content_description="DE v1",
            content_markdown="# Nährend\n\nDE v1 text",
            author_type="translation_human",
            translated_from_lang="en",
            translated_from_hash=en1["content_hash"],
        )

        await _post_view(
            c, cid,
            lang="en",
            content_title="Nourishing",
            content_description="EN v2 (deeper)",
            content_markdown="# Nourishing\n\nEN v2 body with new paragraph",
            author_type="original_human",
        )

        r = await c.get(f"/api/concepts/{cid}/views")
        views = {v["lang"]: v for v in r.json()["views"]}
        assert views["en"]["is_anchor"] is True
        assert views["en"]["stale"] is False
        assert views["de"]["stale"] is True


@pytest.mark.asyncio
async def test_anchor_moves_to_edited_language():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c)

        await _post_view(
            c, cid,
            lang="en",
            content_title="Nourishing",
            content_description="EN",
            content_markdown="EN body",
            author_type="original_human",
        )
        await _post_view(
            c, cid,
            lang="de",
            content_title="Nährend (neu)",
            content_description="DE neu",
            content_markdown="DE frisch geschrieben",
            author_type="original_human",
        )

        r = await c.get(f"/api/concepts/{cid}/views")
        body = r.json()
        assert body["anchor_lang"] == "de"
        views = {v["lang"]: v for v in body["views"]}
        assert views["de"]["is_anchor"] is True
        assert views["en"]["is_anchor"] is False


@pytest.mark.asyncio
async def test_pending_when_no_view_exists_for_requested_lang():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c)
        await _post_view(
            c, cid,
            lang="en",
            content_title="Nourishing",
            content_description="EN",
            content_markdown="EN body",
            author_type="original_human",
        )
        r = await c.get(f"/api/concepts/{cid}?lang=es")
        meta = r.json()["language_meta"]
        assert meta["lang"] == "es"
        assert meta["pending"] is True


@pytest.mark.asyncio
async def test_view_upsert_requires_translation_origin_metadata():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c)
        r = await c.post(
            f"/api/concepts/{cid}/views",
            json={
                "lang": "de",
                "content_title": "x",
                "content_description": "y",
                "content_markdown": "z",
                "author_type": "translation_human",
                # missing translated_from_lang/hash
            },
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_history_preserves_superseded_views():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c)
        await _post_view(
            c, cid,
            lang="en",
            content_title="v1 title",
            content_description="v1 desc",
            content_markdown="v1 body",
            author_type="original_human",
        )
        await _post_view(
            c, cid,
            lang="en",
            content_title="v2 title",
            content_description="v2 desc",
            content_markdown="v2 body",
            author_type="original_human",
        )
        r = await c.get(f"/api/concepts/{cid}/views/en/history")
        views = r.json()["views"]
        assert len(views) == 2
        statuses = [v["status"] for v in views]
        assert statuses[0] == "canonical"
        assert statuses[1] == "superseded"


# ---------------------------------------------------------------------------
# On-demand attunement (stub backend)
# ---------------------------------------------------------------------------

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


@pytest.mark.asyncio
async def test_missing_view_enqueues_attunement(stub_backend):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c, "on-demand")
        await c.post(f"/api/concepts/{cid}/views", json={
            "lang": "en",
            "content_title": "Anchor Title",
            "content_description": "Anchor description",
            "content_markdown": "# Anchor\n\nAnchor body.",
            "author_type": "original_human",
        })
        r = await c.get(f"/api/concepts/{cid}?lang=de")
        assert r.status_code == 200
        body = r.json()
        assert body["language_meta"]["lang"] == "de"

    for _ in range(40):
        if any(c["target_lang"] == "de" for c in stub_backend.calls):
            break
        await asyncio.sleep(0.05)
    assert any(c["target_lang"] == "de" for c in stub_backend.calls), \
        "expected background attunement to run for de"

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r2 = await c.get(f"/api/concepts/{cid}?lang=de")
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["language_meta"]["pending"] is False
        assert body2["name"].startswith("[de] ")
        assert body2["story_content"].startswith("[de] ")


@pytest.mark.asyncio
async def test_attunement_carries_glossary(stub_backend):
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c, "glossary-attune")
        await c.patch("/api/glossary/de", json={"entries": [
            {"source_term": "tending", "target_term": "hüten", "notes": "Schäferin"},
        ]})
        await c.post(f"/api/concepts/{cid}/views", json={
            "lang": "en",
            "content_title": "Nourishing",
            "content_description": "Everything that sustains.",
            "content_markdown": "# Nourishing\n\nTending circulates.",
            "author_type": "original_human",
        })
        await c.get(f"/api/concepts/{cid}?lang=de")

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
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c, "no-backend")
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
        rows = _cache.all_canonical_views("concept", cid)
        assert all(v.lang != "de" for v in rows)


# ---------------------------------------------------------------------------
# LibreTranslate backend (free, no key) + glossary post-substitution
# ---------------------------------------------------------------------------

def _mock_translate_response(text: str):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"translatedText": text})
    return resp


def test_libretranslate_translates_plain_text():
    backend = LibreTranslateBackend(base_url="http://stub")
    with patch("httpx.Client") as ClientCls:
        client = MagicMock()
        client.post = MagicMock(return_value=_mock_translate_response("Hallo Welt"))
        ClientCls.return_value.__enter__ = MagicMock(return_value=client)
        ClientCls.return_value.__exit__ = MagicMock(return_value=False)
        title, desc, md = backend.attune(
            source_markdown="Hello world",
            source_title="Hello",
            source_description="Hello friend",
            source_lang="en",
            target_lang="de",
            glossary_prompt="",
        )
        assert "Hallo" in title
        assert client.post.called


def test_glossary_post_substitutes_anchor_terms():
    """Glossary tending→hüten + ripening→reifen appear in the output."""
    glossary = [("tending", "hüten"), ("ripening", "reifen")]
    out = _apply_glossary("The practice is tending and ripening.", glossary)
    assert "hüten" in out
    assert "reifen" in out


def test_glossary_preserves_code_fences_and_urls():
    glossary = [("tending", "hüten")]
    raw = "Read tending at `tending.md` or https://example.com/tending for details."
    out = _apply_glossary(raw, glossary)
    assert "`tending.md`" in out
    assert "https://example.com/tending" in out
    assert "Read hüten at" in out


def test_glossary_word_boundary_case_insensitive():
    """Substitution matches whole words only, case-insensitive — 'Pretending' doesn't match 'tending'."""
    glossary = [("tending", "hüten")]
    raw = "Tending is tending. Pretending? No."
    out = _apply_glossary(raw, glossary)
    assert "hüten" in out.lower()
    assert "Pretending" in out or "pretending" in out.lower()


def test_glossary_preserves_image_syntax():
    glossary = [("tending", "hüten")]
    raw = "See ![the tending](visuals:tending prompt) and tending."
    out = _apply_glossary(raw, glossary)
    assert "visuals:tending prompt" in out
    assert "hüten" in out


# ---------------------------------------------------------------------------
# Localized API error messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concept_not_found_localized_via_query_lang():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/concepts/does-not-exist?lang=de")
        assert r.status_code == 404
        # German message for concept_not_found
        assert "Begriff 'does-not-exist' nicht gefunden" in r.json()["detail"]


@pytest.mark.asyncio
async def test_concept_not_found_localized_via_accept_language():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get(
            "/api/concepts/does-not-exist",
            headers={"accept-language": "es-ES,es;q=0.9,en;q=0.8"},
        )
        assert r.status_code == 404
        assert "no encontrado" in r.json()["detail"]


@pytest.mark.asyncio
async def test_unsupported_locale_localized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c, "bad-lang")
        r = await c.post(
            f"/api/concepts/{cid}/views",
            json={
                "lang": "zz",
                "content_title": "x",
                "author_type": "original_human",
            },
        )
        assert r.status_code == 400
        # Without Accept-Language, default is English
        assert "Unsupported locale 'zz'" in r.json()["detail"]


@pytest.mark.asyncio
async def test_spec_list_honors_lang():
    """The spec-registry list endpoint substitutes title/summary from spec views."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Create a spec entry directly
        spec_id = f"test-spec-{uuid4().hex[:6]}"
        r = await c.post(
            "/api/spec-registry",
            json={
                "spec_id": spec_id,
                "title": "English Spec Title",
                "summary": "English spec summary",
            },
            headers={"X-API-Key": "dev-key"},
        )
        assert r.status_code == 201, r.text

        # Write a German view for it via the generic entity-views endpoint
        r = await c.post(
            f"/api/entity-views/spec/{spec_id}",
            json={
                "lang": "de",
                "content_title": "Deutscher Entwurfs-Titel",
                "content_description": "Deutsche Zusammenfassung",
                "author_type": "original_human",
            },
        )
        assert r.status_code == 200, r.text

        # Listing with ?lang=de should substitute
        r = await c.get("/api/spec-registry?lang=de")
        assert r.status_code == 200
        by_id = {s["spec_id"]: s for s in r.json() if s["spec_id"] == spec_id}
        assert spec_id in by_id
        assert by_id[spec_id]["title"] == "Deutscher Entwurfs-Titel"


def test_register_default_prefers_libretranslate_without_key(monkeypatch):
    """With no COHERENCE_TRANSLATOR set and no anthropic key, installs LibreTranslate."""
    translator_service.set_backend(None)
    monkeypatch.delenv("COHERENCE_TRANSLATOR", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with patch("app.services.translator_backends._read_keystore_key", return_value=None):
        name = register_default_backend()
    assert name == "libretranslate"
    assert translator_service.has_backend() is True


# ---------------------------------------------------------------------------
# Caller locale flows through every text-returning surface
# ---------------------------------------------------------------------------

class _StubSnippetBackend:
    """Deterministic snippet backend for testing news/discovery on-demand flow.

    Returns `[{lang}] {text}` so tests can assert the locale arrived at the
    backend without depending on a network translator.
    """

    def attune(self, *, source_markdown, source_title, source_description,
               source_lang, target_lang, glossary_prompt):
        def stamp(s: str) -> str:
            return f"[{target_lang}] {s}" if s else s
        return stamp(source_title), stamp(source_description), stamp(source_markdown)


@pytest.mark.asyncio
async def test_ideas_list_honors_accept_language_header(monkeypatch):
    """/api/ideas picks up `Accept-Language` even when ?lang= is absent."""
    from app.services import translator_service as _tsvc
    prev = _tsvc._BACKEND
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
            # Seed an idea
            idea_id = f"view-idea-{uuid4().hex[:6]}"
            r = await c.post(
                "/api/ideas",
                json={
                    "id": idea_id,
                    "name": "Tending the garden",
                    "description": "Practice of attending to a living field.",
                    "potential_value": 1.0,
                    "estimated_cost": 1.0,
                },
                headers={"X-API-Key": "dev-key"},
            )
            assert r.status_code in (200, 201), r.text

            # Write a German view
            r = await c.post(
                f"/api/entity-views/idea/{idea_id}",
                json={
                    "lang": "de",
                    "content_title": "Den Garten hüten",
                    "content_description": "Praxis des Hütens eines lebendigen Feldes.",
                    "author_type": "original_human",
                },
            )
            assert r.status_code == 200

            # Accept-Language only — no ?lang=
            r = await c.get(
                "/api/ideas",
                headers={"accept-language": "de-DE,de;q=0.9"},
            )
            assert r.status_code == 200
            ideas = {i["id"]: i for i in r.json()["ideas"]}
            assert idea_id in ideas
            assert ideas[idea_id]["name"] == "Den Garten hüten"
    finally:
        _tsvc.set_backend(prev)


@pytest.mark.asyncio
async def test_spec_list_honors_accept_language_header():
    """/api/spec-registry picks up `Accept-Language` without ?lang=."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        spec_id = f"view-spec-{uuid4().hex[:6]}"
        r = await c.post(
            "/api/spec-registry",
            json={"spec_id": spec_id, "title": "Feature X", "summary": "Does X."},
            headers={"X-API-Key": "dev-key"},
        )
        assert r.status_code == 201
        r = await c.post(
            f"/api/entity-views/spec/{spec_id}",
            json={
                "lang": "es",
                "content_title": "Característica X",
                "content_description": "Hace X.",
                "author_type": "original_human",
            },
        )
        assert r.status_code == 200
        r = await c.get(
            "/api/spec-registry",
            headers={"accept-language": "es"},
        )
        assert r.status_code == 200
        matches = [s for s in r.json() if s["spec_id"] == spec_id]
        assert matches, f"spec {spec_id} missing from list"
        assert matches[0]["title"] == "Característica X"


@pytest.mark.asyncio
async def test_concepts_domain_list_honors_accept_language_header():
    """/api/concepts/domain/{domain} picks up `Accept-Language` without ?lang=."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        cid = await _create_concept(c, "domain-accept-lang")
        await _post_view(
            c, cid,
            lang="en",
            content_title="Nourishing",
            content_description="Everything that sustains circulates.",
            content_markdown="# Nourishing\n\nbody",
            author_type="original_human",
        )
        r = await c.post(
            f"/api/entity-views/concept/{cid}",
            json={
                "lang": "de",
                "content_title": "Nährend",
                "content_description": "Alles, was erhält, zirkuliert.",
                "author_type": "original_human",
            },
        )
        assert r.status_code == 200
        r = await c.get(
            "/api/concepts/domain/living-collective",
            headers={"accept-language": "de"},
        )
        assert r.status_code == 200
        items = r.json().get("items") or r.json().get("concepts") or []
        hits = [c for c in items if c.get("id") == cid]
        assert hits, f"concept {cid} not in domain list"
        assert hits[0]["name"] == "Nährend"


@pytest.mark.asyncio
async def test_news_feed_translates_snippets_on_demand(monkeypatch):
    """/api/news/feed runs titles/descriptions through the snippet backend."""
    import app.services.translator_service as _tsvc
    prev = _tsvc._BACKEND
    _tsvc.set_backend(_StubSnippetBackend())
    _tsvc._SNIPPET_CACHE.clear()
    # Stub fetch_feeds to return a deterministic item
    from app.services import news_ingestion_service
    from app.services.news_ingestion_service import NewsItem

    async def _fake_fetch(*_args, **_kwargs):
        return [
            NewsItem(
                title="A gentle rain",
                description="The river breathes.",
                url="https://example.com/rain",
                published_at="2026-04-16T00:00:00Z",
                source="Example",
            ),
        ]

    monkeypatch.setattr(news_ingestion_service, "fetch_feeds", _fake_fetch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
            r = await c.get("/api/news/feed", headers={"accept-language": "de"})
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["lang"] == "de"
            assert body["items"][0]["title"].startswith("[de] ")
            assert body["items"][0]["description"].startswith("[de] ")
    finally:
        _tsvc.set_backend(prev)
        _tsvc._SNIPPET_CACHE.clear()


@pytest.mark.asyncio
async def test_news_feed_english_returns_raw_titles(monkeypatch):
    """English callers get RSS items untouched — no pointless round trip."""
    import app.services.translator_service as _tsvc
    prev = _tsvc._BACKEND
    _tsvc.set_backend(_StubSnippetBackend())
    from app.services import news_ingestion_service
    from app.services.news_ingestion_service import NewsItem

    async def _fake_fetch(*_args, **_kwargs):
        return [NewsItem(title="A gentle rain", description="The river breathes.",
                         url="https://example.com/rain", published_at=None, source="X")]

    monkeypatch.setattr(news_ingestion_service, "fetch_feeds", _fake_fetch)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
            r = await c.get("/api/news/feed")
            assert r.status_code == 200
            assert r.json()["items"][0]["title"] == "A gentle rain"
    finally:
        _tsvc.set_backend(prev)


@pytest.mark.asyncio
async def test_translate_snippet_memoizes_backend_calls(monkeypatch):
    """Same snippet + target_lang should hit the backend once, not twice."""
    import app.services.translator_service as _tsvc
    prev = _tsvc._BACKEND
    calls = {"n": 0}

    class _CountingBackend:
        def attune(self, *, source_markdown, source_title, source_description,
                   source_lang, target_lang, glossary_prompt):
            calls["n"] += 1
            return f"T({source_title})", f"T({source_description})", source_markdown

    _tsvc.set_backend(_CountingBackend())
    _tsvc._SNIPPET_CACHE.clear()
    try:
        _tsvc.translate_snippet("hello", "world", source_lang="en", target_lang="de")
        _tsvc.translate_snippet("hello", "world", source_lang="en", target_lang="de")
        assert calls["n"] == 1
    finally:
        _tsvc.set_backend(prev)
        _tsvc._SNIPPET_CACHE.clear()


@pytest.mark.asyncio
async def test_resonance_cross_domain_substitutes_idea_names():
    """/api/resonance/cross-domain renders idea names in the caller's locale."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # The endpoint reads whatever pairs are cached — just verify it accepts
        # lang and passes it through without error. We can't cheaply seed a
        # structural pair here, so we assert the envelope and that the endpoint
        # doesn't 500 on Accept-Language paths.
        r = await c.get(
            "/api/resonance/cross-domain?limit=1",
            headers={"accept-language": "de"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "pairs" in body
        assert "min_coherence_used" in body
    translator_service.set_backend(None)


def test_canonical_views_batch_matches_per_idea():
    """canonical_views (the batch) returns, for each id, exactly the record the
    per-idea canonical_view returns — one query for a whole listing instead of
    one SELECT per idea (the N+1 /api/ideas?lang=xx fired over up to 200 ideas).

    One strange-minimal fixture covers four boundaries: a present view, an absent
    id (absent from the dict, mirroring canonical_view -> None), latest-by-
    updated_at winning when an entity has two canonical writes, and empty input.
    """
    lang = "de"
    ids = [f"idea-batch-{uuid4().hex[:8]}" for _ in range(3)]
    for i in (0, 1):
        _cache.write_view(
            entity_type="idea", entity_id=ids[i], lang=lang,
            content_title=f"Titel {i}", content_description=f"Beschreibung {i}",
            content_markdown="", author_type="test",
        )
    # ids[0] gets a SECOND (newer) canonical write — the latest must win, the same
    # way canonical_view sorts by updated_at and takes the newest.
    _cache.write_view(
        entity_type="idea", entity_id=ids[0], lang=lang,
        content_title="Titel 0 neu", content_description="neu",
        content_markdown="", author_type="test",
    )

    batch = _cache.canonical_views("idea", ids, lang)

    # exactly the ids that have a canonical view; the third is absent
    assert set(batch.keys()) == {ids[0], ids[1]}
    assert ids[2] not in batch
    assert _cache.canonical_view("idea", ids[2], lang) is None
    # each batch record IS the per-idea canonical_view record (same row + title)
    for i in (0, 1):
        per = _cache.canonical_view("idea", ids[i], lang)
        assert per is not None
        assert batch[ids[i]].id == per.id
        assert batch[ids[i]].content_title == per.content_title
    # latest-wins: ids[0]'s batch record is the newer write
    assert batch[ids[0]].content_title == "Titel 0 neu"
    # empty input short-circuits to {} (no query)
    assert _cache.canonical_views("idea", [], lang) == {}


def test_resonance_pair_to_out_batch_matches_per_call():
    """resonance._pair_to_out projects the SAME names whether it reads each view
    via a per-idea canonical_view (canon=None) or from a pre-batched dict (canon
    supplied) — the batch threaded into the listing must be a faithful substitute
    for the two-SELECTs-per-pair it replaces.

    Strange-minimal: one pair where side A has a German canonical view and side B
    has none. That single pair exercises the title override (A), the absent-view
    None branch (B keeps its anchor name), and batch-vs-per-call agreement at once.
    """
    from app.routers import resonance as _res
    from app.services import idea_resonance_service as _rs

    lang = "de"
    id_a = f"idea-pair-a-{uuid4().hex[:8]}"
    id_b = f"idea-pair-b-{uuid4().hex[:8]}"  # deliberately gets NO view
    _cache.write_view(
        entity_type="idea", entity_id=id_a, lang=lang,
        content_title="Symbiose", content_description="",
        content_markdown="", author_type="test",
    )

    pair = _rs.ResonancePair(
        idea_id_a=id_a, name_a="Symbiosis", domain_a=["biology"],
        idea_id_b=id_b, name_b="Microservices", domain_b=["software"],
        crk_score=0.9, ot_distance=0.1, coherence=0.85, d_codex=0.2,
        cross_domain=True, strong=True, discovered_at="2026-06-03T00:00:00Z",
    )

    # The batch the listing would build (collecting both pair ids in one query).
    canon = _cache.canonical_views("idea", [id_a, id_b], lang)

    per_call = _res._pair_to_out(pair, lang)            # canon=None → per-idea SELECTs
    batched = _res._pair_to_out(pair, lang, canon)      # reads from the pre-batched dict

    # A's name comes from the German view; B has no view so keeps its anchor name.
    assert per_call.name_a == "Symbiose"
    assert per_call.name_b == "Microservices"
    # Faithful substitute: batched output is identical to the per-call output.
    assert batched.name_a == per_call.name_a
    assert batched.name_b == per_call.name_b
    # The absent id is simply not in the batch dict (mirrors canonical_view -> None).
    assert id_b not in canon


def _count_write_view_for(entity_id: str):
    """Wrap translation_cache_service.write_view with a call-counter that still
    calls through to the real write (the attune flow depends on the writes
    actually landing). Returns a context-manager-ish (patcher, counter) usable
    inside a ``with`` block; ``counter['n']`` holds writes seen for ``entity_id``.
    """
    real = _cache.write_view
    counter = {"n": 0}

    def _spy(*args, **kwargs):
        if kwargs.get("entity_id") == entity_id:
            counter["n"] += 1
        return real(*args, **kwargs)

    return patch.object(_cache, "write_view", _spy), counter


def test_edge_stub_batch_preserves_attune_write_count(stub_backend):
    """A node with NO canonical view that appears in MULTIPLE edge stubs is
    attuned-on-miss exactly ONCE — the batched ``view=`` + ``seen_attuned`` path
    must produce the IDENTICAL number of ``write_view`` calls as the per-stub
    path, and the IDENTICAL projected text on every stub.

    This is the test that catches a subtle batch bug: with a pre-loop snapshot,
    every stub of a missing node sees it absent. Without the ``seen_attuned``
    guard the second stub would attune again (an extra ``write_view`` for the
    translated view) — a silent write-count regression. We pin it by running
    BOTH paths on equivalent fixtures and asserting equal write counts, plus
    the strange edge that the second stub still renders translated (the snapshot
    was refreshed from the freshly-written view, mirroring the per-call re-query).
    """
    from app.routers import edges as _edges

    lang = "de"

    def _stub(node_id: str) -> dict:
        # A localizable node-stub shape (concept ∈ _LOCALIZABLE_NODE_TYPES) with
        # NO canonical view yet — forces the attune-on-miss path.
        return {"id": node_id, "type": "concept", "name": "Sourcebound"}

    # ── Reference: the per-stub path (each call live-queries canonical_view). ──
    ref_id = f"node-edgewc-ref-{uuid4().hex[:8]}"
    patcher_ref, ref_counter = _count_write_view_for(ref_id)
    s1, s2 = _stub(ref_id), _stub(ref_id)
    with patcher_ref:
        _edges._project_edge_stub(s1, lang)   # first occurrence: anchor + attune
        _edges._project_edge_stub(s2, lang)   # second: view now present → skip
    # First-occurrence attune wrote two views (EN anchor + DE translated); the
    # second occurrence found the view present and wrote nothing.
    assert ref_counter["n"] == 2, ref_counter["n"]
    assert s1["name"] == "[de] Sourcebound"
    assert s2["name"] == "[de] Sourcebound"  # second stub projected from the cache

    # ── Batched path: one snapshot up front, seen-set across the two stubs. ──
    bat_id = f"node-edgewc-bat-{uuid4().hex[:8]}"
    patcher_bat, bat_counter = _count_write_view_for(bat_id)
    b1, b2 = _stub(bat_id), _stub(bat_id)
    # The snapshot the listing builds before the loop: bat_id has no view, so it
    # is absent (canonical_views mirrors canonical_view -> None).
    canon = _cache.canonical_views("node", [bat_id], lang)
    assert bat_id not in canon
    seen: set[str] = set()
    with patcher_bat:
        r1 = _edges._project_edge_stub(b1, lang, view=canon.get(bat_id), seen_attuned=seen)
        if r1 is not None:
            canon[bat_id] = r1
        r2 = _edges._project_edge_stub(b2, lang, view=canon.get(bat_id), seen_attuned=seen)
        if r2 is not None:
            canon[bat_id] = r2

    # Faithfulness: the batch writes EXACTLY as many times as the per-stub path.
    assert bat_counter["n"] == ref_counter["n"] == 2
    # And the node was attuned only once (seen-set held the second stub back).
    assert seen == {bat_id}
    # Output parity: both stubs render the SAME translated text the per-stub
    # path produced — the second stub projected from the refreshed snapshot.
    assert b1["name"] == "[de] Sourcebound"
    assert b2["name"] == "[de] Sourcebound"


@pytest.mark.asyncio
async def test_list_edges_batches_views_and_attunes_shared_node_once(stub_backend):
    """End-to-end through GET /api/edges, ONE page, TWO edges sharing one no-view
    node: the shared node appears in two to_node stubs on the same page. It is
    rendered in the caller's locale on BOTH stubs, and its translated view is
    written exactly once across the page (the wired batch + seen-set path)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        a = await _create_concept(c, "edge-a")
        b = await _create_concept(c, "edge-b")
        shared = await _create_concept(c, "edge-shared")  # the no-view node both edges point at

        # A unique edge type so the listing page is EXACTLY these two edges —
        # both to_node=shared, so the shared node is in two stubs on one page.
        etype = f"wc-shares-{uuid4().hex[:8]}"
        for src in (a, b):
            r = await c.post("/api/edges", json={
                "from_id": src, "to_id": shared, "type": etype,
            })
            assert r.status_code == 201, r.text

        shared_id = shared  # _create_concept passes id=slug, so the node id IS the slug
        patcher, counter = _count_write_view_for(shared_id)
        with patcher:
            r = await c.get(f"/api/edges?type={etype}&lang=de")
            assert r.status_code == 200, r.text
            page = r.json()

        # Both edges share the same to_node; both stubs render translated.
        to_stubs = [e["to_node"] for e in page["items"]]
        assert len(to_stubs) == 2
        assert all(s["id"] == shared_id for s in to_stubs)
        assert all(s["name"].startswith("[de] ") for s in to_stubs), to_stubs
        # The shared node's anchor + translated view were each written once on
        # the first stub; the second stub found the view present (refreshed
        # snapshot + seen-set) and wrote nothing. Without the seen-set the second
        # stub would attune again — counter would exceed 2.
        assert counter["n"] == 2, counter["n"]
