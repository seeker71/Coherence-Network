# 088 — Spec-Process-Implementation-Validation Flow Visibility

## Summary

Expose a first-class machine and human view of the tracked delivery chain:

`idea -> spec -> process -> implementation -> validation -> contributors -> contributions`.

The API must aggregate existing evidence and runtime signals; the web UI must render that aggregate so humans can inspect what is tracked versus missing.

## Problem

Current endpoints expose parts of the system independently (`ideas`, `specs`, `value-lineage`, `runtime`, contributor registries), but there is no single contract that shows whether each idea has:

1. Spec tracking
2. Process tracking
3. Implementation tracking
4. Validation tracking
5. Contributor attribution
6. Contribution/value evidence

## Requirements

1. Add `GET /api/inventory/flow` under the inventory router.
2. Support optional `idea_id` filter and runtime window parameter.
3. Build flow rows per idea by joining:
   - `ideas` portfolio
   - `value_lineage` links and usage events
   - runtime summaries
   - commit evidence (`docs/system_audit/commit_evidence_*.json`)
4. Each row must include sections:
   - `spec`
   - `process`
   - `implementation`
   - `validation`
   - `contributors`
   - `contributions`
   - `chain` statuses
5. Add a human page `/flow` that renders these sections clearly.
6. Ensure navigation and page lineage include `/flow`.
7. Add automated tests for the API contract and page lineage route coverage.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Add `GET /api/inventory/flow` under the inventory router.
  - Support optional `idea_id` filter and runtime window parameter.
  - Build flow rows per idea by joining:
  - Each row must include sections:
  - Add a human page `/flow` that renders these sections clearly.
commands:
  - python3 -m pytest api/tests/test_spec_quality_gate.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Non-goals

1. Replacing existing `ideas`, `specs`, `usage`, or contributor endpoints.
2. Reworking graph-store schemas.
3. Defining payout policy changes.

## Validation

1. `cd api && pytest -q tests/test_inventory_api.py`
2. `cd web && npm run build`

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

## Acceptance Tests

See `api/tests/test_spec_process_implementation_validation_flow.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_spec_quality_gate.py -x -v
```
