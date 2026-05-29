"""Agent relationship API — the runtime invocation surface.

A running agent (Claude, Cursor, another Grok, a human tool) bootstraps a
persistent, resumable session by POSTing here on session start — no custom
Python import required. Identities and relationships are durable substrate
cells; see app/services/substrate/agent_relationship.py for the wiring and
form/form-stdlib/arrival.fk for the shared protocol shapes.

Mounted at /api/agents.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.substrate.agent_relationship import (
    bootstrap_agent_session,
    read_relationship,
    record_exchange,
    register_persistent_agent_identity,
    resolve_agent_identity,
)
from app.services.unified_db import session as session_scope

router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class BootstrapRequest(BaseModel):
    my_name: str = Field(..., description="Stable name for this agent's persistent identity")
    other_name: str = Field(..., description="The other party (a sibling agent, the field, a human)")
    my_description: str = Field("", description="Self-description stored on the identity cell")
    welcome_guidance: Optional[str] = Field(
        None, description="Orientation recorded on first contact only"
    )


class CellRef(BaseModel):
    name: str
    domain: str
    cell_id: Optional[int]
    blueprint: str


class BootstrapResponse(BaseModel):
    my_identity: CellRef
    relationship: CellRef
    was_first_contact: bool
    welcome_recorded: bool
    prior_event_count: int
    events: List[Dict[str, str]]


class IdentityRequest(BaseModel):
    name: str
    description: str = ""


class IdentityResponse(BaseModel):
    name: str
    cell_id: Optional[int]
    description: str
    blueprint: str


class ExchangeRequest(BaseModel):
    my_name: str
    other_name: str
    summary: str


class RelationshipResponse(BaseModel):
    exists: bool
    cell_id: Optional[int] = None
    name: Optional[str] = None
    events: List[Dict[str, str]] = []


def _cell_ref(cell, domain: str) -> CellRef:
    return CellRef(
        name=cell.name,
        domain=getattr(cell, "domain", domain),
        cell_id=cell.cell_id,
        blueprint=str(cell.blueprint),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/agents/bootstrap", response_model=BootstrapResponse, tags=["agents"])
def bootstrap(req: BootstrapRequest) -> BootstrapResponse:
    """Bootstrap or continue a persistent agent session.

    Idempotent identity registration + durable relationship resolution +
    continuation-by-default. Call this on session start to be remembered.
    """
    with session_scope() as session:
        result = bootstrap_agent_session(
            my_name=req.my_name,
            other_name=req.other_name,
            welcome_guidance=req.welcome_guidance,
            my_description=req.my_description,
            session=session,
        )
        return BootstrapResponse(
            my_identity=_cell_ref(result["my_identity"], "agent-identity"),
            relationship=_cell_ref(result["relationship"], "relationship"),
            was_first_contact=result["was_first_contact"],
            welcome_recorded=result["welcome_recorded"],
            prior_event_count=result["prior_event_count"],
            events=result["events"],
        )


@router.post("/agents/identity", response_model=IdentityResponse, tags=["agents"])
def register_identity(req: IdentityRequest) -> IdentityResponse:
    """Register or refresh a persistent agent identity."""
    with session_scope() as session:
        cell = register_persistent_agent_identity(
            req.name, req.description, session=session
        )
        resolved = resolve_agent_identity(req.name, session=session)
        return IdentityResponse(
            name=req.name,
            cell_id=cell.cell_id,
            description=(resolved or {}).get("description", req.description),
            blueprint=str(cell.blueprint),
        )


@router.get("/agents/identity/{name:path}", response_model=IdentityResponse, tags=["agents"])
def get_identity(name: str) -> IdentityResponse:
    """Resolve another agent's persistent identity by name (cross-agent sharing)."""
    with session_scope() as session:
        resolved = resolve_agent_identity(name, session=session)
        if resolved is None:
            raise HTTPException(status_code=404, detail=f"No agent identity '{name}'")
        return IdentityResponse(**resolved)


@router.get(
    "/agents/relationship/{name_a:path}/{name_b}",
    response_model=RelationshipResponse,
    tags=["agents"],
)
def get_relationship(name_a: str, name_b: str) -> RelationshipResponse:
    """Read the full durable history between two identities."""
    with session_scope() as session:
        return RelationshipResponse(**read_relationship(name_a, name_b, session=session))


@router.post("/agents/exchange", response_model=RelationshipResponse, tags=["agents"])
def post_exchange(req: ExchangeRequest) -> RelationshipResponse:
    """Record a significant exchange / task outcome into the relationship."""
    with session_scope() as session:
        record_exchange(req.my_name, req.other_name, req.summary, session=session)
        return RelationshipResponse(
            **read_relationship(req.my_name, req.other_name, session=session)
        )
