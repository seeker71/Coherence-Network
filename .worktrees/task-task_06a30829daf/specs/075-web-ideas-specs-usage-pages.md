# Spec 075: Web Pages For Ideas, Specs, Usage (Human Parity)

## Goal
On `https://coherence-network.vercel.app/`, provide human-browsable pages for:
- ideas
- specs
- usage (runtime + friction)

Also ensure web pages that fetch the API work in production even when `NEXT_PUBLIC_API_URL` is not configured.

## Requirements
### Navigation
1. Home page must link to:
   - `/portfolio`
   - `/ideas`
   - `/specs`
   - `/usage`

### API Base Default
2. Client pages must default API base to production Railway when `NEXT_PUBLIC_API_URL` is unset.
   - Production default: `https://coherence-network-production.up.railway.app`
   - Dev default: `http://localhost:8000`

### New Pages
3. `/ideas` lists ideas from `GET /api/ideas`.
4. `/ideas/[idea_id]` shows idea details, open questions, and links to relevant APIs.
5. `/specs` lists specs from `GET /api/inventory/system-lineage` (`specs.items`).
6. `/usage` shows:
   - runtime summary by idea from `GET /api/runtime/ideas/summary`
   - friction report from `GET /api/friction/report`


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Home page must link to:
  - Client pages must default API base to production Railway when `NEXT_PUBLIC_API_URL` is unset.
  - `/ideas` lists ideas from `GET /api/ideas`.
  - `/ideas/[idea_id]` shows idea details, open questions, and links to relevant APIs.
  - `/specs` lists specs from `GET /api/inventory/system-lineage` (`specs.items`).
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Non-Goals
- Full editing UI (create/update ideas) in web.
- Complex visualizations.

## Implementation (Allowed Files)
- `specs/075-web-ideas-specs-usage-pages.md`
- `web/lib/api.ts`
- `web/app/page.tsx`
- `web/app/portfolio/page.tsx`
- `web/app/contributors/page.tsx`
- `web/app/assets/page.tsx`
- `web/app/contributions/page.tsx`
- `web/app/tasks/page.tsx`
- `web/app/import/page.tsx`
- `web/app/search/page.tsx`
- `web/app/project/[ecosystem]/[name]/page.tsx`
- `web/app/friction/page.tsx`
- `web/app/gates/page.tsx`
- `web/app/api-health/page.tsx`
- `web/app/api/health-proxy/route.ts`
- `web/app/api/runtime-beacon/route.ts`
- `web/app/ideas/page.tsx`
- `web/app/ideas/[idea_id]/page.tsx`
- `web/app/specs/page.tsx`
- `web/app/usage/page.tsx`
- `docs/system_audit/commit_evidence_2026-02-15_web-ideas-specs-usage-pages.json`

## Validation
- `cd web && npm ci --cache ./tmp-npm-cache --no-fund --no-audit && npm run build`
- `python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-15_web-ideas-specs-usage-pages.json`

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

See `api/tests/test_web_ideas_specs_usage_pages.py` for test cases covering this spec's requirements.

