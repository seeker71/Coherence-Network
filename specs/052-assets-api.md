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

---

### `GET /api/assets/{asset_id}`

**Purpose**: Retrieve a specific asset by ID

**Request**
- `asset_id`: UUID (path)

**Response 200**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "type": "CODE",
  "description": "API server for Coherence Network",
  "total_cost": 350.00,
  "created_at": "2026-02-15T10:00:00Z"
}
```

**Response 404**
```json
{
  "detail": "Asset not found"
}
```

---

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
- `specs/052-assets-api.md` — This spec

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
