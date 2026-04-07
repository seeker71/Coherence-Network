---
idea_id: user-surfaces
status: done
source:
  - file: web/app/nodes/page.tsx
    symbols: [node visibility]
  - file: web/app/tasks/page.tsx
    symbols: [task list]
  - file: web/app/tasks/[task_id]/page.tsx
    symbols: [task detail]
done_when:
  - "cc tasks shows idea names (not IDs) and clean provider labels"
  - "cc tasks shows a \"recently completed\" section"
  - "cc task <id> shows full (untruncated) output and activity timeline"
  - "cc task <id> shows error_summary when present"
  - "coherencycoin.com/pipeline loads and shows live task flow"
  - "/pipeline shows per-provider success rates"
  - "/pipeline shows active node names and task counts"
constraints:
  - "No new database tables required for R4 (compute on-the-fly or cache in memory)"
  - "CLI must remain zero-dependency (no new npm packages)"
  - "Web page must use existing shadcn/ui components"
  - "Must not break existing /tasks page"
---

> **Parent idea**: [user-surfaces](../ideas/user-surfaces.md)
> **Source**: [`web/app/nodes/page.tsx`](../web/app/nodes/page.tsx) | [`web/app/tasks/page.tsx`](../web/app/tasks/page.tsx) | [`web/app/tasks/[task_id]/page.tsx`](../web/app/tasks/[task_id]/page.tsx)

# Node and Task Visibility — `cc tasks`, `cc task <id>`, Web Pipeline Dashboard

**Idea ID**: `node-task-visibility`
**Status**: Draft — 2026-03-28
**Author**: product-manager agent (task_d73edbae8000792b)

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
