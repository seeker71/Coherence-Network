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