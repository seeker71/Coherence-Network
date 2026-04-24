"""IP registration service — Story Protocol SDK integration (pending).

Per specs/story-protocol-integration.md R1. The spec describes async
registration of an asset as an IP Asset on Story Protocol, returning
an IP Asset ID stored on the asset's graph node.

**Not yet wired.** The real implementation requires the Story Protocol
SDK and a partner-selection gate:
  - Which chain? Story Protocol's own L2 on Base? Sepolia for testing?
  - Which signer? Platform-owned hot wallet or per-contributor wallet?
  - Which royalty module config? Default split vs configurable?

Until those decisions land, this module provides the function
signatures the rest of the system can import and call. Functions
raise `IpRegistrationPending` with a clear message so callers can
either check `is_ready()` first or catch the exception and fall
back to marking the asset's `ip_status` as `pending`.

Once partner selection completes:
  - Replace `IpRegistrationPending` raises with real SDK calls
  - Implement `register_ip_asset()` to call `sp.register_ip(...)`
  - Implement `get_ip_status()` to query the chain
  - Implement `record_derivative()` to wire the royalty module
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class IpRegistrationPending(Exception):
    """Raised when IP registration is invoked before Story Protocol
    SDK integration lands."""


@dataclass(frozen=True)
class IpRegistrationResult:
    """Shape the real implementation will return."""

    sp_ip_id: str
    tx_hash: str
    royalty_module_address: Optional[str]
    registered_at: str  # ISO 8601


def is_ready() -> bool:
    """Return True once the Story Protocol SDK is wired and a signer
    is configured. Returns False for the current partner-gated state.
    """
    return False


def register_ip_asset(
    asset_id: str,
    creator_id: str,
    *,
    content_hash: str,
    metadata: Optional[dict] = None,
) -> IpRegistrationResult:
    """Register an asset as an IP Asset on Story Protocol.

    Returns an IpRegistrationResult with the on-chain IP Asset ID,
    transaction hash, and royalty module address. The caller stores
    `sp_ip_id` on the asset's graph node under property `sp_ip_id`
    and flips `ip_status` from `pending` to `registered`.
    """
    raise IpRegistrationPending(
        "Story Protocol SDK integration is pending partner selection. "
        "See specs/story-protocol-integration.md R1 for the contract."
    )


def get_ip_status(sp_ip_id: str) -> dict:
    """Query the on-chain status of a registered IP Asset.

    Returns a dict with fields the settlement service reads to confirm
    the asset's IP Asset is confirmed and accruing royalties.
    """
    raise IpRegistrationPending(
        "Story Protocol SDK integration is pending partner selection."
    )


def record_derivative(
    child_asset_id: str,
    parent_sp_ip_id: str,
    *,
    royalty_split_parent: float = 0.15,
    royalty_split_child: float = 0.85,
) -> IpRegistrationResult:
    """Register a derivative work with the royalty module.

    Configures the parent/child royalty split so future CC flows
    attribute proportionally. Default 15%/85% per spec R7.
    """
    if abs(royalty_split_parent + royalty_split_child - 1.0) > 0.001:
        raise ValueError(
            "royalty_split_parent + royalty_split_child must sum to 1.0"
        )
    raise IpRegistrationPending(
        "Story Protocol royalty module integration is pending partner selection."
    )
