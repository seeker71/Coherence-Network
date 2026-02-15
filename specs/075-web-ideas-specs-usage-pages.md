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
