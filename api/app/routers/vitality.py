"""Workspace vitality routes — living-system health metrics.

GET /workspaces/{workspace_id}/vitality — workspace health score and signals
"""

from __future__ import annotations

from fastapi import APIRouter

from app.services import vitality_service

router = APIRouter()


@router.get("/workspaces/{workspace_id}/vitality")
async def get_vitality(workspace_id: str) -> dict:
    """Return living-system health metrics for a workspace."""
    return vitality_service.compute_vitality(workspace_id=workspace_id)
