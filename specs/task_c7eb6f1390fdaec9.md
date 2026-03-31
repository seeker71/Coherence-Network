# Spec: Consolidate Navigation — /nodes and /pipeline

**Idea ID**: task_c7eb6f1390fdaec9
**Type**: UX / Navigation Consolidation
**Status**: Draft
**Author**: product-manager agent
**Date**: 2026-03-28

---

## Summary

Four web pages overlap significantly in the data they present:

| Page | What it shows |
|------|---------------|
| `/automation` | Provider readiness, usage limits, exec stats, federation nodes overview |
| `/usage` | Provider health, daily task summary, runtime cost, friction, host-runner stats, view performance |
| `/remote-ops` | Deploy/health status, create-task controls, queue / running pipeline |
| `/nodes` | Federation node list, per-node health, provider stats per node, streaks, messaging |
| `/pipeline` | Running tasks, activity feed, provider stats |

The result is a fragmented mental model: a user trying to answer "is my node healthy?" visits `/nodes`; to dispatch a task they visit `/remote-ops`; to understand why tasks are failing they visit `/automation` and `/usage`. Three or four tab-hops for one coherent question.

**Goal**: Consolidate to two clear, well-scoped pages:

1. **`/nodes`** — Everything about *machines and providers*: federation list, health metrics, capabilities, provider stats, per-node streaks, remote control (dispatch tasks, pick-up), messages.
2. **`/pipeline`** — Everything about *task execution flow*: queue, running, completed tasks, streaks by node, provider performance, runtime cost, daily summary, friction signals.

Remove `/automation`, `/usage`, and `/remote-ops` — replace each with a redirect to the appropriate new page so all existing links and bookmarks keep working.

---

## Goals

1. **Fewer navigation choices** — operators find information in at most one hop.
2. **Clear mental model** — `/nodes` = hardware/providers; `/pipeline` = work/tasks.
3. **No data loss** — every data point currently visible on the four old pages appears on the two new pages.
4. **Backward compatibility** — old URLs 301-redirect so bookmarks and external links continue to work.
5. **Measurable improvement** — the number of nav links pointing to deprecated pages drops to zero; redirect coverage is 100%.

---

## Non-Goals

- API changes — all existing API endpoints remain; this spec covers the web layer only.
- Design redesign — sections can be lifted with minimal visual change; polish is a separate concern.
- Mobile-first rewrite — maintain current responsive patterns.

---

## Existing Files Affected

### Pages to remove (redirect)
| File | Redirects to |
|------|-------------|
| `web/app/automation/page.tsx` | `/nodes` |
| `web/app/usage/page.tsx` | `/pipeline` |
| `web/app/remote-ops/page.tsx` | `/nodes` (remote-control section) |

### Pages to expand
| File | New content added |
|------|-----------------|
| `web/app/nodes/page.tsx` | Sections from `/automation` (provider readiness, exec stats, limit coverage) + sections from `/remote-ops` (deploy health, create-task controls, queue controls) |
| `web/app/pipeline/page.tsx` | Sections from `/usage` (daily summary, runtime cost, friction, quality awareness, view performance, host-runner) + sections from `/remote-ops` (queue view, running view) |

### Navigation file
| File | Change |
|------|--------|
| `web/components/site_header.tsx` | Remove `Automation`, `Usage`, `Remote Ops` from `SECONDARY_NAV`; ensure `Nodes` and `Pipeline` remain in `PRIMARY_NAV` |

### Redirect files to create
```
web/app/automation/page.tsx   → replace with redirect component
web/app/usage/page.tsx        → replace with redirect component
web/app/remote-ops/page.tsx   → replace with redirect component
```

Next.js redirects may alternatively be declared in `next.config.js` as permanent (308/301) redirects — preferred over client-side redirect components because they work without JS and are search-engine friendly.

---

## Detailed Content Mapping

### `/nodes` — absorbs from `/automation` and `/remote-ops`

**Existing `/nodes` sections (keep as-is):**
- Federation node list (node_id, hostname, OS, providers, status, last_seen)
- Per-node capability detail (executors, hardware, system metrics)
- Per-node streak (completed, failed, timed-out, success_rate, last_10, by_provider)
- Message form (send message to a node)

**Add from `/automation`:**
- Provider readiness table (required / configured / severity / missing env)
- Provider exec stats table (overall rate, last-5 rate, avg speed, blocked/attention status)
- Limit coverage summary (providers with remaining metrics, coverage ratio)
- Usage alerts banner (providers approaching limits)

**Add from `/remote-ops`:**
- Deployment health strip (API health, deploy status, uptime)
- Execute-token input + create-task form (executor, task type, model override, flags)
- Run pick-up button
- Active / pending task counts as a live status badge

**Section order on `/nodes`:**
1. Node list & health (existing)
2. Provider readiness & exec stats (from `/automation`)
3. Remote control panel (from `/remote-ops`)
4. Message form (existing, moved to bottom)

---

### `/pipeline` — absorbs from `/usage` and `/remote-ops`

**Existing `/pipeline` sections (keep as-is):**
- Live activity feed (event stream from `/api/federation/nodes/activity`)
- Running tasks list
- Node streak summary

**Add from `/remote-ops`:**
- Queue view (pending tasks with run-task actions)
- Active count badge

**Add from `/usage`:**
- Daily summary (worker events, recovery streak, quality awareness)
- Provider performance table (success rate, last-5, avg speed, blocked flag)
- Friction signals section
- Host-runner by-task-type breakdown
- Runtime cost / ideas table (paginated)
- View performance table
- Top tools & attention areas

**Section order on `/pipeline`:**
1. Status strip — pending + active counts, recovery streak (from `/usage` + `/remote-ops`)
2. Queue — pending tasks (from `/remote-ops`)
3. Running — active tasks (existing)
4. Provider performance (merged from `/usage` + existing)
5. Daily summary — quality awareness, worker events, friction (from `/usage`)
6. Runtime cost — ideas by cost, view performance (from `/usage`)
7. Activity feed (existing, moved to bottom as audit trail)

---

## Redirect Implementation

Add to `next.config.js` (or `next.config.mjs`) under the `redirects` export:

```js
async redirects() {
  return [
    { source: '/automation', destination: '/nodes', permanent: true },
    { source: '/automation/:path*', destination: '/nodes', permanent: true },
    { source: '/usage', destination: '/pipeline', permanent: true },
    { source: '/usage/:path*', destination: '/pipeline', permanent: true },
    { source: '/remote-ops', destination: '/nodes', permanent: true },
    { source: '/remote-ops/:path*', destination: '/nodes', permanent: true },
  ];
},
```

`permanent: true` emits HTTP 308 (Next.js uses 308 for permanent, not 301) so browsers and crawlers cache the redirect.

---

## Navigation Changes

`web/components/site_header.tsx`:

**`PRIMARY_NAV`** — unchanged (already contains Pipeline and Nodes):
```ts
{ href: "/pipeline", label: "Pipeline" },
{ href: "/nodes", label: "Nodes" },
```

**`SECONDARY_NAV`** — remove these three entries:
```ts
{ href: "/automation", label: "Automation" },  // REMOVE
// /usage was not in SECONDARY_NAV but remove any lingering reference
// /remote-ops was not in SECONDARY_NAV but remove any lingering reference
```

Scan all `.tsx` files for `href="/automation"`, `href="/usage"`, `href="/remote-ops"` and update each to the target URL or remove the link.

---

## Proof of Success Metrics

These signals prove the consolidation is working over time:

| Metric | Before | Target after |
|--------|--------|-------------|
| Nav items pointing to deprecated routes | ≥ 3 | 0 |
| Unique operational pages for node + pipeline info | 4 | 2 |
| HTTP status of `GET /automation` | 200 | 308 → `/nodes` |
| HTTP status of `GET /usage` | 200 | 308 → `/pipeline` |
| HTTP status of `GET /remote-ops` | 200 | 308 → `/nodes` |
| Provider stats visible on `/nodes` | No | Yes |
| Queue controls visible on `/nodes` | No (remote-ops only) | Yes |
| Daily summary visible on `/pipeline` | No (usage only) | Yes |

Monitoring: the `/api/health` endpoint and the web navigation audit in CI (`grep -r 'href="/automation"' web/`) should return zero matches after implementation.

---

## Verification Scenarios

### Scenario 1 — Redirect correctness (automation → nodes)

**Setup**: Application deployed with `next.config.js` redirects.
**Action**:
```bash
curl -s -o /dev/null -w "%{http_code} %{redirect_url}" https://coherencycoin.com/automation
```
**Expected**: `308 https://coherencycoin.com/nodes`
**Then**: Following the redirect, `curl -s -o /dev/null -w "%{http_code}" https://coherencycoin.com/nodes` returns `200`.
**Edge**: `curl -s -o /dev/null -w "%{http_code}" https://coherencycoin.com/automation/anything` returns `308` (wildcard path match).

---

### Scenario 2 — Redirect correctness (usage → pipeline, remote-ops → nodes)

**Setup**: Same deployment.
**Action**:
```bash
curl -s -o /dev/null -w "%{http_code} %{redirect_url}" https://coherencycoin.com/usage
curl -s -o /dev/null -w "%{http_code} %{redirect_url}" https://coherencycoin.com/remote-ops
```
**Expected**:
- `/usage` → `308 /pipeline`
- `/remote-ops` → `308 /nodes`
**Edge**: Both return 308 even without a trailing slash or sub-path.

---

### Scenario 3 — Provider stats present on /nodes

**Setup**: At least one provider has run tasks (exec stats exist in the DB).
**Action**: Open browser to `https://coherencycoin.com/nodes` (or `curl -s https://coherencycoin.com/nodes | grep -i "success rate"`).
**Expected**: The page renders a provider exec-stats section showing columns: Provider, Overall Rate, Last 5, Avg Speed, Status. At least one row is visible.
**Edge**: If `/api/providers/stats` returns a non-200, the section renders a graceful "Provider stats unavailable" message instead of crashing.

---

### Scenario 4 — Queue / pipeline controls present on /nodes

**Setup**: At least one pending task exists (`GET /api/tasks/pending` returns rows).
**Action**:
```bash
# Verify the API has pending tasks
curl -s https://api.coherencycoin.com/api/tasks/pending | jq '.total'
# Load /nodes and confirm queue section renders
curl -s https://coherencycoin.com/nodes | grep -i "pending\|queue"
```
**Expected**: The `/nodes` page includes a queue section listing pending tasks with a "Run" button. The count matches `total` from the API.
**Edge**: If `total` is 0, the section renders "No pending tasks" instead of an empty table.

---

### Scenario 5 — Daily summary present on /pipeline

**Setup**: Daily summary API returns data (`GET /api/runtime/daily-summary` returns a valid payload).
**Action**: Open `https://coherencycoin.com/pipeline` and look for friction / quality-awareness widgets (previously only on `/usage`).
**Action (curl)**:
```bash
curl -s https://coherencycoin.com/pipeline | grep -i "friction\|quality awareness\|recovery streak"
```
**Expected**: At least one of these phrases appears in the rendered HTML, confirming the daily-summary sections have been promoted to `/pipeline`.
**Edge**: If the daily-summary endpoint is unavailable, the pipeline page degrades gracefully (shows a "Partial data" warning, not a 500 error).

---

### Scenario 6 — No deprecated nav links remain (regression guard)

**Setup**: Post-implementation codebase.
**Action**:
```bash
grep -r 'href="/automation"' web/
grep -r 'href="/usage"' web/
grep -r 'href="/remote-ops"' web/
```
**Expected**: Zero matches in all three greps. Any link that previously pointed to the old routes either points to `/nodes` or `/pipeline`, or has been removed.
**Edge**: The `next.config.js` redirects entry itself is not a "nav link" — the grep should only catch JSX/TSX `href` attributes.

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| `/nodes` page becomes too long / overwhelming | Implement collapsible sections or tabs within the page (e.g., Overview / Providers / Control) |
| Remote-control panel on `/nodes` breaks if execute-token state is not preserved across the now-larger page | Ensure the `useRemoteOps` hook is imported correctly and token state is scoped to the control panel section |
| `/usage` had paginated runtime cost view — pagination params in URL must still work on `/pipeline` | Keep `?page=` and `?page_size=` query params working on `/pipeline` |
| Existing internal links in markdown docs, emails, or external tools point to `/automation` or `/remote-ops` | The 308 permanent redirect means all such links keep working |
| Cloudflare may cache the 308 response indefinitely | Set `Cache-Control: max-age=3600` on redirect responses, not indefinitely |
| The `/remote-ops` page is a client component (`"use client"`) — its hooks (`useRemoteOps`) must be adapted for the server-rendered `/nodes` page | Extract the interactive control panel into a `"use client"` sub-component; keep the rest of `/nodes` as a server component |

---

## Known Gaps and Follow-up Tasks

1. **Section tab/accordion UI**: When `/nodes` and `/pipeline` absorb more content, a tab or accordion pattern within each page will improve scannability. This is a polish task — out of scope here.
2. **Usage as a standalone report**: The paginated runtime cost view in `/usage` is a report, not a navigation destination. Consider exposing it as `/pipeline/report` or `/pipeline?view=cost` in a follow-up spec.
3. **Automation page metadata**: The `/automation` page has an SEO meta description about "provider automation readiness". After the redirect, `/nodes` metadata should be updated to cover this use-case explicitly.
4. **CI lint rule**: Add a CI step (`grep -r 'href="/automation"' web/ && exit 1 || exit 0`) to prevent future regressions where someone adds a link back to the deprecated routes.
5. **Analytics**: If page-view tracking is in place, deprecate the `/automation`, `/usage`, and `/remote-ops` event types and ensure `/nodes` and `/pipeline` event counts rise proportionally.
