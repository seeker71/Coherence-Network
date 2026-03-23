"""Transparent Audit Ledger service -- spec 123."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Generator, Optional, Sequence

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, desc, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.models.audit_ledger import (
    AuditEntry,
    AuditEntryCreate,
    AuditEntryType,
    AuditSnapshot,
    VerificationResult,
)
from app.services.unified_db import Base, session as db_session, ensure_schema

logger = logging.getLogger(__name__)

GENESIS_HASH = f"sha256:{hashlib.sha256(b'coherence-network-genesis').hexdigest()}"


class AuditEntryRecord(Base):
    __tablename__ = "audit_ledger"

    # We use a simple integer primary key for sequential ordering
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sender_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    receiver_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    amount_cc: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reference_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    previous_hash: Mapped[str] = mapped_column(String, nullable=False)

    def to_model(self) -> AuditEntry:
        try:
            metadata = json.loads(self.metadata_json)
        except Exception:
            metadata = {}
        
        # Ensure timestamp is UTC-aware even if returned as naive from DB (common with SQLite)
        ts = self.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        
        return AuditEntry(
            entry_id=f"aud_{self.id:05d}",
            entry_type=AuditEntryType(self.entry_type),
            timestamp=ts,
            sender_id=self.sender_id,
            receiver_id=self.receiver_id,
            amount_cc=self.amount_cc,
            reason=self.reason,
            reference_id=self.reference_id,
            metadata=metadata,
            hash=self.hash,
            previous_hash=self.previous_hash,
        )


class AuditSnapshotRecord(Base):
    __tablename__ = "audit_snapshots"

    snapshot_id: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False)
    head_hash: Mapped[str] = mapped_column(String, nullable=False)
    head_entry_id: Mapped[str] = mapped_column(String, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    signer_instance_id: Mapped[str] = mapped_column(String, nullable=False)

    def to_model(self) -> AuditSnapshot:
        return AuditSnapshot(
            snapshot_id=self.snapshot_id,
            timestamp=self.timestamp,
            entry_count=self.entry_count,
            head_hash=self.head_hash,
            head_entry_id=self.head_entry_id,
            signature=self.signature,
            signer_instance_id=self.signer_instance_id,
        )


def compute_entry_hash(
    previous_hash: str,
    entry_type: str,
    timestamp: datetime,
    sender_id: str,
    receiver_id: str,
    amount_cc: float,
    reason: str,
    reference_id: Optional[str],
    metadata: dict[str, Any],
) -> str:
    """Compute SHA-256 hash over entry content per spec 123."""
    # Ensure timestamp is awareness-safe even if returned as naive from DB
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    
    # Standardize timestamp to ISO8601 UTC string with Z suffix
    # We truncate microseconds to ensure consistency across DB storage/retrieval
    ts_utc = timestamp.astimezone(timezone.utc).replace(microsecond=0)
    ts_str = ts_utc.isoformat().replace("+00:00", "Z")
    
    # Stable JSON for metadata
    meta_str = json.dumps(metadata, sort_keys=True)
    
    # Concatenate fields
    content = (
        f"{previous_hash}{entry_type}{ts_str}{sender_id}{receiver_id}"
        f"{amount_cc:.8f}{reason}{reference_id or ''}{meta_str}"
    )
    res = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"
    if os.getenv("DEBUG_AUDIT"):
        print(f"DEBUG HASH: content={content!r} hash={res}")
    return res


def append_entry(
    entry: AuditEntryCreate,
    session_override: Optional[Session] = None,
) -> AuditEntry:
    """Append a new entry to the audit ledger with hash chaining."""
    ensure_schema()
    
    def _execute(session: Session) -> AuditEntry:
        # 1. Get previous hash (head of chain)
        # Use a lock to ensure sequential entry_id and correct hash chain
        # In SQLite this is implicit with serializable transactions
        # In Postgres, we might want an advisory lock or similar, but
        # simple SERIAL + last row read should be enough if we use a single transaction.
        
        last_entry = session.query(AuditEntryRecord).order_by(AuditEntryRecord.id.desc()).first()
        prev_hash = last_entry.hash if last_entry else GENESIS_HASH
        
        now = datetime.now(timezone.utc)
        
        # 2. Compute hash
        entry_hash = compute_entry_hash(
            previous_hash=prev_hash,
            entry_type=entry.entry_type.value,
            timestamp=now,
            sender_id=entry.sender_id,
            receiver_id=entry.receiver_id,
            amount_cc=entry.amount_cc,
            reason=entry.reason,
            reference_id=entry.reference_id,
            metadata=entry.metadata,
        )
        
        # 3. Create record
        record = AuditEntryRecord(
            entry_type=entry.entry_type.value,
            timestamp=now,
            sender_id=entry.sender_id,
            receiver_id=entry.receiver_id,
            amount_cc=entry.amount_cc,
            reason=entry.reason,
            reference_id=entry.reference_id,
            metadata_json=json.dumps(entry.metadata),
            hash=entry_hash,
            previous_hash=prev_hash,
        )
        
        session.add(record)
        session.flush() # Populate record.id
        session.refresh(record)
        
        return record.to_model()

    if session_override:
        return _execute(session_override)
    
    with db_session() as session:
        return _execute(session)


def list_entries(
    entry_types: Optional[list[AuditEntryType]] = None,
    sender_id: Optional[str] = None,
    receiver_id: Optional[str] = None,
    user_id: Optional[str] = None, # matches either sender or receiver
    reference_id: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    min_amount: Optional[float] = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AuditEntry], int]:
    """List audit entries with filters and pagination."""
    ensure_schema()
    page = max(1, page)
    page_size = max(1, min(page_size, 500))
    offset = (page - 1) * page_size
    
    with db_session() as session:
        query = session.query(AuditEntryRecord)
        
        if entry_types:
            query = query.filter(AuditEntryRecord.entry_type.in_([t.value for t in entry_types]))
        if sender_id:
            query = query.filter(AuditEntryRecord.sender_id == sender_id)
        if receiver_id:
            query = query.filter(AuditEntryRecord.receiver_id == receiver_id)
        if user_id:
            from sqlalchemy import or_
            query = query.filter(or_(AuditEntryRecord.sender_id == user_id, AuditEntryRecord.receiver_id == user_id))
        if reference_id:
            query = query.filter(AuditEntryRecord.reference_id == reference_id)
        if from_date:
            query = query.filter(AuditEntryRecord.timestamp >= from_date)
        if to_date:
            query = query.filter(AuditEntryRecord.timestamp <= to_date)
        if min_amount is not None:
            query = query.filter(AuditEntryRecord.amount_cc >= min_amount)
            
        total = query.count()
        records = query.order_by(AuditEntryRecord.id.desc()).offset(offset).limit(page_size).all()
        
        # Get latest head hash for response
        head_record = session.query(AuditEntryRecord).order_by(AuditEntryRecord.id.desc()).first()
        head_hash = head_record.hash if head_record else GENESIS_HASH
        
        return [r.to_model() for r in records], total


def verify_chain(
    from_entry_id: Optional[str] = None,
    to_entry_id: Optional[str] = None,
) -> VerificationResult:
    """Verify hash chain integrity from genesis or a given checkpoint."""
    ensure_schema()
    start_time = time.monotonic()
    
    with db_session() as session:
        query = session.query(AuditEntryRecord).order_by(AuditEntryRecord.id.asc())
        
        if from_entry_id:
            try:
                from_id_int = int(from_entry_id.replace("aud_", ""))
                query = query.filter(AuditEntryRecord.id >= from_id_int)
            except ValueError:
                pass
        
        if to_entry_id:
            try:
                to_id_int = int(to_entry_id.replace("aud_", ""))
                query = query.filter(AuditEntryRecord.id <= to_id_int)
            except ValueError:
                pass
                
        records = query.all()
        
        verified = True
        entries_checked = 0
        first_invalid_id = None
        computed_hash = GENESIS_HASH
        
        # If we started from a middle entry, we need its recorded previous_hash to start
        if records and from_entry_id:
            computed_hash = records[0].previous_hash
            
        for r in records:
            # Recompute hash
            try:
                metadata = json.loads(r.metadata_json)
            except Exception:
                metadata = {}
                
            actual_computed = compute_entry_hash(
                previous_hash=r.previous_hash,
                entry_type=r.entry_type,
                timestamp=r.timestamp,
                sender_id=r.sender_id,
                receiver_id=r.receiver_id,
                amount_cc=r.amount_cc,
                reason=r.reason,
                reference_id=r.reference_id,
                metadata=metadata,
            )
            
            # Check 1: Content matches recorded hash
            if actual_computed != r.hash:
                if os.getenv("DEBUG_AUDIT"):
                    print(f"DEBUG: Content hash mismatch at aud_{r.id:05d}")
                    print(f"  Expected (recorded): {r.hash}")
                    print(f"  Actual (computed):   {actual_computed}")
                verified = False
                first_invalid_id = f"aud_{r.id:05d}"
                break
                
            # Check 2: Chaining matches previous entry
            if r.previous_hash != computed_hash:
                if os.getenv("DEBUG_AUDIT"):
                    print(f"DEBUG: Chaining mismatch at aud_{r.id:05d}")
                    print(f"  Expected prev_hash: {computed_hash}")
                    print(f"  Actual prev_hash:   {r.previous_hash}")
                verified = False
                first_invalid_id = f"aud_{r.id:05d}"
                break
                
            computed_hash = r.hash
            entries_checked += 1
            
        head_record = session.query(AuditEntryRecord).order_by(AuditEntryRecord.id.desc()).first()
        expected_head_hash = head_record.hash if head_record else GENESIS_HASH
        
        # If to_entry_id was specified, the expected head is that entry's hash
        if to_entry_id and records:
             expected_head_hash = records[-1].hash
             
        duration_ms = int((time.monotonic() - start_time) * 1000)
        
        return VerificationResult(
            verified=verified,
            entries_checked=entries_checked,
            from_entry_id=f"aud_{records[0].id:05d}" if records else None,
            to_entry_id=f"aud_{records[-1].id:05d}" if records else None,
            computed_head_hash=computed_hash,
            expected_head_hash=expected_head_hash,
            first_invalid_entry_id=first_invalid_id,
            verification_duration_ms=duration_ms,
            verified_at=datetime.now(timezone.utc),
        )


def create_snapshot(
    instance_id: str,
    private_key: str, # For JWS signing
) -> AuditSnapshot:
    """Create a signed snapshot of the current ledger head."""
    ensure_schema()
    
    with db_session() as session:
        last_entry = session.query(AuditEntryRecord).order_by(AuditEntryRecord.id.desc()).first()
        if not last_entry:
            raise ValueError("Cannot snapshot empty ledger")
            
        count = session.query(AuditEntryRecord).count()
        now = datetime.now(timezone.utc)
        snapshot_id = f"snap_{now.strftime('%Y%m%d_%H%M%S')}"
        head_entry_id = f"aud_{last_entry.id:05d}"
        
        # Mock JWS signing for now - in a real implementation we would use a library
        # that uses the instance's private key.
        payload = {
            "snapshot_id": snapshot_id,
            "timestamp": now.isoformat(),
            "entry_count": count,
            "head_hash": last_entry.hash,
            "head_entry_id": head_entry_id,
            "signer_instance_id": instance_id,
        }
        # In a real system, we'd sign this payload.
        signature = f"jws:mock_signature_of_{hashlib.sha256(json.dumps(payload).encode()).hexdigest()}"
        
        record = AuditSnapshotRecord(
            snapshot_id=snapshot_id,
            timestamp=now,
            entry_count=count,
            head_hash=last_entry.hash,
            head_entry_id=head_entry_id,
            signature=signature,
            signer_instance_id=instance_id,
        )
        
        session.add(record)
        return record.to_model()


def list_snapshots(
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[AuditSnapshot], int]:
    """List audit snapshots."""
    ensure_schema()
    page = max(1, page)
    page_size = max(1, min(page_size, 50))
    offset = (page - 1) * page_size
    
    with db_session() as session:
        total = session.query(AuditSnapshotRecord).count()
        records = session.query(AuditSnapshotRecord).order_by(AuditSnapshotRecord.timestamp.desc()).offset(offset).limit(page_size).all()
        return [r.to_model() for r in records], total


def stream_export(
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
) -> Generator[str, None, None]:
    """Generator for NDJSON export of the ledger."""
    ensure_schema()
    
    with db_session() as session:
        query = session.query(AuditEntryRecord).order_by(AuditEntryRecord.id.asc())
        if from_date:
            query = query.filter(AuditEntryRecord.timestamp >= from_date)
        if to_date:
            query = query.filter(AuditEntryRecord.timestamp <= to_date)
            
        # We yield line by line to support large exports
        # Using yield_per for memory efficiency
        for r in query.yield_per(100):
            yield json.dumps(r.to_model().model_dump(mode="json")) + "\n"
