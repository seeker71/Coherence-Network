"""Metadata self-discovery API routes.

Every endpoint and module in the system is a navigable concept node.
This router exposes the system's own structure as first-class data.

Implements: metadata-self-discovery (Living Codex MetaNodeSystem)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.models.meta import (
    MetaEndpointNode,
    MetaEndpointsResponse,
    MetaModulesResponse,
    MetaSummaryResponse,
    MetaTraceResult,
)
from app.services import meta_service

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
async def get_meta_endpoints(request: Request, tag: str | None = None) -> MetaEndpointsResponse:
    app = request.app
    response = meta_service.list_endpoints(app)
    if tag:
        response.endpoints = [ep for ep in response.endpoints if ep.tag == tag]
        response.total = len(response.endpoints)
    return response


@router.get(
    "/meta/endpoints/{path_hash}",
    response_model=MetaEndpointNode,
    summary="Get single endpoint node",
    description="Returns detailed metadata for a single API endpoint identified by its method:path hash.",
    tags=["meta"],
)
async def get_meta_endpoint(request: Request, path_hash: str) -> MetaEndpointNode:
    app = request.app
    endpoint = meta_service.get_endpoint_by_hash(app, path_hash)
    if not endpoint:
        raise HTTPException(status_code=404, detail=f"Endpoint hash {path_hash} not found")
    return endpoint


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
    app = request.app
    return meta_service.list_modules(app)


@router.get(
    "/meta/summary",
    response_model=MetaSummaryResponse,
    summary="System self-description coverage summary",
    description=(
        "Returns a brief overview of how well the system describes itself — "
        "how many endpoints are traced to specs and ideas."
    ),
    tags=["meta"],
)
async def get_meta_summary(request: Request) -> MetaSummaryResponse:
    app = request.app
    return meta_service.get_summary(app)


@router.get(
    "/meta/trace/{entity_id}",
    response_model=MetaTraceResult,
    summary="Trace idea/spec to its artifacts",
    description="Returns all endpoints and modules linked to a specific idea or spec ID.",
    tags=["meta"],
)
async def get_meta_trace(request: Request, entity_id: str) -> MetaTraceResult:
    app = request.app
    result = meta_service.trace_id(app, entity_id)
    if not result.endpoints and not result.modules:
         raise HTTPException(status_code=404, detail=f"No artifacts found for ID {entity_id}")
    return result
