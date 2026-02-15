"""GitHub Contributor model — spec 029.

Represents contributors fetched from GitHub API for coherence score calculation.
Separate from contribution network Contributor (wallet, hourly_rate).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GitHubContributor(BaseModel):
    """GitHub contributor node for coherence analysis."""

    id: str  # format: "github:login"
    source: str = "github"
    login: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    contributions_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class GitHubContributorCreate(BaseModel):
    """Request body for creating GitHub contributor."""

    login: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    contributions_count: int = 0
