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
