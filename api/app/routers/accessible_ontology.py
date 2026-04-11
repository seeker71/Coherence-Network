"""Accessible ontology API — non-technical contributors extend the ontology naturally.

Design principles:
- No IDs required: contributors use plain names and descriptions.
- Plain-language relationships: "X helps with Y", "X is a kind of Y".
- Review queue: suggestions are pending until a maintainer approves.
- Endorsements: any user can signal which concepts matter most.

Endpoints
---------
POST   /ontology/suggest                      — suggest a new concept
GET    /ontology/suggestions                  — list concept suggestions
GET    /ontology/suggestions/{id}             — get one suggestion
POST   /ontology/suggestions/{id}/approve     — approve (promotes to live ontology)
POST   /ontology/suggestions/{id}/reject      — reject with a note

POST   /ontology/suggest-relationship         — suggest a relationship in plain language
GET    /ontology/relationship-suggestions     — list relationship suggestions
POST   /ontology/relationship-suggestions/{id}/review — approve or reject

POST   /ontology/endorse/{concept_id}         — upvote a concept
GET    /ontology/endorse/{concept_id}         — get endorsement count
GET    /ontology/top-endorsed                 — concepts ranked by endorsements
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models.accessible_ontology import (
    AccessibleConceptResponse,
    GardenView,
    OntologyConceptPatch,
    OntologyContributionStats,
    PlainLanguageContribution,
)
from app.services import accessible_ontology_service as svc

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class SuggestConceptRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120, description="Plain concept name")
    plain_description: str = Field(
        ..., min_length=5, max_length=2000, description="Describe it in your own words"
    )
    example_use: str = Field(
        default="",
        max_length=500,
        description="Optional: a sentence showing how you'd use this concept",
    )
    related_to: list[str] = Field(
        default_factory=list,
        description="Optional list of existing concept IDs or names this relates to",
    )
    contributor: str = Field(default="anonymous", max_length=120)


class ApproveConceptRequest(BaseModel):
    reviewer: str = Field(default="maintainer", max_length=120)
    review_note: str = Field(default="", max_length=1000)
    final_id: str | None = Field(
        default=None,
        description="Override the auto-generated concept ID",
    )
    final_name: str | None = Field(
        default=None,
        description="Override the suggested concept name",
    )


class RejectRequest(BaseModel):
    reviewer: str = Field(default="maintainer", max_length=120)
    review_note: str = Field(default="", max_length=1000)


class SuggestRelationshipRequest(BaseModel):
    from_concept_name: str = Field(
        ..., min_length=1, max_length=120, description="Source concept (name or ID)"
    )
    to_concept_name: str = Field(
        ..., min_length=1, max_length=120, description="Target concept (name or ID)"
    )
    plain_relationship: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="How are they related? E.g. 'leads to', 'is a type of', 'conflicts with'",
    )
    example_sentence: str = Field(
        default="",
        max_length=500,
        description="Optional: a sentence using both concepts together",
    )
    contributor: str = Field(default="anonymous", max_length=120)


class ReviewRelationshipRequest(BaseModel):
    action: str = Field(..., description="'approve' or 'reject'")
    reviewer: str = Field(default="maintainer", max_length=120)
    review_note: str = Field(default="", max_length=1000)


class EndorseRequest(BaseModel):
    contributor: str = Field(default="anonymous", max_length=120)


def _legacy_title(plain_text: str, explicit_title: str | None) -> str:
    title = str(explicit_title or "").strip()
    if title:
        return title
    words = [part for part in plain_text.strip().split() if part]
    return " ".join(words[:8]) or "Untitled concept"


def _legacy_status(api_status: str) -> str:
    if api_status == "confirmed":
        return "placed"
    if api_status == "deprecated":
        return "orphan"
    return "pending"


def _api_status(web_status: str | None) -> str | None:
    if web_status == "placed":
        return "confirmed"
    if web_status == "orphan":
        return "deprecated"
    if web_status == "pending":
        return "pending"
    return None


def _legacy_response(record: dict, *, index: int = 0) -> AccessibleConceptResponse:
    domains = record.get("domains") if isinstance(record.get("domains"), list) else []
    inferred = record.get("inferred_relations") if isinstance(record.get("inferred_relations"), list) else []
    cluster = str(domains[0] if domains else "general")
    return AccessibleConceptResponse(
        id=str(record.get("id") or ""),
        title=str(record.get("title") or "Untitled concept"),
        plain_text=str(record.get("body") or ""),
        contributor_id=str(record.get("contributor_id") or "anonymous"),
        domains=[str(item) for item in domains],
        status=_legacy_status(str(record.get("status") or "pending")),
        inferred_relationships=[
            {
                "concept_id": str(row.get("concept_id") or row.get("target_id") or ""),
                "concept_name": str(row.get("concept_name") or row.get("target_label") or ""),
                "relationship_type": str(row.get("relationship_type") or row.get("type") or "related_to"),
                "confidence": float(row.get("confidence") or 0.0),
                "reason": str(row.get("reason") or ""),
            }
            for row in inferred
            if isinstance(row, dict)
        ],
        garden_position={"cluster": cluster, "x": float(index % 12), "y": float(index // 12)},
        core_concept_match=None,
        created_at=str(record.get("created_at") or ""),
        updated_at=str(record.get("updated_at") or ""),
    )


# ---------------------------------------------------------------------------
# Legacy contribution endpoints
# ---------------------------------------------------------------------------


@router.post("/ontology/contribute", status_code=201, tags=["ontology"], summary="Contribute Concept")
async def contribute_concept(body: PlainLanguageContribution) -> AccessibleConceptResponse:
    record = svc.create_concept(
        title=_legacy_title(body.plain_text, body.title),
        body=body.plain_text,
        domains=body.domains,
        contributor_id=body.contributor_id,
    )
    return _legacy_response(record)


@router.get("/ontology/contributions", tags=["ontology"], summary="List Contributions")
async def list_contributions(
    domain: str | None = Query(default=None),
    status: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> dict[str, object]:
    api_status = _api_status(status)
    items = svc.list_concepts(domain=domain, status=api_status, search=search)
    payload = [_legacy_response(item, index=index).model_dump() for index, item in enumerate(items)]
    return {"items": payload, "total": len(payload)}


@router.get("/ontology/contributions/{concept_id}", tags=["ontology"], summary="Get Contribution")
async def get_contribution(concept_id: str) -> AccessibleConceptResponse:
    record = svc.get_concept(concept_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return _legacy_response(record)


@router.patch("/ontology/contributions/{concept_id}", tags=["ontology"], summary="Patch Contribution")
async def patch_contribution(concept_id: str, body: OntologyConceptPatch) -> AccessibleConceptResponse:
    record = svc.patch_concept(
        concept_id,
        title=body.title,
        body=body.plain_text,
        domains=body.domains,
        status=_api_status(body.status),
    )
    if not record:
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")
    return _legacy_response(record)


@router.delete("/ontology/contributions/{concept_id}", status_code=204, tags=["ontology"], summary="Delete Contribution")
async def delete_contribution(concept_id: str) -> None:
    if not svc.delete_concept(concept_id):
        raise HTTPException(status_code=404, detail=f"Concept '{concept_id}' not found")


@router.get("/ontology/edges", tags=["ontology"], summary="List Ontology Edges")
async def list_ontology_edges() -> dict[str, list[dict[str, object]]]:
    edges: list[dict[str, object]] = []
    for concept in svc.list_concepts(domain=None, status=None, search=None):
        for relation in concept.get("inferred_relations") or []:
            if not isinstance(relation, dict):
                continue
            edges.append(relation)
    return {"edges": edges}


@router.get("/ontology/garden", tags=["ontology"], summary="Get Ontology Garden")
async def get_ontology_garden(limit: int = Query(default=200, ge=1, le=500)) -> GardenView:
    return GardenView(**svc.get_garden_payload(limit=limit))


@router.get("/ontology/stats", tags=["ontology"], summary="Get Ontology Stats")
async def get_ontology_stats() -> OntologyContributionStats:
    return OntologyContributionStats(**svc.get_stats())


# ---------------------------------------------------------------------------
# Concept suggestion endpoints
# ---------------------------------------------------------------------------


@router.post("/ontology/suggest", status_code=201, tags=["ontology"], summary="Suggest a new concept in plain language. No technical knowledge needed")
async def suggest_concept(body: SuggestConceptRequest):
    """Suggest a new concept in plain language. No technical knowledge needed.

    The suggestion enters a review queue. A maintainer approves or rejects it.
    Approved suggestions are automatically added to the live ontology.
    """
    return svc.suggest_concept(
        name=body.name,
        plain_description=body.plain_description,
        contributor=body.contributor,
        example_use=body.example_use,
        related_to=body.related_to,
    )


@router.get("/ontology/suggestions", tags=["ontology"], summary="List concept suggestions. Filter by status to see the review queue")
async def list_concept_suggestions(
    status: str | None = Query(default=None, description="Filter by status: pending, approved, rejected"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List concept suggestions. Filter by status to see the review queue."""
    if status and status not in ("pending", "approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be pending, approved, or rejected")
    return svc.list_concept_suggestions(status=status, limit=limit, offset=offset)


@router.get("/ontology/suggestions/{suggestion_id}", tags=["ontology"], summary="Get a single concept suggestion by ID")
async def get_concept_suggestion(suggestion_id: str):
    """Get a single concept suggestion by ID."""
    record = svc.get_concept_suggestion(suggestion_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Suggestion '{suggestion_id}' not found")
    return record


@router.post("/ontology/suggestions/{suggestion_id}/approve", tags=["ontology"], summary="Approve a concept suggestion and promote it to the live ontology")
async def approve_concept_suggestion(suggestion_id: str, body: ApproveConceptRequest):
    """Approve a concept suggestion and promote it to the live ontology.

    The concept becomes immediately available in the ontology after approval.
    """
    try:
        return svc.approve_concept_suggestion(
            suggestion_id,
            reviewer=body.reviewer,
            review_note=body.review_note,
            final_id=body.final_id,
            final_name=body.final_name,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/ontology/suggestions/{suggestion_id}/reject", tags=["ontology"], summary="Reject a concept suggestion with an optional explanatory note")
async def reject_concept_suggestion(suggestion_id: str, body: RejectRequest):
    """Reject a concept suggestion with an optional explanatory note."""
    try:
        return svc.reject_concept_suggestion(
            suggestion_id,
            reviewer=body.reviewer,
            review_note=body.review_note,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ---------------------------------------------------------------------------
# Relationship suggestion endpoints
# ---------------------------------------------------------------------------


@router.post("/ontology/suggest-relationship", status_code=201, tags=["ontology"], summary="Suggest a relationship between two concepts in plain language")
async def suggest_relationship(body: SuggestRelationshipRequest):
    """Suggest a relationship between two concepts in plain language.

    Example: from="Breath" to="Water" plain_relationship="flows into"
    No need to know formal relationship type IDs.
    """
    return svc.suggest_relationship(
        from_concept_name=body.from_concept_name,
        to_concept_name=body.to_concept_name,
        plain_relationship=body.plain_relationship,
        contributor=body.contributor,
        example_sentence=body.example_sentence,
    )


@router.get("/ontology/relationship-suggestions", tags=["ontology"], summary="List relationship suggestions pending review")
async def list_relationship_suggestions(
    status: str | None = Query(default=None, description="Filter: pending, approved, rejected"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List relationship suggestions pending review."""
    if status and status not in ("pending", "approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be pending, approved, or rejected")
    return svc.list_relationship_suggestions(status=status, limit=limit, offset=offset)


@router.post(
    "/ontology/relationship-suggestions/{suggestion_id}/review",
    tags=["ontology"],
    summary="Approve or reject a relationship suggestion",
)
async def review_relationship_suggestion(suggestion_id: str, body: ReviewRelationshipRequest):
    """Approve or reject a relationship suggestion."""
    try:
        return svc.review_relationship_suggestion(
            suggestion_id,
            action=body.action,
            reviewer=body.reviewer,
            review_note=body.review_note,
        )
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Endorsement endpoints
# ---------------------------------------------------------------------------


@router.post("/ontology/endorse/{concept_id}", status_code=200, tags=["ontology"], summary="Endorse (upvote) a concept to signal its importance to the community")
async def endorse_concept(concept_id: str, body: EndorseRequest):
    """Endorse (upvote) a concept to signal its importance to the community.

    Any contributor can endorse any existing concept. Duplicate endorsements
    from the same contributor are ignored.
    """
    try:
        return svc.endorse_concept(concept_id, contributor=body.contributor)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/ontology/endorse/{concept_id}", tags=["ontology"], summary="Get the endorsement count and list of endorsers for a concept")
async def get_endorsements(concept_id: str):
    """Get the endorsement count and list of endorsers for a concept."""
    try:
        return svc.get_endorsements(concept_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/ontology/top-endorsed", tags=["ontology"], summary="List concepts ranked by number of endorsements")
async def top_endorsed(limit: int = Query(default=20, ge=1, le=100)):
    """List concepts ranked by number of endorsements.

    Useful for surfacing which concepts the community finds most relevant.
    """
    return svc.top_endorsed(limit=limit)
