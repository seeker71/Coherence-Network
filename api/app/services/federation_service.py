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
import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, Index, func
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.types import JSON

from app.models.federation import (
    FederatedInstance,
    FederatedPayload,
    FleetCapabilitySummary,
    FederationNodeRegisterRequest,
    FederationNodeRegisterResponse,
    FederationStrategyEffectivenessReportRequest,
    FederationNodeHeartbeatResponse,
    FederationSyncResult,
    VALID_STRATEGY_TYPES,
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


class FederationNodeRecord(Base):
    __tablename__ = "federation_nodes"

    node_id: Mapped[str] = mapped_column(String, primary_key=True)
    hostname: Mapped[str] = mapped_column(String, nullable=False)
    os_type: Mapped[str] = mapped_column(String, nullable=False)
    providers_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    capabilities_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    registered_at: Mapped[str] = mapped_column(String, nullable=False)
    last_seen_at: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="online", index=True)


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


class NodeMeasurementSummaryRecord(Base):
    """Aggregated measurement summaries pushed by federation nodes (Spec 131)."""
    __tablename__ = "node_measurement_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False)
    decision_point: Mapped[str] = mapped_column(String, nullable=False)
    slot_id: Mapped[str] = mapped_column(String, nullable=False)
    period_start: Mapped[str] = mapped_column(String, nullable=False)
    period_end: Mapped[str] = mapped_column(String, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    successes: Mapped[int] = mapped_column(Integer, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, nullable=False)
    mean_duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_value_score: Mapped[float] = mapped_column(Float, nullable=False)
    error_classes_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    pushed_at: Mapped[str] = mapped_column(String, nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    __table_args__ = (
        Index("idx_nms_node_dp", "node_id", "decision_point"),
        Index("idx_nms_pushed_at", "pushed_at"),
    )


class NodeStrategyBroadcastRecord(Base):
    """Hub strategy broadcasts for federation advisory guidance (Spec 134)."""
    __tablename__ = "node_strategy_broadcasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_type: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    source_node_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("idx_nsb_strategy_type_created_at", "strategy_type", "created_at"),
        Index("idx_nsb_expires_at", "expires_at"),
    )


class NodeStrategyEffectivenessRecord(Base):
    """Outcome tracking for acted-on strategy broadcasts."""
    __tablename__ = "node_strategy_effectiveness"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_broadcast_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    strategy_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    strategy_target: Mapped[str] = mapped_column(String, nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    was_applied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    baseline_value_score: Mapped[float] = mapped_column(Float, nullable=False)
    outcome_value_score: Mapped[float] = mapped_column(Float, nullable=False)
    improvement_score: Mapped[float] = mapped_column(Float, nullable=False)
    observed_at: Mapped[str] = mapped_column(String, nullable=False)
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("idx_nse_strategy_type_target", "strategy_type", "strategy_target"),
        Index("idx_nse_created_at", "created_at"),
    )


class FederatedAggregationRecord(Base):
    """Submissions for federated aggregation merging (Spec 143)."""
    __tablename__ = "federation_aggregations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(String, nullable=False)
    strategy_type: Mapped[str] = mapped_column(String, nullable=False)
    window_start: Mapped[str] = mapped_column(String, nullable=False)
    window_end: Mapped[str] = mapped_column(String, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String, nullable=False)
    sent_at: Mapped[str] = mapped_column(String, nullable=False)
    received_at: Mapped[str] = mapped_column(String, nullable=False)

    __table_args__ = (
        Index("idx_fed_agg_node_hash_sent", "node_id", "payload_hash", "sent_at", unique=True),
        Index("idx_fed_agg_strategy_window", "strategy_type", "window_start", "window_end"),
    )


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
            logger.warning("Federation lineage_link import failed", exc_info=True)
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
            logger.warning("Federation usage_event import failed", exc_info=True)
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

# ---------------------------------------------------------------------------
# Node registration / heartbeat (Spec 132)
# ---------------------------------------------------------------------------

def register_or_update_node(data: FederationNodeRegisterRequest) -> tuple[FederationNodeRegisterResponse, bool]:
    """Upsert a federation node record. Returns (response, created)."""
    _ensure_schema()
    now_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    with _session() as s:
        existing = s.query(FederationNodeRecord).filter_by(node_id=data.node_id).first()
        if existing:
            existing.hostname = data.hostname
            existing.os_type = data.os_type
            existing.providers_json = json.dumps(data.providers)
            existing.capabilities_json = json.dumps(data.capabilities)
            existing.last_seen_at = now_iso
            existing.status = "online"
            resp = FederationNodeRegisterResponse(
                node_id=existing.node_id,
                status=existing.status,
                registered_at=datetime.fromisoformat(existing.registered_at.replace("Z", "+00:00")),
                last_seen_at=datetime.fromisoformat(now_iso.replace("Z", "+00:00")),
            )
            logger.info("Registered node %s (updated)", data.node_id)
            return resp, False
        else:
            rec = FederationNodeRecord(
                node_id=data.node_id,
                hostname=data.hostname,
                os_type=data.os_type,
                providers_json=json.dumps(data.providers),
                capabilities_json=json.dumps(data.capabilities),
                registered_at=now_iso,
                last_seen_at=now_iso,
                status="online",
            )
            s.add(rec)
            resp = FederationNodeRegisterResponse(
                node_id=rec.node_id,
                status=rec.status,
                registered_at=datetime.fromisoformat(now_iso.replace("Z", "+00:00")),
                last_seen_at=datetime.fromisoformat(now_iso.replace("Z", "+00:00")),
            )
            logger.info("Registered node %s (created)", data.node_id)
            return resp, True


def heartbeat_node(
    node_id: str,
    status: str = "online",
    capabilities: dict | None = None,
    refresh_capabilities: bool = False,
) -> FederationNodeHeartbeatResponse | None:
    """Update last_seen_at and status for a node. Returns None if not found."""
    _ensure_schema()
    now_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    with _session() as s:
        rec = s.query(FederationNodeRecord).filter_by(node_id=node_id).first()
        if rec is None:
            return None
        rec.last_seen_at = now_iso
        rec.status = status
        logger.debug("Heartbeat from %s", node_id)
        capabilities_refreshed = False
        if refresh_capabilities and capabilities is not None:
            rec.capabilities_json = json.dumps(capabilities)
            executors = capabilities.get("executors", [])
            if isinstance(executors, list):
                rec.providers_json = json.dumps(executors)
            capabilities_refreshed = True
        return FederationNodeHeartbeatResponse(
            node_id=rec.node_id,
            status=rec.status,
            last_seen_at=datetime.fromisoformat(now_iso.replace("Z", "+00:00")),
            capabilities_refreshed=capabilities_refreshed,
        )


def list_nodes() -> list[dict]:
    """Return all registered federation nodes."""
    _ensure_schema()
    with _session() as s:
        recs = s.query(FederationNodeRecord).all()
        return [
            {
                "node_id": r.node_id,
                "hostname": r.hostname,
                "os_type": r.os_type,
                "providers": json.loads(r.providers_json),
                "capabilities": json.loads(r.capabilities_json),
                "registered_at": r.registered_at,
                "last_seen_at": r.last_seen_at,
                "status": r.status,
            }
            for r in recs
        ]


def get_fleet_capability_summary() -> FleetCapabilitySummary:
    """Aggregate executor/tool/hardware availability across all nodes."""
    _ensure_schema()
    with _session() as s:
        recs = s.query(FederationNodeRecord).all()

    total_nodes = len(recs)
    executor_map: dict[str, dict[str, object]] = {}
    tool_map: dict[str, dict[str, int]] = {}
    total_cpus = 0
    total_memory_gb = 0.0
    gpu_capable_nodes = 0

    for rec in recs:
        node_caps: dict = {}
        try:
            node_caps = json.loads(rec.capabilities_json or "{}")
        except json.JSONDecodeError:
            logger.debug("Malformed capabilities_json for node %s", rec.node_id, exc_info=True)
            node_caps = {}

        executors = node_caps.get("executors", [])
        if isinstance(executors, list):
            for executor in executors:
                key = str(executor)
                bucket = executor_map.setdefault(key, {"node_count": 0, "node_ids": []})
                bucket["node_count"] = int(bucket.get("node_count", 0)) + 1
                node_ids = bucket.get("node_ids", [])
                if isinstance(node_ids, list):
                    node_ids.append(rec.node_id)
                    bucket["node_ids"] = node_ids

        tools = node_caps.get("tools", [])
        if isinstance(tools, list):
            for tool in tools:
                key = str(tool)
                bucket = tool_map.setdefault(key, {"node_count": 0})
                bucket["node_count"] = int(bucket.get("node_count", 0)) + 1

        hardware = node_caps.get("hardware", {})
        if isinstance(hardware, dict):
            cpu_count = hardware.get("cpu_count")
            if isinstance(cpu_count, int):
                total_cpus += cpu_count

            memory_total_gb = hardware.get("memory_total_gb")
            if isinstance(memory_total_gb, (int, float)):
                total_memory_gb += float(memory_total_gb)

            if hardware.get("gpu_available") is True:
                gpu_capable_nodes += 1

    return FleetCapabilitySummary(
        total_nodes=total_nodes,
        executors=executor_map,
        tools=tool_map,
        hardware_summary={
            "total_cpus": total_cpus,
            "total_memory_gb": round(total_memory_gb, 2),
            "gpu_capable_nodes": gpu_capable_nodes,
        },
    )


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


# ---------------------------------------------------------------------------
# Measurement summary storage (Spec 131)
# ---------------------------------------------------------------------------

def _compute_dedup_key(node_id: str, decision_point: str, slot_id: str,
                       period_start: str, period_end: str) -> str:
    """Deterministic SHA-256 hash of the measurement's natural key."""
    raw = f"{node_id}|{decision_point}|{slot_id}|{period_start}|{period_end}"
    return hashlib.sha256(raw.encode()).hexdigest()


def store_measurement_summaries(node_id: str, summaries: list[dict]) -> dict:
    """Bulk-insert measurement summaries with deduplication and conflict resolution.

    Returns a dict with keys: stored, duplicates_skipped, duplicates_replaced.

    Conflict resolution: when a summary with the same dedup_key already exists,
    the incoming summary replaces it only if it has a higher sample_count
    (more data = more accurate aggregate). Otherwise it is skipped.
    """
    _ensure_schema()
    now_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    stored = 0
    duplicates_skipped = 0
    duplicates_replaced = 0

    with _session() as s:
        for sm in summaries:
            dedup_key = _compute_dedup_key(
                node_id,
                sm["decision_point"],
                sm["slot_id"],
                sm["period_start"],
                sm["period_end"],
            )
            existing = (
                s.query(NodeMeasurementSummaryRecord)
                .filter_by(dedup_key=dedup_key)
                .first()
            )
            if existing is not None:
                if sm["sample_count"] > existing.sample_count:
                    # Replace: incoming has more samples
                    existing.sample_count = sm["sample_count"]
                    existing.successes = sm["successes"]
                    existing.failures = sm["failures"]
                    existing.mean_duration_s = sm.get("mean_duration_s")
                    existing.mean_value_score = sm["mean_value_score"]
                    existing.error_classes_json = json.dumps(sm.get("error_classes_json", {}))
                    existing.pushed_at = now_iso
                    duplicates_replaced += 1
                else:
                    duplicates_skipped += 1
                continue

            rec = NodeMeasurementSummaryRecord(
                node_id=node_id,
                decision_point=sm["decision_point"],
                slot_id=sm["slot_id"],
                period_start=sm["period_start"],
                period_end=sm["period_end"],
                sample_count=sm["sample_count"],
                successes=sm["successes"],
                failures=sm["failures"],
                mean_duration_s=sm.get("mean_duration_s"),
                mean_value_score=sm["mean_value_score"],
                error_classes_json=json.dumps(sm.get("error_classes_json", {})),
                pushed_at=now_iso,
                dedup_key=dedup_key,
            )
            s.add(rec)
            stored += 1

    total_stored = stored + duplicates_replaced
    logger.info("Stored %d measurements from %s (skipped=%d, replaced=%d)",
                total_stored, node_id, duplicates_skipped, duplicates_replaced)
    return {
        "stored": stored,
        "duplicates_skipped": duplicates_skipped,
        "duplicates_replaced": duplicates_replaced,
    }


def get_aggregated_node_stats(window_days: int | None = None) -> dict:
    """Aggregate cross-node measurement summaries into fleet-wide provider stats.

    Returns a dict with keys: nodes, providers, task_types, alerts, window_days,
    total_measurements.
    """
    if window_days is None:
        window_days = int(os.environ.get("FEDERATION_STATS_WINDOW_DAYS", "7"))

    _ensure_schema()
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=window_days)).isoformat().replace("+00:00", "Z")

    with _session() as s:
        # Fetch nodes
        node_recs = s.query(FederationNodeRecord).all()
        nodes: dict[str, dict] = {}
        for nr in node_recs:
            nodes[nr.node_id] = {
                "hostname": nr.hostname,
                "os_type": nr.os_type,
                "status": nr.status,
                "last_seen_at": nr.last_seen_at,
            }

        # Fetch measurement summaries within window
        summary_rows = (
            s.query(NodeMeasurementSummaryRecord, FederationNodeRecord)
            .outerjoin(
                FederationNodeRecord,
                NodeMeasurementSummaryRecord.node_id == FederationNodeRecord.node_id,
            )
            .filter(NodeMeasurementSummaryRecord.pushed_at >= cutoff)
            .all()
        )

    if not summary_rows:
        return {
            "nodes": nodes,
            "providers": {},
            "task_types": {},
            "alerts": [],
            "window_days": window_days,
            "total_measurements": 0,
        }

    # Aggregate per provider (slot_id)
    # provider -> {node_id -> list[summary]}
    provider_node_data: dict[str, dict[str, list]] = {}
    # task_type -> provider -> list[summary]
    task_type_data: dict[str, dict[str, list]] = {}

    total_measurements = 0

    for sm, node_rec in summary_rows:
        provider = sm.slot_id
        node_id = sm.node_id
        total_measurements += sm.sample_count

        # Ensure nodes that appear in measurements are represented.
        if node_id not in nodes:
            if node_rec is not None:
                nodes[node_id] = {
                    "hostname": node_rec.hostname,
                    "os_type": node_rec.os_type,
                    "status": node_rec.status,
                    "last_seen_at": node_rec.last_seen_at,
                }
            else:
                nodes[node_id] = {
                    "hostname": "",
                    "os_type": "",
                    "status": "unknown",
                    "last_seen_at": "",
                }

        provider_node_data.setdefault(provider, {}).setdefault(node_id, []).append(sm)

        # Extract task_type from decision_point: "provider_spec" -> "spec"
        dp = sm.decision_point
        if dp.startswith("provider_"):
            task_type = dp[len("provider_"):]
        else:
            task_type = dp
        task_type_data.setdefault(task_type, {}).setdefault(provider, []).append(sm)

    # Build providers response
    providers: dict[str, dict] = {}
    alerts: list[dict] = []

    for provider, node_map in sorted(provider_node_data.items()):
        total_samples = 0
        total_successes = 0
        total_failures = 0
        weighted_duration_sum = 0.0
        duration_sample_count = 0
        per_node: dict[str, dict] = {}

        for nid, sms in sorted(node_map.items()):
            n_samples = sum(sm.sample_count for sm in sms)
            n_successes = sum(sm.successes for sm in sms)
            n_failures = sum(sm.failures for sm in sms)
            n_dur_sum = 0.0
            n_dur_count = 0
            for sm in sms:
                if sm.mean_duration_s is not None:
                    n_dur_sum += sm.mean_duration_s * sm.sample_count
                    n_dur_count += sm.sample_count

            total_samples += n_samples
            total_successes += n_successes
            total_failures += n_failures
            weighted_duration_sum += n_dur_sum
            duration_sample_count += n_dur_count

            per_node[nid] = {
                "success_rate": round(n_successes / n_samples, 3) if n_samples > 0 else 0.0,
                "samples": n_samples,
                "avg_duration_s": round(n_dur_sum / n_dur_count, 1) if n_dur_count > 0 else 0.0,
            }

        overall_success_rate = round(total_successes / total_samples, 3) if total_samples > 0 else 0.0
        avg_duration_s = round(weighted_duration_sum / duration_sample_count, 1) if duration_sample_count > 0 else 0.0

        providers[provider] = {
            "node_count": len(node_map),
            "total_samples": total_samples,
            "total_successes": total_successes,
            "total_failures": total_failures,
            "overall_success_rate": overall_success_rate,
            "avg_duration_s": avg_duration_s,
            "per_node": per_node,
        }

        if overall_success_rate < 0.5:
            alerts.append({
                "provider": provider,
                "metric": "overall_success_rate",
                "value": overall_success_rate,
                "threshold": 0.5,
                "message": f"{provider} network-wide success rate {int(overall_success_rate * 100)}% < 50% threshold",
            })

    # Build task_types response
    task_types: dict[str, dict] = {}
    for tt, provider_map in sorted(task_type_data.items()):
        tt_providers: dict[str, dict] = {}
        for provider, sms in sorted(provider_map.items()):
            t_samples = sum(sm.sample_count for sm in sms)
            t_successes = sum(sm.successes for sm in sms)
            t_dur_sum = 0.0
            t_dur_count = 0
            for sm in sms:
                if sm.mean_duration_s is not None:
                    t_dur_sum += sm.mean_duration_s * sm.sample_count
                    t_dur_count += sm.sample_count
            tt_providers[provider] = {
                "total_samples": t_samples,
                "success_rate": round(t_successes / t_samples, 3) if t_samples > 0 else 0.0,
                "avg_duration_s": round(t_dur_sum / t_dur_count, 1) if t_dur_count > 0 else 0.0,
            }
        task_types[tt] = {"providers": tt_providers}

    return {
        "nodes": nodes,
        "providers": providers,
        "task_types": task_types,
        "alerts": alerts,
        "window_days": window_days,
        "total_measurements": total_measurements,
    }


def list_measurement_summaries(
    node_id: str,
    decision_point: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Query measurement summaries for a node. Returns (rows, total)."""
    _ensure_schema()
    effective_limit = max(1, min(limit, 500))
    with _session() as s:
        q = s.query(NodeMeasurementSummaryRecord).filter_by(node_id=node_id)
        if decision_point:
            q = q.filter_by(decision_point=decision_point)
        total = q.count()
        recs = (
            q.order_by(NodeMeasurementSummaryRecord.pushed_at.desc())
            .offset(offset)
            .limit(effective_limit)
            .all()
        )
        rows = []
        for r in recs:
            try:
                error_classes = json.loads(r.error_classes_json) if r.error_classes_json else {}
            except (json.JSONDecodeError, TypeError):
                error_classes = {}
            rows.append({
                "id": r.id,
                "node_id": r.node_id,
                "decision_point": r.decision_point,
                "slot_id": r.slot_id,
                "period_start": r.period_start,
                "period_end": r.period_end,
                "sample_count": r.sample_count,
                "successes": r.successes,
                "failures": r.failures,
                "mean_duration_s": r.mean_duration_s,
                "mean_value_score": r.mean_value_score,
                "error_classes_json": error_classes,
                "pushed_at": r.pushed_at,
            })
        return rows, total


# ---------------------------------------------------------------------------
# Strategy broadcast computation and retrieval (Spec 134)
# ---------------------------------------------------------------------------

_DEFAULT_STRATEGY_TTL = timedelta(hours=24)


def _extract_strategy_target(strategy_type: str, payload_json: str) -> str:
    """Normalize strategy payload into a deterministic target key."""
    payload: dict = {}
    try:
        payload = json.loads(payload_json) if payload_json else {}
    except json.JSONDecodeError:
        payload = {}

    if strategy_type == "provider_recommendation":
        return str(payload.get("recommended_provider", "unknown"))
    if strategy_type == "provider_warning":
        return str(payload.get("warned_provider", "unknown"))
    if strategy_type == "prompt_variant_winner":
        task_type = str(payload.get("task_type", "unknown"))
        winning_variant = str(payload.get("winning_variant", "unknown"))
        return f"{task_type}:{winning_variant}"
    return "unknown"


def _get_effectiveness_summary() -> dict[tuple[str, str], dict]:
    """Aggregate acted-on strategy outcomes for feedback-aware computation."""
    _ensure_schema()
    with _session() as s:
        recs = (
            s.query(NodeStrategyEffectivenessRecord)
            .filter(NodeStrategyEffectivenessRecord.was_applied.is_(True))
            .all()
        )

    summary: dict[tuple[str, str], dict] = {}
    for rec in recs:
        key = (rec.strategy_type, rec.strategy_target)
        bucket = summary.setdefault(
            key,
            {"sample_count": 0, "improvement_sum": 0.0, "improved_count": 0},
        )
        bucket["sample_count"] += 1
        bucket["improvement_sum"] += float(rec.improvement_score)
        if rec.improvement_score > 0:
            bucket["improved_count"] += 1

    for bucket in summary.values():
        sample_count = max(1, int(bucket["sample_count"]))
        bucket["avg_improvement"] = round(bucket["improvement_sum"] / sample_count, 4)
        bucket["positive_rate"] = round(bucket["improved_count"] / sample_count, 4)
    return summary


def record_strategy_effectiveness(
    strategy_id: int,
    report: FederationStrategyEffectivenessReportRequest,
) -> dict:
    """Record post-action effectiveness for a strategy broadcast."""
    _ensure_schema()
    now_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    observed_at = report.observed_at or datetime.now(tz=timezone.utc)
    observed_iso = observed_at.isoformat().replace("+00:00", "Z")

    with _session() as s:
        strategy = s.query(NodeStrategyBroadcastRecord).filter_by(id=strategy_id).first()
        if strategy is None:
            raise ValueError("strategy not found")

        strategy_target = _extract_strategy_target(strategy.strategy_type, strategy.payload_json)
        improvement_score = round(report.outcome_value_score - report.baseline_value_score, 4)

        rec = NodeStrategyEffectivenessRecord(
            strategy_broadcast_id=strategy_id,
            strategy_type=strategy.strategy_type,
            strategy_target=strategy_target,
            node_id=report.node_id,
            was_applied=report.was_applied,
            baseline_value_score=report.baseline_value_score,
            outcome_value_score=report.outcome_value_score,
            improvement_score=improvement_score,
            observed_at=observed_iso,
            context_json=json.dumps(report.context_json),
            created_at=now_iso,
        )
        s.add(rec)

        return {
            "strategy_id": strategy_id,
            "strategy_type": strategy.strategy_type,
            "strategy_target": strategy_target,
            "node_id": report.node_id,
            "was_applied": report.was_applied,
            "baseline_value_score": report.baseline_value_score,
            "outcome_value_score": report.outcome_value_score,
            "improvement_score": improvement_score,
            "improved": improvement_score > 0,
            "recorded_at": observed_iso,
        }


def compute_and_store_strategies() -> list[dict]:
    """Compute strategy broadcasts from aggregated node stats and store them.

    Generates:
    - provider_recommendation: provider with >90% success across 3+ nodes
    - provider_warning: provider with <50% success across multiple nodes
    - prompt_variant_winner: if prompt measurement data exists

    Returns list of newly created strategy dicts.
    """
    _ensure_schema()

    try:
        stats = get_aggregated_node_stats()
    except Exception:
        logger.warning("get_aggregated_node_stats unavailable; returning empty strategies")
        return []

    providers = stats.get("providers", {})
    if not providers:
        return []

    now_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    expires_iso = (datetime.now(tz=timezone.utc) + _DEFAULT_STRATEGY_TTL).isoformat().replace("+00:00", "Z")

    feedback_summary = _get_effectiveness_summary()
    new_strategies: list[dict] = []

    for provider, pdata in providers.items():
        node_count = pdata.get("node_count", 0)
        success_rate = pdata.get("overall_success_rate", 0.0)
        total_samples = pdata.get("total_samples", 0)
        feedback_key = ("provider_recommendation", provider)
        feedback = feedback_summary.get(feedback_key)
        if feedback and feedback["sample_count"] >= 3 and feedback["avg_improvement"] < -0.05:
            continue

        # provider_recommendation: >90% success across 3+ nodes
        if success_rate > 0.9 and node_count >= 3:
            confidence = float(success_rate)
            if feedback:
                confidence = max(0.0, min(1.0, confidence * (1.0 + feedback["avg_improvement"])))
            payload = {
                "recommended_provider": provider,
                "confidence": round(confidence, 3),
                "node_count": node_count,
                "total_samples": total_samples,
            }
            if feedback:
                payload["effectiveness_feedback"] = {
                    "sample_count": feedback["sample_count"],
                    "avg_improvement": feedback["avg_improvement"],
                    "positive_rate": feedback["positive_rate"],
                }
            new_strategies.append({
                "strategy_type": "provider_recommendation",
                "payload_json": json.dumps(payload),
                "source_node_id": "hub",
                "created_at": now_iso,
                "expires_at": expires_iso,
                "advisory_only": True,
            })

        # provider_warning: <50% success across multiple (2+) nodes
        if success_rate < 0.5 and node_count >= 2:
            warning_feedback = feedback_summary.get(("provider_warning", provider))
            payload = {
                "warned_provider": provider,
                "success_rate": round(success_rate, 3),
                "node_count": node_count,
                "total_samples": total_samples,
            }
            if warning_feedback:
                payload["effectiveness_feedback"] = {
                    "sample_count": warning_feedback["sample_count"],
                    "avg_improvement": warning_feedback["avg_improvement"],
                    "positive_rate": warning_feedback["positive_rate"],
                }
            new_strategies.append({
                "strategy_type": "provider_warning",
                "payload_json": json.dumps(payload),
                "source_node_id": "hub",
                "created_at": now_iso,
                "expires_at": expires_iso,
                "advisory_only": True,
            })

    # prompt_variant_winner: check if prompt measurement data exists
    # Look for task_types that indicate prompt template measurements
    task_types = stats.get("task_types", {})
    for tt, tt_data in task_types.items():
        if "prompt" in tt.lower():
            tt_providers = tt_data.get("providers", {})
            if tt_providers:
                # Pick provider with highest success rate in this prompt task type
                best_provider = None
                best_rate = 0.0
                for prov, prov_data in tt_providers.items():
                    rate = prov_data.get("success_rate", 0.0)
                    if rate > best_rate:
                        best_rate = rate
                        best_provider = prov
                if best_provider and best_rate > 0.0:
                    target = f"{tt}:{best_provider}"
                    winner_feedback = feedback_summary.get(("prompt_variant_winner", target))
                    if winner_feedback and winner_feedback["sample_count"] >= 3 and winner_feedback["avg_improvement"] < -0.05:
                        continue
                    payload = {
                        "task_type": tt,
                        "winning_variant": best_provider,
                        "success_rate": round(best_rate, 3),
                    }
                    if winner_feedback:
                        payload["effectiveness_feedback"] = {
                            "sample_count": winner_feedback["sample_count"],
                            "avg_improvement": winner_feedback["avg_improvement"],
                            "positive_rate": winner_feedback["positive_rate"],
                        }
                    new_strategies.append({
                        "strategy_type": "prompt_variant_winner",
                        "payload_json": json.dumps(payload),
                        "source_node_id": "hub",
                        "created_at": now_iso,
                        "expires_at": expires_iso,
                        "advisory_only": True,
                    })

    # Persist all new strategies
    if new_strategies:
        with _session() as s:
            for st in new_strategies:
                rec = NodeStrategyBroadcastRecord(
                    strategy_type=st["strategy_type"],
                    payload_json=st["payload_json"],
                    source_node_id=st["source_node_id"],
                    created_at=st["created_at"],
                    expires_at=st["expires_at"],
                )
                s.add(rec)
                s.flush()
                st["id"] = rec.id

    logger.info("Computed %d strategies", len(new_strategies))
    return new_strategies


def list_active_strategies(
    strategy_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return non-expired strategy broadcasts, newest first.

    Returns (rows, total).
    """
    _ensure_schema()
    now_iso = datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
    effective_limit = max(1, min(limit, 500))

    with _session() as s:
        q = s.query(NodeStrategyBroadcastRecord).filter(
            NodeStrategyBroadcastRecord.expires_at > now_iso,
        )
        if strategy_type is not None:
            q = q.filter(NodeStrategyBroadcastRecord.strategy_type == strategy_type)

        total = q.count()
        recs = (
            q.order_by(NodeStrategyBroadcastRecord.created_at.desc())
            .offset(offset)
            .limit(effective_limit)
            .all()
        )
        rows = [
            {
                "id": r.id,
                "strategy_type": r.strategy_type,
                "payload_json": r.payload_json,
                "source_node_id": r.source_node_id,
                "created_at": r.created_at,
                "expires_at": r.expires_at,
                "advisory_only": True,
            }
            for r in recs
        ]
        return rows, total


# ---------------------------------------------------------------------------
# Federated Instance Aggregation (Spec 143)
# ---------------------------------------------------------------------------

def ingest_federated_aggregation(node_id: str, data: dict) -> dict:
    """Ingest a partner instance aggregation payload."""
    _ensure_schema()
    
    # 1. Trust verification
    if not check_trust_level(node_id, required_level="verified"):
        raise PermissionError("node trust verification failed")
    
    envelope = data.get("envelope", {})
    payload = data.get("payload", {})
    
    # 2. Duplicate check
    payload_hash = envelope.get("payload_hash")
    sent_at = envelope.get("sent_at")
    
    with _session() as s:
        existing = s.query(FederatedAggregationRecord).filter_by(
            node_id=node_id,
            payload_hash=payload_hash,
            sent_at=sent_at
        ).first()
        if existing:
            return {"status": "duplicate", "dedupe": True, "merge_key": f"{payload['strategy_type']}:{sent_at}"}

        # 3. Store record
        rec = FederatedAggregationRecord(
            node_id=node_id,
            strategy_type=payload["strategy_type"],
            window_start=payload["window_start"],
            window_end=payload["window_end"],
            sample_count=payload["sample_count"],
            metrics_json=json.dumps(payload["metrics"]),
            payload_hash=payload_hash,
            sent_at=sent_at,
            received_at=datetime.now(timezone.utc).isoformat()
        )
        s.add(rec)
        
    return {
        "status": "accepted",
        "merge_key": f"{payload['strategy_type']}:{sent_at}",
        "trust_tier": "verified",
        "dedupe": False
    }


def list_federated_aggregates(strategy_type: str | None = None) -> list[dict]:
    """Retrieve and merge federated aggregation results."""
    _ensure_schema()
    with _session() as s:
        query = s.query(FederatedAggregationRecord)
        if strategy_type:
            query = query.filter_by(strategy_type=strategy_type)
        recs = query.all()
    
    # Group by (strategy_type, window_start, window_end)
    groups = {}
    for r in recs:
        key = (r.strategy_type, r.window_start, r.window_end)
        groups.setdefault(key, []).append(r)
    
    results = []
    for (stype, wstart, wend), items in groups.items():
        if stype == "provider_recommendation":
            merge_strategy = "weighted_mean"
            merged_metrics = _merge_weighted_mean(items)
        elif stype == "prompt_variant_winner":
            merge_strategy = "majority_vote"
            merged_metrics = _merge_majority_vote(items)
        else:
            merge_strategy = "warning_union"
            merged_metrics = _merge_warning_union(items)
            
        results.append({
            "strategy_type": stype,
            "merge_strategy": merge_strategy,
            "value": merged_metrics,
            "metrics": merged_metrics,
            "source_nodes": list(set(r.node_id for r in items)),
            "sample_count": sum(r.sample_count for r in items),
            "window_start": wstart,
            "window_end": wend
        })
    return results


def _merge_weighted_mean(items: list[FederatedAggregationRecord]) -> dict:
    total_samples = sum(r.sample_count for r in items)
    if total_samples == 0: return {}
    
    providers = {}
    for r in items:
        m = json.loads(r.metrics_json)
        p = m.get("provider", "unknown")
        sr = m.get("success_rate", 0.0)
        dur = m.get("avg_duration_s", 0.0)
        
        data = providers.setdefault(p, {"sr_sum": 0.0, "dur_sum": 0.0, "samples": 0})
        data["sr_sum"] += sr * r.sample_count
        data["dur_sum"] += dur * r.sample_count
        data["samples"] += r.sample_count
    
    if not providers: return {}
    best_p = next(iter(providers))
    best_data = providers[best_p]
    
    return {
        "provider": best_p,
        "success_rate": round(best_data["sr_sum"] / best_data["samples"], 3),
        "avg_duration_s": round(best_data["dur_sum"] / best_data["samples"], 1)
    }

def _merge_majority_vote(items: list[FederatedAggregationRecord]) -> dict:
    votes = {}
    for r in items:
        m = json.loads(r.metrics_json)
        variant = m.get("winning_variant", "unknown")
        votes[variant] = votes.get(variant, 0) + 1
    
    if not votes: return {}
    max_v = max(votes.values())
    winners = [v for v, count in votes.items() if count == max_v]
    winners.sort() 
    return {"winning_variant": winners[0], "votes": max_v}

def _merge_warning_union(items: list[FederatedAggregationRecord]) -> dict:
    all_warnings = []
    for r in items:
        try:
            m = json.loads(r.metrics_json)
        except:
            m = {}
        all_warnings.append({"node_id": r.node_id, "warning": m})
    return {"warnings": all_warnings}
