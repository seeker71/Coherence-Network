"""Metadata self-discovery API routes.

Every endpoint and module in the system is a navigable concept node.
This router exposes the system's own structure as first-class data.

Implements: metadata-self-discovery (Living Codex MetaNodeSystem)
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.models.meta import (
    MetaEndpointsResponse,
    MetaModulesResponse,
    MetaSummaryResponse,
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
async def get_meta_endpoints(request: Request) -> MetaEndpointsResponse:
    app = request.app
    return meta_service.list_endpoints(app)


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
