---
idea_id: value-attribution
status: done
source:
  - file: api/app/routers/assets.py
    symbols: [create_asset(), get_asset(), list_assets()]
  - file: api/app/models/asset.py
    symbols: [Asset, AssetCreate, AssetType]
requirements:
  - "POST /api/assets — Create new asset"
  - "GET /api/assets/{id} — Retrieve asset by ID (404 if not found)"
  - "GET /api/assets — List all assets with pagination (limit parameter)"
  - "Asset types: CODE, MODEL, CONTENT, DATA"
  - "total_cost auto-updates when contributions are recorded"
  - "All responses are Pydantic models (JSON-serialized)"
  - "Assets have unique UUID identifiers"
done_when:
  - "POST /api/assets — Create new asset"
  - "GET /api/assets/{id} — Retrieve asset by ID (404 if not found)"
  - "GET /api/assets — List all assets with pagination (limit parameter)"
  - "Asset types: CODE, MODEL, CONTENT, DATA"
  - "total_cost auto-updates when contributions are recorded"
test: "python3 -m pytest api/tests/test_assets.py -x -v"
constraints:
  - "changes scoped to listed files only"
  - "no schema migrations without explicit approval"
---

> **Parent idea**: [value-attribution](../ideas/value-attribution.md)
> **Source**: [`api/app/routers/assets.py`](../api/app/routers/assets.py) | [`api/app/models/asset.py`](../api/app/models/asset.py)

# Spec: Assets API

## Purpose

Manage assets (code, models, content, data) that receive contributions. Assets accumulate total_cost as contributions are recorded. Core entity in the value distribution system.

## Requirements

- [x] POST /api/assets — Create new asset
- [x] GET /api/assets/{id} — Retrieve asset by ID (404 if not found)
- [x] GET /api/assets — List all assets with pagination (limit parameter)
- [x] Asset types: CODE, MODEL, CONTENT, DATA
- [x] total_cost auto-updates when contributions are recorded
- [x] All responses are Pydantic models (JSON-serialized)
- [x] Assets have unique UUID identifiers


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Manage assets (code, models, content, data) that receive contributions.
files_allowed:
  - api/app/routers/assets.py
  - api/app/models/asset.py
  - api/app/adapters/graph_store.py
  - api/tests/test_assets.py
  - specs/assets-api.md
done_when:
  - POST /api/assets — Create new asset
  - GET /api/assets/{id} — Retrieve asset by ID (404 if not found)
  - GET /api/assets — List all assets with pagination (limit parameter)
  - Asset types: CODE, MODEL, CONTENT, DATA
  - total_cost auto-updates when contributions are recorded
commands:
  - python3 -m pytest api/tests/test_assets.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

### `POST /api/assets`

**Purpose**: Create a new asset

**Request**
```json
{
  "type": "CODE",
  "description": "API server for Coherence Network"
}
```

- `type`: String enum (required) — One of: CODE, MODEL, CONTENT, DATA
- `description`: String (required) — Asset description

**Response 201**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "type": "CODE",
  "description": "API server for Coherence Network",
  "total_cost": 0.00,
  "created_at": "2026-02-15T10:00:00Z"
}
```

- `id`: UUID — Auto-generated unique identifier
- `total_cost`: Decimal — Initialized to 0.00, updated as contributions recorded
- `created_at`: DateTime — ISO 8601 UTC timestamp

**Response 422**
```json
{
  "detail": [
    {
      "loc": ["body", "type"],
      "msg": "Input should be 'CODE', 'MODEL', 'CONTENT' or 'DATA'",
      "type": "enum"
    }
  ]
}
```

### `GET /api/assets`

**Purpose**: List all assets with pagination

**Request**
- `limit`: Integer (query, optional, default: 100) — Max assets to return

**Response 200**
```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440000",
    "type": "CODE",
    "description": "API server for Coherence Network",
    "total_cost": 350.00,
    "created_at": "2026-02-15T10:00:00Z"
  },
  {
    "id": "770e8400-e29b-41d4-a716-446655440000",
    "type": "MODEL",
    "description": "Coherence scoring model",
    "total_cost": 500.00,
    "created_at": "2026-02-15T11:00:00Z"
  }
]
```

Results sorted by `created_at` descending (newest first).


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model

```yaml
AssetType: enum
  - CODE      # Source code, applications
  - MODEL     # ML models, algorithms
  - CONTENT   # Documentation, designs
  - DATA      # Datasets, training data

Asset:
  id: UUID
  type: AssetType
  description: String
  total_cost: Decimal (≥ 0.00, updated by contributions)
  created_at: DateTime (ISO 8601 UTC)

AssetCreate:
  type: AssetType
  description: String
```

## Files to Create/Modify

- `api/app/routers/assets.py` — Route handlers (implemented)
- `api/app/models/asset.py` — Pydantic models (implemented)
- `api/app/adapters/graph_store.py` — Storage methods (implemented)
- `api/tests/test_assets.py` — Test suite (implemented)
- `specs/assets-api.md` — This spec

## Acceptance Tests

See `api/tests/test_assets.py`:
- [x] `test_create_get_list_assets` — Create asset, retrieve by ID, list all
- [x] `test_get_asset_404` — 404 when asset not found
- [x] `test_create_asset_422` — 422 validation errors for invalid type

All 3 tests passing.

## Out of Scope

- Asset editing or deletion (immutable once created)
- Asset versioning (single version per asset)
- Asset ownership or permissions (open system)
- Asset search or filtering (simple list only)
- Asset archival or soft delete

## Decision Gates

None — implementation already complete and tested.

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Resource not found**: Return 404 with descriptive message.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Concurrent modification**: Last write wins; no optimistic locking required for MVP.
- **Timeout**: Operations exceeding 30s return 504; safe to retry.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add integration tests for error edge cases.


## Verification

```bash
python3 -m pytest api/tests/test_assets.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
