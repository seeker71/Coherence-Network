# Spec 091: Web Live Refresh and Link Parity

## Goal

Make the web UI behave like a modern operational interface:

1. pages auto-refresh when new runtime data arrives;
2. UI reloads after web deployment version changes;
3. key entity pages are cross-linked for contributor navigation (contributors, contributions, assets, tasks, ideas, flow, gates).

## Requirements

1. Add a shared live-update controller in layout with poll-driven refresh.
2. Add a reusable live-refresh hook for client pages with API-driven data.
3. Wire live-refresh into portfolio, contributors, contributions, assets, tasks, friction, project detail, and gates pages.
4. Add filterable links across contributor/contribution/asset/task pages via query parameters.
5. Ensure all changed pages still pass production build checks.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Add a shared live-update controller in layout with poll-driven refresh.
  - Add a reusable live-refresh hook for client pages with API-driven data.
  - Wire live-refresh into portfolio, contributors, contributions, assets, tasks, friction, project detail, and gates pages.
  - Add filterable links across contributor/contribution/asset/task pages via query parameters.
  - Ensure all changed pages still pass production build checks.
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Validation

- `cd web && npm run build`
- Manual: verify live-update indicator toggles ON/OFF and pages update without manual reload.

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

See `api/tests/test_web_live_refresh_and_link_parity.py` for test cases covering this spec's requirements.

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
