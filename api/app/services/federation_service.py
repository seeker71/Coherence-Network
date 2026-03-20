"""Federation service: receive, validate, and integrate remote instance data.

Remote data arrives as a FederatedPayload containing lineage links and usage
events. Each item becomes a governance ChangeRequest that must be approved
before it affects local rankings. No remote instance can unilaterally change
local prioritization.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

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


# ---------------------------------------------------------------------------
# JSON file store (same pattern as value_lineage_service)
# ---------------------------------------------------------------------------

def _default_path() -> Path:
    logs_dir = Path(__file__).resolve().parents[2] / "logs"
    return logs_dir / "federation.json"


def _path() -> Path:
    configured = os.getenv("FEDERATION_STORE_PATH")
    return Path(configured) if configured else _default_path()


def _ensure_store() -> None:
    path = _path()
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"instances": [], "sync_history": []}, indent=2),
        encoding="utf-8",
    )


def _read_store() -> dict:
    _ensure_store()
    path = _path()
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"instances": [], "sync_history": []}
    if not isinstance(data, dict):
        return {"instances": [], "sync_history": []}
    instances = data.get("instances") if isinstance(data.get("instances"), list) else []
    sync_history = data.get("sync_history") if isinstance(data.get("sync_history"), list) else []
    return {"instances": instances, "sync_history": sync_history}


def _write_store(data: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ---------------------------------------------------------------------------
# Instance CRUD
# ---------------------------------------------------------------------------

def register_instance(instance: FederatedInstance) -> FederatedInstance:
    """Register a remote instance. Overwrites if instance_id already exists."""
    data = _read_store()
    # Remove existing entry with same id
    data["instances"] = [
        i for i in data["instances"] if i.get("instance_id") != instance.instance_id
    ]
    data["instances"].append(instance.model_dump(mode="json"))
    _write_store(data)
    return instance


def list_instances() -> list[FederatedInstance]:
    """List all registered remote instances."""
    data = _read_store()
    out: list[FederatedInstance] = []
    for raw in data["instances"]:
        try:
            out.append(FederatedInstance(**raw))
        except Exception:
            continue
    return out


def get_instance(instance_id: str) -> FederatedInstance | None:
    """Get a single registered instance by ID."""
    data = _read_store()
    for raw in data["instances"]:
        try:
            inst = FederatedInstance(**raw)
        except Exception:
            continue
        if inst.instance_id == instance_id:
            return inst
    return None


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
    data = _read_store()
    data["sync_history"].append({
        "id": f"sync_{uuid4().hex[:12]}",
        "source_instance_id": payload.source_instance_id,
        "timestamp": payload.timestamp,
        "links_received": result.links_received,
        "events_received": result.events_received,
        "governance_requests_created": result.governance_requests_created,
        "accepted": result.accepted,
        "rejected": result.rejected,
        "errors": result.errors,
        "received_at": datetime.now().isoformat(),
    })
    _write_store(data)

    return result


# ---------------------------------------------------------------------------
# Sync history
# ---------------------------------------------------------------------------

def list_sync_history(limit: int = 200) -> list[dict]:
    """Return past sync operations."""
    data = _read_store()
    history = data.get("sync_history", [])
    history.sort(key=lambda x: x.get("received_at", ""), reverse=True)
    return history[:max(1, min(limit, 1000))]


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
