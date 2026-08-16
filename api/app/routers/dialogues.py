"""Unlisted public dialogue cells over the VPC Form-native CPU worker."""

from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool

from app.services import dialogue_service


router = APIRouter(prefix="/dialogues")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


def _public_origin(request: Request) -> str:
    """Use the ASGI network peer; proxy-header trust belongs to the server."""
    return request.client.host if request.client else "unknown"


class DialogueOffer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=1200)
    point_of_view: str = Field(..., min_length=1, max_length=240)
    locale: str = Field(..., min_length=1, max_length=80)
    public_disclosure_ack: Literal[
        "public-unlisted-v1", "public-unlisted-thread-v2"
    ]
    channel_timeout_seconds: int = Field(default=90, ge=10, le=120)

    @field_validator("question", "point_of_view")
    @classmethod
    def text_is_data_not_control(cls, value: str) -> str:
        cleaned = value.strip()
        if _CONTROL_RE.search(cleaned):
            raise ValueError("public dialogue text may not contain control characters")
        return cleaned

    @field_validator("locale")
    @classmethod
    def locale_is_bcp47(cls, value: str) -> str:
        dialogue_service.canonicalize_locale(value)
        return value.strip()


class DialogueCreate(DialogueOffer):
    parent_dialogue_id: str | None = Field(default=None, max_length=80)


class DialogueReply(DialogueOffer):
    public_disclosure_ack: Literal["public-unlisted-thread-v2"]


class DialogueRelease(BaseModel):
    removal_token: str = Field(..., min_length=20, max_length=200)


@router.post("", status_code=status.HTTP_202_ACCEPTED, summary="Offer an unlisted public dialogue turn")
async def start_dialogue(body: DialogueCreate, request: Request, response: Response) -> dict:
    """Persist a turn immediately; the singleton CPU worker attends asynchronously."""
    response.headers["Cache-Control"] = "no-store"
    try:
        return await run_in_threadpool(
            dialogue_service.submit_dialogue,
            **body.model_dump(),
            network_peer=_public_origin(request),
        )
    except dialogue_service.DialogueRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
            headers={"Retry-After": "15"},
        ) from exc


@router.post(
    "/{dialogue_id}/replies",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reply to an unlisted public dialogue turn",
)
async def reply_dialogue(
    dialogue_id: str,
    body: DialogueReply,
    request: Request,
    response: Response,
) -> dict:
    """Persist a child turn while the path fixes the parent edge."""
    response.headers["Cache-Control"] = "no-store"
    try:
        return await run_in_threadpool(
            dialogue_service.submit_dialogue,
            **body.model_dump(),
            network_peer=_public_origin(request),
            parent_dialogue_id=dialogue_id,
        )
    except dialogue_service.DialogueRateLimitError as exc:
        raise HTTPException(
            status_code=429,
            detail=str(exc),
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
            headers={"Retry-After": "15"},
        ) from exc


@router.get(
    "/{dialogue_id}/thread",
    summary="Observe one bounded unlisted public dialogue thread",
)
async def read_dialogue_thread(dialogue_id: str, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    try:
        thread = await run_in_threadpool(
            dialogue_service.get_dialogue_thread,
            dialogue_id,
        )
    except dialogue_service.DialogueThreadDisclosureError as exc:
        raise HTTPException(
            status_code=403,
            detail="This turn grants single-turn access only",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail="Native dialogue thread planning is presently unavailable",
            headers={"Retry-After": "15"},
        ) from exc
    if thread is None:
        raise HTTPException(status_code=404, detail="Dialogue not found")
    return thread


@router.get("/{dialogue_id}", summary="Observe one unlisted public dialogue turn")
async def read_dialogue(dialogue_id: str, response: Response) -> dict:
    response.headers["Cache-Control"] = "no-store"
    dialogue = await run_in_threadpool(dialogue_service.get_dialogue, dialogue_id)
    if dialogue is None:
        raise HTTPException(status_code=404, detail="Dialogue not found")
    return dialogue


@router.delete("/{dialogue_id}", summary="Release an unlisted public dialogue turn")
async def release_dialogue(
    dialogue_id: str,
    body: DialogueRelease,
    response: Response,
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    released = await run_in_threadpool(
        dialogue_service.release_dialogue,
        dialogue_id,
        body.removal_token,
    )
    if not released:
        raise HTTPException(status_code=404, detail="Dialogue or removal capability not found")
    return {"id": dialogue_id, "state": "tombstoned", "released": True}
