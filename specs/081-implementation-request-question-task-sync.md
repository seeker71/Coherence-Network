# Spec 081: Implementation Request Questions -> Task Sync

## Goal
Ensure implementation-request questions are never dropped by converting them into explicit `impl` tasks as soon as they are discovered. The sync must deduplicate by question fingerprint so repeated runs do not flood the task queue.

## Requirements
- [x] Add `POST /api/inventory/questions/sync-implementation-tasks` to scan inventory questions and create tasks for implementation-request questions.
- [x] Mark synced tasks with machine-readable context (`source=implementation_request_question`, fingerprint, idea id, ROI fields).
- [x] Deduplicate creation so rerunning sync does not create duplicate tasks for the same idea/question pair.
- [x] Run this sync before `POST /api/inventory/questions/next-highest-roi-task` returns a suggestion.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Add `POST /api/inventory/questions/sync-implementation-tasks` to scan inventory questions and create tasks for implem...
  - Mark synced tasks with machine-readable context (`source=implementation_request_question`, fingerprint, idea id, ROI ...
  - Deduplicate creation so rerunning sync does not create duplicate tasks for the same idea/question pair.
  - Run this sync before `POST /api/inventory/questions/next-highest-roi-task` returns a suggestion.
commands:
  - python3 -m pytest api/tests/test_agent_task_persistence.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Files To Modify (Allowed)
- `specs/081-implementation-request-question-task-sync.md`
- `api/app/routers/inventory.py`
- `api/app/services/inventory_service.py`
- `api/tests/test_inventory_api.py`

## Validation
```bash
cd api && pytest -q tests/test_inventory_api.py
```

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

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

See `api/tests/test_implementation_request_question_task_sync.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_agent_task_persistence.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
