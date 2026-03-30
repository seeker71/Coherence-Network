"""Graph health API — structural diagnostics and convergence guards (spec-172)."""

from __future__ import annotations

from fastapi import APIRouter

from app.db import graph_health_repo
from app.models.graph_health import ConvergenceGuardBody, ConvergenceGuardResponse
from app.services import graph_health_service as svc

router = APIRouter()


@router.get("/graph/health")
async def get_graph_health():
    snap = svc.get_latest_or_baseline()
    return snap.model_dump(mode="json")


@router.post("/graph/health/compute")
async def compute_graph_health():
    snap = svc.compute_snapshot()
    return snap.model_dump(mode="json")


@router.post("/graph/concepts/{concept_id}/convergence-guard")
async def set_convergence_guard(concept_id: str, body: ConvergenceGuardBody):
    graph_health_repo.set_guard(concept_id, body.reason, body.set_by)
    return ConvergenceGuardResponse(
        concept_id=concept_id,
        convergence_guard=True,
        reason=body.reason,
        set_by=body.set_by,
    ).model_dump(mode="json")


@router.delete("/graph/concepts/{concept_id}/convergence-guard")
async def delete_convergence_guard(concept_id: str):
    graph_health_repo.remove_guard(concept_id)
    return ConvergenceGuardResponse(
        concept_id=concept_id,
        convergence_guard=False,
    ).model_dump(mode="json")


@router.get("/graph/health/roi")
async def graph_health_roi():
    return svc.roi_snapshot()
