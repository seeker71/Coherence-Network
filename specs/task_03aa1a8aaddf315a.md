# Spec: Consolidate /automation, /usage, /remote-ops into /nodes and /pipeline

**Task ID**: task_03aa1a8aaddf315a
**Type**: UX / Frontend
**Status**: Approved
**Date**: 2026-03-29

---

## Summary

Four pages currently expose overlapping data in ways that confuse navigation and fragment the user's mental model:

| Page | What it shows |
|------|--------------|
| `/automation` | Provider stats, automation readiness, node stats, task counts (GardenMap) |
| `/usage` | Provider usage, daily summary, friction, runtime cost, view performance |
| `/remote-ops` | Queue controls, task dispatch, deployment uptime, execute token |
| `/nodes` | Federation node list, health, streak, providers, messaging |
| `/pipeline` | Live task dashboard — active tasks, nodes summary, provider health, activity stream |

The problem: a user wanting to "check on the nodes" must visit `/nodes` *and* `/automation` *and* `/pipeline`. A user wanting to "manage tasks" visits `/remote-ops` *and* `/pipeline`. The mental model is broken.

**Goal**: Consolidate into exactly two destination pages with clear ownership:

1. **`/nodes`** — Everything about *nodes*: the federation list, health, providers per node, system metrics, remote messaging, and the controls to dispatch tasks to specific nodes.
2. **`/pipeline`** — Everything about *task execution*: the live queue, running tasks, completed/failed counts, activity stream, provider performance, streaks, friction.

Remove `/automation`, `/usage`, and `/remote-ops` by redirecting them to the appropriate destination page. Remove these pages from the navigation. Result: simpler nav, clearer ownership, zero data loss.

---

## Motivation

### Current overlap (evidence from code)

- `/automation/page.tsx` fetches: `api/automation/usage`, `api/automation/usage/alerts`, `api/automation/usage/readiness`, **`api/providers/stats`**, **`api/federation/nodes/stats`**, **`api/federation/nodes`**.
  → Overlaps with `/nodes` (federation nodes) and `/pipeline` (provider stats).

- `/usage/page.tsx` fetches: runtime slice, daily summary, **`api/providers/stats`**, view performance.
  → Provider stats also in `/automation` and `/pipeline`. Daily summary (friction, host runner) is operational — belongs on `/pipeline`.

- `/remote-ops/page.tsx` shows: deployment/uptime, execute token form, queue/pipeline section (pending tasks, active count).
  → Queue/pipeline directly duplicates `/pipeline`. Dispatch controls belong on `/nodes` (dispatch *to a node*) or `/pipeline` (dispatch *a task type*).

- `/pipeline/page.tsx` shows: nodes summary, active tasks, provider health, activity stream.
  → Nodes summary duplicates `/nodes`. Provider health duplicates `/automation` and `/usage`.

### Navigation after consolidation

**Before (5 nav entries for operational data)**:
```
/nodes  /pipeline  /automation  /usage  /remote-ops
```

**After (2 nav entries)**:
```
/nodes  /pipeline
```

`/automation`, `/usage`, `/remote-ops` are HTTP 308 permanent redirects.

---

## Requirements

### R1 — `/nodes` becomes the definitive node page

`/nodes` MUST include all of the following, absorbed from removed pages:

1. **Node list** (already present): hostname, OS, status dot, last seen, streak, providers heatmap, system metrics gauges, git SHA.
2. **Fleet summary** (already present): total nodes, online count, tasks running, fleet success rate.
3. **Provider health per node** (from `/automation`): the per-provider success rates are already in `node.streak.by_provider`; no new API calls needed. Expose them in the per-node card already rendered.
4. **Remote messaging** (already present in `/nodes`): MessageForm component.
5. **Task dispatch controls** (absorbed from `/remote-ops`): The `ControlsSection` component and associated `useRemoteOps` hook state — execute token, executor select, task type, model override, run flags. Move these into `/nodes`.
6. **Deployment / uptime status** (absorbed from `/remote-ops`): The `DeploymentUptimeSection` component — API health, proxy health, deploy commit SHA.
7. **Fleet capabilities** (from `/automation`): Optional. If `GET /api/federation/fleet-capabilities` exists, surface total CPU, memory, GPU status as a collapsible fleet metrics panel.

**New section order for `/nodes`**:
```
Fleet summary (stats row)
├── Deployment & Uptime          ← from /remote-ops
├── Task Dispatch Controls       ← from /remote-ops
├── Node List                    ← already in /nodes
└── Send Message                 ← already in /nodes
```

### R2 — `/pipeline` becomes the definitive execution page

`/pipeline` MUST include all of the following, absorbed from removed pages:

1. **Live task queue** (absorbed from `/remote-ops`): `QueuePipelineSection` — pending queue rows, active count, runTask callback.
2. **Active tasks** (already present): executing right now, animated dots.
3. **Activity stream** (already present): last 50 events, color-coded by outcome.
4. **Provider health** (absorbed from `/automation` + `/usage`): Global provider stats table — success rate, last-5 rate, avg speed, selection probability, blocked status. This replaces the partial view on `/pipeline` and the full view on `/automation`/`/usage`.
5. **Daily summary / friction** (absorbed from `/usage`): `FrictionSection`, `HostRunnerSection`, `QualityAwarenessSection`, `ProvidersSection`, `TopToolsAttentionSection`. These are operational pipeline signals and belong here.
6. **Runtime cost** (absorbed from `/usage`): `RuntimeCostSection` — ideas ranked by cost, pagination.
7. **View performance** (absorbed from `/usage`): `ViewPerformanceSection`.
8. **Provider readiness** (absorbed from `/automation`): `ProviderReadinessResponse` data — blocking issues, readiness per provider.
9. **Usage alerts** (absorbed from `/automation`): Usage alerts (limit coverage, ratio thresholds).
10. **Streaks** (existing): node streaks, success rates from node data.

**New section order for `/pipeline`**:
```
Header (What Is Happening Now — keep)
Summary stats row
├── Active tasks (executing right now)
├── Live Queue                   ← from /remote-ops QueuePipelineSection
├── Provider Health              ← unified from /automation + /usage + existing /pipeline
│   ├── Provider readiness
│   ├── Usage alerts
│   └── Per-provider stats table
├── Daily summary
│   ├── Friction
│   ├── Host runner
│   ├── Quality awareness
│   ├── Top tools / attention
│   └── Providers table
├── Activity stream
├── Runtime cost (paginated)
└── View performance
```

### R3 — Remove `/automation`, `/usage`, `/remote-ops`

- All three pages are replaced by `redirect()` calls (Next.js permanent redirect, HTTP 308):
  - `/automation` → `/pipeline`
  - `/usage` → `/pipeline`
  - `/remote-ops` → `/nodes`
- The original `page.tsx` files are replaced with single-line redirect files.
- The original data-fetching helpers (`data.ts`, `types.ts`, etc.) are deleted.
- The `GardenMap` component (`/components/automation/garden-map.tsx`) is deprecated and can be removed or archived.

### R4 — Navigation cleanup

In `site_header.tsx`:
- Remove `{ href: "/automation", label: "Automation" }` from `SECONDARY_NAV` or wherever it appears.
- Ensure `/nodes` and `/pipeline` remain in `PRIMARY_NAV`.

In `page_context_links.tsx`:
- Remove any `CONTEXTS` entries for `/automation`, `/usage`, `/remote-ops`.
- Add `CONTEXTS` entries for `/nodes` and `/pipeline` if missing.

### R5 — Intra-page cross-linking

After consolidation, `/nodes` and `/pipeline` MUST link to each other prominently in their "Where to go next" / nav sections.

### R6 — No data loss

Every data point currently visible on any of the four removed pages MUST be reachable from `/nodes` or `/pipeline` after consolidation. No information may be silently dropped.

---

## API Endpoints Used (no changes required)

The consolidation is purely frontend. The same API endpoints continue to be used; they are just called from different pages.

| Endpoint | Used by (after consolidation) |
|----------|------------------------------|
| `GET /api/federation/nodes` | `/nodes` |
| `GET /api/federation/nodes/stats` | `/nodes` (optional) |
| `GET /api/federation/fleet-capabilities` | `/nodes` (optional) |
| `GET /api/providers/stats` | `/pipeline` |
| `GET /api/automation/usage` | `/pipeline` |
| `GET /api/automation/usage/alerts` | `/pipeline` |
| `GET /api/automation/usage/readiness` | `/pipeline` |
| `GET /api/agent/tasks/active` | `/pipeline` |
| `GET /api/agent/tasks/activity` | `/pipeline` |
| `GET /api/agent/tasks?status=pending` | `/pipeline` |
| `GET /api/agent/tasks?status=running` | `/pipeline` |
| `GET /api/agent/tasks/pending` | `/pipeline` (queue section) |
| `GET /api/health` | `/nodes` (deployment uptime) |
| `GET /api/health/proxy` | `/nodes` (deployment uptime) |
| `GET /api/deploy/contract` | `/nodes` (deployment uptime) |
| `POST /api/agent/tasks` | `/nodes` (dispatch) |
| `POST /api/federation/nodes/{id}/messages` | `/nodes` (messaging) |
| `GET /api/usage/daily-summary` | `/pipeline` |
| `GET /api/usage/runtime` | `/pipeline` |
| `GET /api/usage/view-performance` | `/pipeline` |

---

## Files Changed

### Files modified
| File | Change |
|------|--------|
| `web/app/nodes/page.tsx` | Add DeploymentUptimeSection + ControlsSection (from remote-ops) |
| `web/app/pipeline/page.tsx` | Add QueuePipelineSection + daily summary sections + provider readiness |
| `web/components/site_header.tsx` | Remove /automation from nav |
| `web/components/page_context_links.tsx` | Remove /automation, /usage, /remote-ops contexts; update /nodes and /pipeline |

### Files replaced (page.tsx → redirect)
| File | Change |
|------|--------|
| `web/app/automation/page.tsx` | Replace with `redirect("/pipeline")` |
| `web/app/usage/page.tsx` | Replace with `redirect("/pipeline")` |
| `web/app/remote-ops/page.tsx` | Replace with `redirect("/nodes")` |

### Files deleted
| File | Reason |
|------|--------|
| `web/app/automation/data.ts` | No longer needed; automation data moves to pipeline |
| `web/app/usage/data.ts` | No longer needed; usage data moves to pipeline |
| `web/app/usage/types.ts` | No longer needed |
| `web/app/usage/sections/` | Moved/merged into pipeline page |
| `web/app/remote-ops/controls-section.tsx` | Moved to nodes page |
| `web/app/remote-ops/deployment-uptime-section.tsx` | Moved to nodes page |
| `web/app/remote-ops/queue-pipeline-section.tsx` | Moved to pipeline page |
| `web/app/remote-ops/use-remote-ops.ts` | Moved to nodes or shared hooks |
| `web/app/remote-ops/types.ts` | Moved with the above |
| `web/app/remote-ops/utils.ts` | Moved with the above |
| `web/components/automation/garden-map.tsx` | Deprecated; replace with targeted sections |

---

## Proof of Correctness (How We Know It's Working)

### Metric 1: Navigation item count
Before: 5+ items cover operational data (nodes, pipeline, automation, usage, remote-ops).
After: Exactly 2 operational data items in primary nav (nodes, pipeline). `/automation`, `/usage`, `/remote-ops` are absent.

### Metric 2: Redirect responses
`/automation`, `/usage`, `/remote-ops` must respond with HTTP 308 redirects, not 200.

### Metric 3: Content completeness
All information previously on the removed pages is findable within 1 click from `/nodes` or `/pipeline`.

### Metric 4: No broken inbound links
Any internal link to `/automation`, `/usage`, or `/remote-ops` follows the redirect transparently. Users are never stranded on a 404.

---

## Verification Scenarios

### Scenario 1 — Redirect responses (R3 core requirement)

**Setup**: Application deployed with redirects in place.

**Action**:
```bash
curl -s -o /dev/null -w "%{http_code} %{redirect_url}" https://coherencycoin.com/automation
curl -s -o /dev/null -w "%{http_code} %{redirect_url}" https://coherencycoin.com/usage
curl -s -o /dev/null -w "%{http_code} %{redirect_url}" https://coherencycoin.com/remote-ops
```

**Expected result**:
- `/automation` → `308` redirect to `/pipeline`
- `/usage` → `308` redirect to `/pipeline`
- `/remote-ops` → `308` redirect to `/nodes`

**Edge case**: Visiting `/automation?force_refresh=true` must also redirect (query params preserved or dropped gracefully — no 404).

---

### Scenario 2 — /nodes contains task dispatch controls (R1.5)

**Setup**: `/nodes` page loaded with execute token field visible.

**Action**: Browser navigation to `https://coherencycoin.com/nodes`. Inspect page for presence of:
1. "Execute token" input field (or equivalent label)
2. Executor dropdown (openclaw/codex/etc.)
3. Task type selector (impl/spec/test/review)
4. "Create Task" or "Dispatch" button

**Expected result**: All four elements are rendered without requiring navigation to `/remote-ops`.

**Edge case**: With no execute token, the page renders a warning message ("Execute token not set") rather than throwing an error.

---

### Scenario 3 — /pipeline contains provider health from /automation (R2.4)

**Setup**: At least one provider has recorded task attempts in the API.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/providers/stats | jq '.summary'
```
Then navigate browser to `https://coherencycoin.com/pipeline`.

**Expected result**:
- API returns `{ "total_providers": N, "healthy_providers": M, ... }` with N ≥ 1.
- `/pipeline` page renders a "Provider Health" section listing each provider with success rate, last-5 rate, avg speed, and blocked/ok status. The count N in the API matches the count shown on the page.

**Edge case**: When the API returns `healthy_providers: 0`, the `/pipeline` page renders an alert banner ("all providers degraded" or equivalent), not a blank section.

---

### Scenario 4 — /pipeline contains daily summary sections from /usage (R2.5)

**Setup**: The usage daily summary API returns non-empty friction and provider data.

**Action**:
```bash
curl -s "https://api.coherencycoin.com/api/usage/daily-summary" | jq '.friction'
```
Then visually inspect `https://coherencycoin.com/pipeline`.

**Expected result**:
- API returns friction object with `total`, `top_areas`, etc.
- `/pipeline` renders a "Friction" section (or equivalent heading) with friction count visible. The total from the API matches the number displayed.

**Edge case**: When `daily-summary` is unavailable (API returns 500), the `/pipeline` page displays a partial data warning ("Daily summary unavailable") rather than crashing.

---

### Scenario 5 — Navigation contains only /nodes and /pipeline for operational data (R4)

**Setup**: Any page on the site.

**Action**: Inspect the primary navigation rendered in `<SiteHeader>`.

**Expected result**:
- `/nodes` and `/pipeline` appear as nav items.
- `/automation`, `/usage`, and `/remote-ops` do NOT appear in primary or secondary nav.
- No 404 links exist in the header.

**Browser automation check**:
```javascript
// In browser console on any page
const links = Array.from(document.querySelectorAll('nav a')).map(a => a.href);
console.assert(!links.some(l => l.includes('/automation')), '/automation must not be in nav');
console.assert(!links.some(l => l.includes('/usage')), '/usage must not be in nav');
console.assert(!links.some(l => l.includes('/remote-ops')), '/remote-ops must not be in nav');
console.assert(links.some(l => l.endsWith('/nodes')), '/nodes must be in nav');
console.assert(links.some(l => l.endsWith('/pipeline')), '/pipeline must be in nav');
```

**Edge case**: The `/nodes` page's own "Where to go next" nav section links to `/pipeline`, and the `/pipeline` page's nav links back to `/nodes`.

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| Users have bookmarked `/automation`, `/usage`, or `/remote-ops` | Permanent (308) redirects work transparently in browsers; bookmarks update on next visit |
| `GardenMap` component has unique visualizations with no equivalent | Audit: all data from GardenMap is available via other sections; garden metaphor can be preserved as a subsection of `/pipeline` if desired |
| `useRemoteOps` hook is tightly coupled to `remote-ops/page.tsx` | Hook uses no page-specific state; it can be imported directly into `/nodes/page.tsx` |
| `/usage` sections are large and may increase `/pipeline` bundle size | Sections are lazily rendered; no SSR bundle change since `/pipeline` is already `"use client"` |
| The `remote-ops` controls require client-side state (executeToken) | `/nodes` currently renders as a server component; it must be split: top section server-rendered (node list), bottom section client-rendered (dispatch controls) — or whole page becomes `"use client"` |
| Some tests may reference `/automation` or `/usage` routes | Update test fixtures and e2e selectors to use new routes |
| GardenMap "garden metaphor" has brand value for some users | Consider adding a garden-themed visual accent to `/pipeline` provider section rather than deleting the metaphor entirely |

---

## Known Gaps and Follow-up Tasks

1. **Deferred**: Migrate `/usage` runtime cost pagination to `/pipeline` — pagination state (page, page_size) must be supported in `/pipeline`'s URL params.
2. **Deferred**: Audit `page_context_links.tsx` entries for `/automation`, `/usage`, `/remote-ops` — these context panels also link to the old pages and must be updated.
3. **Deferred**: Remove `GardenMap` component after confirming no other consumers.
4. **Deferred**: Update any e2e/Playwright tests that navigate to `/automation` or `/usage`.
5. **Out of scope**: No changes to the underlying API; this is purely a frontend restructure.
6. **Out of scope**: No changes to `/tasks` or `/flow` pages.
7. **Follow-up idea**: Embed a "pipeline health score" on the homepage dashboard that links to `/pipeline`, making the new page even more central.
8. **Follow-up idea**: Add deep-link anchors to `/pipeline#provider-health`, `/pipeline#queue`, `/nodes#dispatch` so existing internal links can target the exact section.
