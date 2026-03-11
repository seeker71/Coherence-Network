# Spec: [Feature Name]

## Purpose

[At least 1 sentence, ideally 2-4. Explain why this exists, who benefits, and what failure/cost it prevents.]

## Requirements

- [ ] Requirement 1 (specific and testable)
- [ ] Requirement 2 (specific and testable)
- [ ] Requirement 3 (specific and testable)

## Intake: DiSSS (Required for new specs)

### Deconstruction

Break the idea into atomic sub-claims. Each sub-claim should be independently testable and deliverable.

- Sub-claim 1: [concrete statement] — value: [X], cost: [Y], confidence: [0.0–1.0]
- Sub-claim 2: [concrete statement] — value: [X], cost: [Y], confidence: [0.0–1.0]

### Selection

Which sub-claims cover ≥80% of the total value? List only the selected sub-claims and justify why the others are deferred.

- Selected: [sub-claim refs]
- Deferred: [sub-claim refs] — reason: [why]

### Sequencing

Declare ordering constraints for the selected sub-claims.

- `depends_on`: [spec IDs or capability names that must exist first]
- `unblocks`: [spec IDs or capabilities this enables]

### Stakes

What is lost if this isn't done soon? Create accountability.

- `value_decay_days`: [N] — opportunity cost doubles after N days
- `committed_by`: [ISO 8601 date]
- `owner`: [who is accountable]

## Research Inputs (Required)

List the primary sources that informed this spec (docs/changelog/paper/security advisory).
Include publication date and URL for each source.

- `YYYY-MM-DD` - [Source name](https://example.com) - [why it matters for this change]

## Task Card (Required)

```yaml
goal: one sentence goal
files_allowed:
  - exact/path/file.py
done_when:
  - measurable check 1
commands:
  - exact command 1
constraints:
  - hard constraint 1
```

If task card scope is intentionally open-ended, explicitly justify why and list review owner.

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

## Out of Scope

- [What this spec does not include]

## Risks and Assumptions

- [Key implementation risk and mitigation]
- [Assumption that, if false, would invalidate this spec]

## Known Gaps and Follow-up Tasks

- None at spec time.
- If a gap exists, add explicit task/issue references (example: `Follow-up task: task_spec_gap_123`).

## Failure/Retry Reflection

For expected failure modes, document the likely blind spot and next-action guidance.

- Failure mode: [example timeout]
- Blind spot: [what was underestimated]
- Next action: [smallest corrective step]

## Decision Gates (if any)

- [Decisions that need human approval before implementation]
