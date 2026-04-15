"""Verification router — public endpoints for auditing CC flows.

All GET endpoints are unauthenticated — anyone can verify.
POST endpoints (compute/publish) require API key auth.
"""

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


# ---------------------------------------------------------------------------
# Public endpoints (no auth — anyone can verify)
# ---------------------------------------------------------------------------


@router.get("/verification/chain/{asset_id}", summary="Get the Merkle hash chain for an asset")
async def get_chain(
    asset_id: str,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> list[dict[str, Any]]:
    """Fetch the daily hash chain for an asset. No auth required.

    Each entry contains: day, read_count, cc_total, concepts, merkle_hash, prev_hash.
    Anyone can recompute the hash from the data and verify integrity.
    """
    from app.services import verification_service
    return verification_service.get_chain(asset_id, from_date, to_date)


@router.get("/verification/recompute/{asset_id}", summary="Recompute and verify a hash chain")
async def recompute_and_verify(
    asset_id: str,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> dict[str, Any]:
    """Recompute every hash in the chain from underlying data and verify integrity.

    Returns {valid: true/false, entries: N, first_failure: {...} | null}.
    No auth required — this is the core public verification endpoint.
    """
    from app.services import verification_service
    return verification_service.verify_chain(asset_id, from_date, to_date)


@router.get("/verification/snapshot/{week}", summary="Get a weekly signed snapshot")
async def get_snapshot(week: str) -> dict[str, Any]:
    """Fetch a weekly snapshot with Merkle root and Ed25519 signature.

    Week format: 2026-W16. No auth required.
    The payload can be independently verified using the public key.
    """
    from app.services import verification_service
    result = verification_service.get_snapshot(week)
    if not result:
        raise HTTPException(status_code=404, detail=f"Snapshot {week} not found")
    return result


@router.get("/verification/snapshot/{week}/verify", summary="Verify a snapshot signature")
async def verify_snapshot(week: str) -> dict[str, Any]:
    """Recompute Merkle root and verify Ed25519 signature on a snapshot.

    No auth required. Returns {signature_valid: true/false, ...}.
    """
    from app.services import verification_service
    return verification_service.verify_snapshot(week)


@router.get("/verification/public-key", summary="Get the Ed25519 verification public key")
async def get_public_key() -> dict[str, str]:
    """Return the Ed25519 public key used to sign weekly snapshots.

    Third parties use this to independently verify snapshot signatures.
    No auth required.
    """
    from app.services import verification_service
    pub_key = verification_service.get_public_key()
    return {
        "algorithm": "Ed25519",
        "public_key_hex": pub_key,
        "usage": "Verify weekly snapshot signatures with this key",
    }


# ---------------------------------------------------------------------------
# Administrative endpoints (auth required)
# ---------------------------------------------------------------------------


@router.post("/verification/compute-daily", summary="Trigger daily hash computation")
async def compute_daily(target_date: date | None = Query(None)) -> dict[str, Any]:
    """Compute Merkle hashes for all assets with reads on the given date.

    Defaults to yesterday. Auth required.
    """
    from app.services import verification_service
    return verification_service.compute_daily_hashes(target_date)


@router.post("/verification/publish-snapshot", summary="Publish a weekly snapshot")
async def publish_snapshot(week: str | None = Query(None)) -> dict[str, Any]:
    """Compute and publish a weekly snapshot with Merkle root + Ed25519 signature.

    Defaults to previous week. Auth required.
    """
    from app.services import verification_service
    return verification_service.compute_weekly_snapshot(week)
