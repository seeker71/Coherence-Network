"""Renderer Router — pluggable asset renderer registry.

Endpoints:
  POST /api/renderers/register           - Register a renderer for MIME types
  GET  /api/renderers                    - List registered renderers
  GET  /api/renderers/for/{mime_type}    - Find best renderer for a MIME type
  GET  /api/renderers/{renderer_id}      - Get one renderer

See specs/asset-renderer-plugin.md (R2, R3, R7, R9).

Storage is an in-process registry for this initial slice. Graph-backed
storage is a follow-up once the router contract is exercised in tests
and web clients; the spec's source map names graph storage as the
target but doesn't require it to ship in the first PR.
"""

from __future__ import annotations

from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query

from app.models.renderer import Renderer, RendererCreate

router = APIRouter(prefix="/renderers", tags=["renderers"])


# In-process registry. Thread-safe because FastAPI workers don't share memory
# and this is the first slice before graph persistence.
_REGISTRY: Dict[str, Renderer] = {}


@router.post(
    "/register",
    response_model=Renderer,
    status_code=201,
    summary="Register a renderer for one or more MIME types",
)
async def register_renderer(body: RendererCreate) -> Renderer:
    """Register a new renderer. Rejects duplicate IDs with 409.

    cc_split validation (must sum to 1.0) and bundle-size validation
    (≤ 500KB) are enforced by the Pydantic models at request parse time.
    """
    if body.id in _REGISTRY:
        raise HTTPException(
            status_code=409,
            detail=f"renderer with id '{body.id}' already registered",
        )
    renderer = Renderer(**body.model_dump())
    _REGISTRY[renderer.id] = renderer
    return renderer


@router.get("", response_model=List[Renderer], summary="List all registered renderers")
async def list_renderers(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> List[Renderer]:
    """List registered renderers, paginated by insertion order."""
    items = list(_REGISTRY.values())
    return items[offset : offset + limit]


@router.get(
    "/for/{mime_type:path}",
    response_model=Renderer,
    summary="Find the best renderer for a MIME type",
)
async def get_renderer_for_mime(mime_type: str) -> Renderer:
    """Return the highest-version renderer that handles this MIME type.

    Returns 404 if no renderer is registered for the type — the web client
    should then fall back to a generic download surface per spec R3.
    """
    candidates = [r for r in _REGISTRY.values() if mime_type in r.mime_types]
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail=f"no renderer registered for mime type '{mime_type}'",
        )
    # Highest version wins (lexicographic; spec doesn't define strict semver yet).
    return max(candidates, key=lambda r: r.version)


@router.get(
    "/{renderer_id}",
    response_model=Renderer,
    summary="Get a single renderer by id",
)
async def get_renderer(renderer_id: str) -> Renderer:
    if renderer_id not in _REGISTRY:
        raise HTTPException(
            status_code=404,
            detail=f"renderer '{renderer_id}' not found",
        )
    return _REGISTRY[renderer_id]


def _reset_registry_for_tests() -> None:
    """Testing hook. Not part of the public API."""
    _REGISTRY.clear()
