# Spec 076: UI Alignment Overhaul (Search-First OSS Intelligence)

## Goal
Make the public web UI feel like a modern OSS intelligence console:
- search-first information architecture
- persistent global navigation
- clearer page hierarchy and affordances
- fewer "blank/empty" feelings in production

## Background (User Expectations)
Comparable products in the space (dependency intelligence / OSS discovery) emphasize:
- prominent search as the primary action
- clear navigation for key objects (projects, insights, governance/portfolio)
- dashboard-style summaries and next actions

## Requirements
1. Global header appears on every page:
   - brand link to `/`
   - primary nav: Search, Portfolio, Ideas, Specs, Usage, Gates
   - secondary links (still globally discoverable): Contributors, Contributions, Assets, Tasks
   - quick external link: API Docs
2. Home page becomes a search-first landing:
   - hero copy describing what the system does
   - search input that submits to `/search`
   - grid of "console" entry points (Portfolio, Ideas, Specs, Usage, Import, Friction, Gates, Contributors, Assets)
3. Visual direction:
   - non-flat background (subtle gradient/pattern)
   - typography: more intentional than system default
4. No functional regression:
   - existing routes still build and render


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Global header appears on every page:
  - Home page becomes a search-first landing:
  - Visual direction:
  - No functional regression:
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Implementation (Allowed Files)
- `specs/076-ui-alignment-overhaul.md`
- `web/app/layout.tsx`
- `web/app/globals.css`
- `web/tailwind.config.ts`
- `web/app/page.tsx`
- `web/components/site_header.tsx`
- `docs/system_audit/commit_evidence_2026-02-16_ui-alignment-overhaul.json`

## Validation
- `cd web && npm ci --cache ./tmp-npm-cache --no-fund --no-audit --prefer-offline && npm run build`
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-16_ui-alignment-overhaul.json`

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

See `api/tests/test_ui_alignment_overhaul.py` for test cases covering this spec's requirements.

