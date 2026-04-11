"""DIF feedback router — track verification accuracy for quality improvement."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Any

from app.services import dif_feedback_service

router = APIRouter()


class DifVerificationRecord(BaseModel):
    """Record a DIF verification result."""
    task_id: str
    task_type: str = ""
    file_path: str = ""
    language: str = ""
    dif_result: dict[str, Any] = {}
    agent_action: str = "pending"
    idea_id: str = ""
    provider: str = ""


class DifOutcomeUpdate(BaseModel):
    """Update the outcome of a task's DIF verifications."""
    task_id: str
    outcome: str  # success | failure | timeout


@router.get("/dif/stats", summary="DIF accuracy statistics — true/false positive rates, accuracy by language")
async def dif_stats():
    """DIF accuracy statistics — true/false positive rates, accuracy by language."""
    return dif_feedback_service.get_stats()


@router.get("/dif/recent", summary="Recent DIF verification entries with scores and outcomes")
async def dif_recent(limit: int = Query(default=20, ge=1, le=100)):
    """Recent DIF verification entries with scores and outcomes."""
    return dif_feedback_service.get_recent(limit=limit)


@router.post("/dif/record", status_code=201, summary="Record a DIF verification result for accuracy tracking")
async def record_verification(body: DifVerificationRecord):
    """Record a DIF verification result for accuracy tracking."""
    return dif_feedback_service.record_verification(
        task_id=body.task_id,
        task_type=body.task_type,
        file_path=body.file_path,
        language=body.language,
        dif_result=body.dif_result,
        agent_action=body.agent_action,
        idea_id=body.idea_id,
        provider=body.provider,
    )


@router.post("/dif/outcome", summary="Update all DIF feedback entries for a task with the final outcome")
async def update_outcome(body: DifOutcomeUpdate):
    """Update all DIF feedback entries for a task with the final outcome."""
    updated = dif_feedback_service.update_outcome(body.task_id, body.outcome)
    return {"task_id": body.task_id, "outcome": body.outcome, "entries_updated": updated}


@router.post("/dif/flush", summary="Flush DIF feedback buffer to graph_nodes for persistent storage")
async def flush_to_graph():
    """Flush DIF feedback buffer to graph_nodes for persistent storage."""
    flushed = dif_feedback_service.flush_to_api()
    return {"flushed": flushed}
