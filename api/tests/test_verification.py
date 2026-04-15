"""Flow-centric tests for the public verification framework.

Tests the verification system as a third party would use it:
register asset → record reads → compute daily hashes → verify chain →
publish snapshot → verify signature.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"


def _uid(prefix: str = "test-asset") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Hash determinism (the foundation of verification)
# ---------------------------------------------------------------------------


def test_hash_determinism():
    """Same input always produces the same hash."""
    from app.services.verification_service import compute_hash

    h1 = compute_hash("asset-1", date(2026, 4, 15), 100, 1.5, "lc-space,lc-land", "0" * 64)
    h2 = compute_hash("asset-1", date(2026, 4, 15), 100, 1.5, "lc-space,lc-land", "0" * 64)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_hash_changes_with_input():
    """Different input produces different hash."""
    from app.services.verification_service import compute_hash, GENESIS_HASH

    h1 = compute_hash("asset-1", date(2026, 4, 15), 100, 1.5, "lc-space", GENESIS_HASH)
    h2 = compute_hash("asset-1", date(2026, 4, 15), 101, 1.5, "lc-space", GENESIS_HASH)  # different read_count
    assert h1 != h2


def test_merkle_root_single():
    """Merkle root of one hash is that hash."""
    from app.services.verification_service import compute_merkle_root

    assert compute_merkle_root(["abc123"]) == "abc123"


def test_merkle_root_deterministic():
    """Merkle root is deterministic for same inputs."""
    from app.services.verification_service import compute_merkle_root

    hashes = ["aaa", "bbb", "ccc", "ddd"]
    r1 = compute_merkle_root(hashes)
    r2 = compute_merkle_root(hashes)
    assert r1 == r2


# ---------------------------------------------------------------------------
# Ed25519 signing
# ---------------------------------------------------------------------------


def test_sign_and_verify():
    """Sign a message and verify with the public key."""
    from app.services.verification_service import sign_message, verify_signature, get_public_key

    try:
        import cryptography  # noqa: F401
    except ImportError:
        pytest.skip("cryptography not installed")

    message = b"test verification payload"
    sig = sign_message(message)
    pub = get_public_key()

    assert sig  # non-empty
    assert pub  # non-empty
    assert verify_signature(message, sig, pub)


def test_tampered_message_fails_verification():
    """Tampered message fails signature verification."""
    from app.services.verification_service import sign_message, verify_signature, get_public_key

    try:
        import cryptography  # noqa: F401
    except ImportError:
        pytest.skip("cryptography not installed")

    message = b"original message"
    sig = sign_message(message)
    pub = get_public_key()

    assert not verify_signature(b"tampered message", sig, pub)


# ---------------------------------------------------------------------------
# API endpoints (public, no auth)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_public_key_endpoint():
    """GET /api/verification/public-key returns key without auth."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/verification/public-key")
        assert r.status_code == 200
        body = r.json()
        assert body["algorithm"] == "Ed25519"
        assert "public_key_hex" in body


@pytest.mark.asyncio
async def test_chain_empty_asset():
    """GET /api/verification/chain/{id} returns empty list for unknown asset."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/verification/chain/nonexistent-asset")
        assert r.status_code == 200
        assert r.json() == []


@pytest.mark.asyncio
async def test_recompute_empty_chain():
    """Recompute on empty chain returns valid=true, entries=0."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        r = await c.get("/api/verification/recompute/nonexistent-asset")
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is True
        assert body["entries"] == 0


@pytest.mark.asyncio
async def test_compute_daily_and_verify():
    """Record reads → compute daily hashes → verify chain integrity."""
    from app.services import read_tracking_service, verification_service
    from app.services.unified_db import Base, engine as get_engine
    from datetime import date as _date

    # Ensure new tables exist (ORM models registered by importing the services)
    Base.metadata.create_all(get_engine())

    asset_id = _uid()
    today = _date.today()

    # Record some reads
    for _ in range(5):
        read_tracking_service.record_read(asset_id, "lc-space")

    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as c:
        # Trigger daily computation for today
        r = await c.post(f"/api/verification/compute-daily?target_date={today.isoformat()}")
        assert r.status_code == 200
        body = r.json()
        assert body["computed"] >= 1

        # Verify the chain
        r = await c.get(f"/api/verification/recompute/{asset_id}")
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is True
        assert body["entries"] >= 1


@pytest.mark.asyncio
async def test_read_tracking_stats():
    """Read tracking provides table stats for monitoring."""
    from app.services import read_tracking_service

    stats = read_tracking_service.get_table_stats()
    assert "total_rows" in stats
    assert "estimated_size_mb" in stats
    assert "needs_archive" in stats
