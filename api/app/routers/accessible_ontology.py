"""Accessible ontology API — plain-language concepts contributors add without graph jargon."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from app.services import accessible_ontology_service as ao

router = APIRouter()

VALID_STATUSES = {"pending", "confirmed", "deprecated"}


class OntologyConceptCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=2000)
    domains: list[str] = Field(default_factory=list)
    contributor_id: Optional[str] = None

    @field_validator("domains")
    @classmethod
    def at_most_five_domains(cls, v: list[str]) -> list[str]:
        if len(v) > 5:
            raise ValueError("domains must have at most 5 entries")
        return v


class OntologyConceptPatch(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    body: Optional[str] = Field(None, min_length=1, max_length=2000)
    domains: Optional[list[str]] = None
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class OntologyResonateRequest(BaseModel):
    contributor_id: Optional[str] = None


@router.post("/ontology/concepts", status_code=201)
def create_concept(payload: OntologyConceptCreate) -> dict[str, Any]:
    return ao.create_concept(
        payload.title,
        payload.body,
        payload.domains,
        payload.contributor_id,
    )


@router.get("/ontology/concepts")
def list_concepts(
    domain: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
) -> list[dict[str, Any]]:
    return ao.list_concepts(domain, status, search)


@router.get("/ontology/concepts/{concept_id}")
def get_concept(concept_id: str) -> dict[str, Any]:
    out = ao.get_concept(concept_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    return out


@router.patch("/ontology/concepts/{concept_id}")
def patch_concept(concept_id: str, payload: OntologyConceptPatch) -> dict[str, Any]:
    out = ao.patch_concept(
        concept_id,
        payload.title,
        payload.body,
        payload.domains,
        payload.status,
    )
    if out is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    return out


@router.delete("/ontology/concepts/{concept_id}", status_code=200)
def delete_concept(concept_id: str) -> dict[str, str]:
    if not ao.delete_concept(concept_id):
        raise HTTPException(status_code=404, detail="Concept not found")
    return {"deleted": concept_id}


@router.post("/ontology/concepts/{concept_id}/resonate", status_code=200)
def resonate_concept(concept_id: str, payload: OntologyResonateRequest) -> dict[str, Any]:
    out = ao.resonate(concept_id, payload.contributor_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    return out


@router.get("/ontology/concepts/{concept_id}/related")
def get_related(
    concept_id: str,
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
) -> list[dict[str, Any]]:
    out = ao.get_related(concept_id, min_confidence)
    if out is None:
        raise HTTPException(status_code=404, detail="Concept not found")
    return out


@router.get("/ontology/garden")
def get_garden(limit: int = Query(default=200, ge=1, le=500)) -> dict[str, Any]:
    return ao.get_garden_payload(limit=limit)


@router.get("/ontology/stats")
def get_ontology_stats() -> dict[str, Any]:
    return ao.get_stats()


@router.get("/ontology/domains")
def get_domains() -> list[dict[str, Any]]:
    return ao.get_domains_list()


@router.get("/ontology/activity")
def get_activity(since: Optional[str] = None) -> list[dict[str, Any]]:
    return ao.get_activity(since)
