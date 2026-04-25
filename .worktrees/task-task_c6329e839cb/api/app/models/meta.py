"""Models for metadata self-discovery - endpoint, module, and type concept nodes.

Every API route is a codex.meta/route node.
Every Pydantic model is a codex.meta/type node.
Every code module is a codex.meta/module node.
The system introspects itself and exposes its full structure as navigable data.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class EndpointEdge(BaseModel):
    type: str  # "implements_spec", "traces_idea", "defined_in_module", "uses_type"
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
    request_model: Optional[str] = None  # codex.meta/type id for request body
    response_model: Optional[str] = None  # codex.meta/type id for response
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


# Type / Model nodes


class TypeField(BaseModel):
    name: str
    type_str: str  # Python type annotation as string
    required: bool
    default: Optional[Any] = None
    description: Optional[str] = None


class TypeNode(BaseModel):
    """A Pydantic model exposed as a codex.meta/type concept node."""

    id: str  # e.g. "codex.meta/type/IdeaModel"
    name: str  # class name
    module: str  # dotted module path
    fields: list[TypeField] = []
    used_in_endpoints: list[str] = []  # endpoint node IDs (request or response)
    base_classes: list[str] = []
    edges: list[EndpointEdge] = []


# Full graph


class MetaGraphNode(BaseModel):
    id: str
    label: str
    node_type: str  # "route", "module", "type", "spec", "idea"
    properties: dict[str, Any] = {}


class MetaGraphEdge(BaseModel):
    source: str
    target: str
    edge_type: str


class MetaGraphResponse(BaseModel):
    nodes: list[MetaGraphNode]
    edges: list[MetaGraphEdge]
    node_count: int
    edge_count: int


# Response wrappers


class MetaEndpointsResponse(BaseModel):
    total: int
    endpoints: list[EndpointNode]


class MetaModulesResponse(BaseModel):
    total: int
    modules: list[ModuleNode]


class MetaTypesResponse(BaseModel):
    total: int
    types: list[TypeNode]


class MetaSummaryResponse(BaseModel):
    endpoint_count: int
    module_count: int
    type_count: int
    traced_count: int  # endpoints with spec/idea links
    spec_coverage: float  # fraction of endpoints linked to a spec
