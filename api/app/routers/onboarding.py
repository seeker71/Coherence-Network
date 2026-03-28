"""Onboarding endpoints — Trust-on-First-Use (TOFU) identity registration.

Spec 168: Zero-friction contributor onboarding for the MVP.

POST /api/onboarding/register   — claim a handle, get a session token
GET  /api/onboarding/session    — validate a session token → contributor profile
POST /api/onboarding/upgrade    — upgrade trust_level via OAuth (stub → 501)
GET  /api/onboarding/roi        — live ROI signals for the onboarding funnel
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, field_validator
import re

from app.services import onboarding_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    handle: str
    email: Optional[str] = None
    hint_github: Optional[str] = None
    hint_wallet: Optional[str] = None

    @field_validator("handle")
    @classmethod
    def handle_format(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.fullmatch(r"[a-z0-9_\-]{3,40}", v):
            raise ValueError(
                "Handle must be 3–40 characters using only a-z, 0-9, _ or -"
            )
        return v


class RegisterResponse(BaseModel):
    contributor_id: str
    session_token: str
    trust_level: str
    handle: str
    created: bool
    roi_signals: dict


class SessionResponse(BaseModel):
    contributor_id: str
    handle: str
    trust_level: str
    linked_identities: int
    email: Optional[str]
    hint_github: Optional[str]
    hint_wallet: Optional[str]


class UpgradeRequest(BaseModel):
    contributor_id: str
    provider: str
    provider_id: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    metadata: Optional[dict] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", response_model=RegisterResponse, summary="TOFU registration")
async def register(body: RegisterRequest) -> RegisterResponse:
    """Claim a unique handle and receive an opaque session token.

    No verification required. Trust level starts at ``tofu`` and can be
    upgraded to ``verified`` later via ``POST /api/onboarding/upgrade``.
    """
    try:
        result = onboarding_service.register(
            handle=body.handle,
            email=body.email,
            hint_github=body.hint_github,
            hint_wallet=body.hint_wallet,
        )
    except ValueError as exc:
        if "handle_taken" in str(exc):
            raise HTTPException(status_code=409, detail="handle_taken")
        raise HTTPException(status_code=422, detail=str(exc))

    roi = onboarding_service.get_roi_signals()
    return RegisterResponse(
        contributor_id=result["contributor_id"],
        session_token=result["session_token"],
        trust_level=result["trust_level"],
        handle=result["handle"],
        created=result["created"],
        roi_signals=roi,
    )


@router.get("/session", response_model=SessionResponse, summary="Validate session token")
async def get_session(authorization: str = Header(...)) -> SessionResponse:
    """Return the contributor profile associated with a session token.

    Expects ``Authorization: Bearer <token>`` header.
    Returns 401 if the token is unknown or malformed.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="invalid_authorization_header")
    token = authorization.removeprefix("Bearer ").strip()
    profile = onboarding_service.resolve_session(token)
    if profile is None:
        raise HTTPException(status_code=401, detail="invalid_or_expired_token")
    return SessionResponse(**profile)


@router.post("/upgrade", summary="Upgrade trust level via OAuth [stub — 501]")
async def upgrade_oauth(body: UpgradeRequest) -> dict:
    """Upgrade a TOFU session to verified after OAuth confirmation.

    **Status**: MVP stub — returns 501 until OAuth flow is implemented (Spec 169).

    When implemented, this endpoint will:
    1. Accept an OAuth provider + provider_id (from the OAuth callback).
    2. Call ``contributor_identity_service.link_identity`` with ``verified=True``.
    3. Update the onboarding session ``trust_level`` to ``"verified"``.

    Planned providers: ``github``, ``google``, ``ethereum``.
    """
    raise HTTPException(
        status_code=501,
        detail={
            "message": "OAuth upgrade not yet implemented. Planned for Spec 169.",
            "upgrade_path": {
                "github": "POST /api/identity/oauth/github → callback upgrades trust_level",
                "ethereum": "POST /api/identity/verify-ethereum → EIP-712 signature",
            },
            "current_trust_level": "tofu",
            "spec_ref": "spec-168",
        },
    )


@router.get("/roi", summary="Onboarding ROI signals")
async def roi_signals() -> dict:
    """Return live ROI signals for the onboarding funnel.

    Fields:
    - ``handle_registrations`` — total TOFU registrations
    - ``verified_count`` — contributors who completed OAuth upgrade
    - ``verified_ratio`` — fraction of verified contributors (0.0–1.0)
    - ``avg_time_to_verify_days`` — mean days from register → verify (null if none)
    """
    return onboarding_service.get_roi_signals()
