# Spec: Federated Instance Aggregation [idea:federated-instance-aggregation]

## Purpose

Federation needs a safe protocol for partner instances to share execution outcomes without allowing untrusted or low-quality data to contaminate hub decisions. This spec defines trust verification, payload validation, and deterministic merge strategies so fleet-wide aggregation improves decision quality while preserving local node autonomy and auditability.

## Requirements

- [ ] Partner instances submit aggregation payloads through a signed federation envelope that includes `node_id`, `sent_at`, `schema_version`, and `payload_hash`.
- [ ] Hub verifies partner trust state before accepting payloads using registration status, trust tier, and signature validity checks.
- [ ] Hub rejects unsafe or malformed submissions with deterministic error codes and does not persist partial records.
- [ ] Accepted submissions are merged through strategy-specific deterministic reducers (`weighted_mean`, `majority_vote`, `warning_union`) with explicit tie-break rules.
- [ ] Merge strategy selection is policy-driven by `strategy_type` and does not branch ad hoc inside routers.
- [ ] Aggregated outputs preserve provenance (`source_nodes`, `sample_count`, `window_start`, `window_end`) for downstream explainability.
- [ ] Local node runtime decisions remain advisory-aware but autonomous: aggregated federation guidance cannot hard-override local Thompson Sampling.
- [ ] Aggregation endpoint behavior is idempotent for duplicate payloads identified by `(node_id, payload_hash, sent_at_bucket)`.

## Research Inputs (Required)

- `2026-03-22` - [Spec Template](https://github.com/seeker71/Coherence-Network/blob/main/specs/TEMPLATE.md) - canonical quality contract and required sections.
- `2026-03-22` - [Spec 120: Minimum Federation Layer](https://github.com/seeker71/Coherence-Network/blob/main/specs/120-minimum-federation-layer.md) - baseline hub/node federation responsibilities and API style.
- `2026-03-22` - [Spec 131: Federation Measurement Push](https://github.com/seeker71/Coherence-Network/blob/main/specs/131-federation-measurement-push.md) - existing node-to-hub measurement transport pattern reused by aggregation ingestion.
- `2026-03-22` - [Spec 132: Federation Node Identity](https://github.com/seeker71/Coherence-Network/blob/main/specs/132-federation-node-identity.md) - trusted node identity lifecycle and node metadata constraints.
- `2026-03-22` - [Spec 134: Federation Strategy Propagation](https://github.com/seeker71/Coherence-Network/blob/main/specs/134-federation-strategy-propagation.md) - advisory strategy model and local precedence contract preserved by this work.

## Task Card (Required)

```yaml
goal: Define a secure, deterministic federated aggregation protocol for partner instance result sharing and trust-aware merge behavior
files_allowed:
  - specs/143-federated-instance-aggregation.md
  - api/app/models/federation.py
  - api/app/routers/federation.py
  - api/app/services/federation_service.py
  - api/tests/test_federated_instance_aggregation.py
done_when:
  - Spec defines protocol envelope, trust verification contract, and deterministic merge strategy matrix
  - Acceptance tests enumerate success, reject, dedupe, and merge tie-break behavior
  - Spec passes quality validation script without errors
commands:
  - python3 scripts/validate_spec_quality.py --file specs/143-federated-instance-aggregation.md
constraints:
  - no hard override of local Thompson Sampling by federated aggregates
  - no provider-specific branching in routers or orchestration layers
  - trust verification must fail closed when required evidence is missing
```

## API Contract (if applicable)

### `POST /api/federation/instances/{node_id}/aggregate`

Submit partner instance aggregation payload for trust-gated merge.

**Request**
- `node_id`: string (path)

```json
{
  "envelope": {
    "schema_version": "v1",
    "node_id": "node_alpha",
    "sent_at": "2026-03-22T16:30:00Z",
    "payload_hash": "sha256:3a4b...",
    "signature": "base64:MEUC..."
  },
  "payload": {
    "strategy_type": "provider_recommendation",
    "window_start": "2026-03-22T15:30:00Z",
    "window_end": "2026-03-22T16:30:00Z",
    "sample_count": 84,
    "metrics": {
      "provider": "openrouter/deepseek-v3",
      "success_rate": 0.91,
      "avg_duration_s": 63.4
    }
  }
}
```

**Response 202**
```json
{
  "status": "accepted",
  "merge_key": "provider_recommendation:2026-03-22T16",
  "trust_tier": "verified_partner",
  "dedupe": false
}
```

**Response 409**
```json
{
  "detail": "duplicate payload for merge window",
  "dedupe": true
}
```

**Response 422**
```json
{
  "detail": "invalid payload: missing metrics.success_rate for provider_recommendation"
}
```

**Response 403**
```json
{
  "detail": "node trust verification failed"
}
```

## Data Model (if applicable)

```yaml
FederatedAggregationEnvelope:
  properties:
    schema_version: { type: string, enum: [v1] }
    node_id: { type: string }
    sent_at: { type: datetime }
    payload_hash: { type: string }
    signature: { type: string }

FederatedAggregationPayload:
  properties:
    strategy_type:
      type: string
      enum: [provider_recommendation, prompt_variant_winner, provider_warning]
    window_start: { type: datetime }
    window_end: { type: datetime }
    sample_count: { type: integer, minimum: 1 }
    metrics: { type: object }

FederatedAggregationMergeResult:
  properties:
    strategy_type: { type: string }
    merge_strategy: { type: string, enum: [weighted_mean, majority_vote, warning_union] }
    value: { type: object }
    source_nodes: { type: list[string] }
    sample_count: { type: integer }
    window_start: { type: datetime }
    window_end: { type: datetime }
```

## Files to Create/Modify

- `specs/143-federated-instance-aggregation.md` - spec contract for protocol, trust verification, and merge behavior.
- `api/app/models/federation.py` - request/response and trust-verification model types for aggregation ingestion.
- `api/app/routers/federation.py` - `POST /api/federation/instances/{node_id}/aggregate` endpoint and validation wiring.
- `api/app/services/federation_service.py` - trust verification logic, dedupe checks, and deterministic merge reducers.
- `api/tests/test_federated_instance_aggregation.py` - acceptance coverage for trusted/denied flows and merge determinism.

## Acceptance Tests

- `api/tests/test_federated_instance_aggregation.py::test_accepts_verified_partner_payload_and_returns_202`
- `api/tests/test_federated_instance_aggregation.py::test_rejects_unverified_partner_with_403`
- `api/tests/test_federated_instance_aggregation.py::test_rejects_malformed_payload_with_422`
- `api/tests/test_federated_instance_aggregation.py::test_duplicate_payload_is_idempotent_409`
- `api/tests/test_federated_instance_aggregation.py::test_weighted_mean_merge_is_deterministic`
- `api/tests/test_federated_instance_aggregation.py::test_majority_vote_tie_break_is_deterministic`
- `api/tests/test_federated_instance_aggregation.py::test_warning_union_merge_preserves_provenance`
- `api/tests/test_federated_instance_aggregation.py::test_local_thompson_sampling_precedence_preserved`

## Concurrency Behavior

- **Read operations**: Trust metadata and prior merge windows are read concurrently without locks.
- **Write operations**: Duplicate suppression uses deterministic merge key and conflict-safe insertion semantics.
- **Merge execution**: Reducers operate on immutable submission snapshots per merge window to avoid race-dependent outcomes.

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/143-federated-instance-aggregation.md
```

## Out of Scope

- Federated payment settlement or token economics for shared compute.
- Cross-instance transport protocol migration (for example gRPC or message bus replacement).
- Cryptographic key management UX and rotation workflows.
- UI dashboard implementation for federated merge lineage.

## Risks and Assumptions

- **Risk**: Trust signals may be stale, allowing degraded nodes to submit misleading data. *Mitigation*: fail-closed trust checks and time-bounded verification freshness.
- **Risk**: Reducer policy drift may cause non-deterministic outputs across deployments. *Mitigation*: strategy-to-reducer matrix defined in service policy and validated by acceptance tests.
- **Assumption**: Partner nodes can produce verifiable signatures aligned with registered identity metadata.
- **Assumption**: Existing federation storage can index dedupe keys without large schema redesign.

## Known Gaps and Follow-up Tasks

- Follow-up task: implement key rotation and revoked-key propagation for federation partners.
- Follow-up task: add per-partner trust score decay and automated quarantine thresholds.
- Follow-up issue: define replay-attack tolerance window and canonical sent_at bucketing granularity.

## Failure/Retry Reflection

- Failure mode: valid payload rejected due to stale trust cache.
  - Blind spot: cache freshness policy underestimates partner update cadence.
  - Next action: force trust cache refresh on first verification failure before final reject.

- Failure mode: merge outputs diverge between environments.
  - Blind spot: reducer tie-break criteria not encoded explicitly.
  - Next action: encode deterministic tie-break by lexical `node_id` ordering and fixed precision rounding.

## Decision Gates (if any)

- Confirm acceptable signature algorithm set for federation envelope v1.
- Confirm default dedupe time bucket (`minute` vs `five_minute`) for high-throughput partners.
