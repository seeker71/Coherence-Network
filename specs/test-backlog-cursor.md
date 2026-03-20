# Test backlog for Cursor E2E

1. Create file api/backlog_cursor_test.txt with exactly: CURSOR-BACKLOG-E2E-OK
2. Add a unit test in api/tests/test_cursor_e2e.py that asserts the file exists and contains CURSOR-BACKLOG-E2E-OK

3. docs/PLAN.md Sprint 0 — Skeleton, CI, deploy: git push → CI green; /health 200; landing live
4. docs/PLAN.md Sprint 1 — Graph: 5K+ npm packages; API returns real data; search works
5. docs/PLAN.md Sprint 2 — Coherence + UI: /project/npm/react shows score; search across npm+PyPI
6. docs/PLAN.md Sprint 3 — Import Stack: Drop package-lock.json → full risk analysis + tree
7. docs/PLAN.md Month 1 — Concept specs, indexer, top 1K npm packages, basic API
8. docs/PLAN.md Month 2 — Coherence algorithm spec, calculator agent, dashboard, PyPI indexing
9. specs/001-health-check.md — Any remaining health check items
10. specs/002-agent-orchestration-api.md — Any remaining agent API items
11. Add or improve tests for existing API endpoints per specs
12. Review and improve docs/AGENT-DEBUGGING.md and docs/MODEL-ROUTING.md

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

See `api/tests/test_backlog_cursor.py` for test cases covering this spec's requirements.

