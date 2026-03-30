"""Models for metadata self-discovery — endpoint and module concept nodes."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class EndpointEdge(BaseModel):
    type: str  # "implements_spec", "traces_idea", "defined_in_module"
    target_id: str
    target_label: Optional[str] = None


class EndpointNode(BaseModel):
    id: str  # e.g. "GET /api/ideas"
    method: str
    path: str
    name: str
    summary: Optional[str] = None
    tags: list[str] = []
    spec_id: Optional[str] = None
    idea_id: Optional[str] = None
    module: Optional[str] = None
    edges: list[EndpointEdge] = []


class ModuleNode(BaseModel):
    id: str  # module dotted path e.g. "app.routers.ideas"
    name: str
    module_type: str  # "router", "service", "model", "middleware"
    file_path: Optional[str] = None
    spec_ids: list[str] = []
    idea_ids: list[str] = []
    endpoint_count: int = 0
    edges: list[EndpointEdge] = []


class MetaEndpointsResponse(BaseModel):
    total: int
    endpoints: list[EndpointNode]


class MetaModulesResponse(BaseModel):
    total: int
    modules: list[ModuleNode]


class MetaSummaryResponse(BaseModel):
    endpoint_count: int
    module_count: int
    traced_count: int  # endpoints with spec/idea links
    spec_coverage: float  # fraction of endpoints linked to a spec
