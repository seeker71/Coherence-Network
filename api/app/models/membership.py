"""Pydantic models for workspace membership (team edges)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MemberRole(str, Enum):
    owner = "owner"
    admin = "admin"
    member = "member"
    viewer = "viewer"


class MembershipStatus(str, Enum):
    pending = "pending"
    active = "active"


class WorkspaceMember(BaseModel):
    contributor_id: str
    contributor_name: str = ""
    role: MemberRole
    status: MembershipStatus
    joined_at: Optional[str] = None


class WorkspaceInvite(BaseModel):
    contributor_id: str
    role: MemberRole = MemberRole.member


class InviteResponse(BaseModel):
    invite_id: str
    contributor_id: str
    workspace_id: str
    role: MemberRole
    status: MembershipStatus


class WorkspaceMembersResponse(BaseModel):
    workspace_id: str
    members: list[WorkspaceMember]
    total: int


class MyWorkspacesItem(BaseModel):
    workspace_id: str
    workspace_name: str = ""
    role: MemberRole
    joined_at: Optional[str] = None


class MyWorkspacesResponse(BaseModel):
    workspaces: list[MyWorkspacesItem]
    total: int
