---
idea_id: value-attribution
status: done
source:
  - file: api/app/routers/distributions.py
    symbols: [create_distribution()]
  - file: api/app/services/distribution_engine.py
    symbols: [DistributionEngine.distribute()]
  - file: api/app/models/distribution.py
    symbols: [Distribution, Payout]
requirements:
  - "POST /api/distributions — Trigger distribution for an asset"
  - "Distribution algorithm: proportional to (cost_amount × (0.5 + coherence_score))"
  - "Coherence weighting: higher coherence = higher payout multiplier"
  - "Handles zero contributions (empty payout list)"
  - "Handles zero weighted cost (empty payout list)"
  - "Payout amounts rounded to 2 decimal places (ROUND_HALF_UP)"
  - "Returns 404 when asset not found"
  - "Async execution for future scaling"
done_when:
  - "POST /api/distributions — Trigger distribution for an asset"
  - "Distribution algorithm: proportional to (cost_amount × (0.5 + coherence_score))"
  - "Coherence weighting: higher coherence = higher payout multiplier"
  - "Handles zero contributions (empty payout list)"
  - "Handles zero weighted cost (empty payout list)"
test: "python3 -m pytest api/tests/test_distributions.py -x -v"
constraints:
  - "changes scoped to listed files only"
  - "no schema migrations without explicit approval"
---

> **Parent idea**: [value-attribution](../ideas/value-attribution.md)
> **Source**: [`api/app/routers/distributions.py`](../api/app/routers/distributions.py) | [`api/app/services/distribution_engine.py`](../api/app/services/distribution_engine.py) | [`api/app/models/distribution.py`](../api/app/models/distribution.py)

# Spec: Distribution Engine

## Purpose

Calculate fair value distribution among contributors based on their contributions weighted by coherence scores. Enables automated payouts proportional to contribution quality and effort.

## Requirements

- [x] POST /api/distributions — Trigger distribution for an asset
- [x] Distribution algorithm: proportional to (cost_amount × (0.5 + coherence_score))
- [x] Coherence weighting: higher coherence = higher payout multiplier
- [x] Handles zero contributions (empty payout list)
- [x] Handles zero weighted cost (empty payout list)
- [x] Payout amounts rounded to 2 decimal places (ROUND_HALF_UP)
- [x] Returns 404 when asset not found
- [x] Async execution for future scaling


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Calculate fair value distribution among contributors based on their contributions weighted by coherence scores.
files_allowed:
  - api/app/routers/distributions.py
  - api/app/services/distribution_engine.py
  - api/app/models/distribution.py
  - api/tests/test_distributions.py
  - specs/distribution-engine.md
done_when:
  - POST /api/distributions — Trigger distribution for an asset
  - Distribution algorithm: proportional to (cost_amount × (0.5 + coherence_score))
  - Coherence weighting: higher coherence = higher payout multiplier
  - Handles zero contributions (empty payout list)
  - Handles zero weighted cost (empty payout list)
commands:
  - python3 -m pytest api/tests/test_distributions.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

### `POST /api/distributions`

**Purpose**: Calculate value distribution for an asset

**Request**
```json
{
  "asset_id": "660e8400-e29b-41d4-a716-446655440000",
  "value_amount": 1000.00
}
```

- `asset_id`: UUID (required) — Asset to distribute value for
- `value_amount`: Decimal (required) — Total value to distribute

**Response 201**
```json
{
  "asset_id": "660e8400-e29b-41d4-a716-446655440000",
  "value_amount": 1000.00,
  "payouts": [
    {
      "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
      "amount": 600.00
    },
    {
      "contributor_id": "660e8400-e29b-41d4-a716-446655440001",
      "amount": 400.00
    }
  ]
}
```

- `payouts`: List of contributor payouts (sorted by contributor_id)
- `amount`: Decimal — Payout amount rounded to 2 decimals

**Distribution Algorithm**:
1. For each contribution: `weighted_cost = cost_amount × (0.5 + coherence_score)`
2. Sum weighted costs per contributor
3. Calculate proportion: `payout = (contributor_weighted / total_weighted) × value_amount`
4. Round to 2 decimals (ROUND_HALF_UP)

**Example**:
- Contributor A: 100 cost × (0.5 + 1.0) = 150 weighted
- Contributor B: 100 cost × (0.5 + 0.5) = 100 weighted
- Total weighted: 250
- Value to distribute: 1000
- Payout A: (150/250) × 1000 = 600.00
- Payout B: (100/250) × 1000 = 400.00

**Response 404**
```json
{
  "detail": "Asset not found"
}
```

**Response 422**
```json
{
  "detail": [
    {
      "loc": ["body", "value_amount"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model

```yaml
Distribution:
  asset_id: UUID
  value_amount: Decimal
  payouts: List[Payout]

DistributionCreate:
  asset_id: UUID
  value_amount: Decimal

Payout:
  contributor_id: UUID
  amount: Decimal
```

## Files to Create/Modify

- `api/app/routers/distributions.py` — Route handler (implemented)
- `api/app/services/distribution_engine.py` — Distribution algorithm (implemented)
- `api/app/models/distribution.py` — Pydantic models (implemented)
- `api/tests/test_distributions.py` — Test suite (implemented)
- `specs/distribution-engine.md` — This spec

## Acceptance Tests

See `api/tests/test_distributions.py`:
- [x] `test_distribution_weighted_by_coherence` — Verify coherence weighting
- [x] `test_distribution_asset_not_found_404` — 404 for nonexistent asset
- [x] `test_distribution_no_contributions_returns_empty_payouts` — Empty payout list when no contributions
- [x] `test_distribution_422` — 422 validation errors

All 4 tests passing.

## Out of Scope

- Payout execution (bank transfers, crypto) — distribution calculation only
- Tax handling or withholding
- Multi-currency distributions
- Historical distribution records (ephemeral calculation)
- Minimum payout thresholds
- Payout approval workflow

## Decision Gates

None — implementation already complete and tested.

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Gate failure**: CI gate blocks merge; author must fix and re-push.
- **Flaky test**: Re-run up to 2 times before marking as genuine failure.
- **Rollback behavior**: Failed deployments automatically roll back to last known-good state.
- **Infrastructure failure**: CI runner unavailable triggers alert; jobs re-queue on recovery.
- **Timeout**: CI jobs exceeding 15 minutes are killed and marked failed; safe to re-trigger.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add deployment smoke tests post-release.


## Verification

```bash
python3 -m pytest api/tests/test_distributions.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
