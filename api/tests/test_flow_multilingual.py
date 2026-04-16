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
async def test_list_locales_includes_en_de_es_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/locales")
        assert r.status_code == 200
        codes = {loc["code"] for loc in r.json()["locales"]}
        assert {"en", "de", "es", "id"}.issubset(codes)
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
    translator_service.set_backend(None)
