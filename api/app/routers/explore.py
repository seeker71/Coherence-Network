"""Explore queue — serendipitous meetings, one after another."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.services import explore_queue_service, reaction_service
from app.services.localized_errors import caller_lang, localize

router = APIRouter()


@router.get(
    "/explore/{entity_type}",
    summary="A walk through entities — each one a possible meeting",
    description=(
        "Returns a small ordered queue of entities of the given type that "
        "the viewer hasn't reacted to yet. Seeded by session_key so each "
        "viewer walks a different path; reseed by passing a new key."
    ),
)
async def explore_queue(
    entity_type: str,
    request: Request,
    limit: int = Query(12, ge=1, le=50),
    contributor_id: str | None = Query(None),
    session_key: str | None = Query(None),
    include_seen: bool = Query(False),
) -> dict:
    if entity_type not in reaction_service.SUPPORTED_ENTITY_TYPES:
        raise HTTPException(
            status_code=400,
            detail=localize(
                "unsupported_entity_type",
                caller_lang(request),
                entity_type=entity_type,
            ),
        )
    queue = explore_queue_service.build_queue(
        entity_type,
        limit=limit,
        contributor_id=contributor_id,
        session_key=session_key,
        include_seen=include_seen,
    )
    return {
        "entity_type": entity_type,
        "queue": queue,
        "count": len(queue),
    }
