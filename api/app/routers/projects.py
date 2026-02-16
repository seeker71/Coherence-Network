"""Project + search API routes (spec 019, 020).

These endpoints are required for the public web E2E flow:
- /search -> calls GET /api/search
- /project/[ecosystem]/[name] -> calls GET /api/projects/... and /coherence
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.adapters.graph_store import GraphStore
from app.models.coherence import CoherenceResponse
from app.models.project import Project, ProjectSummary
from app.services import coherence_service

router = APIRouter()


def get_store(request: Request) -> GraphStore:
    return request.app.state.graph_store


@router.get("/search")
async def search_projects(
    q: str = Query(..., min_length=1, description="Search query (substring match)."),
    limit: int = Query(20, ge=1, le=200),
    store: GraphStore = Depends(get_store),
) -> dict:
    results: list[ProjectSummary] = store.search(q, limit=limit)
    return {"results": [r.model_dump(mode="json") for r in results], "total": len(results)}


@router.get("/projects/{ecosystem}/{name}", response_model=Project)
async def get_project(ecosystem: str, name: str, store: GraphStore = Depends(get_store)) -> Project:
    project = store.get_project(ecosystem, name)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects/{ecosystem}/{name}/coherence", response_model=CoherenceResponse)
async def get_project_coherence(
    ecosystem: str, name: str, store: GraphStore = Depends(get_store)
) -> CoherenceResponse:
    project = store.get_project(ecosystem, name)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    payload = coherence_service.compute_coherence(store, project)
    return CoherenceResponse(**payload)

