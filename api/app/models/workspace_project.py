"""Workspace Project models — grouping primitive for ideas within a workspace."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WorkspaceProjectCreate(BaseModel):
    name: str = Field(min_length=1, description="Project name.")
    description: Optional[str] = Field(default=None, description="Optional project description.")
    workspace_id: str = Field(description="Owning workspace ID.")


class WorkspaceProject(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    workspace_id: str
    idea_count: int = 0
    created_by: Optional[str] = None
    created_at: datetime


class WorkspaceProjectDetail(WorkspaceProject):
    ideas: list[dict] = Field(default_factory=list, description="Ideas belonging to this project.")


class AddIdeaRequest(BaseModel):
    idea_id: str = Field(description="ID of the idea to add to this project.")


class ProjectListResponse(BaseModel):
    projects: list[WorkspaceProject]
    total: int
