# Spec 161: Node and Task Visibility — `cc tasks`, `cc task <id>`, Web Pipeline Dashboard

**Idea ID**: `node-task-visibility`
**Status**: Draft — 2026-03-28
**Author**: product-manager agent (task_d73edbae8000792b)

---

## Summary

Operators and contributors have no ergonomic way to observe what the pipeline is doing. The only way to inspect tasks is by issuing raw `curl` commands against the API. This spec formalises three distinct observability surfaces:

1. **`cc tasks`** — human-readable terminal overview of the live task queue
2. **`cc task <id>`** — full task detail including output, errors, and activity timeline
3. **Web `/pipeline` page** — a live dashboard showing task flow, node status, and provider performance

---

## Problem Statement

### Current Pain Points

| Surface | Current state | Gap |
|---------|--------------|-----|
| `cc tasks` | Lists running/pending/needs_decision. Shows `idea_id` (e.g. `node-task-visibility`) and raw model string (`openrouter/free`). | Idea **name** not resolved; no "recent completions"; provider label unclear |
| `cc task <id>` | Shows status, type, direction (200 chars), idea_id, worker, result (200 chars). | Output truncated; activity/events not shown; errors not formatted; no timing |
| Web `/tasks` page | Exists at `coherencycoin.com/tasks`. Shows task list with paginated rows. | Not a real-time pipeline view; no per-node status; no provider success rates; no routing signal |
| API | Endpoints exist for tasks, active, activity. | No single aggregated `/pipeline/summary` endpoint; `result` field is raw JSON, not rendered |

### Who This Affects

- **Human contributors** running `cc` locally: need to know what's running, which ideas are advancing, if their node is processing tasks.
- **Operators** monitoring pipeline health: need provider success rates and routing decisions visible.
- **New visitors** to the web app: the homepage says the network is alive — the `/pipeline` page must prove it.

---

## Requirements

### R1 — `cc tasks`: Human-Readable Task List

- **R1.1** Resolve `idea_id` → `idea_name` for all displayed tasks. Display as: `"Idea: <name>"` not `"idea: <id>"`.
- **R1.2** Display provider as clean label: `claude`, `codex`, `gemini`, `cursor`, `openrouter` — not the raw model string `openrouter/free` or `claude/claude-sonnet-4-6`.
- **R1.3** Add a "recently completed" section showing the last 5 completed tasks (with idea name, type, duration, provider, and pass/fail).
- **R1.4** Show task `task_type` as a human label: `spec`, `impl`, `test`, `review`, `deploy`, `verify` — not raw strings like `"impl"` (already correct) but never raw JSON.
- **R1.5** `cc tasks <status>` (e.g. `cc tasks failed`) must also resolve idea names and providers.
- **R1.6** Output must be fully human-readable in a terminal without needing `jq` or `curl`.

### R2 — `cc task <id>`: Full Task Detail

- **R2.1** Show the full `result`/`output` field — not truncated. If output > 2000 chars, paginate with `--full` flag or show first 2000 chars with a notice `(output truncated, use --full to see all)`.
- **R2.2** Show `error_summary` and `error_category` when present and non-null.
- **R2.3** Show the activity timeline: fetch `/api/agent/tasks/{id}/activity` and render as a chronological list of events with human-readable labels (not raw `event_type` codes).
- **R2.4** Resolve `idea_id` → `idea_name` in the header.
- **R2.5** Show timing: `created_at`, `claimed_at`, elapsed duration, and `duration_s` from completion event.
- **R2.6** Show provider/model as separate fields: `Provider: claude`, `Model: claude-sonnet-4-6`.
- **R2.7** Show `claimed_by` as the worker name (strip hash suffixes when possible, e.g. `The-Seeker:133172` → `The-Seeker`).
- **R2.8** Show routing decision summary: which executor was selected and why (from `context.route_decision.policy.reason`).

### R3 — Web `/pipeline` Page

- **R3.1** Create route `web/app/pipeline/page.tsx`. The page must be accessible at `coherencycoin.com/pipeline`.
- **R3.2** **Live activity panel** — show the last 30 activity events from `GET /api/agent/tasks/activity`. Auto-refresh every 10 seconds (or SSE if available). Each event shows: timestamp (relative), task type, idea name, node name, provider, event type.
- **R3.3** **Active tasks panel** — show all currently running tasks from `GET /api/agent/tasks/active`. Each row: idea name, task type, provider, node name, elapsed time (live counting).
- **R3.4** **Provider success rates panel** — compute and display per-provider success/failure stats from recent completed tasks. Columns: Provider, Tasks run, Success %, Avg duration. Computed client-side from `GET /api/agent/tasks?status=completed&limit=200`.
- **R3.5** **Queue depth panel** — show count of `pending`, `running`, `failed`, `needs_decision` tasks as stat cards.
- **R3.6** **Node status** — derive active nodes from `GET /api/agent/tasks/active`. Show unique nodes with task count and last-seen time.
- **R3.7** Page must work without authentication.
- **R3.8** Page must load with meaningful data within 2 seconds on a standard connection.
- **R3.9** Add `/pipeline` to the web navigation sidebar.

### R4 — API: Pipeline Summary Endpoint (Optional but Preferred)

- **R4.1** `GET /api/pipeline/summary` returns an aggregated snapshot:
  ```json
  {
    "active_tasks": [...],
    "queue_depth": {"pending": N, "running": N, "failed": N, "needs_decision": N},
    "active_nodes": [{"name": "...", "task_count": N, "last_seen": "..."}],
    "provider_stats": [{"provider": "claude", "total": N, "success": N, "avg_duration_s": N}],
    "recent_activity": [...]
  }
  ```
- **R4.2** This endpoint may be computed on-the-fly (no new DB tables required).
- **R4.3** Response time < 500ms (uses cached data or efficient queries).

### R5 — Task Output Human-Readability

- **R5.1** When displaying task output that contains only an error message like `"Worktree creation failed..."`, the CLI and web must label it clearly as an error, not render it as generic output.
- **R5.2** When `task.output` or `task.result` is a JSON string, attempt to parse and extract a `summary` or `message` key for display. Fall back to raw string if no structured key found.
- **R5.3** The `direction` field (task instruction) must be truncatable with `... (truncated)` in list views. Full direction shows in detail view (`cc task <id>`) without truncation.

---

## Task Card

```yaml
goal: >
  Make pipeline activity visible to human contributors via CLI and web without
  requiring curl. cc tasks and cc task <id> must resolve idea names and show
  clean output. /pipeline web page must show live task flow, node status,
  and provider success rates.
files_allowed:
  - cli/lib/commands/tasks.mjs
  - web/app/pipeline/page.tsx
  - web/app/pipeline/components/*.tsx
  - web/components/nav/sidebar.tsx
  - api/app/routers/pipeline.py
  - api/app/main.py
done_when:
  - cc tasks shows idea names (not IDs) and clean provider labels
  - cc tasks shows a "recently completed" section
  - cc task <id> shows full (untruncated) output and activity timeline
  - cc task <id> shows error_summary when present
  - coherencycoin.com/pipeline loads and shows live task flow
  - /pipeline shows per-provider success rates
  - /pipeline shows active node names and task counts
commands:
  - node cli/bin/cc.mjs tasks
  - node cli/bin/cc.mjs task task_d73edbae8000792b
  - curl -s https://api.coherencycoin.com/api/pipeline/summary
  - curl -sI https://coherencycoin.com/pipeline
constraints:
  - No new database tables required for R4 (compute on-the-fly or cache in memory)
  - CLI must remain zero-dependency (no new npm packages)
  - Web page must use existing shadcn/ui components
  - Must not break existing /tasks page
```

---

## API Contract

### Existing Endpoints Used

| Endpoint | Used by | Notes |
|----------|---------|-------|
| `GET /api/agent/tasks?status=<s>&limit=<n>` | CLI R1, Web R3.5 | Already exists |
| `GET /api/agent/tasks/{id}` | CLI R2 | Already exists |
| `GET /api/agent/tasks/{id}/activity` | CLI R2.3 | Already exists |
| `GET /api/agent/tasks/active` | Web R3.3, R3.6 | Already exists |
| `GET /api/agent/tasks/activity?limit=30` | Web R3.2 | Already exists |
| `GET /api/ideas/{id}` | CLI R1.1, R2.4 | For name resolution |
| `GET /api/ideas?limit=500` | Web R3 | Bulk name lookup |

### New Endpoint (R4)

**`GET /api/pipeline/summary`**

```
Response 200:
{
  "active_tasks": [
    {
      "id": "task_abc123",
      "idea_id": "node-task-visibility",
      "idea_name": "Node and task visibility",
      "task_type": "spec",
      "provider": "claude",
      "model": "claude-sonnet-4-6",
      "node_name": "The-Seeker",
      "claimed_at": "2026-03-28T06:29:22Z",
      "elapsed_s": 94
    }
  ],
  "queue_depth": {
    "pending": 3,
    "running": 2,
    "failed": 1,
    "needs_decision": 0
  },
  "active_nodes": [
    {
      "name": "The-Seeker",
      "task_count": 1,
      "providers": ["claude"],
      "last_seen": "2026-03-28T06:30:28Z"
    }
  ],
  "provider_stats": [
    {
      "provider": "claude",
      "total": 45,
      "success": 42,
      "failed": 3,
      "success_rate": 0.933,
      "avg_duration_s": 310
    }
  ],
  "recent_activity": [
    {
      "task_id": "task_abc123",
      "idea_name": "Node and task visibility",
      "task_type": "spec",
      "node_name": "The-Seeker",
      "provider": "claude",
      "event_type": "heartbeat",
      "elapsed_s": 94,
      "timestamp": "2026-03-28T06:30:28Z"
    }
  ],
  "generated_at": "2026-03-28T06:31:00Z"
}
```

**Implementation note**: Compute `provider_stats` from `SELECT status, model, created_at, updated_at FROM agent_tasks WHERE created_at > NOW() - INTERVAL '24 hours'`. Parse `model` field as `provider/model-name` and aggregate. No new table needed.

---

## Data Model

No new tables. All data is derived from:

- `agent_tasks` table — tasks with status, model, context (idea_id), timing
- `agent_activity` table — event stream per task
- `ideas` table — idea names

### CLI Name Resolution Strategy

`cc tasks` must resolve idea names without N+1 API calls. Strategy:
1. Collect all unique `idea_id` values from the task batch.
2. Issue one `GET /api/ideas?ids=id1,id2,...` (if supported) OR fall back to individual `GET /api/ideas/{id}` calls in parallel (Promise.all).
3. Cache resolved names in-process for the duration of the command.

If the API does not support `?ids=...` filtering, the CLI falls back to parallel fetches capped at 10 concurrent requests.

---

## Files to Create / Modify

| File | Action | Scope |
|------|--------|-------|
| `cli/lib/commands/tasks.mjs` | Modify | R1, R2: resolve names, fix output, add activity timeline |
| `web/app/pipeline/page.tsx` | Create | R3: new pipeline dashboard page |
| `web/app/pipeline/components/ActiveTasksPanel.tsx` | Create | R3.3 active tasks |
| `web/app/pipeline/components/ProviderStatsPanel.tsx` | Create | R3.4 provider stats |
| `web/app/pipeline/components/ActivityFeed.tsx` | Create | R3.2 activity feed |
| `web/app/pipeline/components/QueueDepthCards.tsx` | Create | R3.5 queue depth |
| `web/app/pipeline/components/NodeStatusPanel.tsx` | Create | R3.6 node status |
| `web/components/nav/sidebar.tsx` | Modify | R3.9: add Pipeline nav link |
| `api/app/routers/pipeline.py` | Create | R4: `/api/pipeline/summary` |
| `api/app/main.py` | Modify | R4: register pipeline router |

---

## Verification Scenarios

### Scenario 1 — `cc tasks` shows idea names, not IDs

**Setup**: At least 1 pending or running task exists with an `idea_id` (e.g. `node-task-visibility`).

**Action**:
```bash
node cli/bin/cc.mjs tasks
```

**Expected**:
- Output contains `"Node and task visibility"` (the idea name) — NOT the raw ID `node-task-visibility`.
- Provider is displayed as `claude`, `codex`, `cursor`, `gemini`, or `openrouter` — NOT `claude/claude-sonnet-4-6` or `openrouter/free`.
- A "recently completed" section appears with at least 1 row showing idea name, type, provider, and duration.

**Edge cases**:
- Task with no `idea_id` in context: display `(no idea)` instead of crashing.
- API returns 404 for an idea ID: display `idea_id` as fallback, not an error.
- Empty pipeline: display `"Pipeline idle. No active tasks."` — not an empty table or crash.

---

### Scenario 2 — `cc task <id>` shows full output and activity timeline

**Setup**: A completed task exists with known ID (e.g. `task_d73edbae8000792b`).

**Action**:
```bash
node cli/bin/cc.mjs task task_d73edbae8000792b
```

**Expected**:
- Output includes the full `result` or `output` field — not truncated at 200 chars.
- Shows `Idea: Node and task visibility — cc tasks, cc task <id>, web pipeline dashboard` (resolved name).
- Shows `Provider: claude` and `Model: claude-sonnet-4-6` as separate lines.
- Shows timing: `Created: 2026-03-28 06:29:22 UTC`, `Claimed: ...`, `Duration: ...`.
- Shows an activity timeline section listing events in order (e.g. `06:29:24 agent_heartbeat: step=researching existing CLI and API state`).
- Shows `Worker: The-Seeker` (not `The-Seeker:133172`).

**Edge cases**:
- Task ID does not exist: `Task not found: task_xyz` — not a crash or empty output.
- Task has `error_summary` set: error is displayed prominently with a red `✗` prefix.
- Task `result` is valid JSON: extract and display `summary` or `message` key if present.
- Output > 2000 chars: show first 2000 chars and append `(+N chars, use --full to see all)`.

---

### Scenario 3 — Web `/pipeline` page loads with live data

**Setup**: The system has at least 1 running task and 5+ completed tasks in the last 24 hours.

**Action**:
```bash
curl -sI https://coherencycoin.com/pipeline
```
Then open `https://coherencycoin.com/pipeline` in a browser.

**Expected**:
- HTTP 200 response.
- Page renders within 2 seconds.
- Queue depth cards show `pending: N`, `running: N` with actual numbers (not 0/0 unless truly empty).
- Active tasks panel shows idea name (not idea_id), task type, provider, node name, and live elapsed time.
- Provider stats panel shows at least `claude` with a success rate > 0%.
- Activity feed shows at least 5 recent events with human-readable timestamps (e.g. "2 minutes ago").
- Node status panel shows at least 1 active node with name "The-Seeker" or "Urss-MacBook-Pro.local".

**Edge cases**:
- Pipeline is idle (no running tasks): queue depth cards show 0/0; active tasks shows `"No tasks running"` — not an error.
- API down: page shows `"Pipeline data unavailable"` with a retry button — not a crash or blank screen.
- Auto-refresh: after 10 seconds, data updates without a full page reload.

---

### Scenario 4 — `GET /api/pipeline/summary` returns structured data

**Setup**: Normal pipeline operation.

**Action**:
```bash
curl -s https://api.coherencycoin.com/api/pipeline/summary | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('active_tasks:', len(d['active_tasks']))
print('queue pending:', d['queue_depth']['pending'])
print('provider_stats count:', len(d['provider_stats']))
print('active_nodes:', len(d['active_nodes']))
"
```

**Expected**:
- HTTP 200.
- `active_tasks` is a list (length >= 0).
- `queue_depth` contains keys `pending`, `running`, `failed`, `needs_decision` all as integers.
- `provider_stats` contains at least 1 entry with `provider`, `total`, `success`, `success_rate`, `avg_duration_s`.
- `active_nodes` contains at least 1 entry with `name`, `task_count`, `last_seen`.
- `generated_at` is a valid ISO 8601 UTC timestamp.

**Edge cases**:
- Empty pipeline: all lists are `[]`, queue depths are `0` — not `null` or missing keys.
- Invalid query parameter: `GET /api/pipeline/summary?window=bad` returns 422, not 500.

---

### Scenario 5 — Navigation and discoverability

**Setup**: Web app is deployed at `coherencycoin.com`.

**Action**:
Open `https://coherencycoin.com` in a browser. Navigate to the pipeline page.

**Expected**:
- Sidebar or nav contains a `"Pipeline"` link.
- Clicking `"Pipeline"` navigates to `coherencycoin.com/pipeline`.
- The `/pipeline` route returns HTTP 200.
- On mobile (< 768px), the page is usable (not broken layout).

**Edge cases**:
- Direct navigation to `coherencycoin.com/pipeline` without clicking the nav link works (no 404).
- The existing `/tasks` page at `coherencycoin.com/tasks` still works after nav changes.

---

## Risks and Assumptions

### Risks

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Idea name resolution adds N API calls | Latency in `cc tasks` | Batch fetch with `Promise.all`; cache in-process |
| `provider_stats` aggregation is slow on large tables | Slow `/api/pipeline/summary` | Add 60s TTL in-memory cache; limit to 24h window |
| `result` field contains raw execution output (hundreds KB) | `cc task <id>` hangs terminal | Default to first 2000 chars; `--full` for complete output |
| SSE/live refresh conflicts with Cloudflare CDN caching | Stale data on web page | Use 10s poll interval as fallback; set `Cache-Control: no-store` on `/api/pipeline/summary` |
| CLI `tasks.mjs` has no test coverage | Regressions hard to detect | Add integration test in `cli/tests/tasks.test.mjs` |

### Assumptions

- `GET /api/ideas/{id}` returns `{ id, name, ... }` — the `name` field is the human-readable title.
- `GET /api/agent/tasks/active` returns activity records, not task records (confirmed from API output above).
- The `model` field on tasks follows the pattern `provider/model-name` (e.g. `claude/claude-sonnet-4-6`, `openrouter/free`). Provider is derived by splitting on `/`.
- The web app uses shadcn/ui `Card`, `Badge`, and `Table` components (already in use on `/tasks`).
- The sidebar component is at `web/components/nav/sidebar.tsx` or similar.

---

## Known Gaps and Follow-up Tasks

1. **`cc tasks watch`** — a live terminal refresh mode (like `watch -n2 cc tasks`) is not in scope here but would complement this spec. Track as separate idea.
2. **Thompson Sampling visibility** — provider routing decisions (which executor is winning, exploration vs exploitation ratio) are not exposed in this spec. The pipeline page shows success rates but not the internal sampling state. Track as `spec-thompson-visibility`.
3. **Task output storage** — currently `result` is a plain string. A follow-up should store structured output with sections (files changed, DIF score, commit SHA) as JSON. This spec only improves display of the existing field.
4. **`GET /api/ideas?ids=id1,id2`** bulk endpoint — not confirmed to exist. If missing, the CLI falls back to parallel individual fetches. A follow-up spec should add this endpoint.
5. **Pipeline page SSE** — R3.2 specifies 10s poll as baseline. A follow-up can upgrade to SSE using the existing `/api/agent/tasks/{id}/events` pattern extended to a global stream endpoint.

---

## Evidence of Realization

This spec is realized when ALL of the following are independently verifiable:

1. `node cli/bin/cc.mjs tasks` output contains a full idea name (not a raw ID) for any running task.
2. `node cli/bin/cc.mjs task <any-completed-task-id>` output contains the full untruncated result.
3. `curl -s https://api.coherencycoin.com/api/pipeline/summary | jq .queue_depth` returns a JSON object with integer values.
4. `curl -sI https://coherencycoin.com/pipeline` returns `HTTP/2 200`.
5. A screenshot of `coherencycoin.com/pipeline` showing at least one active task with an idea name is posted to the project's contributor record.

The reviewer MUST run scenarios 1–4 from a clean terminal with no local setup (public endpoints only). Scenario 5 is verified by loading the URL in an incognito browser window.
