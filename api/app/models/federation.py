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
    """Data package from a remote instance.

    Two layers travel together over the same envelope:

    - **Telemetry** (``lineage_links``, ``usage_events``) — small, structured
      observations from a peer instance about value-flow. Cheap to verify,
      auto-appliable once a governance vote clears.
    - **Substance** (``concept_proposals``, ``spec_proposals``,
      ``idea_proposals``, ``teaching_proposals``) — body-level material a
      peer instance would like this body to absorb. Each item becomes a
      governance ChangeRequest with ``auto_apply_on_approval=False``: the
      proposal is held by governance, and a maintainer walks it into the
      repo via a PR. Substance never writes directly into the deployed
      corpus.

    Each proposal dict carries the markdown body plus enough metadata for
    a maintainer to author the file locally. Suggested shape::

        {
            "id": "lc-some-concept",          # or spec slug, idea slug, doc path
            "title": "…",
            "body_markdown": "…",
            "frontmatter": {…},                # optional
            "origin_url": "https://peer…/concepts/lc-some-concept",
            "license": "CC-BY-SA-4.0",         # optional
        }

    The applier records the proposal as ``"stored"`` — the body decides
    how to weave it in.
    """
    source_instance_id: str = Field(min_length=1)
    timestamp: str
    lineage_links: list[dict] = Field(default_factory=list)
    usage_events: list[dict] = Field(default_factory=list)
    concept_proposals: list[dict] = Field(default_factory=list)
    spec_proposals: list[dict] = Field(default_factory=list)
    idea_proposals: list[dict] = Field(default_factory=list)
    teaching_proposals: list[dict] = Field(default_factory=list)
    # Signature for future verification
    signature: Optional[str] = None


class FederationSyncResult(BaseModel):
    """Result of processing a federated payload."""
    source_instance_id: str
    links_received: int = 0
    events_received: int = 0
    proposals_received: int = 0
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


# ---------------------------------------------------------------------------
# Self-sovereign capability manifest (signed per-instance declaration)
# ---------------------------------------------------------------------------
#
# Each instance is the source-of-truth for what IT can do. A capability is a
# claim an instance makes about itself; no central registry, no forced
# uniformity. The fleet emerges from each instance speaking its own
# capabilities — the union of self-declarations, not a coerced aggregate.

class CapabilityManifest(BaseModel):
    """Self-declared capability manifest for this instance.

    Every field's source-of-truth is THIS instance. Other instances may carry
    different shapes (extra fields, fewer fields, different provider sets);
    that diversity is the point. Federation reads peer manifests gracefully —
    unknown fields are preserved, missing fields are accepted as honest
    absence.
    """

    instance_id: str = Field(min_length=1, description="Self-declared instance ID")
    instance_url: str = Field(min_length=1, description="Self-declared base URL")
    providers: list[str] = Field(
        default_factory=list,
        description="AI providers this instance can route to (claude, openai, codex, gemini, etc.). Truth source: this instance's local model routing config.",
    )
    language_coverage: list[str] = Field(
        default_factory=list,
        description="Locale codes this instance serves translations for. Truth source: this instance's translator service.",
    )
    substrate_canonicals: list[str] = Field(
        default_factory=list,
        description="Canonical recipe-shape names this instance carries in its substrate (R_Recovery, R_ObserverConditionedActualization, ...). Truth source: this instance's modality shape registry.",
    )
    economics: dict = Field(
        default_factory=dict,
        description="Economic gates: cc_accepted (bool), cc_rate_per_usd (float|None), staking_enabled (bool). Truth source: this instance's CC economics service.",
    )
    extensions: dict = Field(
        default_factory=dict,
        description="Free-form extension fields. Instances MAY add custom capability shapes here; readers MUST preserve unknown extensions without complaint.",
    )
    declared_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    truth_source: str = Field(
        default="self",
        description='Always "self" — this manifest is the instance speaking about itself, never a third-party assertion.',
    )


class SignedCapabilityManifest(BaseModel):
    """A capability manifest plus the instance's HMAC-SHA256 signature.

    Signature is over the canonical-JSON dump of the manifest. Peers verify
    against the secret they hold for this instance — verification proves
    "this manifest came from this instance," it does not make any instance
    authoritative over others.
    """

    manifest: CapabilityManifest
    signature: str = Field(min_length=1, description="HMAC-SHA256 hex digest")
    signed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CapabilityAlignment(BaseModel):
    """Alignment between two instances' capability manifests.

    Not a hierarchy — just a difference reading. Each instance still serves
    what it serves; this surface helps callers see WHERE the overlap is and
    WHERE each instance carries something unique.
    """

    self_instance_id: str
    peer_instance_id: str
    verified: bool = Field(description="Did the peer's signature verify against the known peer secret?")
    verification_note: str = Field(
        default="",
        description='Why verification passed/failed/was skipped — e.g. "verified", "peer not registered: unsigned alignment only", "signature mismatch".',
    )
    shared_providers: list[str] = Field(default_factory=list)
    shared_languages: list[str] = Field(default_factory=list)
    shared_substrate_canonicals: list[str] = Field(default_factory=list)
    unique_to_self: dict[str, list[str]] = Field(default_factory=dict, description="Capabilities self has that peer lacks, keyed by capability kind.")
    unique_to_peer: dict[str, list[str]] = Field(default_factory=dict, description="Capabilities peer has that self lacks, keyed by capability kind.")


# ---------------------------------------------------------------------------
# Federated substrate canonical exchange — freedom-preserving discovery
# ---------------------------------------------------------------------------
#
# Two instances meeting at the substrate altitude. Neither imports the
# other; each exposes its interned canonical Blueprints, and content-
# addressing (sha256 over name + role_slots) lets the peer test for
# structural alignment without surrendering autonomy.
#
# Status taxonomy ("attestation outcome"):
#   - "aligned"    — peer carries this canonical with the same content_hash
#   - "diverged"   — peer carries this canonical name with a different hash
#   - "discovered" — peer carries a canonical this instance does not have
#
# All three are sovereign attestations: alignment is not absorption,
# divergence is not error, discovery is not import.

ALIGNMENT_STATUSES = frozenset({"aligned", "diverged", "discovered"})


class CanonicalShapeOut(BaseModel):
    """One canonical recipe-shape as exposed across the federation wire."""
    canonical_name: str
    role_slots: list[str] = Field(default_factory=list)
    modality_tags: list[str] = Field(default_factory=list)
    blueprint: dict | None = Field(
        default=None,
        description="Blueprint NodeID as {package, level, type, instance} when this instance has interned the shape",
    )
    content_hash: str = Field(
        description="sha256 hex of canonical_name + role_slots tuple — deterministic across instances",
    )
    interned: bool = Field(
        default=False,
        description="True when this instance carries the canonical cell locally",
    )
    member_count: int = Field(
        default=0,
        description="Number of per-modality cells sharing this canonical's Blueprint on this instance",
    )


class CanonicalShapesListResponse(BaseModel):
    """Full inventory of this instance's canonical recipe-shapes."""
    instance_id: str | None = None
    canonicals: list[CanonicalShapeOut] = Field(default_factory=list)
    count: int = 0


class CanonicalDiscoverResponse(BaseModel):
    """Single-shape lookup — does THIS instance carry this canonical?"""
    canonical_name: str
    found: bool
    content_hash: str | None = None
    blueprint: dict | None = None


class PeerCanonicalEntry(BaseModel):
    """One canonical as reported by a peer in an exchange payload."""
    canonical_name: str = Field(min_length=1)
    role_slots: list[str] = Field(default_factory=list)
    modality_tags: list[str] = Field(default_factory=list)
    content_hash: str = Field(min_length=1)


class CanonicalExchangeRequest(BaseModel):
    """Inbound: a peer's canonical inventory for structural attestation."""
    peer_instance_id: str = Field(
        min_length=1,
        description="Sovereign identifier for the peer — used as the partition key in the attestation mirror",
    )
    peer_endpoint_url: str | None = None
    canonicals: list[PeerCanonicalEntry] = Field(default_factory=list)


class CanonicalAttestationOut(BaseModel):
    """One attestation row — how this instance views a peer's canonical."""
    peer_instance_id: str
    canonical_name: str
    peer_content_hash: str
    local_content_hash: str | None = None
    alignment_status: str = Field(description="aligned | diverged | discovered")
    observed_at: str


class CanonicalExchangeResponse(BaseModel):
    """Outbound: the per-canonical attestation outcomes after an exchange."""
    peer_instance_id: str
    received: int = 0
    aligned: int = 0
    diverged: int = 0
    discovered: int = 0
    attestations: list[CanonicalAttestationOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Federated value flow — freedom-preserving CC distribution across instances
# ---------------------------------------------------------------------------
#
# Asset on instance A is mirrored to instance B. B serves a read; B sends A
# an attribution envelope. At settlement time, A computes B's share and sends
# B a settlement envelope. Each instance stays sovereign over what it knows:
# A holds the truth about its assets, B holds the truth about its readers.
# Neither commands the other — both sides may decline. The fleet's value
# flow is the union of self-declared exchanges, not a central ledger.


VALUE_ATTESTATION_STATUSES = frozenset({"received", "verified", "settled", "rejected"})

# Default split when a federated read settles: 80% to the creator, 20% to
# the serving instance. Inspired by the asset-renderer-plugin 85/15 share —
# the serving instance carries delivery cost the same way a renderer does.
DEFAULT_FEDERATED_CREATOR_SHARE = 0.80
DEFAULT_FEDERATED_SERVING_SHARE = 0.20


class AssetMirrorManifest(BaseModel):
    """Manifest a peer sends when asking to mirror one of our assets.

    The peer holds the local asset id; the manifest declares origin so
    later read-attributions can address us as authoritative. Sovereignty:
    we still choose whether to accept; the manifest is a request, not a
    command.
    """
    local_asset_id: str = Field(min_length=1, description="The asset id on the mirroring instance (the one receiving the manifest)")
    origin_instance_id: str = Field(min_length=1, description="Instance that authored the asset")
    origin_asset_id: str = Field(min_length=1, description="Asset id as known to its origin instance")
    origin_url: str = Field(min_length=1, description="URL on the origin instance where the asset lives")
    origin_payment_address: str | None = Field(
        default=None,
        description="Creator's payment address on the origin instance — where settlement CC flows",
    )
    mirrored_at: str | None = None


class AssetMirrorRecord(BaseModel):
    """Round-tripped mirror record — what we store and return."""
    local_asset_id: str
    origin_instance_id: str
    origin_asset_id: str
    origin_url: str
    origin_payment_address: str | None = None
    mirrored_at: str


class ReadAttributionEnvelope(BaseModel):
    """Signed envelope a serving instance sends to an origin instance.

    `signature` is HMAC-SHA256 over the canonical-JSON dump of the envelope
    excluding the signature itself. The origin verifies against the secret
    it holds for the serving instance (stored in
    `FederatedInstanceRecord.public_key`).
    """
    asset_origin_id: str = Field(min_length=1, description="The asset id as known to the origin instance")
    reader_instance_id: str = Field(min_length=1, description="ID of the instance that served the read")
    reader_subject: str | None = Field(
        default=None,
        description="Opaque reader subject on the serving instance (may be hashed or anonymous)",
    )
    read_type: str = Field(default="free", description="free | paid")
    cc_amount: float = Field(default=0.0, ge=0.0)
    concept_resonance: dict[str, float] | None = None
    observed_at: str = Field(description="ISO 8601 UTC timestamp when the read happened")
    signature: str = Field(min_length=1)


class ReadAttributionAck(BaseModel):
    """What the origin instance returns after recording an attribution."""
    asset_origin_id: str
    reader_instance_id: str
    status: str = Field(description="received | verified | rejected")
    federated_reader_id: str | None = Field(
        default=None,
        description="The reader_id under which this read was recorded locally",
    )
    note: str | None = None


class FederatedReadAttestationOut(BaseModel):
    """One stored federated read attestation, as exposed via the API."""
    id: int
    asset_origin_id: str
    reader_instance_id: str
    reader_subject: str | None = None
    read_type: str
    cc_amount: float
    observed_at: str
    received_at: str
    status: str
    signature_verified: bool


class FederatedReadAttestationListResponse(BaseModel):
    asset_origin_id: str | None = None
    reader_instance_id: str | None = None
    attestations: list[FederatedReadAttestationOut] = Field(default_factory=list)
    count: int = 0


class SettlementShareEnvelope(BaseModel):
    """Signed envelope an origin instance sends to a serving instance.

    The origin computed the serving instance's share from attestations it
    received during the period; the envelope declares the amount and the
    constituent reads. Sovereignty: the serving instance verifies, then
    stores in its inbox; downstream CC transfer is a separate breath.
    """
    origin_instance_id: str = Field(min_length=1, description="Instance computing the settlement (the asset's home)")
    serving_instance_id: str = Field(min_length=1, description="Instance receiving the share (read-server)")
    period_start: str = Field(description="ISO 8601 UTC inclusive start of the settlement period")
    period_end: str = Field(description="ISO 8601 UTC exclusive end of the settlement period")
    read_count: int = Field(ge=0)
    cc_amount_to_serving: float = Field(ge=0.0)
    cc_amount_to_creator: float = Field(ge=0.0)
    serving_share: float = Field(ge=0.0, le=1.0)
    creator_share: float = Field(ge=0.0, le=1.0)
    asset_breakdown: list[dict] = Field(
        default_factory=list,
        description="Per-asset entries: {asset_origin_id, read_count, cc_amount_to_serving}",
    )
    signature: str = Field(min_length=1)


class SettlementShareAck(BaseModel):
    """Acknowledgement returned by the serving instance after inbox storage."""
    inbox_id: int
    origin_instance_id: str
    status: str = Field(description="received | verified | rejected")
    note: str | None = None


class SettlementInboxEntryOut(BaseModel):
    """One inbox entry — a settlement envelope the serving side received."""
    id: int
    origin_instance_id: str
    period_start: str
    period_end: str
    read_count: int
    cc_amount_to_serving: float
    cc_amount_to_creator: float
    received_at: str
    status: str
    signature_verified: bool


class SettlementInboxListResponse(BaseModel):
    origin_instance_id: str | None = None
    entries: list[SettlementInboxEntryOut] = Field(default_factory=list)
    count: int = 0


class ComputeFederatedSharesRequest(BaseModel):
    """Trigger a settlement-share computation across federated peers for a period.

    The request says *which* period; the service computes per-peer envelopes
    from this instance's stored federated read attestations.
    """
    period_start: str = Field(description="ISO 8601 UTC inclusive period start")
    period_end: str = Field(description="ISO 8601 UTC exclusive period end")
    serving_share: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override the default serving-side share (default 0.20)",
    )
    serving_instance_id: str | None = Field(
        default=None,
        description="If set, only compute for this peer; otherwise compute for every peer with attestations in the window",
    )
    mark_settled: bool = Field(
        default=True,
        description="If true, attestations included in the envelope flip to status=settled",
    )


class ComputeFederatedSharesResponse(BaseModel):
    period_start: str
    period_end: str
    envelopes: list[SettlementShareEnvelope] = Field(default_factory=list)
    serving_share: float
    creator_share: float
    total_cc_to_serving: float = 0.0
    total_cc_to_creator: float = 0.0
    attestations_settled: int = 0
