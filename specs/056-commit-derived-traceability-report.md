# Spec 056: Commit-Derived Traceability Report

## Goal
Allow the system to derive idea/spec/implementation traceability from a commit SHA without manually entering public links.

## Requirements
1. Add API endpoint `GET /api/gates/commit-traceability`.
2. Endpoint must accept `sha` and `repo` and return:
   - derived idea API references from commit evidence `idea_ids`
   - derived spec references from commit evidence `spec_ids`
   - derived implementation references from commit evidence `change_files` or commit file diff
3. Traceability derivation must read changed `docs/system_audit/commit_evidence_*.json` files in the commit.
4. Response must include machine/human access pointers and explicit unanswered items when derivation is incomplete.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Add API endpoint `GET /api/gates/commit-traceability`.
  - Endpoint must accept `sha` and `repo` and return:
  - Traceability derivation must read changed `docs/system_audit/commit_evidence_*.json` files in the commit.
  - Response must include machine/human access pointers and explicit unanswered items when derivation is incomplete.
commands:
  - python3 -m pytest api/tests/test_commit_evidence_registry_service.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Implementation
- `api/app/services/release_gate_service.py`
- `api/app/routers/gates.py`
- `api/tests/test_release_gate_service.py`
- `api/tests/test_gates.py`

## Validation
- `cd api && /opt/homebrew/bin/python3.11 -m pytest -q tests/test_release_gate_service.py tests/test_gates.py`

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

See `api/tests/test_commit_derived_traceability_report.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_commit_evidence_registry_service.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
