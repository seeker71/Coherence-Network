# Spec: [Feature Name]

## Purpose

[1–2 sentences: WHY this exists, what user problem it solves]

## Requirements

- [ ] Requirement 1 (specific, testable)
- [ ] Requirement 2 (specific, testable)
- [ ] Requirement 3 (specific, testable)

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

## Data Model (if applicable)

```yaml
Resource:
  properties:
    id: { type: string }
    field: { type: string }
```

## Files to Create/Modify

- `api/app/routers/resource.py` — route handler
- `api/app/services/resource_service.py` — business logic
- `api/app/models/resource.py` — Pydantic model

## Acceptance Tests

See `api/tests/test_resource.py` — all tests must pass.

## Out of Scope

- [What this does NOT include]

## Decision Gates (if any)

- [Decisions that need human approval before implementation]
