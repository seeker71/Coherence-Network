# Spec: Value Lineage and Payout Attribution

## Purpose

Create a verifiable, machine-readable chain from **idea -> spec -> implementation -> usage/value signals -> payout preview** so contributors can be rewarded based on measurable system value.

## Requirements

- [ ] API supports creating and fetching a lineage link that binds idea/spec/implementation references and contributor roles.
- [ ] API supports appending usage/value events to a lineage link.
- [ ] API exposes valuation summary for a lineage link (measured value, estimated cost, ROI ratio, event count).
- [ ] API supports payout preview from valuation using explicit role weights and returns per-contributor attribution.
- [ ] All artifacts are persisted in a durable local store for auditability.
- [ ] Missing lineage id returns 404 with `{ "detail": "Lineage link not found" }`.

## API Contract

### `POST /api/value-lineage/links`

Create a lineage link.

**Request**
```json
{
  "idea_id": "oss-interface-alignment",
  "spec_id": "048-value-lineage-and-payout-attribution",
  "implementation_refs": ["PR#26", "commit:e616516"],
  "contributors": {
    "idea": "alice",
    "spec": "bob",
    "implementation": "carol",
    "review": "dave"
  },
  "estimated_cost": 120.0
}
```

**Response 201**
```json
{
  "id": "lnk_123",
  "idea_id": "oss-interface-alignment",
  "spec_id": "048-value-lineage-and-payout-attribution",
  "implementation_refs": ["PR#26", "commit:e616516"],
  "contributors": {
    "idea": "alice",
    "spec": "bob",
    "implementation": "carol",
    "review": "dave"
  },
  "estimated_cost": 120.0
}
```

### `GET /api/value-lineage/links/{lineage_id}`

Fetch lineage link.

**Response 200**
```json
{
  "id": "lnk_123",
  "idea_id": "oss-interface-alignment",
  "spec_id": "048-value-lineage-and-payout-attribution",
  "implementation_refs": ["PR#26", "commit:e616516"],
  "contributors": {
    "idea": "alice",
    "spec": "bob",
    "implementation": "carol",
    "review": "dave"
  },
  "estimated_cost": 120.0
}
```

**Response 404**
```json
{ "detail": "Lineage link not found" }
```

### `POST /api/value-lineage/links/{lineage_id}/usage-events`

Append measurable value signal to lineage link.

**Request**
```json
{
  "source": "api",
  "metric": "adoption_events",
  "value": 45.5
}
```

**Response 201**
```json
{
  "id": "evt_123",
  "lineage_id": "lnk_123",
  "source": "api",
  "metric": "adoption_events",
  "value": 45.5,
  "captured_at": "2026-02-15T00:00:00Z"
}
```

### `GET /api/value-lineage/links/{lineage_id}/valuation`

Return summarized measured value and ROI.

**Response 200**
```json
{
  "lineage_id": "lnk_123",
  "idea_id": "oss-interface-alignment",
  "spec_id": "048-value-lineage-and-payout-attribution",
  "measured_value_total": 100.0,
  "estimated_cost": 120.0,
  "roi_ratio": 0.8333,
  "event_count": 2
}
```

### `POST /api/value-lineage/links/{lineage_id}/payout-preview`

Compute payout attribution for contributors.

**Request**
```json
{
  "payout_pool": 1000.0
}
```

**Response 200**
```json
{
  "lineage_id": "lnk_123",
  "payout_pool": 1000.0,
  "measured_value_total": 100.0,
  "estimated_cost": 120.0,
  "roi_ratio": 0.8333,
  "weights": {
    "idea": 0.1,
    "spec": 0.2,
    "implementation": 0.5,
    "review": 0.2
  },
  "payouts": [
    {"role": "idea", "contributor": "alice", "amount": 100.0},
    {"role": "spec", "contributor": "bob", "amount": 200.0},
    {"role": "implementation", "contributor": "carol", "amount": 500.0},
    {"role": "review", "contributor": "dave", "amount": 200.0}
  ]
}
```

## Data Model

```yaml
LineageLink:
  id: string
  idea_id: string
  spec_id: string
  implementation_refs: string[]
  contributors:
    idea: string?
    spec: string?
    implementation: string?
    review: string?
  estimated_cost: number

UsageEvent:
  id: string
  lineage_id: string
  source: string
  metric: string
  value: number
  captured_at: datetime
```

## Validation Contract

- Tests define contract in `api/tests/test_value_lineage.py`.
- Required behaviors:
  - Create + fetch lineage link works with persistence.
  - Usage events accumulate measured value.
  - Valuation computes `roi_ratio = measured_value_total / estimated_cost` (0 when estimated_cost is 0).
  - Payout preview allocates by role weights among present contributors.
  - Missing lineage returns 404 exact detail message.

## Files to Create/Modify

- `api/app/models/value_lineage.py` — request/response models
- `api/app/services/value_lineage_service.py` — persistence + valuation + payout logic
- `api/app/routers/value_lineage.py` — API endpoints
- `api/app/main.py` — router wiring
- `api/tests/test_value_lineage.py` — contract tests

## Out of Scope

- On-chain payout execution
- Fiat/crypto settlement integration
- Dynamic weight governance beyond static defaults
