# Spec 073: Walkable Flow Runtime Mismatch Fixes

## Goal
Fix public walkability mismatches discovered post-deploy:
- tasks UI requires `/api/agent/tasks` but agent router is not exposed publicly
- contributors/assets web pages assumed object-wrapped responses, but API returns arrays
- contributions web page requires a list endpoint, but API only supports POST

## Requirements
### API
1. Expose agent router under `/api` so `GET /api/agent/tasks` is publicly available.
2. Add `GET /v1/contributions` to list contributions (read-only).
3. Ensure stores implement listing contributions (in-memory + postgres).

### Web
4. Update `/contributors`, `/assets` to accept array responses from `/v1/*`.
5. Update `/contributions` to use the new `GET /v1/contributions`.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Expose agent router under `/api` so `GET /api/agent/tasks` is publicly available.
  - Add `GET /v1/contributions` to list contributions (read-only).
  - Ensure stores implement listing contributions (in-memory + postgres).
  - Update `/contributors`, `/assets` to accept array responses from `/v1/*`.
  - Update `/contributions` to use the new `GET /v1/contributions`.
commands:
  - python3 -m pytest api/tests/test_runtime_drift_check.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Implementation (Allowed Files)
- `api/app/main.py`
- `api/app/routers/contributions.py`
- `api/app/adapters/graph_store.py`
- `api/app/adapters/postgres_store.py`
- `api/tests/test_contributions.py`
- `web/app/contributors/page.tsx`
- `web/app/assets/page.tsx`
- `web/app/contributions/page.tsx`
- `docs/system_audit/commit_evidence_2026-02-15_walkable-flow-runtime-mismatch-fixes.json`

## Validation
- `cd api && /opt/homebrew/bin/python3.11 -m pytest -q tests/test_contributions.py`
- `cd web && npm ci --cache ./tmp-npm-cache --no-fund --no-audit && npm run build`
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_walkable-flow-runtime-mismatch-fixes.json`

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Render error**: Show fallback error boundary with retry action.
- **API failure**: Display user-friendly error message; retry fetch on user action or after 5s.
- **Network offline**: Show offline indicator; queue actions for replay on reconnect.
- **Asset load failure**: Retry asset load up to 3 times; show placeholder on permanent failure.
- **Timeout**: API calls timeout after 10s; show loading skeleton until resolved or failed.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add end-to-end browser tests for critical paths.

## Acceptance Tests

See `api/tests/test_walkable_flow_runtime_mismatch_fixes.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_runtime_drift_check.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
