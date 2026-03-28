"""Models for metadata self-discovery — endpoint and module concept nodes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


class MetaEndpointNode(BaseModel):
    path: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    path_hash: str  # SHA-1 of "{method}:{path}"
    tag: str
    summary: str
    spec_ids: list[str]
    idea_ids: list[str]
    contributors: list[str]
    call_count_30d: int
    last_called_at: Optional[datetime] = None
    status: Literal["active", "deprecated", "unknown"]


class MetaModuleNode(BaseModel):
    name: str
    path: str
    type: Literal["api_router", "service", "model", "adapter", "web_page", "web_component", "middleware", "other"]
    spec_ids: list[str]
    idea_ids: list[str]
    contributors: list[str]
    line_count: int
    last_modified: datetime
    test_file: Optional[str] = None


class MetaEndpointsResponse(BaseModel):
    total: int
    endpoints: list[MetaEndpointNode]
    generated_at: datetime


class MetaModulesResponse(BaseModel):
    total: int
    modules: list[MetaModuleNode]
    generated_at: datetime


class MetaSummaryResponse(BaseModel):
    system: str
    version: str
    generated_at: datetime
    counts: dict[str, int]
    traceability_score: float  # 0.0-1.0
    coverage: dict[str, int]


class MetaTraceResult(BaseModel):
    id: str
    type: Literal["spec", "idea"]
    title: str
    endpoints: list[dict[str, str]]  # list of {"method": method, "path": path}
    modules: list[dict[str, str]]    # list of {"name": name, "path": path}
    contributors: list[str]
    first_commit: Optional[datetime] = None
    call_count_30d: int
