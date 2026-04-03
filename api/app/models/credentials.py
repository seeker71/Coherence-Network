"""Pydantic models for Repo Credentials."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RepoCredentialCreate(BaseModel):
    contributor_id: str = Field(..., description="The ID of the contributor providing the credential")
    repo_url: str = Field(..., description="The repository URL this credential is for")
    credential_type: str = Field(..., description="Type of credential (github_token, ssh_key, etc.)")
    credential_raw: str = Field(..., description="The raw credential (will be hashed before storage)")
    scopes: Optional[List[str]] = Field(default_factory=list, description="List of scopes granted")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")


class RepoCredentialResponse(BaseModel):
    id: str
    contributor_id: str
    repo_url: str
    credential_type: str
    scopes: List[str]
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    status: str
    created_at: Optional[datetime] = None


class RepoCredentialList(BaseModel):
    credentials: List[RepoCredentialResponse]
