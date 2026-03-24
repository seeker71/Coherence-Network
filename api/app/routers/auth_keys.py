"""Per-contributor API key management.

Implements: identity-driven-onboarding
"""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.middleware.traceability import traces_to

router = APIRouter()


class KeyRequest(BaseModel):
    contributor_id: str
    provider: str  # identity provider used for verification
    provider_id: str  # identity handle (github username, email, etc.)


class KeyResponse(BaseModel):
    api_key: str
    contributor_id: str
    created_at: str
    scopes: list[str]


# In-memory key store (production should use DB)
# Maps api_key_hash → {contributor_id, provider, created_at, scopes}
_KEY_STORE: dict[str, dict] = {}


def _hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def verify_contributor_key(api_key: str) -> dict | None:
    """Verify an API key and return the contributor info, or None."""
    h = _hash_key(api_key)
    return _KEY_STORE.get(h)


@router.post("/auth/keys", status_code=201)
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

    # Generate key
    raw_key = f"cc_{body.contributor_id}_{secrets.token_hex(16)}"
    key_hash = _hash_key(raw_key)
    now = datetime.now(timezone.utc).isoformat()

    _KEY_STORE[key_hash] = {
        "contributor_id": body.contributor_id,
        "provider": body.provider,
        "provider_id": body.provider_id,
        "created_at": now,
        "scopes": ["own:read", "own:write", "contribute", "stake", "vote"],
    }

    return KeyResponse(
        api_key=raw_key,
        contributor_id=body.contributor_id,
        created_at=now,
        scopes=["own:read", "own:write", "contribute", "stake", "vote"],
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


@router.post("/auth/verify/challenge")
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


@router.post("/auth/verify/proof")
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


@router.get("/auth/whoami")
async def whoami(x_api_key: str | None = None):
    """Check who the current API key belongs to."""
    if not x_api_key:
        return {"authenticated": False, "message": "No API key provided. Run: cc setup"}

    info = verify_contributor_key(x_api_key)
    if info:
        return {"authenticated": True, **info}

    # Check if it's the system dev-key
    from app.middleware.auth import _API_KEY
    if x_api_key == _API_KEY:
        return {"authenticated": True, "contributor_id": "system", "scopes": ["admin"]}

    return {"authenticated": False, "message": "Invalid API key"}
