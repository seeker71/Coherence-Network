"""Locales router — list supported languages and their coverage.

Supports the multilingual web surface. Coverage counts are computed from the
content_translations cache at request time (cheap: indexed scan).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import translation_cache_service as _cache
from app.services import translator_service

router = APIRouter()


class GlossaryEntryPayload(BaseModel):
    source_term: str = Field(min_length=1)
    target_term: str = Field(min_length=1)
    notes: str | None = None


class GlossaryUpsertBody(BaseModel):
    entries: list[GlossaryEntryPayload]


@router.get("/locales", summary="List supported locales with coverage stats")
async def list_locales() -> dict:
    """List supported locales and how much of the concept space is reachable
    in each. Coverage is computed as: for every concept that has any view,
    how many have a canonical view in this lang, how many of those are
    original authoring, how many are human-attuned, how many machine-attuned,
    and how many are currently stale relative to the anchor.
    """
    from sqlalchemy import select
    from collections import defaultdict

    with _cache._session() as s:  # noqa: SLF001
        rows = list(s.scalars(
            select(_cache.EntityViewRecord).where(
                _cache.EntityViewRecord.status == _cache.STATUS_CANONICAL,
            )
        ))

    per_entity: dict[tuple[str, str], list[_cache.EntityViewRecord]] = defaultdict(list)
    for r in rows:
        per_entity[(r.entity_type, r.entity_id)].append(r)

    # Per-lang tallies
    counters: dict[str, dict[str, int]] = {
        code: {"original": 0, "human": 0, "machine": 0, "stale": 0}
        for code in translator_service.SUPPORTED_LOCALES
    }
    for views in per_entity.values():
        anchor = _cache.find_anchor(views)
        for v in views:
            if v.lang not in counters:
                continue
            if v.author_type == _cache.AUTHOR_TYPE_ORIGINAL_HUMAN:
                counters[v.lang]["original"] += 1
            elif v.author_type == _cache.AUTHOR_TYPE_TRANSLATION_HUMAN:
                counters[v.lang]["human"] += 1
            elif v.author_type == _cache.AUTHOR_TYPE_TRANSLATION_MACHINE:
                counters[v.lang]["machine"] += 1
            if _cache.is_stale(v, anchor):
                counters[v.lang]["stale"] += 1

    locales = []
    for meta in translator_service.list_locales():
        entry = dict(meta)
        entry["coverage"] = counters.get(meta["code"], {"original": 0, "human": 0, "machine": 0, "stale": 0})
        locales.append(entry)
    return {"locales": locales, "default": translator_service.DEFAULT_LOCALE}


@router.get("/glossary/{lang}", summary="List glossary anchor terms for a language")
async def get_glossary(lang: str) -> dict:
    if not translator_service.is_supported(lang):
        raise HTTPException(status_code=400, detail=f"Unsupported locale '{lang}'")
    entries = _cache.glossary_for(lang)
    return {
        "lang": lang,
        "entries": [
            {
                "source_term": e.source_term,
                "target_term": e.target_term,
                "notes": e.notes,
            }
            for e in entries
        ],
    }


@router.patch("/glossary/{lang}", summary="Upsert glossary anchor terms for a language")
async def patch_glossary(lang: str, body: GlossaryUpsertBody) -> dict:
    """Upsert glossary entries. The file in docs/vision-kb/glossary/{lang}.md is
    the source of truth; this endpoint is how the sync pass projects that file
    into the cache. Users can also call it directly to tune a rendering.
    """
    if not translator_service.is_supported(lang):
        raise HTTPException(status_code=400, detail=f"Unsupported locale '{lang}'")
    written = 0
    for entry in body.entries:
        _cache.upsert_glossary_entry(lang, entry.source_term, entry.target_term, entry.notes)
        written += 1
    return {"lang": lang, "upserted": written}
