"""DB-backed contributor API key store.

Three flows cover the service's contract:

  · mint: raw key returned once, only the hash persisted, label +
    scopes + provider recorded, empty contributor_id rejected
  · verify: round-trips the row, updates last_used_at, returns None
    on unknown/empty keys; revoke blocks future verify and enforces
    owner check; revoke is idempotent; revoke on unknown key is a
    no-op
  · list + count + get: list_for returns only this contributor's
    keys newest-first, hides revoked by default (include_revoked
    shows all), count_active excludes revoked, get_by_id returns
    row or None
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from app.services import contributor_key_store as store


def _reset_table() -> None:
    from app.services.unified_db import session as db_session, ensure_schema
    ensure_schema()
    with db_session() as sess:
        sess.query(store.ContributorApiKeyRecord).delete()


def test_mint_flow():
    """Mint returns raw key exactly once, persists only the hash,
    records label/provider/scopes, and rejects empty contributor_id."""
    _reset_table()
    result = store.mint("alice", label="laptop", provider="github",
                        provider_id="alice")
    assert result.raw_key.startswith("cc_alice_")
    assert len(result.raw_key) > 30
    assert result.row.contributor_id == "alice"
    assert result.row.label == "laptop"
    assert result.row.provider == "github"
    assert result.row.scopes == store.DEFAULT_SCOPES
    assert result.row.active is True
    assert result.row.revoked_at is None

    # Only the hash lives on the row — id != raw key.
    assert result.row.id != result.raw_key
    assert len(result.row.id) == 64  # sha256 hex
    assert result.row.id == hashlib.sha256(result.raw_key.encode()).hexdigest()

    # Empty contributor_id → ValueError.
    with pytest.raises(ValueError):
        store.mint("")


def test_verify_and_revoke_flow():
    """Verify round-trips, updates last_used_at, None on unknown/empty;
    revoke blocks future verify, enforces owner, is idempotent, and
    returns False on unknown key."""
    _reset_table()

    # Verify round-trip.
    minted = store.mint("alice", label="laptop")
    row = store.verify(minted.raw_key)
    assert row is not None
    assert row.contributor_id == "alice" and row.label == "laptop"

    # Unknown + empty keys return None, not errors.
    assert store.verify("cc_ghost_" + "0" * 32) is None
    assert store.verify("") is None

    # Verify refreshes last_used_at.
    time_minted = datetime(2026, 1, 1, tzinfo=timezone.utc)
    fresh = store.mint("alice", now=time_minted)
    assert fresh.row.last_used_at is None
    later = datetime(2026, 2, 15, 12, 34, 56, tzinfo=timezone.utc)
    used = store.verify(fresh.raw_key, now=later)
    assert used is not None
    assert used.last_used_at is not None
    assert used.last_used_at.startswith("2026-02-15T12:34:56")

    # Revoke blocks future verify.
    assert store.verify(minted.raw_key) is not None
    assert store.revoke(minted.row.id, owner_contributor_id="alice") is True
    assert store.verify(minted.raw_key) is None

    # Owner check: Bob can't revoke Alice's key.
    alice_key = store.mint("alice")
    assert store.revoke(alice_key.row.id, owner_contributor_id="bob") is False
    assert store.verify(alice_key.raw_key) is not None

    # Idempotent: second revoke returns False (no-op), key already revoked.
    assert store.revoke(alice_key.row.id, owner_contributor_id="alice") is True
    assert store.revoke(alice_key.row.id, owner_contributor_id="alice") is False

    # Unknown key revoke → False.
    assert store.revoke("nonexistent_hash", owner_contributor_id="alice") is False


def test_list_count_and_get_flow():
    """list_for returns only this contributor's keys newest-first,
    hides revoked by default (include_revoked shows them);
    count_active excludes revoked; get_by_id returns row or None."""
    _reset_table()
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # Two Alice keys (different timestamps) + one Bob key.
    store.mint("alice", label="one", now=base)
    store.mint("alice", label="two", now=base + timedelta(hours=1))
    store.mint("bob", label="bobs", now=base + timedelta(hours=2))

    alice_keys = store.list_for("alice")
    assert [k.label for k in alice_keys] == ["two", "one"]
    for k in alice_keys:
        assert k.contributor_id == "alice"

    # Revoke hides by default; include_revoked=True shows all.
    _reset_table()
    keep = store.mint("alice", label="keepme")
    revoke_me = store.mint("alice", label="revokeme")
    store.revoke(revoke_me.row.id, owner_contributor_id="alice")
    assert [k.label for k in store.list_for("alice")] == ["keepme"]
    assert sorted(k.label for k in store.list_for("alice", include_revoked=True)) == [
        "keepme", "revokeme",
    ]

    # count_active reflects revoke.
    _reset_table()
    store.mint("alice")
    alice_b = store.mint("alice")
    store.mint("bob")
    assert store.count_active() == 3
    store.revoke(alice_b.row.id, owner_contributor_id="alice")
    assert store.count_active() == 2

    # get_by_id returns row or None.
    _reset_table()
    minted = store.mint("alice")
    fetched = store.get_by_id(minted.row.id)
    assert fetched is not None and fetched.contributor_id == "alice"
    assert store.get_by_id("nope") is None
    # Keep 'keep' referenced so mypy doesn't flag it; real assertion is above.
    _ = keep
