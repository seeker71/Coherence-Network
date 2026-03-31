# Spec 080: Persistent Store Test Contributor Guard

## Goal
Prevent test contributors from polluting persistent contributor data.

## Requirements
- [x] Persistent stores reject contributor creation for test emails.
- [x] Persistent stores purge previously stored test contributors at load/startup.
- [x] Any contributions linked to purged test contributors are removed.
- [x] API returns `422` when persistent store rejects a test contributor.
- [x] Existing non-persistent test flows remain unaffected.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Persistent stores reject contributor creation for test emails.
  - Persistent stores purge previously stored test contributors at load/startup.
  - Any contributions linked to purged test contributors are removed.
  - API returns `422` when persistent store rejects a test contributor.
  - Existing non-persistent test flows remain unaffected.
commands:
  - python3 -m pytest api/tests/test_contributor_hygiene.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Files To Modify (Allowed)
- `specs/080-persistent-store-test-contributor-guard.md`
- `api/app/services/contributor_hygiene.py`
- `api/app/adapters/graph_store.py`
- `api/app/adapters/postgres_store.py`
- `api/app/routers/contributors.py`
- `api/app/routers/contributions.py`
- `api/tests/test_contributor_hygiene.py`

## Validation
```bash
cd api && pytest -q tests/test_contributor_hygiene.py tests/test_contributors.py tests/test_contributions.py
```

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
- **Follow-up**: Review coverage and add missing edge-case tests.

## Acceptance Tests

See `api/tests/test_persistent_store_test_contributor_guard.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_contributor_hygiene.py -x -v
```
