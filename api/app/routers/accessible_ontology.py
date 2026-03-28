"""Accessible ontology router — plain-language concept submission for non-technical contributors.

Endpoints:
  POST   /api/ontology/contribute          Submit a plain-language concept
  GET    /api/ontology/contributions       List all contributions (paged, filtered)
  GET    /api/ontology/contributions/{id}  Get a single contribution
  PATCH  /api/ontology/contributions/{id}  Update a contribution
  DELETE /api/ontology/contributions/{id}  Remove a contribution
  GET    /api/ontology/garden              Garden-view aggregation for UI
  GET    /api/ontology/stats               Observability stats
  GET    /api/ontology/edges               List inferred relationships
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.accessible_ontology import (
    PlainLanguageContribution,
    OntologyConceptPatch,
)
from app.services import accessible_ontology_service as svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Contribution CRUD
# ---------------------------------------------------------------------------

@router.post("/ontology/contribute", status_code=201, tags=["ontology"])
async def submit_contribution(body: PlainLanguageContribution):
    """Submit a plain-language concept to the ontology.

    No graph theory knowledge required.  The system infers where the concept
    fits and returns plain-language placement info alongside a garden position.
    """
    # Idempotency: detect duplicate before insertion by checking if title+contributor combo exists
    existing = svc.list_contributions(contributor_id=body.contributor_id)
    for item in existing["items"]:
        if item["title"].lower() == (body.title or "").lower() and body.title:
            raise HTTPException(status_code=409, detail="Concept already contributed by this user")

    result = svc.submit_plain_language(
        plain_text=body.plain_text,
        contributor_id=body.contributor_id,
        domains=body.domains,
        title=body.title,
        view_preference=body.view_preference,
    )
    return result


@router.get("/ontology/contributions", tags=["ontology"])
async def list_contributions(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    domain: str | None = Query(default=None, description="Filter by domain"),
    status: str | None = Query(default=None, description="Filter by status: pending|placed|orphan"),
    contributor_id: str | None = Query(default=None, description="Filter by contributor"),
):
    """List ontology contributions with optional filters."""
    return svc.list_contributions(
        limit=limit,
        offset=offset,
        domain=domain,
        status=status,
        contributor_id=contributor_id,
    )


@router.get("/ontology/contributions/{concept_id}", tags=["ontology"])
async def get_contribution(concept_id: str):
    """Get a single ontology contribution by ID."""
    record = svc.get_contribution(concept_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Contribution '{concept_id}' not found")
    return record


@router.patch("/ontology/contributions/{concept_id}", tags=["ontology"])
async def patch_contribution(concept_id: str, body: OntologyConceptPatch):
    """Update title, plain_text, domains, or status of a contribution."""
    result = svc.patch_contribution(concept_id, body.model_dump(exclude_none=True))
    if result is None:
        raise HTTPException(status_code=404, detail=f"Contribution '{concept_id}' not found")
    return result


@router.delete("/ontology/contributions/{concept_id}", status_code=204, tags=["ontology"])
async def delete_contribution(concept_id: str):
    """Remove a contribution and its inferred edges."""
    if not svc.delete_contribution(concept_id):
        raise HTTPException(status_code=404, detail=f"Contribution '{concept_id}' not found")


# ---------------------------------------------------------------------------
# Garden view & stats
# ---------------------------------------------------------------------------

@router.get("/ontology/garden", tags=["ontology"])
async def garden_view(limit: int = Query(default=200, ge=1, le=1000)):
    """Return garden-view data for the non-technical UI.

    Concepts are organised into clusters by domain, each with an x/y position
    and a relationship count.  The UI can render these as cards, flowers, or
    graph nodes depending on the viewer's preference.
    """
    return svc.garden_view(limit=limit)


@router.get("/ontology/stats", tags=["ontology"])
async def get_stats():
    """Return statistics proving the accessible-ontology feature is working.

    Includes placement_rate (fraction of contributions the system successfully
    placed in the graph), contributor count, domain diversity, and edge count.
    """
    return svc.get_stats()


@router.get("/ontology/edges", tags=["ontology"])
async def list_edges(
    concept_id: str | None = Query(default=None, description="Filter edges by concept"),
    limit: int = Query(default=100, ge=1, le=500),
):
    """List inferred relationships between accessible ontology contributions."""
    return {"edges": svc.get_inferred_edges(concept_id=concept_id, limit=limit)}
