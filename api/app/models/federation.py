"""Federation models for cross-instance data exchange."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class FederatedInstance(BaseModel):
    """A remote Coherence instance."""
    instance_id: str = Field(min_length=1, description="Unique ID of the remote instance")
    name: str = Field(min_length=1)
    endpoint_url: str = Field(min_length=1, description="Base URL of the remote API")
    public_key: Optional[str] = None  # For future signature verification
    registered_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_sync_at: Optional[str] = None
    trust_level: str = Field(default="pending", description="Trust level: unknown, pending, verified, trusted")


class FederatedPayload(BaseModel):
    """Data package from a remote instance."""
    source_instance_id: str = Field(min_length=1)
    timestamp: str
    lineage_links: list[dict] = Field(default_factory=list)
    usage_events: list[dict] = Field(default_factory=list)
    # Signature for future verification
    signature: Optional[str] = None


class FederationSyncResult(BaseModel):
    """Result of processing a federated payload."""
    source_instance_id: str
    links_received: int = 0
    events_received: int = 0
    governance_requests_created: int = 0
    accepted: int = 0
    rejected: int = 0
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Node identity registration / heartbeat models (Spec 132)
# ---------------------------------------------------------------------------

class FederationNodeRegisterRequest(BaseModel):
    """Request body for POST /api/federation/nodes."""
    node_id: str = Field(min_length=16, max_length=16)
    hostname: str
    os_type: str = Field(description="macos | windows | linux | vps")
    providers: list[str] = Field(default_factory=list)
    capabilities: dict = Field(default_factory=dict)


class FederationNodeRegisterResponse(BaseModel):
    """Response for node registration."""
    node_id: str
    status: str
    registered_at: datetime
    last_seen_at: datetime


class FederationNodeHeartbeatRequest(BaseModel):
    """Request body for POST /api/federation/nodes/{node_id}/heartbeat."""
    status: str = "online"


class FederationNodeHeartbeatResponse(BaseModel):
    """Response for node heartbeat."""
    node_id: str
    status: str
    last_seen_at: datetime


# ---------------------------------------------------------------------------
# Measurement summary models (Spec 131)
# ---------------------------------------------------------------------------

class MeasurementSummary(BaseModel):
    """A single aggregated measurement summary for a (decision_point, slot_id) pair."""
    node_id: str = Field(min_length=1)
    decision_point: str = Field(min_length=1)
    slot_id: str = Field(min_length=1)
    period_start: datetime
    period_end: datetime
    sample_count: int = Field(ge=1)
    successes: int = Field(ge=0)
    failures: int = Field(ge=0)
    mean_duration_s: Optional[float] = None
    mean_value_score: float = Field(ge=0.0, le=1.0)
    error_classes_json: dict = Field(default_factory=dict)


class MeasurementPushRequest(BaseModel):
    """Batch of measurement summaries pushed by a node."""
    summaries: list[MeasurementSummary] = Field(min_length=1)


class MeasurementPushResponse(BaseModel):
    """Response after storing measurement summaries."""
    stored: int
    node_id: str


class MeasurementSummaryStored(MeasurementSummary):
    """A stored measurement summary with server-assigned fields."""
    id: int
    pushed_at: datetime


class MeasurementListResponse(BaseModel):
    """Paginated list of stored measurement summaries."""
    node_id: str
    summaries: list[MeasurementSummaryStored]
    total: int
    limit: int
    offset: int
