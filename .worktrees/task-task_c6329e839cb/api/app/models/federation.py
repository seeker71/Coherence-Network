"""Federation models for cross-instance data exchange."""

from __future__ import annotations

from datetime import datetime, timezone
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
    is_autonomous: bool = Field(False, description="If true, node executes tasks automatically (Heartbeat Protocol)")
    heartbeat_interval_ms: int = Field(900000, description="Target heartbeat frequency (default 15m)")


class FederationNodeRegisterResponse(BaseModel):
    """Response for node registration."""
    node_id: str
    status: str
    registered_at: datetime
    last_seen_at: datetime


class NodeCapabilities(BaseModel):
    """Auto-discovered capability manifest for a federation node."""

    executors: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    hardware: dict = Field(default_factory=dict)
    models_by_executor: dict[str, list[str]] = Field(default_factory=dict)
    probed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class FleetCapabilitySummary(BaseModel):
    """Aggregated fleet capability summary across registered nodes."""

    total_nodes: int = 0
    executors: dict = Field(default_factory=dict)
    tools: dict = Field(default_factory=dict)
    hardware_summary: dict = Field(default_factory=dict)


class FederationNodeHeartbeatRequest(BaseModel):
    """Request body for POST /api/federation/nodes/{node_id}/heartbeat."""
    status: str = "online"
    capabilities: NodeCapabilities | dict | None = None
    git_sha: str | None = None
    system_metrics: dict | None = None


class FederationNodeHeartbeatResponse(BaseModel):
    """Response for node heartbeat."""
    node_id: str
    status: str
    last_seen_at: datetime
    capabilities_refreshed: bool = False


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
    duplicates_skipped: int = 0
    duplicates_replaced: int = 0


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


# ---------------------------------------------------------------------------
# Strategy broadcast models (Spec 134)
# ---------------------------------------------------------------------------

VALID_STRATEGY_TYPES = frozenset({
    "provider_recommendation",
    "prompt_variant_winner",
    "provider_warning",
})


class FederationStrategyBroadcast(BaseModel):
    """A single federation strategy broadcast."""
    id: int
    strategy_type: str
    payload_json: str
    source_node_id: str
    created_at: datetime
    expires_at: datetime
    advisory_only: bool = True


class FederationStrategyListResponse(BaseModel):
    """Paginated list of active strategy broadcasts."""
    strategies: list[FederationStrategyBroadcast]
    total: int
    limit: int
    offset: int


class FederationStrategyEffectivenessReportRequest(BaseModel):
    """Node-reported outcome after acting on a strategy broadcast."""
    node_id: str = Field(min_length=1)
    was_applied: bool = True
    baseline_value_score: float = Field(ge=0.0, le=1.0)
    outcome_value_score: float = Field(ge=0.0, le=1.0)
    observed_at: Optional[datetime] = None
    context_json: dict = Field(default_factory=dict)


class FederationStrategyEffectivenessReportResponse(BaseModel):
    """Recorded effectiveness outcome for one acted-on strategy."""
    strategy_id: int
    strategy_type: str
    strategy_target: str
    node_id: str
    was_applied: bool
    baseline_value_score: float
    outcome_value_score: float
    improvement_score: float
    improved: bool
    recorded_at: datetime


# ---------------------------------------------------------------------------
# Federated Instance Aggregation models (Spec 143)
# ---------------------------------------------------------------------------

class FederatedAggregationEnvelope(BaseModel):
    """Secure protocol envelope for partner instance aggregation payloads."""
    schema_version: str = Field(default="v1")
    node_id: str = Field(min_length=1)
    sent_at: datetime
    payload_hash: str
    signature: str


class FederatedAggregationPayload(BaseModel):
    """Content for federated aggregation merging."""
    strategy_type: str = Field(description="provider_recommendation | prompt_variant_winner | provider_warning")
    window_start: datetime
    window_end: datetime
    sample_count: int = Field(ge=1)
    metrics: dict


class FederatedAggregationRequest(BaseModel):
    """Request body for POST /api/federation/instances/{node_id}/aggregate."""
    envelope: FederatedAggregationEnvelope
    payload: FederatedAggregationPayload


class FederatedAggregationResponse(BaseModel):
    """Response for aggregation ingestion."""
    status: str = "accepted"
    merge_key: str
    trust_tier: str
    dedupe: bool = False


class FederatedAggregationMergeResult(BaseModel):
    """A merged aggregation result across multiple nodes."""
    strategy_type: str
    merge_strategy: str
    value: dict
    metrics: dict  # Included for convenience in UI/API
    source_nodes: list[str]
    sample_count: int
    window_start: datetime
    window_end: datetime


class FederatedAggregationListResponse(BaseModel):
    """Response for GET /api/federation/aggregates."""
    aggregates: list[FederatedAggregationMergeResult]


# ---------------------------------------------------------------------------
# Marketplace federated payload types (Spec 121)
# ---------------------------------------------------------------------------

MARKETPLACE_PAYLOAD_TYPES = frozenset({
    "MARKETPLACE_LISTING",
    "MARKETPLACE_FORK",
})


class MarketplaceFederatedPayload(BaseModel):
    """Federated payload envelope for marketplace sync (spec 121)."""

    type: str = Field(description="MARKETPLACE_LISTING or MARKETPLACE_FORK")
    source_instance_id: str = Field(min_length=1)
    sent_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    listing_id: str = Field(min_length=1)
    data: dict = Field(default_factory=dict, description="Full listing or fork payload")
