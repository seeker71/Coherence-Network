"""Metadata self-discovery API routes.

Every endpoint, module, and Pydantic model in the system is a navigable concept
node in the codex.meta namespace. This router exposes the system's own structure
as first-class data.

Implements: meta-node system (Living Codex MetaNodeSystem)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.models.meta import (
    EndpointNode,
    MetaCoverageResponse,
    MetaEndpointsResponse,
    MetaGraphResponse,
    MetaModulesResponse,
    MetaSummaryResponse,
    MetaTypesResponse,
    ModuleNode,
)
from app.services import config_service, meta_service


class ConfigPatch(BaseModel):
    """Partial config update. Keys are merged into ~/.coherence-network/config.json."""
    updates: dict[str, Any]

router = APIRouter()


@router.get(
    "/meta/endpoints",
    response_model=MetaEndpointsResponse,
    summary="List all API endpoints as concept nodes",
    description=(
        "Returns every API endpoint registered in the system as a navigable "
        "concept node. Each node carries edges to the spec that defines it, "
        "the idea that spawned it, and the module that implements it."
    ),
    tags=["meta"],
)
async def get_meta_endpoints(request: Request) -> MetaEndpointsResponse:
    return meta_service.list_endpoints(request.app)


@router.get(
    "/meta/endpoints/{path_hash}",
    response_model=EndpointNode,
    summary="Single endpoint node by path_hash",
    description=(
        "Returns the endpoint node whose stable 8-char hex `path_hash` matches. "
        "Returns 404 if no endpoint has that hash."
    ),
    tags=["meta"],
)
async def get_meta_endpoint_by_hash(path_hash: str, request: Request) -> EndpointNode:
    node = meta_service.get_endpoint_by_hash(request.app, path_hash)
    if node is None:
        raise HTTPException(status_code=404, detail=f"endpoint not found: {path_hash}")
    return node


@router.get(
    "/meta/modules",
    response_model=MetaModulesResponse,
    summary="List all code modules as concept nodes",
    description=(
        "Returns every code module (routers, services, models) as a concept node "
        "with edges to the specs and ideas that created it."
    ),
    tags=["meta"],
)
async def get_meta_modules(request: Request) -> MetaModulesResponse:
    return meta_service.list_modules(request.app)


@router.get(
    "/meta/modules/{module_name}",
    response_model=ModuleNode,
    summary="Single code module node by name",
    description=(
        "Accepts either the dotted module path (`app.routers.ideas`) or the "
        "short last-segment name (`ideas`). Returns 404 if no module matches."
    ),
    tags=["meta"],
)
async def get_meta_module_by_name(module_name: str, request: Request) -> ModuleNode:
    node = meta_service.get_module_by_name(request.app, module_name)
    if node is None:
        raise HTTPException(status_code=404, detail=f"module not found: {module_name}")
    return node


@router.get(
    "/meta/coverage",
    response_model=MetaCoverageResponse,
    summary="Traceability coverage across the API surface",
    description=(
        "Returns total/traced endpoint counts, overall coverage percentage, "
        "module counts, and the list of untraced paths. Numbers are consistent "
        "with `/meta/endpoints` (same trace registry, same denominator)."
    ),
    tags=["meta"],
)
async def get_meta_coverage(request: Request) -> MetaCoverageResponse:
    return meta_service.get_coverage(request.app)


@router.get(
    "/meta/types",
    response_model=MetaTypesResponse,
    summary="List all Pydantic models as codex.meta/type nodes",
    description=(
        "Returns every Pydantic model in app.models as a TypeNode. "
        "Each node includes field definitions, required/optional status, "
        "and edges back to the endpoints that use it as request or response type. "
        "This is the codex.meta/type layer - the system introspecting its own schema."
    ),
    tags=["meta"],
)
async def get_meta_types(request: Request) -> MetaTypesResponse:
    return meta_service.list_types(request.app)


@router.get(
    "/meta/graph",
    response_model=MetaGraphResponse,
    summary="Full meta-node graph (nodes + edges)",
    description=(
        "Returns the complete meta-node graph: routes, modules, types, specs, "
        "and ideas as nodes; their relationships as typed edges. "
        "Suitable for graph visualization and traversal queries. "
        "node_type values: 'route', 'module', 'type', 'spec', 'idea'."
    ),
    tags=["meta"],
)
async def get_meta_graph(request: Request) -> MetaGraphResponse:
    return meta_service.get_graph(request.app)


@router.get(
    "/meta/docs",
    response_class=PlainTextResponse,
    summary="Auto-generated Markdown API reference",
    description=(
        "Returns a Markdown document describing every endpoint, type, and module "
        "in the system. Generated live from codex.meta introspection - always "
        "up to date with the running code."
    ),
    tags=["meta"],
)
async def get_meta_docs(request: Request) -> str:
    return meta_service.get_docs(request.app)


@router.get(
    "/meta/summary",
    response_model=MetaSummaryResponse,
    summary="System self-description coverage summary",
    description=(
        "Returns a brief overview of how well the system describes itself: "
        "how many endpoints are traced to specs and ideas, how many types "
        "are introspected, and overall spec coverage percentage."
    ),
    tags=["meta"],
)
async def get_meta_summary(request: Request) -> MetaSummaryResponse:
    return meta_service.get_summary(request.app)


# ---------------------------------------------------------------------------
# Editable config (user config at ~/.coherence-network/config.json)
# ---------------------------------------------------------------------------


@router.get(
    "/config",
    summary="Read the user-editable config",
    tags=["config"],
)
async def get_config() -> dict[str, Any]:
    """Return the user-editable config from ~/.coherence-network/config.json.

    This is the file that overrides defaults. Secrets are excluded.
    """
    return config_service.get_editable_config()


@router.patch(
    "/config",
    summary="Update user-editable config",
    tags=["config"],
)
async def patch_config(body: ConfigPatch) -> dict[str, Any]:
    """Merge updates into ~/.coherence-network/config.json.

    Sensitive keys (api_key, github_token, database_url) are filtered out.
    Returns the updated config.
    """
    return config_service.update_editable_config(body.updates)
