"""Presence — soft heartbeat + read endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.services import presence_service, reaction_service
from app.services.localized_errors import caller_lang, localize

router = APIRouter()


class HeartbeatIn(BaseModel):
    fingerprint: str = Field(..., min_length=4, max_length=128)


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
