# Project Manager Backlog

One work item per line. Orchestrator processes in order. Prefix with spec filename when a spec exists.

1. specs/005-project-manager-pipeline.md — Implement the project manager orchestrator
2. docs/PLAN.md Sprint 0 — Graph foundation, indexer, basic API skeleton
3. specs/004-ci-pipeline.md — Complete CI pipeline per spec
4. specs/003-agent-telegram-decision-loop.md — Complete Telegram decision flow
5. docs/PLAN.md Sprint 1 — 5K+ npm packages, API returns real data, search works

6. docs/PLAN.md Sprint 0 — Skeleton, CI, deploy: git push → CI green; /health 200; landing live
7. docs/PLAN.md Sprint 1 — Graph: 5K+ npm packages; API returns real data; search works
8. docs/PLAN.md Sprint 2 — Coherence + UI: /project/npm/react shows score; search across npm+PyPI
9. docs/PLAN.md Sprint 3 — Import Stack: Drop package-lock.json → full risk analysis + tree
10. docs/PLAN.md Month 1 — Concept specs, indexer, top 1K npm packages, basic API
11. docs/PLAN.md Month 2 — Coherence algorithm spec, calculator agent, dashboard, PyPI indexing
12. specs/001-health-check.md — Any remaining health check items
13. specs/002-agent-orchestration-api.md — Any remaining agent API items
14. Add or improve tests for existing API endpoints per specs
15. Review and improve docs/AGENT-DEBUGGING.md and docs/MODEL-ROUTING.md
16. specs/007-meta-pipeline-backlog.md items 13-18 — Execute measured production improvements from docs/system_audit/pipeline_improvement_snapshot_2026-02-19.json


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 001, 002, 003, 004, 007

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - All requirements implemented and tests pass
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

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

See `api/tests/test_backlog.py` for test cases covering this spec's requirements.

