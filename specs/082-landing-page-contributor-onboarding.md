# Spec 082: Landing Page Contributor Onboarding + Value Highlights

## Goal
Make the root web page inviting for new contributors while clearly explaining the core system idea and showing high-value opportunities. The page should surface top estimated-benefit ideas and recent measurable achievements so contributors can pick impact-first work quickly.

## Requirements
- [x] Landing page includes a contributor-focused hero with clear calls to action.
- [x] Landing page explains the main idea chain from idea to measured value.
- [x] Landing page shows top ideas ranked by estimated collective upside.
- [x] Landing page shows measurable recent achievements from lineage valuation data.
- [x] Landing page remains machine-friendly with links to API docs and existing web routes.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Landing page includes a contributor-focused hero with clear calls to action.
  - Landing page explains the main idea chain from idea to measured value.
  - Landing page shows top ideas ranked by estimated collective upside.
  - Landing page shows measurable recent achievements from lineage valuation data.
  - Landing page remains machine-friendly with links to API docs and existing web routes.
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Files To Modify (Allowed)
- `specs/082-landing-page-contributor-onboarding.md`
- `web/app/page.tsx`
- `docs/system_audit/commit_evidence_2026-02-16_landing-page-contributor-onboarding.json`

## Validation
```bash
cd web && npm run build
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

See `api/tests/test_landing_page_contributor_onboarding.py` for test cases covering this spec's requirements.

