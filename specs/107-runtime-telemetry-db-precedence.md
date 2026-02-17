# Spec: Runtime Telemetry DB Precedence

## Purpose

Ensure production readiness (`GET /api/ready`) does not fail due to runtime telemetry persistence being routed to a JSON file when a database is available, keeping the public deploy contract green.

## Requirements

- [ ] When a runtime database URL is configured, runtime telemetry events must be persisted to the database even if `RUNTIME_EVENTS_PATH` is set.
- [ ] `GET /api/health/persistence` must not fail the global persistence contract due to runtime telemetry being file-routed when a database is configured.
- [ ] Add a regression test proving DB precedence when both `RUNTIME_DATABASE_URL` and `RUNTIME_EVENTS_PATH` are set.

## API Contract (if applicable)

N/A - no API contract changes in this spec.

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

