"""Interest registration API — privacy-first community gathering.

POST /api/interest/register   — express interest (creates graph node)
GET  /api/interest/community  — consent-filtered community directory
GET  /api/interest/community/{id} — single person (consent-filtered)
GET  /api/interest/stats       — aggregate interest stats (no PII)
GET  /api/interest/roles       — available roles
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, field_validator

from app.services import interest_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/interest", tags=["interest"])


class RegisterInterestRequest(BaseModel):
    """Registration form submission."""
    name: str
    email: EmailStr
    location: str = ""
    skills: str = ""
    offering: str = ""
    resonant_roles: list[str] = []
    message: str = ""
    locale: str = "en"
    consent_share_name: bool = False
    consent_share_location: bool = False
    consent_share_skills: bool = False
    consent_findable: bool = False
    consent_email_updates: bool = False

    @field_validator("locale")
    @classmethod
    def validate_locale(cls, v: str) -> str:
        v = (v or "").strip().lower()
        return v if v in {"en", "de", "es", "id"} else "en"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) < 2:
            raise ValueError("Name must be at least 2 characters")
        return v

    @field_validator("resonant_roles")
    @classmethod
    def validate_roles(cls, v: list[str]) -> list[str]:
        valid = interest_service.VALID_ROLES
        return [r for r in v if r in valid]


class RegisterInterestResponse(BaseModel):
    """Returned after successful registration. No email exposed."""
    id: str
    name: str
    resonant_roles: list[str]
    message: str


class CommunityMember(BaseModel):
    """A consenting community member's public profile."""
    id: str
    name: str
    location: Optional[str] = None
    skills: Optional[str] = None
    offering: Optional[str] = None
    resonant_roles: list[str] = []


class InterestStats(BaseModel):
    """Aggregate interest stats — no personal information."""
    total_interested: int
    findable_count: int
    role_interest: dict[str, int]
    location_regions: dict[str, int]


class RoleInfo(BaseModel):
    """A role the field is calling for."""
    slug: str
    name: str
    description: str


ROLES = [
    RoleInfo(slug="living-structure-weaver", name="Living-structure weaver", description="People who sense how the field wants to shelter itself. Architects, builders, earthship enthusiasts, cob practitioners, bamboo growers."),
    RoleInfo(slug="nourishment-alchemist", name="Nourishment alchemist", description="People attuned to how land wants to feed the field. Permaculturists, fermentation practitioners, food foresters, communal cooks."),
    RoleInfo(slug="frequency-holder", name="Frequency holder", description="People whose sound attunes the field. Musicians, sound healers, voice practitioners, silence holders."),
    RoleInfo(slug="vitality-keeper", name="Vitality keeper", description="People whose presence amplifies the glow. Bodyworkers, movement facilitators, nature immersion guides, breathwork practitioners."),
    RoleInfo(slug="transmission-source", name="Transmission source", description="People whose mastery radiates. Experienced community builders, facilitators, elders of any tradition that resonates."),
    RoleInfo(slug="form-grower", name="Form-grower", description="People who work with earth, timber, stone, water as living materials. Hands that know how to shape space that breathes."),
]


@router.post(
    "/register",
    response_model=RegisterInterestResponse,
    summary="Express interest in The Living Collective",
)
async def register_interest(body: RegisterInterestRequest) -> RegisterInterestResponse:
    """Create an interested-person node. Email is stored but never exposed via API."""
    try:
        node = interest_service.register_interest(
            name=body.name,
            email=body.email,
            location=body.location,
            skills=body.skills,
            offering=body.offering,
            resonant_roles=body.resonant_roles,
            message=body.message,
            locale=body.locale,
            consent_share_name=body.consent_share_name,
            consent_share_location=body.consent_share_location,
            consent_share_skills=body.consent_share_skills,
            consent_findable=body.consent_findable,
            consent_email_updates=body.consent_email_updates,
        )
    except Exception as exc:
        logger.exception("Registration failed")
        raise HTTPException(status_code=500, detail="Registration failed — please try again")

    props = node.get("properties", {})
    return RegisterInterestResponse(
        id=node["id"],
        name=node.get("name", body.name),
        resonant_roles=props.get("resonant_roles", body.resonant_roles),
        message=props.get("message", ""),
    )


@router.get(
    "/community",
    response_model=list[CommunityMember],
    summary="Consent-filtered community directory",
)
async def list_community(limit: int = 200) -> list[CommunityMember]:
    """List people who have opted in to being visible. Private fields always stripped."""
    members = interest_service.list_community(limit=limit)
    result = []
    for m in members:
        props = m.get("properties", m)
        result.append(CommunityMember(
            id=m.get("id", ""),
            name=m.get("name", "A resonant soul"),
            location=props.get("location"),
            skills=props.get("skills"),
            offering=props.get("offering"),
            resonant_roles=props.get("resonant_roles", []),
        ))
    return result


@router.get(
    "/community/{person_id}",
    response_model=CommunityMember,
    summary="Single person public profile",
)
async def get_person(person_id: str) -> CommunityMember:
    """Get a single person's consent-filtered profile."""
    person = interest_service.get_person_public(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found or not publicly visible")
    props = person.get("properties", person)
    return CommunityMember(
        id=person.get("id", ""),
        name=person.get("name", "A resonant soul"),
        location=props.get("location"),
        skills=props.get("skills"),
        offering=props.get("offering"),
        resonant_roles=props.get("resonant_roles", []),
    )


@router.get(
    "/stats",
    response_model=InterestStats,
    summary="Aggregate interest statistics (no PII)",
)
async def get_stats() -> InterestStats:
    """Aggregated stats about interest — no personal information exposed."""
    stats = interest_service.get_interest_stats()
    return InterestStats(**stats)


@router.get(
    "/roles",
    response_model=list[RoleInfo],
    summary="Available community roles",
)
async def list_roles() -> list[RoleInfo]:
    """The 6 roles the field is calling for."""
    return ROLES
