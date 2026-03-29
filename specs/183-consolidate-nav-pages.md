# Spec 183 — Consolidate /automation, /usage, /remote-ops → /nodes and /pipeline

**Idea ID**: fecc6d087c4e
**Task ID**: task_a4cc2c47e2484dd7
**Author**: product-manager agent
**Date**: 2026-03-28
**Status**: proposed

---

## Summary

Four navigation pages currently expose overlapping data with unclear boundaries:

| Page | What it shows |
|---|---|
| `/automation` | Provider automation readiness, provider exec stats, federation node list, usage alerts |
| `/usage` | Provider health, daily summary, runtime costs, friction, quality awareness |
| `/remote-ops` | Task queue, pipeline controls, deployment uptime, dispatch controls |
| `/nodes` | Federation node list, system metrics, streaks, messaging |

Users are forced to visit multiple pages to answer single questions like "is my node healthy?" or "why did that task fail?". The mental model is fractured: automation health, execution performance, and infrastructure live in three different places.

**This spec defines a 2-page consolidation:**

1. **`/nodes`** — Everything about nodes and providers: who is online, what they can do, their health over time, remote control actions, and messaging.
2. **`/pipeline`** — Everything about task execution: queue, running tasks, completed results, provider performance, streaks, and friction.

Pages `/automation`, `/usage`, and `/remote-ops` are removed and replaced with HTTP 301 redirects to the appropriate target.

---

## Goals

- **Reduce navigation confusion**: Users answer their question on one page, not three.
- **Clearer mental model**: Nodes = infrastructure; Pipeline = execution.
- **No information loss**: Every data element currently shown is preserved in the new layout.
- **Proof over time**: Both pages include visible last-updated timestamps and health trend indicators so users can confirm the consolidation is working.

---

## Non-Goals

- **No API changes**: All existing API endpoints remain as-is. This is purely a front-end reorganization.
- **No data model changes**: No new fields, no schema migrations.
- **No design system overhaul**: Use existing shadcn/ui components and existing patterns.

---

## Current Overlap Map

### Data shown in multiple places today

| Data element | `/automation` | `/usage` | `/remote-ops` | `/nodes` |
|---|:---:|:---:|:---:|:---:|
| Provider exec stats (success rate, last 5, avg speed) | ✓ | ✓ | — | — |
| Federation node list (hostname, OS, status) | ✓ | — | — | ✓ |
| Task queue (pending, running counts) | — | — | ✓ | — |
| Provider readiness (configured, missing env vars) | ✓ | — | — | — |
| Provider usage alerts | ✓ | ✓ | — | — |
| Daily summary (friction, quality awareness) | — | ✓ | — | — |
| Node streak (completed, failed, by provider) | — | — | — | ✓ |
| Pipeline controls (dispatch, executor, model) | — | — | ✓ | — |
| Deployment uptime / API health | — | — | ✓ | — |
| System metrics (CPU, memory, disk) | — | — | — | ✓ |
| Runtime cost by idea | — | ✓ | — | — |

---

## Target Page Architecture

### Page 1: `/nodes` — "Infrastructure View"

**Purpose**: Answer "what is the network capable of right now?"

**Sections (ordered by user priority):**

1. **Network health bar** — live count: `N nodes online`, `P providers healthy`, last-seen timestamps. Color-coded: green < 5 min, yellow < 60 min, red > 60 min. This is the top-of-page signal that proves the page is live.

2. **Node cards grid** — one card per registered node, each showing:
   - Hostname, OS icon, status badge
   - System metrics: CPU %, memory %, disk %
   - Last seen (relative time)
   - Git SHA (version, with up-to-date indicator)
   - Streak summary: completed / failed / success_rate
   - Providers & executors listed
   - Expand button → per-provider breakdown (by_provider stats from streak)

3. **Provider readiness panel** — table of all tracked providers with:
   - Configured (yes/no)
   - Required (yes/no)
   - Status (ok / attention / blocked)
   - Missing env vars (if any)
   - Blocking issues callout (red banner if `all_required_ready = false`)

4. **Provider exec stats** — the success-rate / last-5 / avg-speed table currently split between `/automation` and `/usage`. Single unified table here with per-provider details.

5. **Remote control panel** — moved from `/remote-ops`:
   - Execute token input
   - Executor selector, task type, model override
   - Force paid / run as PR thread / auto-merge toggles
   - "Create task" and "Pick up task" action buttons
   - Status/error display

6. **Node messaging** — existing form from `/nodes/MessageForm.tsx`, unchanged.

7. **Fleet capabilities summary** — total CPUs, total RAM, GPU-capable nodes (currently hidden in `/automation`'s garden-map component).

**Data sources (no new APIs needed):**
- `GET /api/federation/nodes` — node list
- `GET /api/federation/nodes/stats` — network stats, node info
- `GET /api/automation/usage/readiness` — provider readiness
- `GET /api/providers/stats` — provider exec stats
- `GET /api/automation/usage` — limit coverage, unavailable providers
- `POST /api/agent/tasks` — create task (remote control)
- `POST /api/agent/pipeline-status` — queue status (for remote-control display)

---

### Page 2: `/pipeline` — "Execution View"

**Purpose**: Answer "what is the network executing right now, and how well?"

**Sections (ordered by user priority):**

1. **Live task counter bar** — `N pending / M running / K completed today`. Refreshes every 30 s. Proves the page is live.

2. **Running tasks** — live list of currently executing tasks: task ID, node, provider, elapsed time, progress event stream summary (last event from activity log).

3. **Pending queue** — paginated table of queued tasks: task ID, type, queued-at, assigned executor. Controls to filter by executor.

4. **Completed tasks** — paginated reverse-chronological list with outcome badges (✓ completed, ✗ failed, ⏱ timed-out), provider used, duration.

5. **Provider performance panel** — exec stats (success_rate, last_5_rate, avg_duration_s, blocked, needs_attention) plus alerts from `GET /api/providers/stats`. This is the canonical location for provider performance; `/nodes` shows a summary-only version with a link here for details.

6. **Daily summary** — moved from `/usage`:
   - Friction score and signals
   - Quality awareness score
   - Worker failed events (raw, recoverable, active)
   - Recovery streak vs target
   - Top tools / attention areas table
   - Host runner breakdown by task type

7. **Streaks dashboard** — aggregated across all nodes: total completed today, total failed, network-wide success rate. Trend sparklines (last 7 days) to show whether things are getting better.

8. **Runtime cost by idea** — table from `/usage` (runtime_cost_estimate per idea), paginated.

9. **View performance** — average API runtime cost by route, moved from `/usage`.

**Data sources (no new APIs needed):**
- `GET /api/agent/pipeline-status` — queue + running + recent
- `GET /api/providers/stats` — provider performance
- `GET /api/agent/usage` — daily summary, friction, streaks
- `GET /api/federation/nodes` — per-node streaks
- `GET /api/agent/tasks` — completed task list, paginated

---

## Redirects

Three pages are deleted. Their routes redirect permanently:

| Removed route | Redirect target | Rationale |
|---|---|---|
| `/automation` | `/nodes` | Provider readiness + node list → nodes |
| `/usage` | `/pipeline` | Execution metrics + daily summary → pipeline |
| `/remote-ops` | `/nodes` | Remote control → nodes |

**Implementation**: Next.js `next.config.js` `redirects()` array, HTTP 301.

```js
// next.config.js additions
{
  source: '/automation',
  destination: '/nodes',
  permanent: true,
},
{
  source: '/usage',
  destination: '/pipeline',
  permanent: true,
},
{
  source: '/remote-ops',
  destination: '/nodes',
  permanent: true,
},
```

---

## Navigation Changes

### `site_header.tsx`

Remove from the Operations group:
- `/automation`

Add to the primary nav if not already present:
- `/nodes` (Nodes)
- `/pipeline` (Pipeline)

### `page_context_links.tsx`

- Remove `/automation` context definition → merge its `machinePaths` into `/nodes` context.
- Remove `/remote-ops` context definition → merge its `machinePaths` into `/nodes` context.
- Update `/usage` context → redirect entry pointing to `/pipeline`.

### NavLinksSection in `/usage`

The `NavLinksSection` component currently renders cross-page links. After migration, the component is removed from the deleted page. Any usages in surviving pages should be updated to link to `/nodes` and `/pipeline` instead of `/automation`, `/usage`, `/remote-ops`.

---

## Files to Modify

### Deleted pages (content merged, file removed)
- `web/app/automation/` — entire directory removed after content migration
- `web/app/usage/` — entire directory removed after content migration
- `web/app/remote-ops/` — entire directory removed after content migration

### Modified pages
- `web/app/nodes/page.tsx` — expand with provider readiness, exec stats, remote control panel, fleet summary
- `web/app/pipeline/page.tsx` — expand with daily summary, runtime costs, view performance, streaks dashboard

### Config & navigation
- `web/next.config.js` — add 301 redirects
- `web/components/site_header.tsx` — remove `/automation` from nav
- `web/components/page_context_links.tsx` — update context definitions

### Optional (if reused components exist)
- `web/app/usage/sections.tsx` → move section components into `web/components/pipeline/`
- `web/app/remote-ops/controls-section.tsx` → move into `web/components/nodes/`

---

## Acceptance Criteria

- [ ] Navigating to `/automation` returns HTTP 301 → `/nodes`
- [ ] Navigating to `/usage` returns HTTP 301 → `/pipeline`
- [ ] Navigating to `/remote-ops` returns HTTP 301 → `/nodes`
- [ ] `/nodes` page loads without error and displays federation node list, provider readiness, provider exec stats, and remote control panel
- [ ] `/pipeline` page loads without error and displays task queue, running tasks, daily summary, provider performance, and runtime costs
- [ ] No navigation links remain pointing to `/automation`, `/usage`, or `/remote-ops`
- [ ] Both pages display a visible "last updated" timestamp so users can confirm live data
- [ ] `/nodes` remote control panel can dispatch a task and shows status feedback
- [ ] All sections that were previously available on removed pages are reachable on the new pages

---

## Proof of Working — Observable Signals

**For `/nodes`:**
- `Network health bar` shows green/yellow/red status within 5 s of page load
- Provider readiness panel shows "all required ready" or a blocking issues banner
- Remote control panel renders without crashing; executor dropdown is populated

**For `/pipeline`:**
- Live task counter updates after 30 s without page reload
- Daily summary section shows friction score > 0 (or "no data" gracefully)
- Provider performance table shows at least one row

**Trend proof over time** (answers the open question "show whether it is working"):
- Add a small data-freshness chip to each major section: `"Updated 2m ago"`. This makes it immediately visible whether sections are receiving live data.
- The streaks dashboard (7-day sparkline) shows execution trend lines. An improving trend line is concrete proof the consolidation is not hiding data.
- Both pages expose `generated_at` timestamps from API responses in the UI footer.

---

## Verification Scenarios

### Scenario 1 — Redirect chain works end-to-end

**Setup**: A browser or curl client navigating to old pages.

**Action**:
```bash
curl -sI https://coherencycoin.com/automation | grep -E "location|HTTP"
curl -sI https://coherencycoin.com/usage | grep -E "location|HTTP"
curl -sI https://coherencycoin.com/remote-ops | grep -E "location|HTTP"
```

**Expected result**:
- Each returns `HTTP/1.1 301 Moved Permanently`
- `location:` header points to `/nodes`, `/pipeline`, and `/nodes` respectively.

**Edge case**: A direct fetch to `/automation` with `?force_refresh=true` query param must also redirect cleanly (query params forwarded or stripped — 301 is acceptable either way).

---

### Scenario 2 — /nodes page loads and shows live node data

**Setup**: At least one federation node registered and seen within the last 60 minutes.

**Action**: Navigate browser to `https://coherencycoin.com/nodes`

**Expected result**:
- Page loads with HTTP 200
- Network health bar shows at least 1 node online (green or yellow badge)
- Node cards section renders at least one card with hostname and status
- Provider readiness panel renders (may show "no providers" if none configured, but must not throw an error)
- Provider exec stats table renders (may show empty if no runs yet)
- Remote control panel renders with executor dropdown

**Edge case**: If `GET /api/federation/nodes` returns 500, the page must render a graceful error state for that section (e.g., "Node data unavailable") without crashing the full page.

---

### Scenario 3 — /pipeline page shows execution data

**Setup**: At least 5 tasks have been completed in the last 24 hours.

**Action**: Navigate browser to `https://coherencycoin.com/pipeline`

**Expected result**:
- Page loads with HTTP 200
- Live task counter bar shows non-zero counts (pending ≥ 0, running ≥ 0, completed > 0)
- Completed tasks section shows at least 5 rows with outcome badges
- Provider performance table shows success_rate column populated
- Daily summary section shows friction score or a "no data" placeholder (not a crash)
- Runtime cost section shows at least one idea row

**Edge case**: If `GET /api/agent/pipeline-status` returns empty (no tasks yet), the running tasks section shows "No tasks currently running" and the page does not crash.

---

### Scenario 4 — Remote control dispatch from /nodes

**Setup**: Valid `AGENT_EXECUTE_TOKEN` available; at least one executor registered.

**Action**:
1. Navigate to `/nodes`
2. Scroll to Remote Control panel
3. Enter execute token, select executor, enter task type "spec"
4. Click "Create Task"

**Expected result**:
- POST to `/api/agent/tasks` returns HTTP 200 or 201
- Status feedback appears in the panel: "Task created: task_<id>"
- No page navigation required (inline feedback)

**Edge case**: If execute token is wrong, the panel shows an error message (e.g., "Execute token invalid — HTTP 403") and does not crash. The error is visible in the UI.

---

### Scenario 5 — No broken internal links after migration

**Setup**: Production site with redirects live.

**Action**:
```bash
# Check that no page links to the removed routes
curl -s https://coherencycoin.com/nodes | grep -E '"/automation"|"/remote-ops"'
curl -s https://coherencycoin.com/pipeline | grep -E '"/automation"|"/usage"|"/remote-ops"'
curl -s https://coherencycoin.com/ | grep -E '"/automation"|"/remote-ops"'
```

**Expected result**: All three commands return empty output — no rendered anchor tags pointing to removed routes.

**Edge case**: If any link exists (e.g., in a footer or nav component that was missed), the redirect ensures users aren't stranded — but the link should still be cleaned up to avoid confusing UX.

---

## Risks and Assumptions

| Risk | Likelihood | Mitigation |
|---|---|---|
| Users have bookmarked `/automation` or `/usage` | Medium | HTTP 301 redirects are permanent and browser-cached — users are transparently forwarded. |
| Merged pages become too long and overwhelming | Medium | Use collapsible sections and tab-based sub-navigation within each page (defer to the UX spec task_5cb9d9ff27681827 for tab patterns). |
| Provider readiness data missing on `/nodes` | Low | Page shows graceful "unavailable" state with try-again timestamp; no hard crash. |
| `/usage` data structures (UsageSearchParams, pagination) need migration | Medium | Carry pagination query params from `/usage` into `/pipeline`. Map `page` and `page_size` params to the same names. |
| `NavLinksSection` component currently imported by `/usage` | Low | Component is deleted with the page; any surviving usages must be audited before deletion. |
| Breaking change for external tools linking to old routes | Low | Redirects cover 99% of cases. API endpoints are unchanged. |

---

## Known Gaps and Follow-up Tasks

1. **Tab sub-navigation**: The `/nodes` page may warrant tabs (Overview / Providers / Remote Control / Messages) once all sections are merged. Defer to UX spec (task_5cb9d9ff27681827).
2. **Mobile layout**: Merged pages will be longer. Confirm mobile scroll / sticky header behavior per the mobile-first spec.
3. **Streaks sparkline**: A 7-day trend sparkline on `/pipeline` requires aggregate data from `GET /api/federation/nodes` or a new `GET /api/agent/streak-history` endpoint. Raise as a follow-up idea.
4. **View performance section**: Currently depends on `loadViewPerformance` in `/usage/data.ts`. This helper must be moved or re-imported in `/pipeline`.
5. **`cc nodes` CLI**: The `cc nodes` CLI command currently reads from the `/nodes` page API endpoint. No changes needed — the API remains unchanged.

---

## Implementation Order (for the impl agent)

1. Add redirects to `next.config.js`
2. Expand `web/app/nodes/page.tsx` with merged sections from `/automation` and `/remote-ops`
3. Expand `web/app/pipeline/page.tsx` with merged sections from `/usage`
4. Update `web/components/site_header.tsx` nav links
5. Update `web/components/page_context_links.tsx` context definitions
6. Delete `web/app/automation/`, `web/app/usage/`, `web/app/remote-ops/` directories
7. Audit for any remaining cross-links (`grep -r "automation\|remote-ops" web/app/`) and fix
8. Deploy and run Verification Scenarios 1–5
