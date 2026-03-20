"""GitHub Organization model — spec 029.

Represents organizations fetched from GitHub API for coherence analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class GitHubOrganization(BaseModel):
    """GitHub organization node for coherence analysis."""

    id: str  # format: "github:login"
    login: str
    type: str  # "Organization" or "User"
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None


class GitHubOrganizationCreate(BaseModel):
    """Request body for creating GitHub organization."""

    login: str
    type: str  # "Organization" or "User"
    name: Optional[str] = None
    avatar_url: Optional[str] = None
