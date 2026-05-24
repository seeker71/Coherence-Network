"""Permanent storage service — Arweave + IPFS upload + integrity check (R3, R10).

Per specs/story-protocol-integration.md R3 and R10. The spec describes
asynchronous upload of asset content to Arweave (via an Irys/Bundlr
bundler) and to IPFS, recording the Arweave transaction id, the IPFS
content identifier, and a SHA-256 content hash on the asset graph
node. R10 returns the recomputed hash so callers can detect tamper.

**Mock bundler, real interface.** This iteration holds upload state
in module-level dicts and synthesizes deterministic content-addressed
ids of the shape:

  - ``arweave_tx_id = "ar:mock:" + sha256(content)[:16]``
  - ``ipfs_cid = "Qm" + sha256(content)[:44]``  (CIDv0-shaped)

The function signatures are the contract callers will use against the
real Irys bundler and a real IPFS HTTP API (or a managed pinning
service like Pinata / web3.storage) once partner selection lands;
only the body that performs the network upload and the synchronous
return will change. Persistence is a follow-up breath — when the
StorageRecord PostgreSQL table arrives (see spec Data Model), the
dicts move to rows behind the same surface.

The three named functions the spec's `source:` block claims for this
file:

  - ``upload_to_arweave(content, metadata) -> dict``
  - ``upload_to_ipfs(content) -> dict``
  - ``verify_content_integrity(asset_id, expected_hash) -> dict``

In the mock, ``verify_content_integrity`` recomputes the SHA-256 from
the bytes held in-process for the asset. In production it would re-
fetch the bytes from the Arweave gateway and the IPFS gateway and
compare both recomputed hashes against the stored expected hash, so
tamper at either surface is detectable independently.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# Module-level state — first iteration. Replaced by graph_service +
# PostgreSQL persistence once the StorageRecord table lands.
_arweave_uploads: Dict[str, Dict[str, Any]] = {}
_ipfs_uploads: Dict[str, Dict[str, Any]] = {}
_asset_storage: Dict[str, Dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_hex(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _mint_arweave_tx_id(content_hash: str) -> str:
    """Deterministic content-addressed mock Arweave transaction id.
    Same content → same id (Arweave/Irys is itself content-addressed,
    so a real bundler also returns the same id for re-upload of
    identical bytes)."""
    return f"ar:mock:{content_hash[:16]}"


def _mint_ipfs_cid(content_hash: str) -> str:
    """Deterministic CIDv0-shaped mock IPFS content id. Real IPFS
    returns a base58-encoded multihash; this prefix marks the value as
    a stub so nothing accidentally publishes it to a real gateway."""
    return f"Qm{content_hash[:44]}"


def upload_to_arweave(
    content: bytes,
    metadata: Optional[dict] = None,
    *,
    asset_id: Optional[str] = None,
) -> dict:
    """Upload bytes to Arweave via a (mocked) Irys bundler.

    Returns ``{arweave_tx_id, content_hash, size_bytes, uploaded_at,
    metadata}``. Content-addressed: same bytes always produce the same
    ``arweave_tx_id``, matching the real bundler's behavior.

    ``asset_id`` is optional — when provided, the upload is keyed by
    asset so ``verify_content_integrity`` can later re-fetch the bytes
    by asset id. Without it the upload is still recorded under its
    content hash so de-duplication works.
    """
    if content is None:
        raise ValueError("content is required")
    if not isinstance(content, (bytes, bytearray)):
        raise ValueError(
            f"content must be bytes, got {type(content).__name__}"
        )

    raw = bytes(content)
    content_hash = _sha256_hex(raw)
    arweave_tx_id = _mint_arweave_tx_id(content_hash)
    record = {
        "arweave_tx_id": arweave_tx_id,
        "content_hash": content_hash,
        "size_bytes": len(raw),
        "uploaded_at": _now_iso(),
        "metadata": dict(metadata) if isinstance(metadata, dict) else {},
    }
    _arweave_uploads[arweave_tx_id] = {**record, "content": raw}
    if asset_id:
        _link_asset(
            asset_id,
            arweave_tx_id=arweave_tx_id,
            content_hash=content_hash,
            content=raw,
        )
    return dict(record)


def upload_to_ipfs(
    content: bytes,
    *,
    asset_id: Optional[str] = None,
) -> dict:
    """Upload bytes to IPFS via a (mocked) HTTP API / pinning service.

    Returns ``{ipfs_cid, content_hash, size_bytes, uploaded_at}``.
    Content-addressed: same bytes always produce the same ``ipfs_cid``,
    matching the real IPFS behavior.

    ``asset_id`` is optional — when provided, the upload is keyed by
    asset so ``verify_content_integrity`` can later re-fetch the bytes
    by asset id. Without it the upload is still recorded under its
    CID so de-duplication works.
    """
    if content is None:
        raise ValueError("content is required")
    if not isinstance(content, (bytes, bytearray)):
        raise ValueError(
            f"content must be bytes, got {type(content).__name__}"
        )

    raw = bytes(content)
    content_hash = _sha256_hex(raw)
    ipfs_cid = _mint_ipfs_cid(content_hash)
    record = {
        "ipfs_cid": ipfs_cid,
        "content_hash": content_hash,
        "size_bytes": len(raw),
        "uploaded_at": _now_iso(),
    }
    _ipfs_uploads[ipfs_cid] = {**record, "content": raw}
    if asset_id:
        _link_asset(
            asset_id,
            ipfs_cid=ipfs_cid,
            content_hash=content_hash,
            content=raw,
        )
    return dict(record)


def verify_content_integrity(asset_id: str, expected_hash: str) -> dict:
    """Compare a stored content hash against a freshly recomputed one.

    Returns ``{asset_id, integrity, arweave_hash, ipfs_hash,
    expected_hash, arweave_tx_id, ipfs_cid, checked_at}``.

    - ``integrity`` is ``"passed"`` when every surface that returned a
      hash matches ``expected_hash`` (and at least one surface
      returned a hash); ``"failed"`` otherwise (including when the
      asset is unknown to this service).
    - In this mock, the recomputed hashes come from the bytes held
      in-process. In production, they come from re-fetching the bytes
      from the Arweave gateway and the IPFS gateway respectively, so
      tamper at either surface is detectable independently.

    The dict surfaces both recomputed hashes so the caller can tell
    *which* surface failed, not just that something did.
    """
    if not asset_id:
        raise ValueError("asset_id is required")
    if not expected_hash:
        raise ValueError("expected_hash is required")

    record = _asset_storage.get(asset_id)
    if record is None:
        return {
            "asset_id": asset_id,
            "integrity": "failed",
            "reason": "no_storage_record",
            "expected_hash": expected_hash,
            "arweave_hash": None,
            "ipfs_hash": None,
            "arweave_tx_id": None,
            "ipfs_cid": None,
            "checked_at": _now_iso(),
        }

    arweave_content = record.get("arweave_content")
    ipfs_content = record.get("ipfs_content")
    arweave_hash = _sha256_hex(arweave_content) if arweave_content is not None else None
    ipfs_hash = _sha256_hex(ipfs_content) if ipfs_content is not None else None

    surfaces = []
    if arweave_hash is not None:
        surfaces.append(arweave_hash == expected_hash)
    if ipfs_hash is not None:
        surfaces.append(ipfs_hash == expected_hash)
    integrity = "passed" if surfaces and all(surfaces) else "failed"

    return {
        "asset_id": asset_id,
        "integrity": integrity,
        "expected_hash": expected_hash,
        "arweave_hash": arweave_hash,
        "ipfs_hash": ipfs_hash,
        "arweave_tx_id": record.get("arweave_tx_id"),
        "ipfs_cid": record.get("ipfs_cid"),
        "checked_at": _now_iso(),
    }


def get_storage_record(asset_id: str) -> Optional[dict]:
    """Return the in-process storage record for an asset, or None.
    Excludes the raw bytes so the return is JSON-safe."""
    record = _asset_storage.get(asset_id)
    if record is None:
        return None
    return {
        "asset_id": asset_id,
        "arweave_tx_id": record.get("arweave_tx_id"),
        "ipfs_cid": record.get("ipfs_cid"),
        "content_hash": record.get("content_hash"),
        "size_bytes": record.get("size_bytes"),
        "uploaded_at": record.get("uploaded_at"),
    }


def _link_asset(
    asset_id: str,
    *,
    arweave_tx_id: Optional[str] = None,
    ipfs_cid: Optional[str] = None,
    content_hash: Optional[str] = None,
    content: Optional[bytes] = None,
) -> None:
    """Merge per-asset storage record with one or both surface results.

    Stores the raw bytes per-surface so ``verify_content_integrity``
    can detect tamper independently at Arweave and IPFS in production.
    """
    record = _asset_storage.setdefault(asset_id, {})
    if arweave_tx_id is not None:
        record["arweave_tx_id"] = arweave_tx_id
        if content is not None:
            record["arweave_content"] = content
    if ipfs_cid is not None:
        record["ipfs_cid"] = ipfs_cid
        if content is not None:
            record["ipfs_content"] = content
    if content_hash is not None:
        record["content_hash"] = content_hash
    if content is not None:
        record["size_bytes"] = len(content)
    record["uploaded_at"] = _now_iso()


def _reset_for_tests() -> None:
    """Clear module-level state. Call from a pytest fixture so each
    test starts on fresh ground."""
    _arweave_uploads.clear()
    _ipfs_uploads.clear()
    _asset_storage.clear()
