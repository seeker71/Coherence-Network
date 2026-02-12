# Spec: Sprint 3 — Import Stack

## Purpose

Per docs/PLAN.md Sprint 3: Drop package-lock.json → full risk analysis + tree. Allow users to upload a package-lock.json (or requirements.txt via spec 025), parse npm/pypi dependencies, enrich with GraphStore (project + coherence data), and return a risk analysis with dependency tree.

## Requirements

- [x] POST /api/import/stack accepts multipart file (package-lock.json)
- [x] Parse package-lock.json to extract packages (name@version) from packages (v2/v3) or dependencies (v1)
- [x] For each package: look up in GraphStore; get coherence if present; otherwise "unknown"
- [x] Return packages with coherence scores and dependencies
- [x] Aggregate risk: count unknown, low (<0.4), medium (0.4–0.7), high (≥0.7)
- [x] Uses GraphStore; no Neo4j
- [x] Real parsing (no mocks)

## API Contract

### POST /api/import/stack

**Request**

- Content-Type: multipart/form-data with field `file` (package-lock.json)
- Or: Content-Type: application/json with body `{"content": "..."}` (lockfile string)

**Response 200**

```json
{
  "packages": [
    {
      "name": "react",
      "version": "18.2.0",
      "coherence": 0.72,
      "status": "known",
      "dependencies": ["lodash@4.17.21"]
    }
  ],
  "risk_summary": {
    "unknown": 2,
    "low": 1,
    "medium": 5,
    "high": 12
  }
}
```

**Response 400** — Invalid lockfile or unsupported format

## Data Model

```yaml
ImportPackage:
  name: string
  version: string
  coherence: float | null  # null = unknown
  status: "known" | "unknown"
  dependencies: list[string]  # "name@version"
RiskSummary:
  unknown: int
  low: int    # coherence < 0.4
  medium: int  # 0.4 <= coherence < 0.7
  high: int   # coherence >= 0.7
```

## Files to Create/Modify

- `api/app/routers/import_stack.py` — POST /api/import/stack
- `api/app/services/import_stack_service.py` — parse lockfile, enrich, compute risk
- `api/app/models/import_stack.py` — Pydantic models

## Acceptance Tests

- POST /api/import/stack with valid package-lock.json returns 200 with packages and risk_summary
- POST with invalid JSON returns 400
- Packages in GraphStore get coherence; others get status "unknown"
- risk_summary counts are correct

## Out of Scope

- PyPI (requirements.txt) — future
- Graph visualization of tree
- Web UI for import (separate spec)

## See also

- [008-sprint-1-graph-foundation.md](008-sprint-1-graph-foundation.md) — GraphStore
- [020-sprint-2-coherence-api.md](020-sprint-2-coherence-api.md) — coherence endpoint

## Decision Gates

- Thresholds (0.4, 0.7) for low/medium/high are placeholders; override via config later
- python-multipart dependency added for file upload (standard FastAPI requirement)
