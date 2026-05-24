"""Flow tests for permanent_storage_service — story-protocol-integration R3, R10.

Exercises the three named functions the spec's `source:` block claims:
upload_to_arweave, upload_to_ipfs, verify_content_integrity. The
service holds state in module-level dicts in this iteration; each test
starts fresh via the autouse reset fixture.
"""

from __future__ import annotations

import hashlib

import pytest

from app.services import permanent_storage_service


@pytest.fixture(autouse=True)
def _reset():
    permanent_storage_service._reset_for_tests()
    yield
    permanent_storage_service._reset_for_tests()


# ---------------------------------------------------------------------------
# upload_to_arweave
# ---------------------------------------------------------------------------


def test_upload_to_arweave_returns_tx_id():
    result = permanent_storage_service.upload_to_arweave(
        b"rammed-earth-kitchen-blueprint", {"type": "BLUEPRINT"}
    )
    assert "arweave_tx_id" in result
    assert result["arweave_tx_id"].startswith("ar:mock:")
    assert result["size_bytes"] == len(b"rammed-earth-kitchen-blueprint")


def test_upload_to_arweave_deterministic():
    content = b"identical bytes produce identical tx ids"
    first = permanent_storage_service.upload_to_arweave(content)
    second = permanent_storage_service.upload_to_arweave(content)
    assert first["arweave_tx_id"] == second["arweave_tx_id"]
    assert first["content_hash"] == second["content_hash"]


def test_upload_to_arweave_includes_content_hash():
    content = b"check the sha256 made it through"
    expected = hashlib.sha256(content).hexdigest()
    result = permanent_storage_service.upload_to_arweave(content)
    assert result["content_hash"] == expected


def test_upload_to_arweave_rejects_non_bytes():
    with pytest.raises(ValueError, match="bytes"):
        permanent_storage_service.upload_to_arweave("a string is not bytes")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# upload_to_ipfs
# ---------------------------------------------------------------------------


def test_upload_to_ipfs_returns_cid():
    result = permanent_storage_service.upload_to_ipfs(b"glb-binary-payload")
    assert "ipfs_cid" in result
    assert result["ipfs_cid"].startswith("Qm")
    assert result["size_bytes"] == len(b"glb-binary-payload")


def test_upload_to_ipfs_deterministic():
    content = b"same bytes to same cid"
    first = permanent_storage_service.upload_to_ipfs(content)
    second = permanent_storage_service.upload_to_ipfs(content)
    assert first["ipfs_cid"] == second["ipfs_cid"]
    assert first["content_hash"] == second["content_hash"]


def test_upload_to_ipfs_includes_content_hash():
    content = b"hash on the ipfs side too"
    expected = hashlib.sha256(content).hexdigest()
    result = permanent_storage_service.upload_to_ipfs(content)
    assert result["content_hash"] == expected


# ---------------------------------------------------------------------------
# verify_content_integrity
# ---------------------------------------------------------------------------


def test_verify_content_integrity_passes_for_unchanged_content():
    asset_id = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    content = b"the blueprint that the asset will commit to"
    ar = permanent_storage_service.upload_to_arweave(
        content, {"type": "BLUEPRINT"}, asset_id=asset_id
    )
    permanent_storage_service.upload_to_ipfs(content, asset_id=asset_id)

    result = permanent_storage_service.verify_content_integrity(
        asset_id, ar["content_hash"]
    )
    assert result["integrity"] == "passed"
    assert result["expected_hash"] == ar["content_hash"]
    assert result["arweave_hash"] == ar["content_hash"]
    assert result["ipfs_hash"] == ar["content_hash"]


def test_verify_content_integrity_fails_for_changed_hash():
    asset_id = "asset-tamper-001"
    content = b"original bytes the creator uploaded"
    permanent_storage_service.upload_to_arweave(content, asset_id=asset_id)
    permanent_storage_service.upload_to_ipfs(content, asset_id=asset_id)

    wrong_hash = hashlib.sha256(b"different bytes someone is claiming").hexdigest()
    result = permanent_storage_service.verify_content_integrity(asset_id, wrong_hash)
    assert result["integrity"] == "failed"
    assert result["expected_hash"] == wrong_hash
    # The recomputed hashes are the real content's hash — they don't
    # equal the wrong expected_hash, which is what trips the fail.
    real_hash = hashlib.sha256(content).hexdigest()
    assert result["arweave_hash"] == real_hash
    assert result["ipfs_hash"] == real_hash


def test_verify_returns_both_arweave_and_ipfs_hashes():
    asset_id = "asset-dual-surface"
    content = b"both surfaces report independently"
    ar = permanent_storage_service.upload_to_arweave(content, asset_id=asset_id)
    ipfs = permanent_storage_service.upload_to_ipfs(content, asset_id=asset_id)

    result = permanent_storage_service.verify_content_integrity(
        asset_id, ar["content_hash"]
    )
    assert result["arweave_hash"] is not None
    assert result["ipfs_hash"] is not None
    assert result["arweave_tx_id"] == ar["arweave_tx_id"]
    assert result["ipfs_cid"] == ipfs["ipfs_cid"]


def test_verify_unknown_asset_fails_closed():
    result = permanent_storage_service.verify_content_integrity(
        "never-uploaded", "abc123" * 10
    )
    assert result["integrity"] == "failed"
    assert result["reason"] == "no_storage_record"
    assert result["arweave_hash"] is None
    assert result["ipfs_hash"] is None


def test_verify_requires_asset_id_and_hash():
    with pytest.raises(ValueError, match="asset_id"):
        permanent_storage_service.verify_content_integrity("", "deadbeef")
    with pytest.raises(ValueError, match="expected_hash"):
        permanent_storage_service.verify_content_integrity("asset-x", "")
