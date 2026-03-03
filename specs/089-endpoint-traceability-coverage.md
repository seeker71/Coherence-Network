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
