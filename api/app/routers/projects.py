"""Project and search routes — spec 008, 019, 020."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.adapters.graph_store import GraphStore
from app.models.coherence import CoherenceResponse
from app.models.error import ErrorDetail
from app.models.project import Project
from app.services.coherence_service import compute_coherence

router = APIRouter()


def get_graph_store(request: Request) -> GraphStore:
    """Dependency: GraphStore from app state."""
    return request.app.state.graph_store


@router.get(
    "/projects/{ecosystem}/{name}",
    response_model=Project,
    responses={404: {"description": "Project not found", "model": ErrorDetail}},
)
async def get_project(
    ecosystem: str,
    name: str,
    store: GraphStore = Depends(get_graph_store),
):
    """Return project by ecosystem and name."""
    proj = store.get_project(ecosystem, name)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


@router.get(
    "/projects/{ecosystem}/{name}/coherence",
    response_model=CoherenceResponse,
    responses={404: {"description": "Project not found", "model": ErrorDetail}},
)
async def get_project_coherence(
    ecosystem: str,
    name: str,
    store: GraphStore = Depends(get_graph_store),
):
    """Return coherence score and components for project — spec 020."""
    proj = store.get_project(ecosystem, name)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    data = compute_coherence(store, proj)
    return CoherenceResponse(**data)


@router.get("/search")
async def search(
    q: str,
    limit: int = 20,
    store: GraphStore = Depends(get_graph_store),
):
    """Search projects by name or description."""
    results = store.search(q, limit=min(limit, 100))
    return {"results": results, "total": len(results)}


@router.get("/")
async def root():
    """Return API info."""
    return {
        "name": "Coherence Network API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
        "message": "Welcome to Coherence Network API"
    }
