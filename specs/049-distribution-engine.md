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
- `specs/049-distribution-engine.md` — This spec

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
