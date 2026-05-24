"""IP registration service — Story Protocol queue surface (first iteration).

Per specs/story-protocol-integration.md R1 and R7. The spec describes
async registration of an asset as an IP Asset on Story Protocol,
returning an IP Asset ID stored on the asset's graph node, and a
derivative-work royalty record using the 15/85 default split.

**Mock SDK, real interface.** This iteration holds registration and
derivative state in module-level dicts and synthesizes a deterministic
`sp_ip_id` of the shape `sp:mock:<asset_id_prefix>`. The function
signatures are the contract callers will use against the real Story
Protocol SDK once partner selection (chain + signer + royalty module)
lands; only the body that mints `sp_ip_id` and the synchronous return
will change. Persistence is a follow-up breath — when the IPRegistration
PostgreSQL table arrives (see spec Data Model), the dicts move to rows
behind the same surface.

The three named functions the spec's `source:` block claims for this
file:

  - `register_ip_asset(asset_id, metadata) -> dict`
  - `get_ip_status(asset_id) -> dict`
  - `record_derivative(parent_asset_id, derivative_asset_id, derivative_type) -> dict`
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


# Module-level state — first iteration. Replaced by graph_service +
# PostgreSQL persistence once the IPRegistration table lands.
_registrations: Dict[str, Dict[str, Any]] = {}
_derivatives: Dict[str, Dict[str, Any]] = {}


# Royalty split defaults from spec R7.
DEFAULT_ROYALTY_SPLIT = {"parent": 0.15, "derivative": 0.85}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mint_sp_ip_id(asset_id: str) -> str:
    """Deterministic mock IP Asset ID. The real SDK returns an
    on-chain hex address; this prefix marks the value as a stub so
    nothing accidentally pushes it to a real chain."""
    prefix = asset_id[:8] if len(asset_id) >= 8 else asset_id
    return f"sp:mock:{prefix}"


def _validate_metadata(metadata: Any) -> Optional[str]:
    """Return None if metadata is acceptable, otherwise a reason string.

    Acceptable metadata is a dict (possibly empty). Non-dict values,
    or a dict carrying a sentinel `_force_failure` key, transition the
    registration to `failed`. The sentinel exists for the test that
    proves the failure path without needing a real SDK error."""
    if metadata is None:
        return None
    if not isinstance(metadata, dict):
        return f"metadata must be a dict, got {type(metadata).__name__}"
    if metadata.get("_force_failure"):
        reason = metadata.get("_force_failure_reason", "forced failure")
        return str(reason)
    return None


def register_ip_asset(asset_id: str, metadata: Optional[dict] = None) -> dict:
    """Queue (and, in this iteration, immediately complete) an IP Asset
    registration with Story Protocol.

    Returns a dict with `asset_id`, `sp_ip_id`, `ip_status`, and
    `registered_at`. On malformed metadata the status is `failed` and
    the dict carries a `reason` field; `sp_ip_id` is None in that case.

    Idempotent: registering the same `asset_id` twice returns the
    existing record. To re-register, callers must clear state via
    `_reset_for_tests()` (production will offer an explicit retry path).
    """
    if not asset_id:
        raise ValueError("asset_id is required")

    existing = _registrations.get(asset_id)
    if existing is not None:
        return dict(existing)

    failure_reason = _validate_metadata(metadata)
    now = _now_iso()
    if failure_reason is not None:
        record = {
            "asset_id": asset_id,
            "sp_ip_id": None,
            "ip_status": "failed",
            "reason": failure_reason,
            "registered_at": None,
            "queued_at": now,
            "metadata": metadata if isinstance(metadata, dict) else {},
        }
    else:
        record = {
            "asset_id": asset_id,
            "sp_ip_id": _mint_sp_ip_id(asset_id),
            "ip_status": "registered",
            "registered_at": now,
            "queued_at": now,
            "metadata": metadata or {},
        }
    _registrations[asset_id] = record
    return dict(record)


def get_ip_status(asset_id: str) -> dict:
    """Return the current IP registration record for `asset_id`.

    For unknown assets returns `{"asset_id": asset_id,
    "ip_status": "not_registered"}` so callers can treat absence as a
    first-class state rather than handling a None.
    """
    record = _registrations.get(asset_id)
    if record is None:
        return {"asset_id": asset_id, "ip_status": "not_registered"}
    return dict(record)


def record_derivative(
    parent_asset_id: str,
    derivative_asset_id: str,
    derivative_type: str,
    *,
    royalty_split: Optional[Dict[str, float]] = None,
) -> dict:
    """Record a derivative-work relationship with the parent IP Asset.

    Stores the parent → derivative edge with a royalty split. Default
    is `{"parent": 0.15, "derivative": 0.85}` per spec R7; callers
    pass `royalty_split={"parent": X, "derivative": Y}` to override.
    The split must sum to 1.0 within a small tolerance.

    Returns the recorded relationship as a dict.
    """
    if not parent_asset_id or not derivative_asset_id:
        raise ValueError("parent_asset_id and derivative_asset_id are required")
    if parent_asset_id == derivative_asset_id:
        raise ValueError("a derivative cannot be its own parent")
    if not derivative_type:
        raise ValueError("derivative_type is required")

    split = dict(royalty_split) if royalty_split else dict(DEFAULT_ROYALTY_SPLIT)
    if set(split.keys()) != {"parent", "derivative"}:
        raise ValueError("royalty_split must have keys 'parent' and 'derivative'")
    total = split["parent"] + split["derivative"]
    if abs(total - 1.0) > 0.001:
        raise ValueError(f"royalty_split must sum to 1.0, got {total}")

    record = {
        "parent_asset_id": parent_asset_id,
        "derivative_asset_id": derivative_asset_id,
        "derivative_type": derivative_type,
        "royalty_split": split,
        "recorded_at": _now_iso(),
    }
    _derivatives[derivative_asset_id] = record
    return dict(record)


def _reset_for_tests() -> None:
    """Clear module-level state. Call from a pytest fixture so each
    test starts on fresh ground."""
    _registrations.clear()
    _derivatives.clear()
