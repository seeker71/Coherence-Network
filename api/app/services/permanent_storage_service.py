"""Permanent storage service — Arweave + IPFS bundler integration (pending).

Per specs/story-protocol-integration.md R3. The spec describes
permanent upload of asset content to Arweave via a bundler (Irys/
Bundlr) and content-addressed retrieval via IPFS. The resulting
`arweave_tx_id` and `ipfs_cid` are stored on the asset's graph node.

**Not yet wired.** The real implementation requires bundler service
selection and a platform-owned funding wallet:
  - Which bundler? Irys (formerly Bundlr) vs direct Arweave node
  - Which IPFS gateway? Pinata / Web3.Storage / self-hosted
  - Funding model? Platform pays bundler in AR / USDC per upload?
  - Max file size? 50MB proposed in spec; larger needs chunked upload

Until those decisions land, this module provides the function
signatures so the rest of the system can import and call. Functions
raise `PermanentStoragePending` with a clear message so callers
can mark the asset's storage refs as `pending` and retry once
the service is live.

Content integrity verification (`verify_content_integrity`) already
exists in `story_protocol_bridge.verify_content_integrity()` and
does NOT depend on the storage service — it can be called today
against any already-stored `arweave_tx_id` or local content hash.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class PermanentStoragePending(Exception):
    """Raised when a permanent storage upload is invoked before the
    bundler/IPFS integration lands."""


@dataclass(frozen=True)
class PermanentStorageResult:
    """Shape the real implementation will return."""

    arweave_tx_id: Optional[str]
    ipfs_cid: Optional[str]
    content_hash: str  # sha256:<hex>
    uploaded_at: str   # ISO 8601
    size_bytes: int


def is_ready() -> bool:
    """Return True once the Arweave bundler client and IPFS gateway
    are configured. Returns False for the current partner-gated state.
    """
    return False


def upload_to_arweave(
    content: bytes,
    *,
    mime_type: str,
    tags: Optional[dict] = None,
) -> str:
    """Upload raw content to Arweave via the configured bundler.

    Returns the Arweave transaction ID on success. The caller is
    responsible for computing the SHA-256 hash and storing it on
    the asset node alongside the returned tx_id.
    """
    raise PermanentStoragePending(
        "Arweave bundler integration is pending partner selection. "
        "See specs/story-protocol-integration.md R3 for the contract."
    )


def upload_to_ipfs(
    content: bytes,
    *,
    mime_type: str,
) -> str:
    """Upload content to IPFS via the configured gateway.

    Returns the content identifier (CID) on success.
    """
    raise PermanentStoragePending(
        "IPFS gateway integration is pending partner selection."
    )


def upload(
    content: bytes,
    *,
    mime_type: str,
    tags: Optional[dict] = None,
) -> PermanentStorageResult:
    """Upload to both Arweave and IPFS in parallel; return the
    combined result.

    This is the recommended entry point — it ensures both storage
    tiers are populated so the asset has permanent (Arweave) and
    retrievable (IPFS) paths.
    """
    raise PermanentStoragePending(
        "Permanent storage integration is pending partner selection."
    )


def verify_content_integrity(
    expected_content_hash: str,
    arweave_tx_id: Optional[str] = None,
    ipfs_cid: Optional[str] = None,
) -> dict:
    """Fetch content from permanent storage and verify its SHA-256
    hash matches the expected value.

    Returns a dict with `arweave_match`, `ipfs_match`, and `overall_ok`.
    Both `arweave_tx_id` and `ipfs_cid` are optional — pass what's
    available. If neither is provided, raises ValueError.

    The hashing half of this check is already implemented in
    `app.services.story_protocol_bridge.verify_content_integrity()`
    — once fetch is live, this function just fetches bytes from
    the two sources and hands them to the bridge's pure hasher.
    """
    if arweave_tx_id is None and ipfs_cid is None:
        raise ValueError(
            "at least one of arweave_tx_id or ipfs_cid must be provided"
        )
    raise PermanentStoragePending(
        "Permanent storage integration is pending partner selection."
    )
