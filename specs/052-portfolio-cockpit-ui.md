# Spec: Portfolio Cockpit UI

## Purpose

Provide a human interface to prioritize unanswered questions by ROI, submit answers directly, and view runtime cost by idea.

## Requirements

- [ ] Web page `/portfolio` exists and is linked from home.
- [ ] Page fetches `GET /api/inventory/system-lineage` and displays question + runtime sections.
- [ ] Page allows answering unanswered questions via `POST /api/ideas/{idea_id}/questions/answer`.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Provide a human interface to prioritize unanswered questions by ROI, submit answers directly, and view runtime cost by idea.
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Web page `/portfolio` exists and is linked from home.
  - Page fetches `GET /api/inventory/system-lineage` and displays question + runtime sections.
  - Page allows answering unanswered questions via `POST /api/ideas/{idea_id}/questions/answer`.
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Validation Contract

- `web` build succeeds with the new route.
- Manual check: `/portfolio` renders and answer action posts successfully.

## Files

- `web/app/portfolio/page.tsx`
- `web/app/page.tsx`

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

See `api/tests/test_portfolio_cockpit_ui.py` for test cases covering this spec's requirements.

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
