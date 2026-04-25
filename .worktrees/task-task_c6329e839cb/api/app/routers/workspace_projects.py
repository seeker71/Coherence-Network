"""Workspace Project routes — group ideas within a workspace.

Projects are graph nodes with edges to member ideas.  Follows the same
pattern as workspaces.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.middleware.auth import require_api_key
from app.models.workspace_project import (
    AddIdeaRequest,
    ProjectListResponse,
    WorkspaceProject,
    WorkspaceProjectCreate,
    WorkspaceProjectDetail,
)
from app.services import workspace_project_service

router = APIRouter()


@router.post(
    "/workspaces/{workspace_id}/projects",
    response_model=WorkspaceProject,
    status_code=201,
    summary="Create Project",
)
async def create_project(
    workspace_id: str,
    data: WorkspaceProjectCreate,
    _key: str = Depends(require_api_key),
) -> WorkspaceProject:
    # Override workspace_id from path — body field is ignored in favour of path.
    try:
        proj = workspace_project_service.create_project(
            name=data.name,
            description=data.description,
            workspace_id=workspace_id,
            created_by=None,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return WorkspaceProject(**proj)


@router.get(
    "/workspaces/{workspace_id}/projects",
    response_model=ProjectListResponse,
    summary="List Projects",
)
async def list_projects(workspace_id: str) -> ProjectListResponse:
    projects = workspace_project_service.list_projects(workspace_id)
    return ProjectListResponse(
        projects=[WorkspaceProject(**p) for p in projects],
        total=len(projects),
    )


@router.get(
    "/projects/{project_id}",
    response_model=WorkspaceProjectDetail,
    summary="Get Project",
)
async def get_project(project_id: str) -> WorkspaceProjectDetail:
    proj = workspace_project_service.get_project(project_id)
    if proj is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return WorkspaceProjectDetail(**proj)


@router.delete("/projects/{project_id}", status_code=204, summary="Delete Project")
async def delete_project(
    project_id: str,
    _key: str = Depends(require_api_key),
) -> None:
    deleted = workspace_project_service.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post(
    "/projects/{project_id}/ideas",
    status_code=201,
    summary="Add Idea To Project",
)
async def add_idea_to_project(
    project_id: str,
    data: AddIdeaRequest,
    _key: str = Depends(require_api_key),
) -> dict:
    try:
        edge = workspace_project_service.add_idea_to_project(project_id, data.idea_id)
    except ValueError as e:
        msg = str(e)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        # Cross-workspace rejection
        raise HTTPException(status_code=400, detail=msg)
    return edge


@router.delete("/projects/{project_id}/ideas/{idea_id}", status_code=204, summary="Remove Idea From Project")
async def remove_idea_from_project(
    project_id: str,
    idea_id: str,
    _key: str = Depends(require_api_key),
) -> None:
    removed = workspace_project_service.remove_idea_from_project(project_id, idea_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Edge not found")


@router.get("/ideas/{idea_id}/projects", response_model=ProjectListResponse, summary="List Projects For Idea")
async def list_projects_for_idea(idea_id: str) -> ProjectListResponse:
    projects = workspace_project_service.list_projects_for_idea(idea_id)
    return ProjectListResponse(
        projects=[WorkspaceProject(**p) for p in projects],
        total=len(projects),
    )
