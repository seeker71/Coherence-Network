"""Flow-centric tests for multilingual concept views.

Every language rendering is an equal view. The anchor (freshest human-touched
view) can live in any language. Stale views emerge from the hash graph, not
from a hardcoded source-language assumption.

Covers:
  - GET /api/locales
  - PATCH /api/glossary/{lang}
  - POST /api/concepts/{id}/views  (original_human, translation_human)
  - GET /api/concepts/{id}?lang=... returns the right view + language_meta
  - GET /api/concepts/{id}/views lists the anchor + staleness
  - Editing the anchor view stales the other-lang views until they re-attune
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services import translator_service

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


async def _create_concept(c: AsyncClient) -> str:
    cid = _uid()
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
# Locales listing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_locales_matches_installed_message_bundles():
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/locales")
        assert r.status_code == 200
        codes = {loc["code"] for loc in r.json()["locales"]}
        assert _installed_locale_codes().issubset(codes)
        assert r.json()["default"] == "en"


def test_api_locale_manifest_matches_installed_message_bundles():
    manifest_path = REPO_ROOT / "api" / "app" / "data" / "locale_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    codes = {entry["code"] for entry in manifest["locales"]}
    assert _installed_locale_codes().issubset(codes)
    assert manifest["default"] == "en"


def test_api_locale_manifest_supports_production_image_fallback(tmp_path, monkeypatch):
    manifest_path = tmp_path / "locale_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "default": "en",
                "locales": [
                    {"code": "en", "name": "English", "native_name": "English"},
                    {"code": "fr", "name": "French", "native_name": "Français"},
                    {
                        "code": "pt-br",
                        "name": "Brazilian Portuguese",
                        "native_name": "Português (Brasil)",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(translator_service, "_WEB_MESSAGES_DIR", tmp_path / "missing")
    monkeypatch.setattr(translator_service, "_API_LOCALE_MANIFEST", manifest_path)

    locales = translator_service._discover_supported_locales()

    assert list(locales) == ["en", "fr", "pt-br"]
    assert locales["pt-br"]["native_name"] == "Português (Brasil)"


# ---------------------------------------------------------------------------
# Glossary PATCH
# ---------------------------------------------------------------------------

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
# View CRUD + anchor + staleness
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

        # Fetching in German gets the German view; it's not the anchor (EN was more recent),
        # but it's fresh (translated_from_hash matches EN's current content_hash)
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

        # Edit the English view — its hash changes; German now points at the old hash
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
        # German referenced the old English hash → now stale
        assert views["de"]["stale"] is True


@pytest.mark.asyncio
async def test_anchor_moves_to_edited_language():
    """When a non-English view is edited as original_human authoring in that
    language, it becomes the anchor even if an English view exists.
    """
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
        # A German speaker authors an updated version directly in German
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
        # EN is now not the anchor; it's also not stale by translated_from_hash
        # (it was authored directly, translated_from_lang is null)
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
        # newest-first ordering — the v2 canonical, v1 superseded
        assert statuses[0] == "canonical"
        assert statuses[1] == "superseded"
