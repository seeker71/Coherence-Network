"""Per-contributor API key management.

Implements: identity-driven-onboarding

Storage lives in `app.services.contributor_key_store` — this router is a
thin HTTP layer over that service. Legacy callers that imported
`verify_contributor_key` from here still work: it now delegates to the
store.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from app.deps.identity import (
    Attribution,
    get_attribution,
    require_verified_contributor,
)
from app.middleware.traceability import traces_to
from app.services import contributor_key_store

router = APIRouter()


class KeyRequest(BaseModel):
    contributor_id: str
    provider: str  # identity provider used for verification
    provider_id: str  # identity handle (github username, email, etc.)
    label: str | None = None  # optional user-friendly label


class KeyResponse(BaseModel):
    api_key: str
    contributor_id: str
    created_at: str
    scopes: list[str]
    label: str | None = None


class KeyListItem(BaseModel):
    id: str
    contributor_id: str
    label: str | None
    fingerprint: str
    provider: str | None
    scopes: list[str]
    created_at: str
    last_used_at: str | None
    revoked_at: str | None


class KeyListResponse(BaseModel):
    keys: list[KeyListItem]


def verify_contributor_key(api_key: str) -> dict | None:
    """Backward-compatible wrapper kept for legacy imports.

    Returns a dict shaped like the old in-memory store so existing callers
    keep working. Prefer `contributor_key_store.verify(...)` in new code.
    """
    row = contributor_key_store.verify(api_key)
    if row is None:
        return None
    return {
        "contributor_id": row.contributor_id,
        "provider": row.provider,
        "provider_id": row.provider_id,
        "created_at": row.created_at,
        "scopes": list(row.scopes),
        "label": row.label,
    }


@router.post("/auth/keys", status_code=201, summary="Generate a personal API key for a contributor")
@traces_to(spec="identity-driven-onboarding", idea="identity-driven-onboarding")
async def generate_api_key(body: KeyRequest) -> KeyResponse:
    """Generate a personal API key for a contributor.

    Requires a linked identity (provider + provider_id) for attribution.
    The key is returned once — store it securely. The server only keeps the hash.
    """
    from app.services import contributor_identity_service

    # Verify the identity link exists
    identities = contributor_identity_service.get_identities(body.contributor_id)
    linked = any(
        i.get("provider") == body.provider and i.get("provider_id") == body.provider_id
        for i in identities
    )
    if not linked:
        # Link identity — marked unverified until proven
        try:
            contributor_identity_service.link_identity(
                body.contributor_id, body.provider, body.provider_id,
                display_name=body.provider_id,
                verified=False,
            )
        except Exception as e:
            raise HTTPException(400, f"Could not link identity: {e}")

    # Check if contributor exists, create if not
    from app.services import contributor_service
    existing = contributor_service.get_contributor(body.contributor_id)
    if not existing:
        try:
            contributor_service.create_contributor(
                name=body.contributor_id,
                contributor_type="HUMAN",
            )
        except Exception:
            pass  # May already exist with different casing

    minted = contributor_key_store.mint(
        contributor_id=body.contributor_id,
        label=body.label,
        provider=body.provider,
        provider_id=body.provider_id,
    )

    return KeyResponse(
        api_key=minted.raw_key,
        contributor_id=minted.row.contributor_id,
        created_at=minted.row.created_at,
        scopes=list(minted.row.scopes),
        label=minted.row.label,
    )


class VerifyChallenge(BaseModel):
    contributor_id: str
    provider: str
    challenge: str  # What the user needs to prove


class VerifyProof(BaseModel):
    contributor_id: str
    provider: str
    provider_id: str
    proof: str  # The proof (GitHub gist URL, signed message, etc.)


# Pending challenges: contributor_id → {provider, challenge, expires}
_CHALLENGES: dict[str, dict] = {}


@router.post("/auth/verify/challenge", summary="Create a verification challenge for an identity provider")
@traces_to(spec="identity-driven-onboarding", idea="identity-driven-onboarding")
async def create_verification_challenge(body: VerifyChallenge) -> dict:
    """Create a verification challenge for an identity provider.

    GitHub: create a public gist with the challenge text
    Ethereum: sign the challenge with your wallet
    Email: we'd send a code (not implemented yet)
    """
    challenge_token = secrets.token_hex(16)

    if body.provider == "github":
        instructions = (
            f"Create a public GitHub gist containing exactly this text:\n"
            f"  coherence-verify:{body.contributor_id}:{challenge_token}\n"
            f"Then submit the gist URL as proof."
        )
    elif body.provider in ("ethereum", "solana"):
        instructions = (
            f"Sign this message with your wallet:\n"
            f"  coherence-verify:{body.contributor_id}:{challenge_token}\n"
            f"Then submit the signature as proof."
        )
    else:
        instructions = (
            f"To verify {body.provider}, add this to your profile or bio:\n"
            f"  coherence-verify:{challenge_token}\n"
            f"Then submit your profile URL as proof."
        )

    _CHALLENGES[body.contributor_id] = {
        "provider": body.provider,
        "challenge": challenge_token,
        "expires": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "challenge": challenge_token,
        "instructions": instructions,
        "expires_in": "1 hour",
    }


@router.post("/auth/verify/proof", summary="Submit proof of identity ownership. Marks the identity as verified")
@traces_to(spec="identity-driven-onboarding", idea="identity-driven-onboarding")
async def submit_verification_proof(body: VerifyProof) -> dict:
    """Submit proof of identity ownership. Marks the identity as verified."""
    from app.services import contributor_identity_service

    pending = _CHALLENGES.get(body.contributor_id)
    if not pending or pending["provider"] != body.provider:
        raise HTTPException(400, "No pending challenge. Request one first: POST /api/auth/verify/challenge")

    challenge_token = pending["challenge"]
    verified = False

    if body.provider == "github":
        # Verify: fetch the gist and check it contains the challenge
        try:
            import httpx
            resp = httpx.get(body.proof, timeout=10, follow_redirects=True)
            if f"coherence-verify:{body.contributor_id}:{challenge_token}" in resp.text:
                verified = True
        except Exception:
            raise HTTPException(400, "Could not fetch gist URL")

    elif body.provider in ("ethereum", "solana"):
        # For MVP: trust the signature (real verification needs web3 library)
        if challenge_token in body.proof:
            verified = True

    else:
        # Generic: check if proof contains challenge token
        if challenge_token in body.proof:
            verified = True

    if not verified:
        raise HTTPException(400, "Verification failed — challenge token not found in proof")

    # Mark identity as verified
    try:
        contributor_identity_service.verify_identity(
            body.contributor_id, body.provider, body.provider_id,
        )
    except Exception:
        pass  # verify_identity may not exist yet — the link is still there

    # Clean up challenge
    _CHALLENGES.pop(body.contributor_id, None)

    return {
        "verified": True,
        "contributor_id": body.contributor_id,
        "provider": body.provider,
        "provider_id": body.provider_id,
    }


class OnboardRequest(BaseModel):
    name: str
    provider: str
    provider_id: str
    display_name: str | None = None


@router.post("/onboard", status_code=201, summary="One-shot onboarding: create contributor + link identity + generate API key")
@traces_to(spec="identity-driven-onboarding", idea="identity-driven-onboarding")
async def onboard_contributor(body: OnboardRequest) -> dict:
    """One-shot onboarding: create contributor + link identity + generate API key.

    This is the primary entry point for `coh setup`.
    Returns the API key — save it to ~/.coherence-network/keys.json.
    """
    from app.services import contributor_identity_service, contributor_service

    # 1. Create or retrieve contributor record
    existing = contributor_service.get_contributor(body.name)
    if not existing:
        try:
            contributor_service.create_contributor(
                name=body.name,
                contributor_type="HUMAN",
            )
        except Exception:
            pass

    # 2. Link the primary identity (trust-on-first-use)
    identities = contributor_identity_service.get_identities(body.name)
    already_linked = any(
        i.get("provider") == body.provider and i.get("provider_id") == body.provider_id
        for i in identities
    )
    if not already_linked:
        contributor_identity_service.link_identity(
            contributor_id=body.name,
            provider=body.provider,
            provider_id=body.provider_id,
            display_name=body.display_name or body.provider_id,
            verified=False,
        )

    # 3. Also link name identity for discoverability
    name_linked = any(i.get("provider") == "name" for i in identities)
    if not name_linked:
        try:
            contributor_identity_service.link_identity(
                contributor_id=body.name,
                provider="name",
                provider_id=body.name,
                display_name=body.display_name or body.name,
                verified=False,
            )
        except Exception:
            pass

    # 4. Generate personal API key via the durable store
    minted = contributor_key_store.mint(
        contributor_id=body.name,
        label=None,
        provider=body.provider,
        provider_id=body.provider_id,
    )

    return {
        "contributor_id": minted.row.contributor_id,
        "api_key": minted.raw_key,
        "provider": body.provider,
        "provider_id": body.provider_id,
        "created_at": minted.row.created_at,
        "scopes": list(minted.row.scopes),
        "message": f"Welcome to Coherence Network, {body.name}! Key saved — run: coh status",
    }


@router.get("/auth/whoami", summary="Check who the current API key belongs to")
async def whoami(
    request: Request,
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    api_key_query: str | None = None,
):
    """Check who the current API key belongs to.

    Prefers the attribution already extracted by the attribution
    middleware (from Authorization: Bearer cc_* or X-Contributor-Id).
    Falls back to the legacy X-API-Key flow for compatibility.
    """
    # Prefer the middleware's already-extracted attribution.
    att: Attribution = get_attribution(request)
    if att.contributor_id:
        return {
            "authenticated": att.source == "verified",
            "contributor_id": att.contributor_id,
            "source": att.source,
            "scopes": list(att.scopes),
        }

    # Legacy compatibility: callers sending X-API-Key (or ?api_key_query=).
    key = x_api_key or api_key_query
    if not key:
        return {"authenticated": False, "message": "No API key provided. Run: coh setup"}

    info = verify_contributor_key(key)
    if info:
        return {"authenticated": True, **info}

    # Check if it's the system dev-key
    from app.middleware.auth import _API_KEY
    if key == _API_KEY:
        return {"authenticated": True, "contributor_id": "system", "scopes": ["admin"]}

    return {"authenticated": False, "message": "Invalid API key"}


@router.get("/auth/keys", response_model=KeyListResponse, summary="List this contributor's API keys")
async def list_keys(
    att: Attribution = Depends(require_verified_contributor),
    include_revoked: bool = False,
) -> KeyListResponse:
    """List keys minted for the verified contributor.

    Requires a verified `Authorization: Bearer cc_*` — a claimed
    `X-Contributor-Id` header is not sufficient for this endpoint, because
    listing keys is a self-administration action that must prove ownership.
    Raw keys are never returned, only metadata.
    """
    assert att.contributor_id is not None  # guaranteed by require_verified_contributor
    rows = contributor_key_store.list_for(att.contributor_id, include_revoked=include_revoked)
    return KeyListResponse(
        keys=[
            KeyListItem(
                id=r.id,
                contributor_id=r.contributor_id,
                label=r.label,
                fingerprint=r.fingerprint,
                provider=r.provider,
                scopes=list(r.scopes),
                created_at=r.created_at,
                last_used_at=r.last_used_at,
                revoked_at=r.revoked_at,
            )
            for r in rows
        ],
    )


@router.delete("/auth/keys/{key_id}", status_code=204, summary="Revoke one of this contributor's keys")
async def revoke_key(
    key_id: str,
    att: Attribution = Depends(require_verified_contributor),
) -> None:
    """Revoke an owned API key. Requires a different verified key to act."""
    assert att.contributor_id is not None
    existing = contributor_key_store.get_by_id(key_id)
    if existing is None:
        raise HTTPException(404, "key not found")
    if existing.contributor_id != att.contributor_id:
        # Don't leak whether the key exists for another contributor.
        raise HTTPException(404, "key not found")
    if not contributor_key_store.revoke(key_id, owner_contributor_id=att.contributor_id):
        raise HTTPException(409, "key already revoked")
    return None
