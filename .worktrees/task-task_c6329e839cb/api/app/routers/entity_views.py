"""Generic entity-views router — one API for language views of any entity type.

Unifies concepts, ideas, contributions, assets under a single CRUD surface:

  POST   /api/entity-views/{entity_type}/{entity_id}          — upsert a view
  GET    /api/entity-views/{entity_type}/{entity_id}          — list canonical views + anchor
  GET    /api/entity-views/{entity_type}/{entity_id}/history  — history per lang

The prefix ``entity-views`` avoids collision with ``/api/views/*`` (which the
read-tracking router owns: /views/stats, /views/trending, /views/summary, etc).

Concept-specific endpoints at /api/concepts/{id}/views remain for backward-compat
and because they verify the concept exists. The generic surface serves ideas and
anything else that lands next.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import translation_cache_service as translation_cache
from app.services import translator_service

router = APIRouter()


SUPPORTED_ENTITY_TYPES = {"concept", "idea", "contribution", "asset", "spec"}


class ViewUpsert(BaseModel):
    lang: str
    content_title: str = ""
    content_description: str = ""
    content_markdown: str = ""
    author_type: str = "translation_human"
    author_id: str | None = None
    translator_model: str | None = None
    translated_from_lang: str | None = None
    translated_from_hash: str | None = None
    notes: str | None = None


def _check_entity_type(entity_type: str) -> None:
    if entity_type not in SUPPORTED_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported entity_type '{entity_type}'. Supported: "
                   f"{sorted(SUPPORTED_ENTITY_TYPES)}",
        )


@router.post("/entity-views/{entity_type}/{entity_id}", summary="Upsert a language view for any entity")
async def upsert_view(entity_type: str, entity_id: str, body: ViewUpsert):
    _check_entity_type(entity_type)
    if not translator_service.is_supported(body.lang):
        raise HTTPException(status_code=400, detail=f"Unsupported locale '{body.lang}'")
    if body.author_type not in {
        translation_cache.AUTHOR_TYPE_ORIGINAL_HUMAN,
        translation_cache.AUTHOR_TYPE_TRANSLATION_HUMAN,
        translation_cache.AUTHOR_TYPE_TRANSLATION_MACHINE,
    }:
        raise HTTPException(status_code=400, detail=f"Invalid author_type '{body.author_type}'")
    if body.author_type != translation_cache.AUTHOR_TYPE_ORIGINAL_HUMAN:
        if not body.translated_from_lang or not body.translated_from_hash:
            raise HTTPException(
                status_code=400,
                detail="translated_from_lang and translated_from_hash are required "
                       "unless author_type is 'original_human'",
            )

    rec = translation_cache.write_view(
        entity_type=entity_type,
        entity_id=entity_id,
        lang=body.lang,
        content_title=body.content_title,
        content_description=body.content_description,
        content_markdown=body.content_markdown,
        author_type=body.author_type,
        author_id=body.author_id,
        translator_model=body.translator_model,
        translated_from_lang=body.translated_from_lang,
        translated_from_hash=body.translated_from_hash,
        notes=body.notes,
    )
    return {
        "id": rec.id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "lang": rec.lang,
        "content_hash": rec.content_hash,
        "author_type": rec.author_type,
        "translated_from_lang": rec.translated_from_lang,
        "translated_from_hash": rec.translated_from_hash,
        "status": rec.status,
        "updated_at": rec.updated_at.isoformat() if rec.updated_at else None,
    }


@router.get("/entity-views/{entity_type}/{entity_id}", summary="List all canonical views for an entity (with anchor + staleness)")
async def list_views(entity_type: str, entity_id: str):
    _check_entity_type(entity_type)
    views = translation_cache.all_canonical_views(entity_type, entity_id)
    anchor = translation_cache.find_anchor(views)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "anchor_lang": anchor.lang if anchor else None,
        "views": [
            {
                "lang": v.lang,
                "author_type": v.author_type,
                "content_hash": v.content_hash,
                "translated_from_lang": v.translated_from_lang,
                "translated_from_hash": v.translated_from_hash,
                "is_anchor": anchor is not None and v.id == anchor.id,
                "stale": translation_cache.is_stale(v, anchor),
                "updated_at": v.updated_at.isoformat() if v.updated_at else None,
            }
            for v in views
        ],
    }


@router.get("/views/{entity_type}/{entity_id}/history", summary="View history for (entity, lang) — canonical + superseded")
async def list_view_history(entity_type: str, entity_id: str, lang: str = Query(..., description="Target locale")):
    _check_entity_type(entity_type)
    if not translator_service.is_supported(lang):
        raise HTTPException(status_code=400, detail=f"Unsupported locale '{lang}'")
    rows = translation_cache.list_history(entity_type, entity_id, lang)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "lang": lang,
        "views": [
            {
                "id": r.id,
                "status": r.status,
                "author_type": r.author_type,
                "author_id": r.author_id,
                "content_hash": r.content_hash,
                "translated_from_lang": r.translated_from_lang,
                "translated_from_hash": r.translated_from_hash,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "notes": r.notes,
            }
            for r in rows
        ],
    }
