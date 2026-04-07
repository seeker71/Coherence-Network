from __future__ import annotations
import logging, re
from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, field_validator
from app.services import onboarding_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

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
            raise ValueError("Handle must be 3-40 chars: a-z, 0-9, _ or -")
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

@router.post("/register", response_model=RegisterResponse, summary="TOFU registration")
async def register(body: RegisterRequest) -> RegisterResponse:
    """Claim a unique handle, receive a session token. Trust-on-first-use (TOFU). Spec 168."""
    try:
        result = onboarding_service.register(
            handle=body.handle, email=body.email,
            hint_github=body.hint_github, hint_wallet=body.hint_wallet,
        )
    except ValueError as exc:
        if "handle_taken" in str(exc):
            raise HTTPException(status_code=409, detail="handle_taken")
        raise HTTPException(status_code=422, detail=str(exc))
    roi = onboarding_service.get_roi_signals()
    return RegisterResponse(
        contributor_id=result["contributor_id"], session_token=result["session_token"],
        trust_level=result["trust_level"], handle=result["handle"],
        created=result["created"], roi_signals=roi,
    )

@router.get("/session", response_model=SessionResponse, summary="Validate session token")
async def get_session(authorization: str = Header(...)) -> SessionResponse:
    """Return contributor profile for a Bearer session token. Returns 401 if invalid."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="invalid_authorization_header")
    token = authorization.removeprefix("Bearer ").strip()
    profile = onboarding_service.resolve_session(token)
    if profile is None:
        raise HTTPException(status_code=401, detail="invalid_or_expired_token")
    return SessionResponse(**profile)

class ContributorListItem(BaseModel):
    contributor_id: str
    handle: str
    trust_level: str
    email: Optional[str]
    created_at: Optional[str]

@router.get("/contributors", response_model=list[ContributorListItem], summary="List registered contributors")
async def list_contributors(limit: int = 200) -> list[ContributorListItem]:
    """Return all registered contributors (newest first). Satisfies 'appear in contributor list' requirement."""
    rows = onboarding_service.list_contributors(limit=limit)
    return [ContributorListItem(**r) for r in rows]

@router.post("/upgrade", summary="Upgrade trust level via OAuth [stub 501]")
async def upgrade_oauth(body: UpgradeRequest) -> dict:
    """Stub: upgrade TOFU to verified via OAuth. Planned for Spec 169."""
    raise HTTPException(status_code=501, detail={
        "message": "OAuth upgrade not yet implemented. Planned for Spec 169.",
        "upgrade_path": {
            "github": "POST /api/identity/verify/github",
            "ethereum": "POST /api/identity/verify/ethereum",
        },
        "current_trust_level": "tofu",
        "spec_ref": "spec-168",
    })

@router.get("/roi", summary="Onboarding ROI signals")
async def roi_signals() -> dict:
    """Live ROI signals: handle_registrations, verified_ratio, avg_time_to_verify_days."""
    return onboarding_service.get_roi_signals()
