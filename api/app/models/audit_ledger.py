"""Pydantic models for the Transparent Audit Ledger -- spec 123."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditEntryType(str, Enum):
    # CC Transactions
    CC_MINTED = "CC_MINTED"
    CC_BURNED = "CC_BURNED"
    CC_TRANSFER = "CC_TRANSFER"
    CC_ATTRIBUTION = "CC_ATTRIBUTION"
    
    # Governance
    GOVERNANCE_VOTE = "GOVERNANCE_VOTE"
    GOVERNANCE_DECISION = "GOVERNANCE_DECISION"
    
    # Valuation
    VALUATION_CHANGE = "VALUATION_CHANGE"
    
    # Treasury (spec 122)
    DEPOSIT_INITIATED = "DEPOSIT_INITIATED"
    DEPOSIT_CONFIRMED = "DEPOSIT_CONFIRMED"
    WITHDRAWAL_REQUESTED = "WITHDRAWAL_REQUESTED"
    WITHDRAWAL_APPROVED = "WITHDRAWAL_APPROVED"
    WITHDRAWAL_COMPLETED = "WITHDRAWAL_COMPLETED"
    WITHDRAWAL_REJECTED = "WITHDRAWAL_REJECTED"
    
    # Marketplace (spec 121)
    MARKETPLACE_PUBLISH = "MARKETPLACE_PUBLISH"
    MARKETPLACE_FORK = "MARKETPLACE_FORK"
    
    # System
    SNAPSHOT_CREATED = "SNAPSHOT_CREATED"


class AuditEntry(BaseModel):
    entry_id: str = Field(description="Monotonically increasing, gap-free (aud_00001)")
    entry_type: AuditEntryType
    timestamp: datetime = Field(description="UTC timestamp")
    sender_id: str = Field(min_length=1, description="Originator (user, SYSTEM, or EXTERNAL)")
    receiver_id: str = Field(min_length=1, description="Recipient (user, GOVERNANCE, TREASURY, or SYSTEM)")
    amount_cc: float = Field(ge=0.0, description="CC amount (0.0 for non-financial entries)")
    reason: str = Field(min_length=1, max_length=1000)
    reference_id: Optional[str] = Field(None, description="Links to source record (deposit_id, idea_id, etc.)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Entry-type-specific structured data")
    hash: str = Field(description="SHA-256 hash of entry content")
    previous_hash: str = Field(description="SHA-256 hash of previous entry")


class AuditEntryCreate(BaseModel):
    """Internal model for creating an entry (id/hash/timestamp/prev_hash set by service)."""
    entry_type: AuditEntryType
    sender_id: str
    receiver_id: str
    amount_cc: float = 0.0
    reason: str
    reference_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditSnapshot(BaseModel):
    snapshot_id: str = Field(description="snap_YYYYMMDD")
    timestamp: datetime
    entry_count: int = Field(ge=0)
    head_hash: str
    head_entry_id: str
    signature: str = Field(description="JWS signature")
    signer_instance_id: str


class VerificationResult(BaseModel):
    verified: bool
    entries_checked: int = Field(ge=0)
    from_entry_id: Optional[str] = None
    to_entry_id: Optional[str] = None
    computed_head_hash: str
    expected_head_hash: str
    first_invalid_entry_id: Optional[str] = None
    verification_duration_ms: int
    verified_at: datetime


class AuditTransactionResponse(BaseModel):
    entries: list[AuditEntry]
    total: int
    page: int
    page_size: int
    head_hash: Optional[str] = None


class AuditGovernanceResponse(BaseModel):
    entries: list[AuditEntry]
    total: int
    page: int
    page_size: int
    head_hash: Optional[str] = None


class AuditTreasuryResponse(BaseModel):
    entries: list[AuditEntry]
    total: int
    page: int
    page_size: int
    head_hash: Optional[str] = None


class AuditSnapshotResponse(BaseModel):
    snapshots: list[AuditSnapshot]
    total: int
    page: int
    page_size: int
