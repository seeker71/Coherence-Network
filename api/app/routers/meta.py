"""Metadata self-discovery API routes.

Every endpoint, module, and Pydantic model in the system is a navigable concept
node in the codex.meta namespace. This router exposes the system's own structure
as first-class data.

Implements: meta-node system (Living Codex MetaNodeSystem)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app.models.meta import (
    MetaEndpointsResponse,
    MetaGraphResponse,
    MetaModulesResponse,
    MetaSummaryResponse,
    MetaTypesResponse,
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
