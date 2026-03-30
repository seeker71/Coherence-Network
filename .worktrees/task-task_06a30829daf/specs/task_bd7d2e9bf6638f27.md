# Spec: Consolidate /automation, /usage, /remote-ops → /nodes and /pipeline

**Task ID**: `task_bd7d2e9bf6638f27`
**Type**: UX consolidation / navigation simplification
**Status**: draft
**Date**: 2026-03-29
**Author**: product-manager agent

---

## Summary

Four overlapping web pages create cognitive friction for operators navigating the Coherence Network
dashboard. The pages share data sources, duplicate widgets, and offer no clear mental model for
when to visit which one.

This spec consolidates them into **two canonical pages**:

| New page | Replaces | Focus |
|---|---|---|
| `/nodes` | `/nodes` (existing) + `/automation` | Everything about nodes: federation, health, providers, capabilities, messaging, remote control |
| `/pipeline` | `/pipeline` (existing) + `/remote-ops` + `/usage` | Everything about task execution: queue, running, completed, streaks, provider performance, cost |

The old routes `/automation`, `/usage`, and `/remote-ops` are removed and replaced with HTTP 301
redirects to the appropriate new destination.

---

## Problem Statement

### Current overlap

| Data / Widget | /automation | /usage | /remote-ops | /nodes | /pipeline |
|---|---|---|---|---|---|
| Provider health / stats | ✓ (exec stats, readiness) | ✓ (provider stats table) | — | — | ✓ (alerts) |
| Node list / status | ✓ (federation nodes, network nodes) | — | — | ✓ (full detail) | ✓ (node streak) |
| Task queue / pipeline | — | — | ✓ (queue + controls) | — | ✓ (running/pending) |
| Daily cost / runtime | — | ✓ (runtime cost estimate) | — | — | — |
| Provider usage (daily) | ✓ (GardenMap) | ✓ (ProvidersSection) | — | — | — |
| Remote dispatch / controls | — | — | ✓ (ControlsSection) | ✓ (MessageForm) | — |
| Streaks / quality | — | ✓ (friction, quality awareness) | — | — | ✓ (streak) |

Five distinct overlaps. A user diagnosing a failing provider must visit at least two pages today.

### Goal

One mental model:
- **I want to know about the network (nodes and providers)** → go to `/nodes`
- **I want to know about work (tasks running, queue, cost)** → go to `/pipeline`

No ambiguity, no duplicate tables, no dead-end navigation.

---

## Requirements

### R1 — /nodes page (enhanced)

The existing `/nodes` page is the canonical home for all node and provider information. It must
include:

| Section | Source today | Notes |
|---|---|---|
| Federation node list (status, OS, last seen) | `/nodes` existing | Keep |
| Node capabilities (executors, hardware, GPU) | `/nodes` existing | Keep |
| Node system metrics (CPU, memory, disk) | `/nodes` existing | Keep |
| Node streaks | `/nodes` existing | Keep |
| Provider readiness matrix | `/automation` only | Move here |
| Provider exec stats table (success rate, speed, last-5) | `/automation` + `/usage` | Merge into single table |
| Provider usage alerts | `/automation` only | Move here |
| Remote message dispatch (MessageForm) | `/nodes` existing | Keep |
| Remote control panel (dispatch task, pick-up) | `/remote-ops` only | Move here |
| Fleet capabilities summary (CPU, memory, GPU totals) | `/automation` only | Move here |

**All provider data lives in `/nodes`.** There is no longer a separate "automation" or "provider
health" page.

### R2 — /pipeline page (enhanced)

The existing `/pipeline` page is the canonical home for all task execution data. It must include:

| Section | Source today | Notes |
|---|---|---|
| Running tasks (live, streaming activity) | `/pipeline` existing | Keep |
| Pending queue (with pick-up controls) | `/remote-ops` only | Move here |
| Completed tasks (streaks, success rates) | `/pipeline` existing | Keep |
| Provider performance by task type | `/pipeline` existing | Keep |
| Daily cost / runtime cost estimate | `/usage` only | Move here |
| Host runner summary (by task type, streaks) | `/usage` only | Move here |
| Friction / quality awareness signals | `/usage` only | Move here |
| Top tools / top attention areas | `/usage` only | Move here |
| View performance table | `/usage` only | Move here |

**All execution and cost data lives in `/pipeline`.** There is no separate "usage" page.

### R3 — Redirects

Old routes must redirect permanently (HTTP 301) to the new canonical page:

| Old route | → New route |
|---|---|
| `/automation` | `/nodes` |
| `/usage` | `/pipeline` |
| `/remote-ops` | `/pipeline` |

Redirects are implemented via Next.js `redirects()` in `next.config.ts` (or `next.config.js`).
The old page directories (`web/app/automation/`, `web/app/usage/`, `web/app/remote-ops/`) are
deleted after redirects are verified working.

### R4 — Navigation updates

All internal `<Link>` components pointing to `/automation`, `/usage`, or `/remote-ops` must be
updated to point to `/nodes` or `/pipeline`. Search locations:

- `web/app/*/page.tsx` — nav breadcrumbs
- `web/components/**/*.tsx` — any shared nav components
- `web/app/layout.tsx` or any top-level nav bar

### R5 — Page titles and descriptions

| Route | `<title>` | Meta description |
|---|---|---|
| `/nodes` | `Nodes` | Network nodes, provider health, fleet capabilities, and remote controls. |
| `/pipeline` | `Pipeline` | Task execution: queue, running, completed, cost, and provider performance. |

### R6 — No data loss

Every data widget currently shown on any of the four source pages must appear on one of the two
destination pages. No information is silently dropped.

---

## API Dependencies (no changes required)

The spec requires **no new API endpoints**. The consolidation is purely a frontend reorganisation.
Existing endpoints used:

**For /nodes:**
- `GET /api/federation/nodes` — node list
- `GET /api/federation/nodes/stats` — network stats with node info
- `GET /api/federation/nodes/fleet-capabilities` — fleet summary
- `GET /api/automation/usage/readiness` — provider readiness
- `GET /api/providers/stats` — provider exec stats
- `GET /api/automation/usage/alerts` — usage alerts
- `POST /api/agent/messages` — send message to node (MessageForm)
- `POST /api/agent/tasks` — dispatch new task (remote control)
- `POST /api/agent/tasks/{id}/pick-up` — pick up pending task

**For /pipeline:**
- `GET /api/agent/tasks?status=running` — running tasks
- `GET /api/agent/tasks?status=pending` — pending queue
- `GET /api/agent/tasks?status=completed` — completed tasks
- `GET /api/agent/activity` — live activity stream
- `GET /api/providers/stats` — provider performance
- `GET /api/runtime/summary` — daily runtime cost
- `GET /api/daily-summary` — daily summary (friction, quality, host runner, tools)
- `GET /api/view-performance` — view performance table

---

## Data Model

No schema changes. All data flows from existing endpoints.

---

## File Inventory

### Files to create / modify

| File | Change |
|---|---|
| `web/app/nodes/page.tsx` | Add provider readiness, exec stats, alerts, remote controls, fleet summary sections |
| `web/app/pipeline/page.tsx` | Add queue (pick-up controls), daily cost, host runner, friction, quality, top tools, view performance sections |
| `web/next.config.ts` (or `.js`) | Add `redirects()` for `/automation → /nodes`, `/usage → /pipeline`, `/remote-ops → /pipeline` |

### Files to delete (after redirects verified)

| File | Notes |
|---|---|
| `web/app/automation/page.tsx` | Content moved to `/nodes` |
| `web/app/usage/page.tsx` | Content moved to `/pipeline` |
| `web/app/usage/data.ts` | Migrate needed helpers to `/pipeline` data loader |
| `web/app/usage/types.ts` | Migrate needed types |
| `web/app/usage/sections/` | All section components; migrate or inline |
| `web/app/remote-ops/page.tsx` | Content moved to `/pipeline` |
| `web/app/remote-ops/controls-section.tsx` | Migrate to pipeline |
| `web/app/remote-ops/queue-pipeline-section.tsx` | Migrate to pipeline |
| `web/app/remote-ops/deployment-uptime-section.tsx` | Evaluate — uptime widget belongs in `/nodes` |
| `web/app/remote-ops/use-remote-ops.ts` (hook) | Migrate interactive logic to pipeline |
| `web/components/automation/garden-map.tsx` | Delete (data now shown as standard tables/cards in `/nodes`) |

### Navigation files to update

| File | Change |
|---|---|
| `web/app/usage/sections/NavLinksSection.tsx` | Delete (dead file after redirect) |
| Any file linking to `/automation`, `/usage`, `/remote-ops` | Update href to `/nodes` or `/pipeline` |

---

## Implementation Notes

### Phased approach (recommended)

**Phase 1 — Redirects first (no data loss risk):**
Add the three redirects in `next.config.ts`. Old routes immediately start sending users to the
right place. Validate that no pages break. Zero visual change to `/nodes` or `/pipeline`.

**Phase 2 — Enrich /nodes:**
Port provider readiness, exec stats table, alerts, remote controls panel, fleet capabilities from
`/automation` and `remote-ops` into `/nodes`. Verify parity with old `/automation` page using the
verification scenarios below.

**Phase 3 — Enrich /pipeline:**
Port queue/pick-up controls, daily cost, host runner, friction, quality awareness, top tools,
view performance from `/usage` and `/remote-ops` into `/pipeline`. Verify parity.

**Phase 4 — Delete old files:**
Remove `web/app/automation/`, `web/app/usage/`, `web/app/remote-ops/`, and
`web/components/automation/`. Update all navigation links.

### Avoiding duplication during transition

During Phases 2–3, provider stats may appear on both `/nodes` and `/pipeline`. This is acceptable
temporarily. The spec requires that after Phase 4, each data element appears **exactly once**.

### Provider stats: one table, two uses

`GET /api/providers/stats` is called by both `/nodes` (for readiness) and `/pipeline` (for
performance). This is fine — the same endpoint, different presentation context:
- `/nodes`: "Is this provider healthy enough to receive tasks?" — status, readiness, blocked flag
- `/pipeline`: "How did providers perform on recent tasks?" — success rate, speed, last-5, task-type breakdown

---

## Proof of Value / Tracking Progress

To show this consolidation is working over time:

1. **Navigation link audit**: run `grep -r "/automation\|/usage\|/remote-ops" web/` after Phase 4.
   Result should be zero matches (excluding `next.config.ts` redirect declarations).

2. **Redirect health check**: `curl -sI https://coherencycoin.com/automation | grep -i location`
   must return `Location: .../nodes`. Same for `/usage → /pipeline`, `/remote-ops → /pipeline`.

3. **Page load timing**: `/nodes` and `/pipeline` must each load in under 3 seconds on cold cache
   (Next.js SSR). Document baseline before and after migration.

4. **User session breadth**: monitor how many distinct pages a user visits per session.
   Pre-consolidation: average >3 pages for node/provider diagnostics.
   Post-consolidation: target ≤2 pages for the same diagnostic task.

---

## Verification Scenarios

### Scenario 1 — Redirects work for all three old routes

**Setup**: Production is deployed with the new `next.config.ts` redirects in place.
**Action**:
```bash
curl -sI https://coherencycoin.com/automation | grep -i "^location\|^http"
curl -sI https://coherencycoin.com/usage       | grep -i "^location\|^http"
curl -sI https://coherencycoin.com/remote-ops  | grep -i "^location\|^http"
```
**Expected**:
- `/automation` → HTTP 301, `Location: /nodes` (or absolute URL `https://coherencycoin.com/nodes`)
- `/usage` → HTTP 301, `Location: /pipeline`
- `/remote-ops` → HTTP 301, `Location: /pipeline`

**Edge case**: Direct fetch of old page source (no follow) should not return 200. A browser
following the redirect should land on `/nodes` or `/pipeline` successfully (HTTP 200).

---

### Scenario 2 — /nodes displays provider health data (was only on /automation)

**Setup**: At least one provider (e.g. `claude`) has execution stats in the system
(`GET /api/providers/stats` returns at least one entry).
**Action**: Navigate browser to `https://coherencycoin.com/nodes`.
**Expected**:
- Page renders with HTTP 200.
- A "Provider Health" or "Providers" section is visible.
- The section shows at least one provider row with: provider name, success rate (e.g. `94%`),
  last-5 rate, avg duration, status (`ok` / `attention` / `blocked`).
- A "Provider Readiness" section shows whether required providers are configured.

**Edge case**: If `/api/providers/stats` returns an error or empty object, the section renders a
graceful fallback message (not a crash). No unhandled exceptions.

---

### Scenario 3 — /pipeline displays task queue with pick-up controls (was only on /remote-ops)

**Setup**: At least one task exists with `status=pending` in the system.
**Action**: Navigate browser to `https://coherencycoin.com/pipeline`.
**Expected**:
- Page renders with HTTP 200.
- A "Queue" section shows the pending task: `task_id`, `task_type`, truncated `direction`.
- A "Pick up" button is present next to the task.
- Clicking "Pick up" sends `POST /api/agent/tasks/{id}/pick-up` and updates the UI.

**Edge case**: If the queue is empty, the section shows "No pending tasks" — not an empty white
box. If the API is unreachable, the queue section shows an error state, not a blank page.

---

### Scenario 4 — /pipeline displays daily cost / usage data (was only on /usage)

**Setup**: The daily summary API (`GET /api/daily-summary`) returns non-empty data with at least
one provider row and a non-zero total cost.
**Action**: Navigate browser to `https://coherencycoin.com/pipeline`.
**Expected**:
- A "Runtime Cost" or "Daily Summary" section appears.
- At least one idea row shows a non-zero `runtime_cost_estimate`.
- Provider rows from the daily summary are rendered (provider name + cost/call counts).

**Edge case**: If `runtime_cost_estimate` is 0 for all items, show zero values with proper
formatting (not blank). If the daily summary endpoint fails, the section degrades gracefully.

---

### Scenario 5 — No internal links point to the removed routes

**Setup**: Phase 4 complete — old page directories deleted.
**Action**:
```bash
grep -r 'href="/automation"\|href="/usage"\|href="/remote-ops"' web/app web/components
```
**Expected**: Zero matches (empty output).

**Edge case**: The `next.config.ts` file _will_ contain the old route strings (as redirect source
patterns). This is expected and does not count as a "broken link". Only `<Link href="...">` and
`<a href="...">` references are forbidden.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|---|---|---|
| `/nodes` page becomes too long / slow to scroll | Medium | Implement collapsible sections; put remote controls in a slide-over panel |
| `/pipeline` page's SSR load time increases (more API calls) | Medium | Implement `Promise.allSettled` with per-section error boundaries; add `revalidate = 60` for stable sections |
| `/remote-ops` controls panel requires client-side interactivity (token input, executor selects) | High | Port the `use-remote-ops` hook logic to a client component embedded inside the `/pipeline` SSR page — same pattern as `/remote-ops/page.tsx` today |
| Navigation links in blog posts or external docs still reference old routes | Low | Redirects handle this permanently; no broken links |
| The `garden-map.tsx` component has unique visual logic not replicated in standard tables | Low | Decide whether to keep it as an optional widget or fully replace with tables; spec leaves this to impl |

---

## Known Gaps and Follow-up Tasks

- [ ] `/nodes` page mobile layout: provider table is wide — needs responsive treatment (card stacking on small screens, same pattern as `/usage` today).
- [ ] Deployment/uptime section from `/remote-ops` (Railway deploy status) — evaluate whether it belongs in `/nodes` (infra) or `/pipeline` (ops). Default: `/nodes`.
- [ ] `garden-map.tsx` — the animated organism metaphor may be worth keeping as an optional view toggle within `/nodes`. Out of scope for this spec; flag as a follow-up.
- [ ] `/usage/sections/ViewPerformanceSection.tsx` renders a per-page cost table — this can move to `/pipeline` but also belongs in a future `/analytics` page. Move to `/pipeline` now; extract later.
- [ ] Provider stats appear in both `/nodes` (readiness) and `/pipeline` (performance) — one shared component could de-duplicate rendering logic. Nice-to-have, not required for this spec.
