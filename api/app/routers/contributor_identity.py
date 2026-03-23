"""Contributor Identity endpoints — link accounts, verify via OAuth/signature."""

from __future__ import annotations

import json
import logging
import urllib.parse

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.services import contributor_identity_service
from app.services.config_service import get_config
from app.services.identity_providers import registry_as_dict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/identity", tags=["identity"])


# ---------------------------------------------------------------------------
# Request/response models
# ---------------------------------------------------------------------------

class LinkIdentityRequest(BaseModel):
    contributor_id: str
    provider: str
    provider_id: str
    display_name: str | None = None
    avatar_url: str | None = None
    verified: bool = False
    metadata: dict | None = None


class VerifyEthereumRequest(BaseModel):
    contributor_id: str
    address: str
    message: str
    signature: str


# ---------------------------------------------------------------------------
# OAuth config helper
# ---------------------------------------------------------------------------

def _get_oauth_config(provider: str) -> dict:
    """Load OAuth config for a provider from ~/.coherence-network/config.json."""
    config = get_config()
    return config.get("oauth", {}).get(provider, {})


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/providers", summary="List all supported identity providers")
async def list_providers() -> dict:
    """Return all supported identity providers grouped by category."""
    return {"categories": registry_as_dict()}


@router.post("/link", summary="Link an identity to a contributor")
async def link_identity(body: LinkIdentityRequest) -> dict:
    """Link an identity to a contributor. No API key needed.

    Anyone can link their GitHub, email, wallet address, or any other
    identity to their contributor name. Verification is optional.
    """
    if body.provider not in contributor_identity_service.SUPPORTED_PROVIDERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported provider '{body.provider}'. "
                   f"Supported: {contributor_identity_service.SUPPORTED_PROVIDERS}",
        )
    return contributor_identity_service.link_identity(
        contributor_id=body.contributor_id,
        provider=body.provider,
        provider_id=body.provider_id,
        display_name=body.display_name,
        avatar_url=body.avatar_url,
        verified=body.verified,
        metadata=body.metadata,
    )


@router.get("/{contributor_id}", summary="Get all linked identities for a contributor")
async def get_identities(contributor_id: str) -> list[dict]:
    """Return all linked identities for a contributor."""
    return contributor_identity_service.get_identities(contributor_id)


@router.delete("/{contributor_id}/{provider}", summary="Unlink an identity")
async def unlink_identity(contributor_id: str, provider: str) -> dict:
    """Remove a linked identity from a contributor."""
    removed = contributor_identity_service.unlink_identity(contributor_id, provider)
    if not removed:
        raise HTTPException(status_code=404, detail="Identity not found")
    return {"status": "unlinked", "contributor_id": contributor_id, "provider": provider}


@router.get("/lookup/{provider}/{provider_id}", summary="Find contributor by identity")
async def find_by_identity(provider: str, provider_id: str) -> dict:
    """Look up which contributor owns a specific identity."""
    contributor_id = contributor_identity_service.find_contributor_by_identity(provider, provider_id)
    if not contributor_id:
        raise HTTPException(status_code=404, detail="No contributor found for this identity")
    return {"contributor_id": contributor_id, "provider": provider, "provider_id": provider_id}


# ---------------------------------------------------------------------------
# GitHub OAuth flow
# ---------------------------------------------------------------------------

@router.post("/verify/github", summary="Start GitHub OAuth verification")
async def verify_github_start(
    contributor_id: str = Query(..., description="Contributor to link"),
) -> dict:
    """Start GitHub OAuth flow. Returns a redirect URL.

    If GitHub OAuth is not configured, returns an error suggesting manual entry.
    """
    oauth = _get_oauth_config("github")
    client_id = oauth.get("client_id", "")
    if not client_id:
        return {
            "status": "oauth_not_configured",
            "message": "GitHub OAuth is not configured. Use manual linking instead.",
            "manual_link_url": "/api/identity/link",
        }
    # Build GitHub authorize URL
    state = urllib.parse.quote(contributor_id, safe="")
    redirect_uri = _get_callback_url("github")
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "scope": "read:user",
        "state": state,
        "redirect_uri": redirect_uri,
    })
    redirect_url = f"https://github.com/login/oauth/authorize?{params}"
    return {"redirect_url": redirect_url}


@router.get("/callback/github", summary="GitHub OAuth callback")
async def github_callback(
    code: str = Query(...),
    state: str = Query(""),
) -> dict:
    """Handle GitHub OAuth callback. Exchanges code for token, gets user info, links identity."""
    import urllib.request

    oauth = _get_oauth_config("github")
    client_id = oauth.get("client_id", "")
    client_secret = oauth.get("client_secret", "")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")

    contributor_id = urllib.parse.unquote(state) if state else ""
    if not contributor_id:
        raise HTTPException(status_code=400, detail="Missing contributor_id in state")

    # Exchange code for access token
    try:
        token_data = json.dumps({
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
        }).encode()
        req = urllib.request.Request(
            "https://github.com/login/oauth/access_token",
            data=token_data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_resp = json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("GitHub token exchange failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to exchange GitHub code for token")

    access_token = token_resp.get("access_token", "")
    if not access_token:
        raise HTTPException(status_code=502, detail="GitHub did not return an access token")

    # Get user info
    try:
        user_req = urllib.request.Request(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(user_req, timeout=10) as resp:
            user_info = json.loads(resp.read().decode())
    except Exception as exc:
        logger.warning("GitHub user info fetch failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to fetch GitHub user info")

    github_login = user_info.get("login", "")
    display_name = user_info.get("name") or github_login
    avatar_url = user_info.get("avatar_url", "")
    profile_url = user_info.get("html_url", "")

    result = contributor_identity_service.link_identity(
        contributor_id=contributor_id,
        provider="github",
        provider_id=github_login,
        display_name=display_name,
        avatar_url=avatar_url,
        verified=True,
        metadata={"profile_url": profile_url, "github_id": user_info.get("id")},
    )
    return {
        "status": "linked",
        "provider": "github",
        "provider_id": github_login,
        "display_name": display_name,
        "verified": True,
        **result,
    }


# ---------------------------------------------------------------------------
# Ethereum signature verification
# ---------------------------------------------------------------------------

@router.post("/verify/ethereum", summary="Verify Ethereum address via signature")
async def verify_ethereum(body: VerifyEthereumRequest) -> dict:
    """Verify an Ethereum address by checking a signed message.

    If eth_account is not installed, accepts the address as unverified.
    """
    verified = False
    verification_note = ""

    try:
        from eth_account.messages import encode_defunct
        from eth_account import Account

        message = encode_defunct(text=body.message)
        recovered = Account.recover_message(message, signature=body.signature)
        if recovered.lower() == body.address.lower():
            verified = True
            verification_note = "Signature verified via eth_account"
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Signature does not match address. Recovered: {recovered}",
            )
    except ImportError:
        # eth_account not installed — accept as unverified
        verified = False
        verification_note = "eth_account not installed; address recorded as unverified"
    except HTTPException:
        raise
    except Exception as exc:
        verified = False
        verification_note = f"Signature verification failed: {exc}"

    result = contributor_identity_service.link_identity(
        contributor_id=body.contributor_id,
        provider="ethereum",
        provider_id=body.address,
        display_name=body.address[:8] + "..." + body.address[-4:] if len(body.address) > 12 else body.address,
        verified=verified,
        metadata={"verification_note": verification_note},
    )
    return {
        "status": "linked",
        "verified": verified,
        "verification_note": verification_note,
        **result,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_callback_url(provider: str) -> str:
    """Build the OAuth callback URL."""
    from app.services.config_service import get_api_base
    base = get_api_base()
    return f"{base}/api/identity/callback/{provider}"
