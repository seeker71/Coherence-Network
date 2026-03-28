# Spec: Consolidate `/automation`, `/usage`, `/remote-ops` into `/nodes` and `/pipeline`

## Summary

Four web surfaces today expose overlapping operational data: **`/automation`** (provider readiness, usage tables, alerts, federation node stats, fleet capabilities), **`/usage`** (provider usage, daily summary, runtime cost, friction, quality), **`/remote-ops`** (deploy contract, pipeline status, queue, controls), and **`/nodes`** (federation list, messaging, health-adjacent context). **`/pipeline`** already covers task execution health (streaks, provider performance, activity). Operators must learn multiple URLs for one mental model (“where is the network?” vs “where is work flowing?”).

This spec defines a **two-page operational model**:

1. **`/nodes`** — **Everything about the physical/logical network**: federation roster, last-seen health, provider attachments per node, inter-node messaging, remote control actions, fleet capabilities, and **provider adapter readiness** that is fundamentally “what can this node run?” (content currently split across automation + nodes).
2. **`/pipeline`** — **Everything about task execution**: queues (pending/running), completed/failed streaks, provider performance, automation usage signals that measure **throughput and cost of work** (daily summaries, execution stats), and **remote ops controls** that affect deploy/queue behavior (content from usage + remote-ops + parts of automation).

**Remove** standalone routes **`/automation`**, **`/usage`**, and **`/remote-ops`**. Replace them with **HTTP redirects** (permanent where safe) to the correct consolidated page and optional **hash or query anchors** for deep links (e.g. `/pipeline#usage`, `/nodes#providers`) so bookmarks and docs keep working.

**Related pages (out of scope for removal but must update links):** `/tasks`, `/flow`, `/gates`, `/agent`, `/dashboard`, `/today`, `/portfolio`, `/import`, `/search`, `/api-health`, `/friction`, `/blog`, and `web/components/site_header.tsx` secondary nav. **`/runtime`** already redirects to `/usage`; after consolidation it must redirect to **`/pipeline`** (or `/nodes` if that becomes the only runtime-cost surface — default **`/pipeline`** for execution-cost alignment).

### Open question: Improving the idea, proving it works, and making proof clearer over time

| Mechanism | Purpose |
|-----------|---------|
| **Versioned verification** | This spec’s Verification Scenarios are re-run on each release; add a short `spec_version` field in `docs/SPEC-TRACKING.md` or the spec frontmatter when behavior changes. |
| **Playwright / Vitest route tests** | Assert redirect status codes (308/307), `Location` headers or final URL for `/automation` → `/nodes` or `/pipeline` per matrix below, and that primary nav contains no removed labels. |
| **Integration test manifest** | Update `web/tests/integration/page-data-source.test.ts` to drop `/usage` and `/automation` as primary audited routes and add `/nodes` + `/pipeline` sections covering merged API hints. |
| **Page-level “data freshness” strip** | On `/nodes` and `/pipeline`, show **last successful fetch time** and **API base** (already common patterns) so operators see staleness without guessing. |
| **Canonical machine paths** | Extend `web/components/page_context_links.tsx` so `/nodes` and `/pipeline` list the **union** of machine paths previously split across removed pages (traceability for reviewers). |
| **Heartbeat to product** | Optional: one JSON summary endpoint or static `inventory` row listing “consolidated_routes” for external monitors — **follow-up** if not already covered by `/api/inventory/page-lineage`. |

---

## Purpose

Reduce navigation entropy and duplicate mental models for operators and contributors. A single **Nodes** page answers “who is on the network and what can they do?” A single **Pipeline** page answers “what work is moving, how healthy is execution, and what are we spending?” This prevents split-brain troubleshooting (checking automation vs usage vs remote-ops for the same incident).

---

## Requirements

### Functional

- [ ] **R1 — Redirects:** Requests to **`GET /automation`**, **`GET /usage`**, and **`GET /remote-ops`** (and paginated variants e.g. `/usage?page=2`) respond with **3xx redirect** to **`/nodes`** or **`/pipeline`** per the mapping in **Redirect mapping** below. Sub-routes, if any, follow the same rule (e.g. query strings preserved).
- [ ] **R2 — Content merge:** All user-visible capabilities of the three removed pages are reachable from **`/nodes`** and/or **`/pipeline`** without requiring the old URLs (except via redirect). No loss of **API-backed sections** unless explicitly deferred in **Known Gaps**.
- [ ] **R3 — Navigation:** **Site header** (`web/components/site_header.tsx`) **must not** list `/automation`, `/usage`, or `/remote-ops`. **Primary** nav continues to highlight **`/pipeline`** and **`/nodes`** (already present). **Secondary (“More”)** menu drops entries that pointed at removed routes; cross-links inside pages point to `/nodes` or `/pipeline`.
- [ ] **R4 — Deep links:** Document and implement **in-page anchors** or **query params** for major sections (e.g. provider table, daily summary, remote controls) so external docs can link precisely.
- [ ] **R5 — Client behavior:** `web/components/live_updates_controller.tsx` and any `ROUTER_REFRESH_*` rules that reference `/automation` or `/remote-ops` are updated to the new paths.
- [ ] **R6 — `/runtime`:** Update redirect target from `/usage` to **`/pipeline`** (or documented alternative).

### Non-functional

- [ ] **N1 — SEO/bookmarks:** Redirects use **308 Permanent Redirect** for GET where Next.js `redirect` permanent option applies, so browsers and search consolidate to two canonical ops URLs.
- [ ] **N2 — Accessibility:** Merged pages preserve heading hierarchy and `aria` labels; no duplicate `h1` on merged sections.
- [ ] **N3 — Performance:** No duplicate fetching of the same API payload across tabs on one page without shared SWR/cache — implementation may refactor loaders into `web/lib/` hooks.

---

## Redirect mapping (normative)

| Old path | New canonical path | Rationale |
|----------|-------------------|-----------|
| `/automation` | `/nodes` | Provider readiness, fleet caps, federation stats are **node-centric**; merge any execution-wide summary blocks into `/pipeline` if they are purely about **task volume** (see implementation notes). |
| `/usage` | `/pipeline` | Daily summary, provider usage, runtime cost, friction tie to **execution and spend**. |
| `/remote-ops` | `/pipeline` | Queue + deploy/controls are **pipeline operations**. |

**Implementation note:** If a section on `/automation` is clearly **execution metrics** (e.g. aggregate task counts not tied to a node row), place it on **`/pipeline`** and redirect `/automation` with **`/pipeline#…`** for that subsection only when splitting is needed; default single redirect `/automation` → `/nodes` per table.

---

## API changes

**Backend REST contracts remain stable unless this spec explicitly adds observability.**

The web app **continues to call** these existing endpoints (non-exhaustive; implementation must preserve coverage):

### Automation / usage (pipeline + cost)

- `GET /api/automation/usage` (+ `compact`, `force_refresh`)
- `GET /api/automation/usage/alerts`
- `GET /api/automation/usage/snapshots`
- `GET /api/automation/usage/readiness`
- `GET /api/automation/usage/provider-validation` (+ `run`)
- `GET /api/automation/usage/daily-summary`

### Federation / nodes

- `GET /api/federation/nodes`
- `GET /api/federation/nodes/stats`
- `GET /api/federation/nodes/capabilities`
- `GET /api/federation/nodes/{node_id}/messages`

### Agent / pipeline

- `GET /api/agent/pipeline-status`
- `GET /api/agent/tasks` (+ filters)
- `GET /api/agent/effectiveness`
- `GET /api/providers/stats` (if still used by merged UI)

### Gates / deploy (remote-ops)

- `GET /api/gates/public-deploy-contract`
- `GET /api/health`

**No new API routes are required** for MVP consolidation; **optional** follow-up: `GET /api/inventory/consolidated-routes` for monitoring (see Known Gaps).

---

## Data model

**N/A** — No PostgreSQL/Neo4j schema changes. UI composition only.

---

## Web surface (exact pages)

| Page | Path | After change |
|------|------|--------------|
| Nodes hub | `/nodes` | Expanded: federation + providers + messages + controls that are node-scoped + automation “readiness” panels that describe **capabilities**. |
| Pipeline hub | `/pipeline` | Expanded: queues, streaks, provider performance + **usage/daily summary** + **remote-ops** queue/deploy UI. |
| Removed | `/automation`, `/usage`, `/remote-ops` | **301/308 redirects** only (or Next.js `redirect()` in `page.tsx` / `next.config.js`). |

---

## Files to create / modify (implementation phase)

Exact list for implementers (may adjust with spec amendment):

- `web/app/automation/page.tsx` → replace body with `redirect("/nodes")` or `next.config` redirect
- `web/app/usage/page.tsx` → `redirect("/pipeline")` (+ move components under `web/app/pipeline/sections/` or `web/app/nodes/sections/`)
- `web/app/remote-ops/page.tsx` → `redirect("/pipeline")` (+ relocate components)
- `web/app/nodes/page.tsx` — merge sections from automation where node-centric
- `web/app/pipeline/page.tsx` — merge sections from usage + remote-ops
- `web/components/site_header.tsx` — remove secondary links to removed routes
- `web/components/page_context_links.tsx` — new contexts for `/nodes`, `/pipeline`; remove or alias old keys
- `web/components/live_updates_controller.tsx` — path prefixes
- `web/app/runtime/page.tsx` — redirect target
- Cross-links: `web/app/flow/page.tsx`, `web/app/dashboard/page.tsx`, `web/app/gates/page.tsx`, `web/app/agent/page.tsx`, `web/components/today/TodayTopIdeaQuickLaunch.tsx`, `web/app/blog/page.tsx`, etc.
- Tests: `web/tests/integration/page-data-source.test.ts`, new Playwright/Vitest tests for redirects
- Docs: `docs/SPEC-TRACKING.md` or `docs/STATUS.md` — one-line entry when shipped

---

## Acceptance criteria

1. Hitting old routes in production always lands on `/nodes` or `/pipeline` with **no 404** and **no blank page**.
2. Operators can complete **both** workflows without the old URLs: (a) inspect federation + messaging + provider readiness, (b) inspect queue + usage + deploy controls.
3. Global nav and “More” menu contain **at most** the two consolidated ops entry points for this scope (plus unrelated pages like `/tasks`).
4. CI passes: `cd web && npm run build` and web tests that cover redirects and merged data bindings.

---

## Verification Scenarios

Each scenario is executable against **production** `https://coherencycoin.com` (or staging) with `curl` and a browser.

### Scenario 1 — Permanent redirect for `/usage` to `/pipeline`

- **Setup:** None (public GET).
- **Action:**  
  `curl -sI "https://coherencycoin.com/usage"`  
  (or local: `curl -sI "http://localhost:3000/usage"` during dev).
- **Expected:** HTTP **308** or **307** with `location:` header whose path is **`/pipeline`** (query string preserved if present: test `curl -sI "https://coherencycoin.com/usage?page=2&page_size=20"` → `Location` contains `page=2`).
- **Edge:** Invalid query still redirects to `/pipeline` (200 on destination); destination page handles empty data without 500.

### Scenario 2 — Redirect `/automation` to `/nodes`

- **Setup:** None.
- **Action:** `curl -sI "https://coherencycoin.com/automation"`
- **Expected:** HTTP **308** or **307**; `Location` path **`/nodes`** (or `/nodes#providers` if spec’d).
- **Edge:** Browser bookmark to `/automation` opens `/nodes`; no React error boundary flash in console (manual check).

### Scenario 3 — Redirect `/remote-ops` to `/pipeline`

- **Setup:** None.
- **Action:** `curl -sI "https://coherencycoin.com/remote-ops"`
- **Expected:** `Location` path **`/pipeline`**.
- **Edge:** WebSocket or client-only features on old page re-tested on `/pipeline`; no duplicate polling (network tab shows single subscription per resource).

### Scenario 4 — Full read cycle: pipeline page loads execution APIs (create-read for “view state”)

- **Setup:** API healthy (`GET /api/health` returns 200).
- **Action:**  
  1. `curl -sS "https://api.coherencycoin.com/api/agent/pipeline-status" | head -c 500`  
  2. Open `https://coherencycoin.com/pipeline` in browser; confirm visible sections include **task summary** and **provider performance** (or merged usage block).
- **Expected:** JSON from (1) is valid; page (2) shows non-error content and **data-placeholder** only when API empty, not on API failure (should show error state, not 500 from Next).
- **Edge:** When `pipeline-status` returns empty object, UI shows explicit “no data” — not infinite loading.

### Scenario 5 — Error handling: missing federation node message target

- **Setup:** Use API `GET /api/federation/nodes` to pick a **nonexistent** node id.
- **Action:** `curl -sS -o /dev/null -w "%{http_code}" "https://api.coherencycoin.com/api/federation/nodes/does-not-exist-000/messages"`
- **Expected:** HTTP **404** or documented empty list — **not** **500**.
- **Edge:** UI on `/nodes` when sending message to invalid selection shows validation error (client-side) before POST.

---

## Task card (for implementation issue)

```yaml
goal: Consolidate /automation, /usage, /remote-ops into /nodes and /pipeline with redirects and merged UI.
files_allowed:
  - web/app/automation/page.tsx
  - web/app/usage/page.tsx
  - web/app/remote-ops/page.tsx
  - web/app/nodes/page.tsx
  - web/app/pipeline/page.tsx
  - web/components/site_header.tsx
  - web/components/page_context_links.tsx
  - web/components/live_updates_controller.tsx
  - web/app/runtime/page.tsx
  - web/tests/integration/page-data-source.test.ts
done_when:
  - curl -sI https://coherencycoin.com/automation | grep -i location | grep -q nodes
  - curl -sI https://coherencycoin.com/usage | grep -i location | grep -q pipeline
  - cd web && npm run build
commands:
  - cd web && npm run build
  - cd web && npx vitest run tests/integration/page-data-source.test.ts
constraints:
  - Do not remove or weaken API endpoints used by merged pages.
  - Do not modify api/tests to force pass; fix implementation if tests are contract tests.
```

---

## Research inputs

- `2025+` — Internal: `web/app/automation/page.tsx`, `web/app/usage/page.tsx`, `web/app/remote-ops/page.tsx`, `web/app/pipeline/page.tsx`, `web/app/nodes/page.tsx` — current data sources.
- `2025+` — `docs/UX Guidance` (AGENTS.md) — progressive disclosure, consistent nav.

---

## Risks and assumptions

- **Risk:** Merged pages become too long → **Mitigation:** tabs or collapsible sections with the same URL + hash anchors.
- **Assumption:** All three old pages are **Next.js app routes** without server middleware that blocks `redirect()` — if middleware intercepts, add explicit redirect rules to `next.config.mjs`.
- **Risk:** External blog/docs link to absolute `/automation` — **Mitigation:** permanent redirects preserve SEO.

---

## Known gaps and follow-up tasks

- **`/agent` page** overlaps pipeline/agent usage; consider folding into `/pipeline` in a later spec — **not** required here.
- **CLI:** If `cc` subcommands reference old paths, update CLI help in a follow-up (not in this spec’s file list).
- **DIF / instrumentation:** Add automated redirect matrix test in CI (list of path → expected Location).

---

## Failure / retry reflection

- **Failure mode:** Partial merge — redirects ship but content missing on `/nodes` or `/pipeline`.
- **Blind spot:** Assuming API errors are rare; merged pages need unified error boundaries.
- **Next action:** Ship redirects first behind feature flag **or** in one PR with section parity checklist.

---

## Out of scope

- Changing provider routing rules, executor policy, or `api/config/model_routing.json`.
- Removing `/tasks` (work cards remain distinct from pipeline **overview**).
- Mobile app or non-web clients beyond redirect behavior.
