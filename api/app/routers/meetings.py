"""Meeting endpoint — the felt state of a viewer meeting an entity.

Each screen in the app is a meeting between a reader and a thing. The
screen should show the vitality of both sides and how they resonate,
so the viewer experiences the encounter as a shared organism, not a
broadcast.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.services import meeting_service, reaction_service
from app.services.localized_errors import caller_lang, localize

router = APIRouter()


@router.get(
    "/meeting/{entity_type}/{entity_id}",
    summary="Felt state of a viewer meeting an entity — for full-screen immersion",
)
async def sense_meeting(
    entity_type: str,
    entity_id: str,
    request: Request,
    contributor_id: str | None = Query(None, description="Optional viewer contributor id"),
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
    return meeting_service.sense_meeting(
        entity_type=entity_type,
        entity_id=entity_id,
        contributor_id=contributor_id,
    )
