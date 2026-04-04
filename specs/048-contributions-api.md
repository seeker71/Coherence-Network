# Spec: Contributions API

## Purpose

Track contributions (time, effort, code) from contributors to assets with automatic coherence scoring. Enables fair value distribution based on contribution history. Supports manual contribution tracking and automated GitHub webhook ingestion.

## Requirements

- [x] POST /api/contributions — Create contribution with contributor_id, asset_id, cost_amount
- [x] GET /api/contributions/{id} — Retrieve contribution by ID (404 if not found)
- [x] GET /api/assets/{asset_id}/contributions — List all contributions to an asset
- [x] GET /api/contributors/{contributor_id}/contributions — List all contributions by a contributor
- [x] POST /api/contributions/github — Track contribution from GitHub webhook (auto-create contributor/asset)
- [x] Coherence score auto-calculated from metadata (has_tests, has_docs, complexity)
- [x] Contributions update asset.total_cost automatically
- [x] All endpoints return 404 when contributor or asset not found
- [x] All responses are Pydantic models (JSON-serialized)


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Track contributions (time, effort, code) from contributors to assets with automatic coherence scoring.
files_allowed:
  - api/app/routers/contributions.py
  - api/app/models/contribution.py
  - api/app/adapters/graph_store.py
  - api/tests/test_contributions.py
  - specs/048-contributions-api.md
done_when:
  - POST /api/contributions — Create contribution with contributor_id, asset_id, cost_amount
  - GET /api/contributions/{id} — Retrieve contribution by ID (404 if not found)
  - GET /api/assets/{asset_id}/contributions — List all contributions to an asset
  - GET /api/contributors/{contributor_id}/contributions — List all contributions by a contributor
  - POST /api/contributions/github — Track contribution from GitHub webhook (auto-create contributor/asset)
commands:
  - python3 -m pytest api/tests/test_contributions.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

### `POST /api/contributions`

**Purpose**: Manually record a contribution

**Request**
```json
{
  "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "660e8400-e29b-41d4-a716-446655440000",
  "cost_amount": 150.00,
  "metadata": {
    "has_tests": true,
    "has_docs": true,
    "complexity": "low"
  }
}
```

- `contributor_id`: UUID (required) — Must exist in GraphStore
- `asset_id`: UUID (required) — Must exist in GraphStore
- `cost_amount`: Decimal (required) — Cost in currency units (≥ 0)
- `metadata`: Object (optional) — Additional contribution metadata

**Response 201**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "660e8400-e29b-41d4-a716-446655440000",
  "cost_amount": 150.00,
  "coherence_score": 1.0,
  "metadata": {
    "has_tests": true,
    "has_docs": true,
    "complexity": "low"
  },
  "timestamp": "2026-02-15T10:30:00Z"
}
```

- `coherence_score`: Float (0.0–1.0) — Auto-calculated from metadata
  - Baseline: 0.5
  - +0.2 if `has_tests=true`
  - +0.2 if `has_docs=true`
  - +0.1 if `complexity="low"`
  - Capped at 1.0

**Response 404**
```json
{
  "detail": "Contributor not found"
}
```
or
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
      "loc": ["body", "cost_amount"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

---

### `GET /api/contributions/{contribution_id}`

**Purpose**: Retrieve a specific contribution by ID

**Request**
- `contribution_id`: UUID (path)

**Response 200**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "660e8400-e29b-41d4-a716-446655440000",
  "cost_amount": 150.00,
  "coherence_score": 1.0,
  "metadata": {},
  "timestamp": "2026-02-15T10:30:00Z"
}
```

**Response 404**
```json
{
  "detail": "Contribution not found"
}
```

---

### `GET /api/assets/{asset_id}/contributions`

**Purpose**: List all contributions to an asset (for rollup calculations)

**Request**
- `asset_id`: UUID (path)

**Response 200**
```json
[
  {
    "id": "770e8400-e29b-41d4-a716-446655440000",
    "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
    "asset_id": "660e8400-e29b-41d4-a716-446655440000",
    "cost_amount": 150.00,
    "coherence_score": 1.0,
    "metadata": {},
    "timestamp": "2026-02-15T10:30:00Z"
  },
  {
    "id": "880e8400-e29b-41d4-a716-446655440000",
    "contributor_id": "990e8400-e29b-41d4-a716-446655440000",
    "asset_id": "660e8400-e29b-41d4-a716-446655440000",
    "cost_amount": 200.00,
    "coherence_score": 0.8,
    "metadata": {},
    "timestamp": "2026-02-15T11:00:00Z"
  }
]
```

**Response 404**
```json
{
  "detail": "Asset not found"
}
```

---

### `GET /api/contributors/{contributor_id}/contributions`

**Purpose**: List all contributions by a contributor (for contributor analytics)

**Request**
- `contributor_id`: UUID (path)

**Response 200**
```json
[
  {
    "id": "770e8400-e29b-41d4-a716-446655440000",
    "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
    "asset_id": "660e8400-e29b-41d4-a716-446655440000",
    "cost_amount": 150.00,
    "coherence_score": 1.0,
    "metadata": {},
    "timestamp": "2026-02-15T10:30:00Z"
  }
]
```

**Response 404**
```json
{
  "detail": "Contributor not found"
}
```

---

### `POST /api/contributions/github`

**Purpose**: Track contribution from GitHub webhook (auto-creates contributor/asset if needed)

**Request**
```json
{
  "contributor_email": "alice@example.com",
  "repository": "org/repo",
  "commit_hash": "abc123def456",
  "cost_amount": 100.00,
  "metadata": {
    "files_changed": 3,
    "lines_added": 50,
    "lines_deleted": 10
  }
}
```

- `contributor_email`: String (required) — Auto-creates contributor if not found
- `repository`: String (required) — Auto-creates asset if not found
- `commit_hash`: String (required) — Stored in metadata
- `cost_amount`: Decimal (required) — Contribution value
- `metadata`: Object (optional) — GitHub commit metadata

**Response 201**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440000",
  "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "660e8400-e29b-41d4-a716-446655440000",
  "cost_amount": 100.00,
  "coherence_score": 0.8,
  "metadata": {
    "files_changed": 3,
    "lines_added": 50,
    "lines_deleted": 10,
    "commit_hash": "abc123def456",
    "repository": "org/repo",
    "contributor_email": "alice@example.com"
  },
  "timestamp": "2026-02-15T12:00:00Z"
}
```

**Coherence Calculation (GitHub)**:
- Baseline: 0.5
- +0.1 if `files_changed > 0`
- +0.2 if `lines_added > 0 && lines_added < 100` (well-scoped)
- +0.1 if `lines_added >= 100` (large changes)
- Capped at 1.0

---

### `POST /api/contributions/github/debug`

**Purpose**: Debug version of GitHub webhook (returns errors instead of raising)

**Request**: Same as `/api/contributions/github`

**Response 200** (success)
```json
{
  "success": true,
  "contribution_id": "770e8400-e29b-41d4-a716-446655440000",
  "contributor_id": "550e8400-e29b-41d4-a716-446655440000",
  "asset_id": "660e8400-e29b-41d4-a716-446655440000"
}
```

**Response 200** (error)
```json
{
  "success": false,
  "error": "Database connection failed",
  "error_type": "ConnectionError",
  "traceback": "..."
}
```


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model

```yaml
Contribution:
  id: UUID
  contributor_id: UUID (FK → Contributor)
  asset_id: UUID (FK → Asset)
  cost_amount: Decimal (≥ 0)
  coherence_score: Float (0.0–1.0)
  metadata: Object
  timestamp: DateTime (ISO 8601 UTC)

ContributionCreate:
  contributor_id: UUID
  asset_id: UUID
  cost_amount: Decimal
  metadata: Object (optional)

GitHubContribution:
  contributor_email: String
  repository: String
  commit_hash: String
  cost_amount: Decimal
  metadata: Object (optional)
```

## Files to Create/Modify

- `api/app/routers/contributions.py` — Route handlers (implemented)
- `api/app/models/contribution.py` — Pydantic models (implemented)
- `api/app/adapters/graph_store.py` — Storage methods (implemented)
- `api/tests/test_contributions.py` — Test suite (implemented)
- `specs/048-contributions-api.md` — This spec

## Acceptance Tests

See `api/tests/test_contributions.py`:
- [x] `test_create_get_contribution_and_asset_rollup_cost` — Create contribution, verify asset.total_cost updates
- [x] `test_create_contribution_404s` — 404 when contributor or asset not found
- [x] `test_get_asset_and_contributor_contributions` — List contributions by asset and contributor
- [x] `test_create_contribution_422` — 422 validation errors for invalid input

All 4 tests passing.

## Out of Scope

- OAuth GitHub authentication (uses webhook payload)
- Contribution approval workflow (contributions are immediately recorded)
- Contribution editing or deletion (immutable audit trail)
- Contribution aggregation by time period (analytics endpoint deferred)
- Advanced coherence algorithms (ML-based scoring deferred)

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
python3 -m pytest api/tests/test_contributions.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
