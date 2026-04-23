"""Memory router — exposes the write/manage/read loop.

Endpoints:
  POST /api/memory/moment          - Record a moment of aliveness (R1)
  GET  /api/memory/recall          - Composed retrieval; synthesis only (R3, R6)
  POST /api/memory/consolidate     - Distill recent moments into principles (R2)

See specs/agent-memory-system.md.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.memory import (
    ConsolidationResult,
    MemoryMoment,
    MemoryMomentCreate,
    MemoryRecall,
)
from app.services import memory_service

router = APIRouter(prefix="/memory", tags=["memory"])


@router.post(
    "/moment",
    response_model=MemoryMoment,
    status_code=201,
    summary="Record a moment of aliveness",
)
async def create_moment(body: MemoryMomentCreate) -> MemoryMoment:
    """Accept a moment with kind (decision/surprise/completion/
    abandonment/weight) and a non-empty why. Raw logs without why
    are rejected by the Pydantic layer at request parse.
    """
    return memory_service.write_moment(body)


@router.get(
    "/recall",
    response_model=MemoryRecall,
    summary="Composed retrieval — synthesis, not raw rows",
)
async def recall(
    about: str = Query(..., description="Node to recall memory about (person, project, self)."),
    for_context: str | None = Query(None, alias="for", description="Optional context framing."),
) -> MemoryRecall:
    """Return a synthesis shape with felt_sense, open_threads, and
    earned_conclusions. Never raw moment rows. Never timestamps.
    """
    return memory_service.compose_recall(about, for_context=for_context)


@router.post(
    "/consolidate",
    response_model=ConsolidationResult,
    summary="Distill recent moments into earned principles",
)
async def consolidate(
    about: str = Query(..., description="Node to consolidate memory for."),
    window_hours: int = Query(24, ge=1, le=720),
) -> ConsolidationResult:
    """Manage-step of the loop — runs at rest, re-reads recent sensings,
    distills into shorter form, archives sources. Output tokens are
    always fewer than input tokens.
    """
    return memory_service.consolidate_at_rest(about, window_hours=window_hours)
