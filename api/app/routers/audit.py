"""Audit ledger router -- spec 123."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app.models.audit_ledger import (
    AuditEntryType,
    AuditGovernanceResponse,
    AuditSnapshotResponse,
    AuditTransactionResponse,
    AuditTreasuryResponse,
    VerificationResult,
)
from app.services import audit_ledger_service

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.get("/transactions", response_model=AuditTransactionResponse, summary="Query CC transaction audit entries")
async def get_audit_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    entry_type: Optional[AuditEntryType] = None,
    user_id: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    min_amount: Optional[float] = None,
):
    """Query CC transaction audit entries."""
    types = [entry_type] if entry_type else [
        AuditEntryType.CC_MINTED,
        AuditEntryType.CC_BURNED,
        AuditEntryType.CC_TRANSFER,
        AuditEntryType.CC_ATTRIBUTION,
    ]
    
    entries, total = audit_ledger_service.list_entries(
        entry_types=types,
        user_id=user_id,
        from_date=from_date,
        to_date=to_date,
        min_amount=min_amount,
        page=page,
        page_size=page_size,
    )
    
    # Get current head hash
    _, _total = audit_ledger_service.list_entries(page_size=1)
    head_hash = entries[0].hash if entries else None
    
    return AuditTransactionResponse(
        entries=entries,
        total=total,
        page=page,
        page_size=page_size,
        head_hash=head_hash,
    )


@router.get("/governance", response_model=AuditGovernanceResponse, summary="Query governance audit entries")
async def get_audit_governance(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    change_request_id: Optional[str] = None,
    voter_id: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
):
    """Query governance audit entries."""
    entries, total = audit_ledger_service.list_entries(
        entry_types=[AuditEntryType.GOVERNANCE_VOTE, AuditEntryType.GOVERNANCE_DECISION],
        sender_id=voter_id,
        reference_id=change_request_id,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    
    head_hash = entries[0].hash if entries else None
    
    return AuditGovernanceResponse(
        entries=entries,
        total=total,
        page=page,
        page_size=page_size,
        head_hash=head_hash,
    )


@router.get("/treasury", response_model=AuditTreasuryResponse, summary="Query treasury audit entries")
async def get_audit_treasury(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    entry_type: Optional[AuditEntryType] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
):
    """Query treasury audit entries."""
    types = [entry_type] if entry_type else [
        AuditEntryType.DEPOSIT_INITIATED,
        AuditEntryType.DEPOSIT_CONFIRMED,
        AuditEntryType.WITHDRAWAL_REQUESTED,
        AuditEntryType.WITHDRAWAL_APPROVED,
        AuditEntryType.WITHDRAWAL_COMPLETED,
        AuditEntryType.WITHDRAWAL_REJECTED,
    ]
    
    entries, total = audit_ledger_service.list_entries(
        entry_types=types,
        from_date=from_date,
        to_date=to_date,
        page=page,
        page_size=page_size,
    )
    
    head_hash = entries[0].hash if entries else None
    
    return AuditTreasuryResponse(
        entries=entries,
        total=total,
        page=page,
        page_size=page_size,
        head_hash=head_hash,
    )


@router.get("/verify", response_model=VerificationResult, summary="Verify hash chain integrity")
async def verify_audit_chain(
    from_entry_id: Optional[str] = None,
    to_entry_id: Optional[str] = None,
):
    """Verify hash chain integrity."""
    return audit_ledger_service.verify_chain(from_entry_id, to_entry_id)


@router.get("/snapshots", response_model=AuditSnapshotResponse, summary="List signed audit snapshots")
async def get_audit_snapshots(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    """List signed audit snapshots."""
    snapshots, total = audit_ledger_service.list_snapshots(page, page_size)
    return AuditSnapshotResponse(
        snapshots=snapshots,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/export", summary="Export ledger as newline-delimited JSON")
async def export_audit_ledger(
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
):
    """Export ledger as newline-delimited JSON."""
    return StreamingResponse(
        audit_ledger_service.stream_export(from_date, to_date),
        media_type="application/x-ndjson",
        headers={"Content-Disposition": "attachment; filename=audit_ledger_export.ndjson"},
    )
