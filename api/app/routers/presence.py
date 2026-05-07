"""Presence — soft heartbeat + read endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.services import presence_invitation_service, presence_service, reaction_service
from app.services.localized_errors import caller_lang, localize

router = APIRouter()


class HeartbeatIn(BaseModel):
    fingerprint: str = Field(..., min_length=4, max_length=128)


class PresenceInviteIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    kind: str = Field(..., min_length=1, max_length=40)
    story: str = Field(..., min_length=1, max_length=2000)
    steward: str = Field(..., min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=200)
    offerings: list[str] = Field(default_factory=list)
    needs: list[str] = Field(default_factory=list)
    ways_to_connect: list[str] = Field(default_factory=list)
    visibility: str = Field(default="network", min_length=1, max_length=40)
    external_url: str | None = Field(default=None, max_length=1000)


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
    "/presences/invite",
    status_code=201,
    summary="Invite a living presence into the graph",
)
async def invite_presence(payload: PresenceInviteIn) -> dict[str, Any]:
    try:
        created, presence = presence_invitation_service.invite_presence(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"created": created, "presence": presence}


@router.get(
    "/presences",
    summary="List graph-backed invited presences",
)
async def list_invited_presences(
    kind: str | None = Query(default=None, min_length=1, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    try:
        items = presence_invitation_service.list_presences(kind=kind, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"count": len(items), "items": items}


@router.get(
    "/presences/{presence_id}",
    summary="Read one graph-backed invited presence",
)
async def get_invited_presence(presence_id: str) -> dict[str, Any]:
    presence = presence_invitation_service.get_presence(presence_id)
    if not presence:
        raise HTTPException(status_code=404, detail=f"presence {presence_id!r} not found")
    return {"presence": presence}


@router.post(
    "/presence/{entity_type}/{entity_id}",
    summary="Heartbeat — you are meeting this entity right now",
)
async def beat(
    entity_type: str,
    entity_id: str,
    payload: HeartbeatIn,
    request: Request,
) -> dict:
    _check_entity_type(entity_type, request)
    return presence_service.beat(
        entity_type=entity_type,
        entity_id=entity_id,
        fingerprint=payload.fingerprint,
    )


@router.get(
    "/presence/{entity_type}/{entity_id}",
    summary="Count of viewers meeting this entity in the last 90s",
)
async def presence_count(
    entity_type: str,
    entity_id: str,
    request: Request,
    fingerprint: str | None = Query(None),
) -> dict:
    _check_entity_type(entity_type, request)
    return presence_service.count(
        entity_type=entity_type,
        entity_id=entity_id,
        fingerprint=fingerprint,
    )


@router.get(
    "/presence/summary",
    summary="Where in the organism are people meeting right now",
)
async def presence_summary() -> dict:
    return presence_service.summary()
