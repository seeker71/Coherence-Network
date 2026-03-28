"""Pydantic models for identity-driven onboarding (TOFU → OAuth upgrade path)."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class OnboardingRegisterRequest(BaseModel):
    """Trust-on-First-Use registration payload."""
    handle: str = Field(..., min_length=2, max_length=64, description="Unique display handle")
    email: Optional[str] = Field(None, description="Optional email hint (unverified)")
    hint_github: Optional[str] = Field(None, description="Optional GitHub username hint (unverified)")
    hint_wallet: Optional[str] = Field(None, description="Optional Ethereum wallet address hint")


class OnboardingRegisterResponse(BaseModel):
    """Response after successful TOFU registration."""
    contributor_id: str
    session_token: str
    trust_level: Literal["tofu", "verified"]
    handle: str
    created: bool  # True if new, False if existing session reissued
    roi_signals: "ROISignals"


class OnboardingSessionResponse(BaseModel):
    """Resolved contributor profile from a session token."""
    contributor_id: str
    handle: str
    trust_level: Literal["tofu", "verified"]
    linked_identities: int
    email: Optional[str]
    hint_github: Optional[str]
    hint_wallet: Optional[str]
    roi_signals: "ROISignals"


class OnboardingUpgradeRequest(BaseModel):
    """Upgrade a TOFU identity to verified via OAuth or signature."""
    contributor_id: str
    provider: str = Field(..., description="Identity provider: github, ethereum, email")
    provider_id: str = Field(..., description="Provider-specific identifier (login, address, email)")
    verified_by: Literal["oauth", "signature", "admin"] = "oauth"
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    metadata: Optional[dict] = None


class OnboardingUpgradeResponse(BaseModel):
    """Response after upgrading trust level."""
    contributor_id: str
    trust_level: Literal["tofu", "verified"]
    provider: str
    provider_id: str
    message: str
    roi_signals: "ROISignals"


class ROISignals(BaseModel):
    """Live ROI metrics for the onboarding funnel."""
    handle_registrations: int = 0
    verified_count: int = 0
    verified_ratio: float = 0.0
    avg_time_to_verify_days: Optional[float] = None
    spec_ref: str = "spec-168"


# Update forward refs
OnboardingRegisterResponse.model_rebuild()
OnboardingSessionResponse.model_rebuild()
OnboardingUpgradeResponse.model_rebuild()
