# Spec: Federation Strategy Propagation

## Purpose

The federation hub needs a lightweight way to convert cross-node measurement signals into reusable strategy guidance that every node can consume. This spec defines how the hub computes and stores advisory strategy broadcasts, plus a pull endpoint that lets nodes fetch active recommendations without overriding local Thompson Sampling decisions.

## Requirements

- [ ] Hub computes aggregate strategy recommendations from cross-node measurement summaries and stores them in `node_strategy_broadcasts`.
- [ ] `node_strategy_broadcasts` includes columns: `id` (PK), `strategy_type` (VARCHAR), `payload_json` (TEXT), `source_node_id` (VARCHAR), `created_at` (TIMESTAMPTZ), `expires_at` (TIMESTAMPTZ).
- [ ] Supported `strategy_type` values are exactly: `provider_recommendation`, `prompt_variant_winner`, `provider_warning`.
- [ ] Nodes fetch active strategy broadcasts via `GET /api/federation/strategies`.
- [ ] `GET /api/federation/strategies` returns only non-expired broadcasts (`expires_at > now()`), newest first.
- [ ] Hub strategy broadcasts are advisory only; local Thompson Sampling data always takes precedence in runtime decisions.
- [ ] API response format is deterministic and machine-readable for automation clients.

## Research Inputs (Required)

- `2026-03-21` - [Spec Template](specs/TEMPLATE.md) - required structure and quality gates for spec authoring.
- `2026-03-21` - [Spec 131: Federation Measurement Push](specs/131-federation-measurement-push.md) - defines upstream cross-node measurement summaries that strategy computation consumes.
- `2026-03-21` - [Spec 132: Federation Node Identity and Registration](specs/132-federation-node-identity.md) - provides node identity conventions reused by `source_node_id`.
- `2026-03-21` - [Spec 120: Minimum Federation Layer](specs/120-minimum-federation-layer.md) - establishes hub/node federation directionality and shared API style.

## Task Card (Required)

```yaml
goal: Add hub strategy broadcast persistence and node pull endpoint for federation advisory guidance
files_allowed:
  - api/app/models/federation.py
  - api/app/routers/federation.py
  - api/app/services/federation_service.py
  - api/app/db/migrations/add_node_strategy_broadcasts.sql
  - api/tests/test_federation_strategy_propagation.py
  - specs/134-federation-strategy-propagation.md
done_when:
  - node_strategy_broadcasts table exists with required columns and strategy_type constraints
  - GET /api/federation/strategies returns active broadcasts in deterministic order
  - runtime selection logic preserves local Thompson Sampling precedence over hub advice
commands:
  - cd api && pytest -q tests/test_federation_strategy_propagation.py
  - python3 scripts/validate_spec_quality.py --file specs/134-federation-strategy-propagation.md
constraints:
  - no hub directive can hard-override local node Thompson Sampling outcomes
  - keep strategy broadcast payload schema extensible via payload_json
  - no auth/trust model additions in this spec
```

## API Contract (if applicable)

### `GET /api/federation/strategies`

Returns active federation strategy broadcasts for node-side advisory use.

**Request**
- `strategy_type`: string (query, optional) — filter to one of `provider_recommendation`, `prompt_variant_winner`, `provider_warning`.
- `limit`: int (query, default 100, max 500).
- `offset`: int (query, default 0).

**Response 200**
```json
{
  "strategies": [
    {
      "id": 41,
      "strategy_type": "provider_recommendation",
      "payload_json": "{\"decision_point\":\"provider_code_gen\",\"recommended_provider\":\"openrouter/deepseek-v3\",\"confidence\":0.82}",
      "source_node_id": "hub",
      "created_at": "2026-03-21T15:00:00Z",
      "expires_at": "2026-03-21T21:00:00Z",
      "advisory_only": true
    }
  ],
  "total": 1,
  "limit": 100,
  "offset": 0
}
```

**Response 422**
```json
{
  "detail": "invalid strategy_type; expected one of: provider_recommendation, prompt_variant_winner, provider_warning"
}
```

## Data Model (if applicable)

### PostgreSQL: `node_strategy_broadcasts`

```sql
CREATE TABLE node_strategy_broadcasts (
    id             SERIAL PRIMARY KEY,
    strategy_type  VARCHAR NOT NULL CHECK (
      strategy_type IN (
        'provider_recommendation',
        'prompt_variant_winner',
        'provider_warning'
      )
    ),
    payload_json   TEXT NOT NULL,
    source_node_id VARCHAR NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at     TIMESTAMPTZ NOT NULL
);

CREATE INDEX idx_nsb_strategy_type_created_at
  ON node_strategy_broadcasts (strategy_type, created_at DESC);
CREATE INDEX idx_nsb_expires_at
  ON node_strategy_broadcasts (expires_at);
```

### Pydantic Model Shape

```yaml
FederationStrategyBroadcast:
  properties:
    id: { type: integer }
    strategy_type:
      type: string
      enum: [provider_recommendation, prompt_variant_winner, provider_warning]
    payload_json: { type: string }
    source_node_id: { type: string }
    created_at: { type: datetime }
    expires_at: { type: datetime }
    advisory_only: { type: boolean, const: true }

FederationStrategyListResponse:
  properties:
    strategies: { type: list[FederationStrategyBroadcast] }
    total: { type: integer }
    limit: { type: integer }
    offset: { type: integer }
```

## Files to Create/Modify

- `specs/134-federation-strategy-propagation.md` - this spec document.
- `api/app/db/migrations/add_node_strategy_broadcasts.sql` - create `node_strategy_broadcasts` table and indexes.
- `api/app/models/federation.py` - add strategy broadcast request/response models.
- `api/app/services/federation_service.py` - add aggregate strategy computation and retrieval methods.
- `api/app/routers/federation.py` - add `GET /api/federation/strategies`.
- `api/tests/test_federation_strategy_propagation.py` - validate persistence, filtering, expiry behavior, and advisory precedence semantics.

## Acceptance Tests

- `api/tests/test_federation_strategy_propagation.py::test_get_strategies_returns_active_broadcasts_only`
- `api/tests/test_federation_strategy_propagation.py::test_get_strategies_filters_by_strategy_type`
- `api/tests/test_federation_strategy_propagation.py::test_get_strategies_pagination_order_newest_first`
- `api/tests/test_federation_strategy_propagation.py::test_invalid_strategy_type_returns_422`
- `api/tests/test_federation_strategy_propagation.py::test_hub_computes_provider_recommendation_from_cross_node_measurements`
- `api/tests/test_federation_strategy_propagation.py::test_hub_computes_prompt_variant_winner_from_cross_node_measurements`
- `api/tests/test_federation_strategy_propagation.py::test_hub_emits_provider_warning_from_error_class_trends`
- `api/tests/test_federation_strategy_propagation.py::test_local_thompson_sampling_precedence_over_hub_advice`

## Concurrency Behavior

- **Broadcast writes**: Hub appends new strategy rows; no in-place mutation required for normal flow.
- **Broadcast reads**: Nodes can pull concurrently; query filters on `expires_at` and ordering are read-safe.
- **Advisory precedence**: Selection runtime uses local Thompson Sampling first; hub strategy is a secondary suggestion layer only.

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/134-federation-strategy-propagation.md
```

## Out of Scope

- Push-based delivery (webhooks, SSE, or websocket) for strategy propagation.
- Authentication and trust policy hardening for federation strategy endpoints.
- Provider-specific enforcement actions that bypass or override local selection.
- UI surfaces for browsing or approving strategy broadcasts.

## Risks and Assumptions

- **Risk**: Poor aggregation heuristics could produce low-quality recommendations. *Mitigation*: keep strategy payloads advisory and short-lived with explicit `expires_at`.
- **Risk**: Stale strategies may linger if expiry windows are too long. *Mitigation*: enforce non-expired query behavior and bias toward shorter TTL defaults.
- **Assumption**: Cross-node measurement summaries in `node_measurement_summaries` are sufficiently populated and normalized for meaningful aggregation.
- **Assumption**: Runtime selector can consume advisory metadata without bypassing existing Thompson Sampling logic.

## Known Gaps and Follow-up Tasks

- Follow-up: define exact aggregation formulas and thresholds per strategy type (confidence, minimum sample floors, warning trigger levels).
- Follow-up: add authenticated federation trust model for strategy producer/consumer integrity.
- Follow-up: add retention/pruning for expired strategy broadcasts.
- Follow-up: add explainability metadata in payloads (`evidence_window`, `sample_count`, `supporting_nodes`) for operator auditability.

## Failure/Retry Reflection

- Failure mode: hub computes a strategy from sparse data.
  - Blind spot: recommendations may overfit early noise.
  - Next action: require minimum cross-node sample threshold before emitting broadcasts.

- Failure mode: expired rows are returned due to query bug.
  - Blind spot: nodes could act on stale guidance.
  - Next action: enforce integration test coverage on `expires_at > now()` filter.

- Failure mode: local selector accidentally treats hub strategy as hard override.
  - Blind spot: advisory contract is violated and local adaptation regresses.
  - Next action: add explicit precedence test asserting local Thompson Sampling wins on conflict.

## Decision Gates (if any)

- Confirm initial TTL defaults for each strategy type.
- Confirm whether `source_node_id` should always be `hub` or support upstream source lineage (for example, aggregated-from subsets).
