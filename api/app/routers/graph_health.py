"""Graph Health API routes (spec-172).

Endpoints:
  GET  /api/graph/health
  POST /api/graph/health/compute
  GET  /api/graph/health/history
  GET  /api/graph/health/roi
  GET  /api/graph/signals
  POST /api/graph/signals/{signal_id}/resolve
  POST /api/graph/concepts/{concept_id}/convergence-guard
  DELETE /api/graph/concepts/{concept_id}/convergence-guard
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.db import graph_health_repo
from app.models.graph_health import (
    ConvergenceGuardRequest,
    ConvergenceGuardResponse,
    GraphHealthHistoryResponse,
    GraphHealthROI,
    GraphHealthSnapshot,
    SignalListResponse,
    SignalResolveRequest,
    SPEC_REF,
)
from app.services import graph_health_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Health snapshot
# ---------------------------------------------------------------------------

@router.get("/graph/health", response_model=GraphHealthSnapshot, tags=["graph-health"])
async def get_graph_health():
    """Return the current (or most-recently-computed) graph health snapshot."""
    try:
        return graph_health_service.get_or_compute_health()
    except Exception as exc:
        logger.error("graph health unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"detail": "Graph database unavailable", "spec_ref": SPEC_REF},
        )


@router.post("/graph/health/compute", response_model=GraphHealthSnapshot, tags=["graph-health"])
async def compute_graph_health():
    """Trigger an immediate, synchronous health computation (max 10 s)."""
    try:
        snapshot, _ = graph_health_service.trigger_compute()
        return snapshot
    except RuntimeError as exc:
        if "cooldown" in str(exc):
            raise HTTPException(
                status_code=429,
                detail="Computation already in flight or cooling down",
            )
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.error("compute failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/graph/health/history", response_model=GraphHealthHistoryResponse, tags=["graph-health"])
async def get_graph_health_history(
    limit: int = Query(default=10, ge=1, le=100),
    since: Optional[str] = Query(default=None, description="ISO 8601 datetime"),
):
    """Return the last N health snapshots in reverse-chronological order."""
    since_dt: Optional[datetime] = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid 'since' datetime format")

    items, total = graph_health_service.get_health_history(limit=limit, since=since_dt)
    return GraphHealthHistoryResponse(items=items, total=total, spec_ref=SPEC_REF)


@router.get("/graph/health/roi", response_model=GraphHealthROI, tags=["graph-health"])
async def get_graph_health_roi(
    period_days: int = Query(default=30, ge=1, le=365),
):
    """Return ROI metrics showing whether the balancing algorithm is working."""
    return graph_health_service.get_roi(period_days=period_days)


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------

@router.get("/graph/signals", response_model=SignalListResponse, tags=["graph-health"])
async def list_graph_signals(
    type: Optional[str] = Query(default=None, alias="type"),
    severity: Optional[str] = Query(default=None),
):
    """Return all unresolved signals, with optional type/severity filters."""
    signals = graph_health_repo.list_signals(
        signal_type=type,
        severity=severity,
        resolved=False,
    )
    return SignalListResponse(signals=signals, total=len(signals), spec_ref=SPEC_REF)


@router.post(
    "/graph/signals/{signal_id}/resolve",
    tags=["graph-health"],
)
async def resolve_graph_signal(signal_id: str, body: SignalResolveRequest):
    """Mark a signal as resolved."""
    existing = graph_health_repo.get_signal(signal_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Signal not found")
    if existing.resolved:
        raise HTTPException(status_code=409, detail="Signal already resolved")

    updated = graph_health_repo.resolve_signal(
        signal_id=signal_id,
        resolution=body.resolution,
        resolved_by=body.resolved_by,
    )
    return updated


# ---------------------------------------------------------------------------
# Convergence guard
# ---------------------------------------------------------------------------

@router.post(
    "/graph/concepts/{concept_id}/convergence-guard",
    response_model=ConvergenceGuardResponse,
    tags=["graph-health"],
)
async def set_convergence_guard(concept_id: str, body: ConvergenceGuardRequest):
    """Set a convergence guard on a concept, suppressing split signals for it."""
    from app.services.concept_service import get_concept
    concept = get_concept(concept_id)
    if concept is None:
        raise HTTPException(status_code=404, detail="Concept not found")

    return graph_health_service.set_guard(
        concept_id=concept_id,
        reason=body.reason,
        set_by=body.set_by,
    )


@router.delete(
    "/graph/concepts/{concept_id}/convergence-guard",
    tags=["graph-health"],
)
async def delete_convergence_guard(concept_id: str):
    """Remove the convergence guard from a concept."""
    removed = graph_health_service.remove_guard(concept_id)
    if not removed:
        raise HTTPException(status_code=404, detail="No convergence guard found for this concept")
    return {"concept_id": concept_id, "convergence_guard": False}
