"""Federation service: receive, validate, and integrate remote instance data.

Remote data arrives as a FederatedPayload containing lineage links and usage
events. Each item becomes a governance ChangeRequest that must be approved
before it affects local rankings. No remote instance can unilaterally change
local prioritization.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from contextlib import contextmanager
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.models.federation import (
    FederatedInstance,
    FederatedPayload,
    FederationSyncResult,
)
from app.models.governance import (
    ActorType,
    ChangeRequestCreate,
    ChangeRequestType,
)
from app.services import governance_service
from app.services import unified_db as _udb
from app.services.unified_db import Base


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------

class FederatedInstanceRecord(Base):
    __tablename__ = "federation_instances"

    instance_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    endpoint_url: Mapped[str] = mapped_column(String, nullable=False)
    public_key: Mapped[str | None] = mapped_column(String, nullable=True)
    registered_at: Mapped[str] = mapped_column(String, nullable=False)
    last_sync_at: Mapped[str | None] = mapped_column(String, nullable=True)
    trust_level: Mapped[str] = mapped_column(String, nullable=False, default="pending")


class FederationSyncHistoryRecord(Base):
    __tablename__ = "federation_sync_history"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_instance_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(String, nullable=False)
    links_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    governance_requests_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    received_at: Mapped[str] = mapped_column(String, nullable=False)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _ensure_schema() -> None:
    _udb.ensure_schema()


@contextmanager
def _session() -> Session:
    with _udb.session() as s:
        yield s


TRUST_LEVELS = {"unknown": 0, "pending": 1, "verified": 2, "trusted": 3}


def verify_payload_signature(payload_json: str, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature of a payload."""
    expected = hmac.new(secret.encode(), payload_json.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def check_trust_level(instance_id: str, required_level: str = "verified") -> bool:
    """Return True if stored trust_level >= required_level."""
    _ensure_schema()
    with _session() as session:
        inst = session.query(FederatedInstanceRecord).filter_by(instance_id=instance_id).first()
        if not inst:
            return False
        current_rank = TRUST_LEVELS.get(inst.trust_level, 0)
        required_rank = TRUST_LEVELS.get(required_level, 0)
        return current_rank >= required_rank


def _record_to_instance(rec: FederatedInstanceRecord) -> FederatedInstance:
    return FederatedInstance(
        instance_id=rec.instance_id,
        name=rec.name,
        endpoint_url=rec.endpoint_url,
        public_key=rec.public_key,
        registered_at=rec.registered_at,
        last_sync_at=rec.last_sync_at,
        trust_level=rec.trust_level,
    )


# ---------------------------------------------------------------------------
# Instance CRUD
# ---------------------------------------------------------------------------

def register_instance(instance: FederatedInstance) -> FederatedInstance:
    """Register a remote instance. Overwrites if instance_id already exists."""
    _ensure_schema()
    with _session() as s:
        existing = s.query(FederatedInstanceRecord).filter_by(instance_id=instance.instance_id).first()
        if existing:
            existing.name = instance.name
            existing.endpoint_url = instance.endpoint_url
            existing.public_key = instance.public_key
            existing.registered_at = instance.registered_at
            existing.last_sync_at = instance.last_sync_at
            existing.trust_level = instance.trust_level
        else:
            rec = FederatedInstanceRecord(
                instance_id=instance.instance_id,
                name=instance.name,
                endpoint_url=instance.endpoint_url,
                public_key=instance.public_key,
                registered_at=instance.registered_at,
                last_sync_at=instance.last_sync_at,
                trust_level="pending",
            )
            s.add(rec)
    return instance


def list_instances() -> list[FederatedInstance]:
    """List all registered remote instances."""
    _ensure_schema()
    with _session() as s:
        recs = s.query(FederatedInstanceRecord).all()
        return [_record_to_instance(r) for r in recs]


def get_instance(instance_id: str) -> FederatedInstance | None:
    """Get a single registered instance by ID."""
    _ensure_schema()
    with _session() as s:
        rec = s.query(FederatedInstanceRecord).filter_by(instance_id=instance_id).first()
        if rec is None:
            return None
        return _record_to_instance(rec)


# ---------------------------------------------------------------------------
# Payload processing
# ---------------------------------------------------------------------------

def receive_payload(payload: FederatedPayload) -> FederationSyncResult:
    """Main entry point: receive data from a remote instance.

    1. Validate source_instance_id is registered
    2. For each lineage_link, create a governance ChangeRequest
    3. For each usage_event, create a governance ChangeRequest
    4. Store the payload for audit
    5. Return sync result with counts
    """
    result = FederationSyncResult(source_instance_id=payload.source_instance_id)

    # 1. Validate registration
    instance = get_instance(payload.source_instance_id)
    if instance is None:
        result.errors.append(
            f"Instance '{payload.source_instance_id}' is not registered"
        )
        result.rejected = len(payload.lineage_links) + len(payload.usage_events)
        return result

    if not check_trust_level(payload.source_instance_id, required_level="pending"):
        raise ValueError(f"Instance trust level too low")

    result.links_received = len(payload.lineage_links)
    result.events_received = len(payload.usage_events)
    governance_created = 0

    # 2. Create governance requests for lineage links
    for link_data in payload.lineage_links:
        try:
            cr = governance_service.create_change_request(
                ChangeRequestCreate(
                    request_type=ChangeRequestType.FEDERATION_IMPORT,
                    title=f"Federation import: lineage link from {payload.source_instance_id}",
                    payload={
                        "federation_type": "lineage_link",
                        "source_instance_id": payload.source_instance_id,
                        "data": link_data,
                    },
                    proposer_id=f"federation:{payload.source_instance_id}",
                    proposer_type=ActorType.MACHINE,
                    auto_apply_on_approval=True,
                )
            )
            governance_created += 1
            result.accepted += 1
        except Exception as exc:
            result.errors.append(f"lineage_link error: {exc}")

    # 3. Create governance requests for usage events
    for event_data in payload.usage_events:
        try:
            cr = governance_service.create_change_request(
                ChangeRequestCreate(
                    request_type=ChangeRequestType.FEDERATION_IMPORT,
                    title=f"Federation import: usage event from {payload.source_instance_id}",
                    payload={
                        "federation_type": "usage_event",
                        "source_instance_id": payload.source_instance_id,
                        "data": event_data,
                    },
                    proposer_id=f"federation:{payload.source_instance_id}",
                    proposer_type=ActorType.MACHINE,
                    auto_apply_on_approval=True,
                )
            )
            governance_created += 1
            result.accepted += 1
        except Exception as exc:
            result.errors.append(f"usage_event error: {exc}")

    result.governance_requests_created = governance_created

    # 4. Update last_sync_at on the instance
    instance.last_sync_at = datetime.now().isoformat()
    register_instance(instance)

    # 5. Store payload for audit
    now_iso = datetime.now().isoformat()
    with _session() as s:
        rec = FederationSyncHistoryRecord(
            id=f"sync_{uuid4().hex[:12]}",
            source_instance_id=payload.source_instance_id,
            timestamp=payload.timestamp,
            links_received=result.links_received,
            events_received=result.events_received,
            governance_requests_created=result.governance_requests_created,
            accepted=result.accepted,
            rejected=result.rejected,
            errors_json=json.dumps(result.errors),
            received_at=now_iso,
        )
        s.add(rec)

    return result


# ---------------------------------------------------------------------------
# Sync history
# ---------------------------------------------------------------------------

def list_sync_history(limit: int = 200) -> list[dict]:
    """Return past sync operations."""
    _ensure_schema()
    effective_limit = max(1, min(limit, 1000))
    with _session() as s:
        recs = (
            s.query(FederationSyncHistoryRecord)
            .order_by(FederationSyncHistoryRecord.received_at.desc())
            .limit(effective_limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "source_instance_id": r.source_instance_id,
                "timestamp": r.timestamp,
                "links_received": r.links_received,
                "events_received": r.events_received,
                "governance_requests_created": r.governance_requests_created,
                "accepted": r.accepted,
                "rejected": r.rejected,
                "errors": json.loads(r.errors_json),
                "received_at": r.received_at,
            }
            for r in recs
        ]


# ---------------------------------------------------------------------------
# Local valuation re-computation
# ---------------------------------------------------------------------------

def compute_local_valuation(remote_links: list, remote_events: list) -> dict:
    """Re-compute valuations locally from remote data.

    Verifiable math, no trust required. Takes raw link and event data
    and computes value metrics independently.
    """
    total_value = 0.0
    total_cost = 0.0

    for link in remote_links:
        if isinstance(link, dict):
            total_cost += float(link.get("estimated_cost", 0.0))

    for event in remote_events:
        if isinstance(event, dict):
            total_value += float(event.get("value", 0.0))

    roi = round(total_value / total_cost, 4) if total_cost > 0 else 0.0

    return {
        "measured_value_total": round(total_value, 4),
        "estimated_cost": round(total_cost, 4),
        "roi_ratio": roi,
        "link_count": len(remote_links),
        "event_count": len(remote_events),
    }
