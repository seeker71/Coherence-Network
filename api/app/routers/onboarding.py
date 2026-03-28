"""Onboarding router — Trust-on-First-Use (TOFU) MVP with OAuth upgrade path.

Spec: specs/168-identity-driven-onboarding-tofu.md

Endpoints:
  POST /api/onboarding/register   — claim handle, get session token
  GET  /api/onboarding/session    — resolve token → contributor profile
  POST /api/onboarding/upgrade    — upgrade TOFU → verified via OAuth
  GET  /api/onboarding/roi        — funnel ROI signals
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from app.models.onboarding import (
    OnboardingRegisterRequest,
    OnboardingRegisterResponse,
    OnboardingSessionResponse,
    OnboardingUpgradeRequest,
    OnboardingUpgradeResponse,
    ROISignals,
)
from app.services import onboarding_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


def _roi() -> ROISignals:
    signals = onboarding_service.get_roi_signals()
    return ROISignals(**signals)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=OnboardingRegisterResponse,
    status_code=201,
    summary="Register a new contributor via TOFU",
    description=(
        "Trust-on-First-Use registration. Claim a unique handle and optionally provide "
        "social hints. Immediately returns a session token — no email verification or "
        "OAuth required for the MVP. Identity can be upgraded to 'verified' later via "
        "POST /api/onboarding/upgrade."
    ),
)
async def register(body: OnboardingRegisterRequest) -> OnboardingRegisterResponse:
    """Claim a handle and receive a TOFU session token."""
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
    return OnboardingRegisterResponse(
        contributor_id=result["contributor_id"],
        session_token=result["session_token"],
        trust_level=result["trust_level"],
        handle=result["handle"],
        created=result["created"],
        roi_signals=_roi(),
    )


@router.get(
    "/session",
    response_model=OnboardingSessionResponse,
    summary="Resolve a session token to a contributor profile",
    description=(
        "Pass a session token in the Authorization header as 'Bearer <token>'. "
        "Returns the contributor profile with trust_level and linked identity count."
    ),
)
async def get_session(
    authorization: str | None = Header(None, alias="Authorization"),
) -> OnboardingSessionResponse:
    """Resolve a session token to a contributor profile."""
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing Bearer token in Authorization header")

    profile = onboarding_service.resolve_session(token)
    if not profile:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")

    return OnboardingSessionResponse(
        contributor_id=profile["contributor_id"],
        handle=profile["handle"],
        trust_level=profile["trust_level"],
        linked_identities=profile["linked_identities"],
        email=profile.get("email"),
        hint_github=profile.get("hint_github"),
        hint_wallet=profile.get("hint_wallet"),
        roi_signals=_roi(),
    )


@router.post(
    "/upgrade",
    response_model=OnboardingUpgradeResponse,
    summary="Upgrade TOFU identity to verified",
    description=(
        "After a contributor has verified their identity via OAuth (e.g., GitHub) or "
        "cryptographic signature, call this endpoint to upgrade trust_level from "
        "'tofu' to 'verified'. The identity link is stored in contributor_identities."
    ),
)
async def upgrade(body: OnboardingUpgradeRequest) -> OnboardingUpgradeResponse:
    """Upgrade a TOFU identity to verified via OAuth or signature."""
    try:
        result = onboarding_service.upgrade_trust(
            contributor_id=body.contributor_id,
            provider=body.provider,
            provider_id=body.provider_id,
            display_name=body.display_name,
            avatar_url=body.avatar_url,
            metadata=body.metadata,
        )
    except ValueError as exc:
        if "contributor_not_found" in str(exc):
            raise HTTPException(status_code=404, detail="Contributor not found")
        raise HTTPException(status_code=422, detail=str(exc))

    return OnboardingUpgradeResponse(
        contributor_id=result["contributor_id"],
        trust_level=result["trust_level"],
        provider=result["provider"],
        provider_id=result["provider_id"],
        message=(
            f"Identity upgraded to 'verified' via {body.provider}. "
            "OAuth flow available at POST /api/identity/verify/github for full verification."
        ),
        roi_signals=_roi(),
    )


@router.get(
    "/roi",
    response_model=ROISignals,
    summary="Onboarding funnel ROI signals",
    description=(
        "Returns live metrics: total handle registrations, verified count, "
        "verified_ratio, and avg_time_to_verify_days. These ROI signals track "
        "the effectiveness of the TOFU → OAuth upgrade funnel."
    ),
)
async def roi_signals() -> ROISignals:
    """Return live onboarding funnel ROI metrics."""
    return _roi()
