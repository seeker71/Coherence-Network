# Spec: [Feature Name]

## Purpose

[At least 1 sentence, ideally 2-4. Explain why this exists, who benefits, and what failure/cost it prevents.]

## Requirements

- [ ] Requirement 1 (specific and testable)
- [ ] Requirement 2 (specific and testable)
- [ ] Requirement 3 (specific and testable)

## API Contract (if applicable)

### `GET /api/resource/{id}`

**Request**
- `id`: string (path)

**Response 200**
```json
{
  "id": "string",
  "field": "value"
}
```

**Response 404**
```json
{ "detail": "Not found" }
```

If not applicable, write: `N/A - no API contract changes in this spec.`

## Data Model (if applicable)

```yaml
Resource:
  properties:
    id: { type: string }
    field: { type: string }
```

If not applicable, write: `N/A - no model changes in this spec.`

## Files to Create/Modify

- `api/app/routers/resource.py` - route handler
- `api/app/services/resource_service.py` - business logic
- `api/app/models/resource.py` - Pydantic model

## Acceptance Tests

List the exact tests (or manual flow) that prove the requirements:

- `api/tests/test_resource.py::test_get_resource_200`
- `api/tests/test_resource.py::test_get_resource_404`

## Verification

Provide executable commands used to validate this spec before phase advancement:

```bash
cd api && pytest -q tests/test_resource.py
cd web && npm run build
```

If manual validation is required, include explicit steps and expected results.

## Registry Sync (ideas only)

If this spec introduces or modifies ideas, include API-based persistence steps:

- `POST /api/ideas` for new idea records (include `potential_value`, `estimated_cost`, `resistance_risk`, `confidence`).
- `PATCH /api/ideas/{idea_id}` for updated ROI measurements (`actual_value`, `actual_cost`, `resistance_risk`, `confidence`, `manifestation_status`).
- Verify with `GET /api/ideas/{idea_id}` and ensure the idea appears in `GET /api/ideas`.

## Out of Scope

- [What this spec does not include]

## Risks and Assumptions

- [Key implementation risk and mitigation]
- [Assumption that, if false, would invalidate this spec]

## Known Gaps and Follow-up Tasks

- None at spec time.
- If a gap exists, add explicit task/issue references (example: `Follow-up task: task_spec_gap_123`).

## Decision Gates (if any)

- [Decisions that need human approval before implementation]

## Idea Traceability
- `idea_id`: `[registered-idea-id]`
- Rationale: [Why this spec advances that specific idea.]
