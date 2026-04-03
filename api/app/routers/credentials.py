"""API router for Repo Credentials."""

import hashlib
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from app.models.credentials import (
    RepoCredentialCreate,
    RepoCredentialResponse,
    RepoCredentialList
)
from app.services import repo_credential_service as service

router = APIRouter(tags=["credentials"])


@router.post("", response_model=RepoCredentialResponse)
async def add_credential(req: RepoCredentialCreate):
    """Add or update a repo-specific credential (hashed)."""
    # Hash the raw credential before passing it to the service
    cred_hash = hashlib.sha256(req.credential_raw.encode("utf-8")).hexdigest()

    # In a real system, the raw credential would also be stored in a 
    # separate secure keystore (like ~/.coherence-network/keys.json 
    # on the host or a Vault/KMS). Here we just store the hash.

    res = service.add_credential(
        contributor_id=req.contributor_id,
        repo_url=req.repo_url,
        credential_type=req.credential_type,
        credential_hash=cred_hash,
        scopes=req.scopes,
        expires_at=req.expires_at
    )

    # The service returns a dict that might not match Response model exactly
    # so we fetch the full record
    full_recs = service.get_credentials(contributor_id=req.contributor_id, repo_url=req.repo_url)
    if not full_recs:
        raise HTTPException(status_code=500, detail="Failed to create/retrieve credential")

    return full_recs[0]


@router.get("", response_model=RepoCredentialList)
async def list_credentials(
    contributor_id: Optional[str] = Query(None),
    repo_url: Optional[str] = Query(None)
):
    """List registered credentials, filtered by contributor or repo."""
    recs = service.get_credentials(contributor_id=contributor_id, repo_url=repo_url)
    return {"credentials": recs}


@router.delete("/{credential_id}")
async def delete_credential(credential_id: str):

    """Remove a credential record."""
    success = service.delete_credential(credential_id)
    if not success:
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"status": "deleted"}
