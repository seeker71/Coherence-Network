"""Workspace CRUD routes — the tenant primitive.

Workspaces own ideas, specs, tasks, agent personas, templates, and pillar
taxonomy. The default workspace 'coherence-network' is auto-ensured at
startup. New contributor teams POST /api/workspaces to create their own.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.workspace import Workspace, WorkspaceCreate, WorkspaceUpdate
from app.services import workspace_service

router = APIRouter()


@router.get("/workspaces", response_model=list[Workspace], summary="List Workspaces")
async def list_workspaces() -> list[Workspace]:
    return workspace_service.list_workspaces()


@router.get("/workspaces/{workspace_id}", response_model=Workspace, summary="Get Workspace")
async def get_workspace(workspace_id: str) -> Workspace:
    ws = workspace_service.get_workspace(workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.post("/workspaces", response_model=Workspace, status_code=201, summary="Create Workspace")
async def create_workspace(data: WorkspaceCreate) -> Workspace:
    created = workspace_service.create_workspace(data)
    if created is None:
        raise HTTPException(status_code=409, detail="Workspace already exists")
    return created


@router.patch("/workspaces/{workspace_id}", response_model=Workspace, summary="Update Workspace")
async def update_workspace(workspace_id: str, data: WorkspaceUpdate) -> Workspace:
    if all(
        field is None
        for field in (
            data.name, data.description, data.pillars, data.visibility,
            data.repo_url, data.default_provider, data.provider_config,
        )
    ):
        raise HTTPException(status_code=400, detail="At least one field required")
    updated = workspace_service.update_workspace(workspace_id, data)
    if updated is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return updated


@router.get("/workspaces/{workspace_id}/pillars", response_model=list[str], summary="Return the pillar taxonomy declared by this workspace")
async def get_workspace_pillars(workspace_id: str) -> list[str]:
    """Return the pillar taxonomy declared by this workspace."""
    if workspace_service.get_workspace(workspace_id) is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace_service.get_pillars_for_workspace(workspace_id)
