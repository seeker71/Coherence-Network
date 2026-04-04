---
idea_id: {parent-idea-slug}
status: active
source:
  - file: api/app/services/example_service.py
    symbols: [function_name(), ClassName]
  - file: api/app/routers/example.py
    symbols: [endpoint handlers]
requirements:
  - "Requirement 1 — concise, testable, one line"
  - "Requirement 2 — what, not how"
  - "Requirement 3 — include API paths where relevant"
done_when:
  - "Measurable check 1"
  - "Measurable check 2"
  - "all tests pass"
test: "cd api && python -m pytest tests/test_example.py -q"
constraints:
  - "Hard constraint 1"
  - "Hard constraint 2"
---

# Spec: [Feature Name]

## Purpose

[2-4 sentences. Why this exists, who benefits, what failure/cost it prevents.]

## Requirements

- [ ] **R1**: [Full requirement text with details — the frontmatter has the summary, this has the detail]
- [ ] **R2**: [Full requirement text]
- [ ] **R3**: [Full requirement text]

## Research Inputs

- `YYYY-MM-DD` - [Source name] — [why it matters]

## API Contract (if applicable)

### `GET /api/resource/{id}`

**Response 200**
```json
{
  "id": "string",
  "field": "value"
}
```

## Data Model (if applicable)

```yaml
Resource:
  id: string
  field: string
```

## Files to Create/Modify

- `api/app/routers/resource.py` — route handler
- `api/app/services/resource_service.py` — business logic
- `api/app/models/resource.py` — Pydantic model

## Acceptance Tests

- `api/tests/test_resource.py::test_get_resource_200`
- `api/tests/test_resource.py::test_get_resource_404`

## Verification

```bash
cd api && pytest -q tests/test_resource.py
```

## Out of Scope

- [What this spec does not include]

## Risks and Assumptions

- [Key risk and mitigation]
- [Assumption that would invalidate this spec if false]
