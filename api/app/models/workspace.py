"""Workspace / tenant primitive.

A Workspace is the top-level tenant: it owns a set of ideas, specs, tasks,
agent personas, templates, and pillar taxonomy. Every Idea and Spec lives
inside exactly one Workspace.

Today workspaces are co-located under workspaces/{slug}/ in this repo with
soft isolation (shared DB, workspace_id column). The long-term goal is true
isolation — separate repo, separate DB, federated discovery. The
WorkspaceResolver abstraction is the single swap point for that migration.

The default workspace 'coherence-network' hosts this project's own ideas
and specs. New contributor teams create their own workspace (e.g.
'my-startup', 'client-engagement-x') with their own pillars, agents, and
templates.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


DEFAULT_WORKSPACE_ID = "coherence-network"


class WorkspaceVisibility(str, Enum):
    PUBLIC = "public"          # anyone can read ideas/specs
    FEDERATION = "federation"  # readable by federated peer nodes only
    PRIVATE = "private"        # this node only


class Workspace(BaseModel):
    id: str = Field(min_length=1, description="Stable slug identifier — used as foreign key on ideas/specs/tasks.")
    name: str = Field(min_length=1)
    description: str = Field(default="")
    pillars: list[str] = Field(default_factory=list, description="Taxonomy for grouping ideas. Workspace-declared.")
    owner_contributor_id: Optional[str] = Field(default=None, description="Contributor who created the workspace.")
    visibility: WorkspaceVisibility = WorkspaceVisibility.PUBLIC
    bundle_path: Optional[str] = Field(
        default=None,
        description="Repo-relative path to workspace bundle (workspaces/{slug}/). None means repo root (legacy default workspace).",
    )
    created_at: datetime
    updated_at: datetime


class WorkspaceCreate(BaseModel):
    id: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9\-]*$",
        description="Slug: lowercase + hyphens.",
    )
    name: str = Field(min_length=1)
    description: str = Field(default="")
    pillars: list[str] = Field(default_factory=list)
    owner_contributor_id: Optional[str] = None
    visibility: WorkspaceVisibility = WorkspaceVisibility.PUBLIC


class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    pillars: Optional[list[str]] = None
    visibility: Optional[WorkspaceVisibility] = None
