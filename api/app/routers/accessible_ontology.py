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


# ---------------------------------------------------------------------------
# Concept suggestion endpoints
# ---------------------------------------------------------------------------


@router.post("/ontology/suggest", status_code=201, tags=["ontology"])
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


@router.get("/ontology/suggestions", tags=["ontology"])
async def list_concept_suggestions(
    status: str | None = Query(default=None, description="Filter by status: pending, approved, rejected"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """List concept suggestions. Filter by status to see the review queue."""
    if status and status not in ("pending", "approved", "rejected"):
        raise HTTPException(status_code=400, detail="status must be pending, approved, or rejected")
    return svc.list_concept_suggestions(status=status, limit=limit, offset=offset)


@router.get("/ontology/suggestions/{suggestion_id}", tags=["ontology"])
async def get_concept_suggestion(suggestion_id: str):
    """Get a single concept suggestion by ID."""
    record = svc.get_concept_suggestion(suggestion_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Suggestion '{suggestion_id}' not found")
    return record


@router.post("/ontology/suggestions/{suggestion_id}/approve", tags=["ontology"])
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


@router.post("/ontology/suggestions/{suggestion_id}/reject", tags=["ontology"])
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


@router.post("/ontology/suggest-relationship", status_code=201, tags=["ontology"])
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


@router.get("/ontology/relationship-suggestions", tags=["ontology"])
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


@router.post("/ontology/endorse/{concept_id}", status_code=200, tags=["ontology"])
async def endorse_concept(concept_id: str, body: EndorseRequest):
    """Endorse (upvote) a concept to signal its importance to the community.

    Any contributor can endorse any existing concept. Duplicate endorsements
    from the same contributor are ignored.
    """
    try:
        return svc.endorse_concept(concept_id, contributor=body.contributor)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/ontology/endorse/{concept_id}", tags=["ontology"])
async def get_endorsements(concept_id: str):
    """Get the endorsement count and list of endorsers for a concept."""
    try:
        return svc.get_endorsements(concept_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/ontology/top-endorsed", tags=["ontology"])
async def top_endorsed(limit: int = Query(default=20, ge=1, le=100)):
    """List concepts ranked by number of endorsements.

    Useful for surfacing which concepts the community finds most relevant.
    """
    return svc.top_endorsed(limit=limit)
