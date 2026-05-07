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

from app.services import anonymous_meeting_trace_service, meeting_service, reaction_service
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


class AnonymousMeetingTraceIn(BaseModel):
    visitor_key: str = Field(min_length=4, max_length=128)
    session_key: str = Field(min_length=4, max_length=128)
    surface: str = Field(min_length=1, max_length=300)
    duration_ms: int = Field(default=0, ge=0, le=86_400_000)
    started_at: str | None = None
    ended_at: str | None = None
    contributor_id: str | None = Field(default=None, max_length=200)


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


@router.post(
    "/meetings/anonymous-traces",
    status_code=201,
    summary="Record a privacy-light anonymous meeting trace",
)
async def record_anonymous_meeting_trace(body: AnonymousMeetingTraceIn) -> dict:
    try:
        return anonymous_meeting_trace_service.record_anonymous_meeting_trace(body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/meetings/anonymous-traces",
    summary="List recent privacy-light anonymous meeting traces",
)
async def list_anonymous_meeting_traces(
    source_point_id: str | None = Query(default=None, min_length=6, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    return anonymous_meeting_trace_service.list_anonymous_meeting_traces(
        source_point_id=source_point_id,
        limit=limit,
    )


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
