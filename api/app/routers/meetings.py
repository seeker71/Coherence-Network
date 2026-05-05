"""Meeting endpoint — the felt state of a viewer meeting an entity.

Each screen in the app is a meeting between a reader and a thing. The
screen should show the vitality of both sides and how they resonate,
so the viewer experiences the encounter as a shared organism, not a
broadcast.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Literal

from app.services import meeting_service, reaction_service
from app.services.localized_errors import caller_lang, localize

router = APIRouter()


class MeetingParticipantIn(BaseModel):
    id: str | None = Field(None, description="Stable participant node id.")
    name: str = Field(min_length=1)
    kind: Literal["person", "agent"] = "person"
    role: str | None = None


class MeetingConceptResonanceIn(BaseModel):
    participant_id: str | None = None
    participant_name: str | None = None
    concept_id: str = Field(min_length=1)
    concept_part_id: str = Field(min_length=1)
    concept_part_label: str | None = None
    concept_excerpt: str | None = None
    resonance: str = Field(min_length=1)
    strength: float = Field(ge=0.0, le=1.0)
    note: str | None = None


class MeetingCaptureIn(BaseModel):
    meeting_id: str | None = None
    title: str = Field(min_length=1)
    happened_at: str | None = None
    channel: str | None = None
    source: str = "api"
    participants: list[MeetingParticipantIn] = Field(min_length=1)
    concept_resonances: list[MeetingConceptResonanceIn] = Field(min_length=1)


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


@router.post(
    "/meetings/captures",
    status_code=201,
    summary="Capture a meeting and who resonated with which concept parts",
)
async def capture_meeting_resonance(body: MeetingCaptureIn) -> dict:
    try:
        return meeting_service.capture_meeting_resonance(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/meetings/resonance",
    summary="Recall who resonated with what part of concepts",
)
async def list_meeting_resonance(
    concept_id: str | None = Query(None),
    participant_id: str | None = Query(None),
    participant_kind: Literal["person", "agent"] | None = Query(None),
    meeting_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    return meeting_service.list_meeting_resonance(
        concept_id=concept_id,
        participant_id=participant_id,
        participant_kind=participant_kind,
        meeting_id=meeting_id,
        limit=limit,
    )
