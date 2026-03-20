# Spec: Runtime Telemetry DB Precedence

## Purpose

Ensure production readiness (`GET /api/ready`) does not fail due to runtime telemetry persistence being routed to a JSON file when a database is available, keeping the public deploy contract green.

## Requirements

- [ ] When a runtime database URL is configured, runtime telemetry events must be persisted to the database even if `RUNTIME_EVENTS_PATH` is set.
- [ ] `GET /api/health/persistence` must not fail the global persistence contract due to runtime telemetry being file-routed when a database is configured.
- [ ] Add a regression test proving DB precedence when both `RUNTIME_DATABASE_URL` and `RUNTIME_EVENTS_PATH` are set.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Ensure production readiness (`GET /api/ready`) does not fail due to runtime telemetry persistence being routed to a JSON file when a database is available, keeping the public deploy contract green.
files_allowed:
  - api/app/services/runtime_event_store.py
  - api/tests/test_runtime_event_store_precedence.py
  - specs/107-runtime-telemetry-db-precedence.md
  - docs/system_audit/commit_evidence_2026-02-17_runtime-telemetry-db-precedence.json
done_when:
  - When a runtime database URL is configured, runtime telemetry events must be persisted to the database even if `RUNTIM...
  - `GET /api/health/persistence` must not fail the global persistence contract due to runtime telemetry being file-route...
  - Add a regression test proving DB precedence when both `RUNTIME_DATABASE_URL` and `RUNTIME_EVENTS_PATH` are set.
commands:
  - cd api && pytest -q --ignore=tests/holdout tests/test_runtime_event_store_precedence.py
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

N/A - no API contract changes in this spec.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `api/app/services/runtime_event_store.py`
- `api/tests/test_runtime_event_store_precedence.py`
- `specs/107-runtime-telemetry-db-precedence.md`
- `docs/system_audit/commit_evidence_2026-02-17_runtime-telemetry-db-precedence.json`

## Acceptance Tests

- Manual validation: `curl -i https://coherence-network-production.up.railway.app/api/ready` returns `200` after deploy.
- `api/tests/test_runtime_event_store_precedence.py::test_runtime_db_precedence_over_events_path_when_runtime_database_url_set`

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


## Verification

```bash
cd api && pytest -q --ignore=tests/holdout tests/test_runtime_event_store_precedence.py
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-17_runtime-telemetry-db-precedence.json
```

## Out of Scope

- Changing Railway/Vercel environment variables or dashboard settings.
- Mirroring runtime telemetry to both DB and JSON file.

## Risks and Assumptions

- Risk: developer environments with `DATABASE_URL` set may start persisting runtime telemetry to the DB; mitigation is that file routing remains available when no DB URL is configured.
- Assumption: the runtime telemetry schema (`runtime_events` table) can be created in the configured DB.

## Known Gaps and Follow-up Tasks

- None at spec time.

## Decision Gates (if any)

None.

