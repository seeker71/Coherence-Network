"""Translations router — POST human or machine translations for any entity.

Fills the spec gap in `multilingual-web` R8: anyone signed-in can
submit a translation and it becomes canonical immediately; the prior
canonical is preserved as superseded (history is the moderation
surface, not a review queue).

The underlying service (`translation_cache_service.write_view`) already
implements supersede semantics, content-hash tracking, and status
transitions. This router exposes it over HTTP.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import translation_cache_service

router = APIRouter(prefix="/translations", tags=["translations"])


class TranslationSubmit(BaseModel):
    """Payload for POST /api/translations."""

    entity_type: str = Field(description="concept, idea, contribution, story, etc.")
    entity_id: str
    lang: str = Field(description="Target language code: de, es, id, en, etc.")
    content_title: str
    content_description: str = ""
    content_markdown: str
    author_type: str = Field(
        default="translation_human",
        description="translation_human | translation_machine | contributor",
    )
    author_id: Optional[str] = None
    translator_model: Optional[str] = None
    translated_from_lang: Optional[str] = None
    translated_from_hash: Optional[str] = None
    notes: Optional[str] = None


class TranslationView(BaseModel):
    """Response body — the newly-canonical translation view."""

    id: str
    entity_type: str
    entity_id: str
    lang: str
    content_title: str
    content_description: str
    content_markdown: str
    content_hash: str
    author_type: str
    author_id: Optional[str]
    translator_model: Optional[str]
    translated_from_lang: Optional[str]
    translated_from_hash: Optional[str]
    status: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime


class TranslationListResponse(BaseModel):
    items: List[TranslationView]
    total: int


def _record_to_view(rec) -> TranslationView:
    return TranslationView(
        id=rec.id,
        entity_type=rec.entity_type,
        entity_id=rec.entity_id,
        lang=rec.lang,
        content_title=rec.content_title,
        content_description=rec.content_description,
        content_markdown=rec.content_markdown,
        content_hash=rec.content_hash,
        author_type=rec.author_type,
        author_id=rec.author_id,
        translator_model=rec.translator_model,
        translated_from_lang=rec.translated_from_lang,
        translated_from_hash=rec.translated_from_hash,
        status=rec.status,
        notes=rec.notes,
        created_at=rec.created_at,
        updated_at=rec.updated_at,
    )


@router.post(
    "",
    response_model=TranslationView,
    status_code=201,
    summary="Submit a translation (human or machine); supersedes any prior canonical",
)
async def submit_translation(body: TranslationSubmit) -> TranslationView:
    """Submit a translation for an entity. Becomes canonical immediately.

    Any prior canonical view for the same (entity, lang) is preserved
    as superseded — history is the moderation surface, not a review
    queue (spec R8).
    """
    try:
        rec = translation_cache_service.write_view(
            entity_type=body.entity_type,
            entity_id=body.entity_id,
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
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _record_to_view(rec)


@router.get(
    "/{entity_type}/{entity_id}",
    response_model=TranslationListResponse,
    summary="List all translation views (canonical + superseded) for an entity",
)
async def list_translations_for_entity(
    entity_type: str,
    entity_id: str,
    lang: Optional[str] = None,
) -> TranslationListResponse:
    """Return every translation view for an entity across languages.
    If `lang` is given, filter to that language's history.
    """
    if lang is not None:
        rows = translation_cache_service.list_history(entity_type, entity_id, lang)
    else:
        rows = translation_cache_service.all_canonical_views(entity_type, entity_id)
    items = [_record_to_view(r) for r in rows]
    return TranslationListResponse(items=items, total=len(items))
