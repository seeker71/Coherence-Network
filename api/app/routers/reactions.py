"""Reactions router — emoji + comment on any entity.

Anyone can express care on any concept, idea, spec, contributor,
community, workspace, asset, contribution, or story. Trust-by-default
— no moderation queue, no sign-in wall. The response carries the
updated summary so callers can refresh their UI without a second fetch.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.services import reaction_service
from app.services.localized_errors import caller_lang, localize

router = APIRouter()


class ReactionIn(BaseModel):
    author_name: str = Field(..., description="How this voice appears alongside its reaction")
    emoji: str | None = Field(None, description="A single emoji or short graphic")
    comment: str | None = Field(None, description="A short thought (optional if emoji is set)")
    locale: str = Field("en", description="Caller locale (for comment display)")
    author_id: str | None = Field(None, description="Optional contributor ID")


def _check_entity_type(entity_type: str, request: Request) -> None:
    if entity_type not in reaction_service.SUPPORTED_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=localize(
                "unsupported_entity_type",
                caller_lang(request),
                entity_type=entity_type,
            ),
        )


@router.post(
    "/reactions/{entity_type}/{entity_id}",
    status_code=201,
    summary="Add an emoji or short comment to any entity",
)
async def add_reaction(
    entity_type: str,
    entity_id: str,
    payload: ReactionIn,
    request: Request,
) -> dict:
    _check_entity_type(entity_type, request)
    try:
        created = reaction_service.add_reaction(
            entity_type=entity_type,
            entity_id=entity_id,
            author_name=payload.author_name,
            emoji=payload.emoji,
            comment=payload.comment,
            locale=payload.locale,
            author_id=payload.author_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    summary = reaction_service.summarise(entity_type, entity_id)
    return {"reaction": created, "summary": summary}


@router.get(
    "/reactions/{entity_type}/{entity_id}",
    summary="List reactions on an entity (newest first) + summary",
)
async def list_reactions(
    entity_type: str,
    entity_id: str,
    request: Request,
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    _check_entity_type(entity_type, request)
    reactions = reaction_service.list_reactions(entity_type, entity_id, limit=limit)
    summary = reaction_service.summarise(entity_type, entity_id)
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "reactions": reactions,
        "summary": summary,
    }


@router.get(
    "/reactions/{entity_type}/{entity_id}/summary",
    summary="Aggregate emoji counts + comment count only",
)
async def summary_reactions(
    entity_type: str, entity_id: str, request: Request
) -> dict:
    _check_entity_type(entity_type, request)
    return reaction_service.summarise(entity_type, entity_id)


@router.get(
    "/reactions/recent",
    summary="Recent reactions across all entities — the felt pulse of the collective",
)
async def recent_reactions(limit: int = Query(20, ge=1, le=100)) -> dict:
    return {
        "reactions": reaction_service.recent_reactions(limit=limit),
    }
