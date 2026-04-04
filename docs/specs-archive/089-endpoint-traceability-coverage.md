# Spec: Endpoint Traceability Coverage

## Purpose

Expose a machine- and human-readable audit of endpoint traceability so every API path can be checked for linkage to idea, spec, process evidence, and validation signals.

## Requirements

- [x] Add `GET /api/inventory/endpoint-traceability` that reports endpoint-level traceability.
- [x] Report summary counts for `total_endpoints`, `with_idea`, `with_spec`, `with_process`, `with_validation`, and `fully_traced`.
- [x] Report gap counts for missing traceability dimensions.
- [x] Include per-endpoint rows with path, methods, source files, and explicit gap reasons.
- [x] Derive endpoint inventory from source, not a hand-maintained list.
- [x] Add route to canonical route registry.
- [x] Add human UI access in `/gates`.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Expose a machine- and human-readable audit of endpoint traceability so every API path can be checked for linkage to idea, spec, process evidence, and validation signals.
files_allowed:
  - api/app/services/inventory_service.py
  - api/app/routers/inventory.py
  - api/app/services/route_registry_service.py
  - config/canonical_routes.json
  - api/tests/test_inventory_api.py
  - web/app/gates/page.tsx
done_when:
  - Add `GET /api/inventory/endpoint-traceability` that reports endpoint-level traceability.
  - Report summary counts for `total_endpoints`, `with_idea`, `with_spec`, `with_process`, `with_validation`, and `fully_...
  - Report gap counts for missing traceability dimensions.
  - Include per-endpoint rows with path, methods, source files, and explicit gap reasons.
  - Derive endpoint inventory from source, not a hand-maintained list.
commands:
  - python3 -m pytest api/tests/test_spec_coverage_validation.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract

### `GET /api/inventory/endpoint-traceability`

**Purpose**: Show whether each API endpoint is traced to idea, spec, process, and validation.

**Response 200**:
```json
{
  "generated_at": "2026-02-16T10:30:00Z",
  "context": {
    "idea_count": 8,
    "spec_count": 82,
    "spec_source": "local",
    "canonical_route_count": 11
  },
  "summary": {
    "total_endpoints": 57,
    "canonical_registered": 11,
    "with_idea": 19,
    "with_spec": 11,
    "with_process": 11,
    "with_validation": 11,
    "fully_traced": 9,
    "missing_idea": 38,
    "missing_spec": 46,
    "missing_process": 46,
    "missing_validation": 46
  },
  "top_gaps": [
    {
      "path": "/api/agent/tasks",
      "methods": ["GET", "POST"],
      "traceability": {
        "fully_traced": false,
        "gaps": ["idea", "spec", "process", "validation", "canonical_route"]
      }
    }
  ],
  "items": []
}
```


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model

```yaml
EndpointTraceabilityRow:
  path: string
  methods: list[string]
  source_files: list[string]
  canonical_route:
    registered: boolean
    methods: list[string]
    method_match: boolean
  idea:
    tracked: boolean
    idea_id: string|null
    idea_ids: list[string]
    source: string
  spec:
    tracked: boolean
    spec_ids: list[string]
  process:
    tracked: boolean
    evidence_count: integer
    task_ids: list[string]
  validation:
    tracked: boolean
    pass_counts:
      local: integer
      ci: integer
      deploy: integer
      e2e: integer
  traceability:
    fully_traced: boolean
    gaps: list[string]
```

## Files to Create/Modify

- `api/app/services/inventory_service.py` — endpoint discovery and traceability aggregation
- `api/app/routers/inventory.py` — new traceability endpoint
- `api/app/services/route_registry_service.py` — canonical route registration
- `config/canonical_routes.json` — canonical route registration
- `api/tests/test_inventory_api.py` — coverage and gap detection test
- `web/app/gates/page.tsx` — human inspection surface

## Acceptance Tests

See `api/tests/test_inventory_api.py`:
- [x] `test_endpoint_traceability_inventory_reports_coverage_and_gaps`

## Out of Scope

- Auto-fixing missing endpoint mappings
- Enforcing merge blocks based on traceability thresholds
- Full web UX for endpoint-level editing

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Render error**: Show fallback error boundary with retry action.
- **API failure**: Display user-friendly error message; retry fetch on user action or after 5s.
- **Network offline**: Show offline indicator; queue actions for replay on reconnect.
- **Asset load failure**: Retry asset load up to 3 times; show placeholder on permanent failure.
- **Timeout**: API calls timeout after 10s; show loading skeleton until resolved or failed.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add end-to-end browser tests for critical paths.


## Verification

```bash
python3 -m pytest api/tests/test_spec_coverage_validation.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
