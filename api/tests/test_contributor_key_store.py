"""Tests for the DB-backed contributor API key store.

Calls the store directly — no HTTP layer — because all the interesting
behaviour lives below the route. HTTP layer is covered in
`test_auth_keys_api.py`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services import contributor_key_store as store


def _reset_table() -> None:
    """Truncate contributor_api_keys between tests so state never leaks.

    Uses the unified_db session to avoid pinning us to sqlite vs postgres.
    """
    from app.services.unified_db import session as db_session, ensure_schema

    ensure_schema()
    with db_session() as sess:
        sess.query(store.ContributorApiKeyRecord).delete()


def test_mint_returns_raw_key_exactly_once():
    _reset_table()
    result = store.mint("alice", label="laptop", provider="github", provider_id="alice")
    assert result.raw_key.startswith("cc_alice_")
    assert len(result.raw_key) > 30
    assert result.row.contributor_id == "alice"
    assert result.row.label == "laptop"
    assert result.row.provider == "github"
    assert result.row.scopes == store.DEFAULT_SCOPES
    assert result.row.active is True
    assert result.row.revoked_at is None


def test_mint_stores_only_the_hash_never_the_raw_key():
    _reset_table()
    result = store.mint("alice")
    # The id on the row is the SHA-256 hash, not the raw key.
    assert result.row.id != result.raw_key
    assert len(result.row.id) == 64  # sha256 hex
    import hashlib
    assert result.row.id == hashlib.sha256(result.raw_key.encode()).hexdigest()


def test_verify_roundtrip_returns_row():
    _reset_table()
    minted = store.mint("alice", label="laptop")
    row = store.verify(minted.raw_key)
    assert row is not None
    assert row.contributor_id == "alice"
    assert row.label == "laptop"


def test_verify_unknown_key_returns_none():
    _reset_table()
    assert store.verify("cc_ghost_" + "0" * 32) is None


def test_verify_empty_key_returns_none():
    _reset_table()
    assert store.verify("") is None


def test_verify_refreshes_last_used_at():
    _reset_table()
    minted = store.mint("alice", now=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert minted.row.last_used_at is None

    later = datetime(2026, 2, 15, 12, 34, 56, tzinfo=timezone.utc)
    row = store.verify(minted.raw_key, now=later)
    assert row is not None
    assert row.last_used_at is not None
    assert row.last_used_at.startswith("2026-02-15T12:34:56")


def test_list_for_returns_only_this_contributors_keys_newest_first():
    _reset_table()
    earliest = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store.mint("alice", label="one", now=earliest)
    store.mint("alice", label="two", now=earliest + timedelta(hours=1))
    store.mint("bob", label="bobs", now=earliest + timedelta(hours=2))

    alice_keys = store.list_for("alice")
    assert [k.label for k in alice_keys] == ["two", "one"]
    for k in alice_keys:
        assert k.contributor_id == "alice"


def test_list_for_hides_revoked_by_default():
    _reset_table()
    a = store.mint("alice", label="keepme")
    b = store.mint("alice", label="revokeme")
    store.revoke(b.row.id, owner_contributor_id="alice")

    active = store.list_for("alice")
    assert [k.label for k in active] == ["keepme"]

    all_keys = store.list_for("alice", include_revoked=True)
    assert sorted(k.label for k in all_keys) == ["keepme", "revokeme"]


def test_revoke_blocks_future_verify():
    _reset_table()
    minted = store.mint("alice")
    assert store.verify(minted.raw_key) is not None

    assert store.revoke(minted.row.id, owner_contributor_id="alice") is True
    assert store.verify(minted.raw_key) is None


def test_revoke_owner_check_blocks_other_contributors():
    _reset_table()
    alice = store.mint("alice")
    # Bob tries to revoke Alice's key — should return False, no effect.
    assert store.revoke(alice.row.id, owner_contributor_id="bob") is False
    # Alice's key still works.
    assert store.verify(alice.raw_key) is not None


def test_revoke_idempotent_returns_false_on_second_call():
    _reset_table()
    minted = store.mint("alice")
    assert store.revoke(minted.row.id, owner_contributor_id="alice") is True
    # Second revoke is a no-op and returns False.
    assert store.revoke(minted.row.id, owner_contributor_id="alice") is False


def test_revoke_unknown_key_returns_false():
    _reset_table()
    assert store.revoke("nonexistent_hash", owner_contributor_id="alice") is False


def test_count_active_excludes_revoked():
    _reset_table()
    store.mint("alice")
    a = store.mint("alice")
    store.mint("bob")
    assert store.count_active() == 3
    store.revoke(a.row.id, owner_contributor_id="alice")
    assert store.count_active() == 2


def test_get_by_id_returns_row_or_none():
    _reset_table()
    minted = store.mint("alice")
    fetched = store.get_by_id(minted.row.id)
    assert fetched is not None
    assert fetched.contributor_id == "alice"
    assert store.get_by_id("nope") is None


def test_mint_requires_contributor_id():
    _reset_table()
    import pytest

    with pytest.raises(ValueError):
        store.mint("")
