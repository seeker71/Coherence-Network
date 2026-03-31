# Spec 156: Tasks page shows fetch error and zero counts despite active tasks

## Purpose

Restore the `/tasks` page as a reliable, contributor-facing pipeline surface by removing "Failed to fetch" failures and ensuring counters/list data reflect real task state. New contributors must be able to open the page and immediately see active pending, running, and completed tasks without manual debugging.

## Requirements

- [ ] The `/tasks` page must load without a browser fetch exception when the API is healthy.
- [ ] Counters on `/tasks` must reflect the same totals as the tasks API response for `pending`, `running`, and `completed`.
- [ ] The page must fetch via the intended app route (same-origin proxied path), not a mismatched cross-origin endpoint.
- [ ] When task data exists, at least one non-zero counter must render non-zero and the task list must show corresponding items.
- [ ] When the fetch fails, the UI must show an explicit error state with retry action and preserve diagnostic detail (error type/message).
- [ ] Zero-state UI may only appear when the API call succeeds and returns zero tasks.

## Research Inputs (Required)

- `2026-03-26` - [Spec Template](./TEMPLATE.md) - required section structure and quality bar.
- `2026-03-26` - [Spec 155: tasks page fetch error](./155-tasks-page-fetch-error.md) - prior CORS/proxy context and related risks.

## Task Card (Required)

```yaml
goal: Fix /tasks so counters and list render real task data and show a correct fallback on fetch failures.
files_allowed:
  - web/app/tasks/page.tsx
  - web/lib/api.ts
  - web/next.config.ts
  - web/tests/tasks-page.spec.ts
  - api/app/routers/agent.py
done_when:
  - /tasks renders task counters matching API totals for pending/running/completed in a healthy environment.
  - /tasks error state appears with actionable retry when API fetch fails.
  - Browser network calls for task data use intended same-origin/proxied route instead of mismatched cross-origin URL.
commands:
  - cd web && npm run build
  - cd web && npm run test -- tasks-page
  - cd api && .venv/bin/pytest -v tests/test_agent_tasks.py
constraints:
  - Do not redesign unrelated pages.
  - Do not modify tests solely to force pass; fix implementation.
  - Keep endpoint and response schema backward compatible.
```

## API Contract (if applicable)

### `GET /api/agent/tasks`

**Request**
- Optional query params:
  - `status`: one of `pending | running | completed | failed` (if supported in current router)
  - `limit`: integer > 0
  - `offset`: integer >= 0

**Response 200**
```json
{
  "items": [
    {
      "id": "task_abc123",
      "status": "running",
      "task_type": "impl",
      "direction": "Fix tasks page fetch behavior",
      "created_at": "2026-03-26T10:00:00Z",
      "updated_at": "2026-03-26T10:03:00Z"
    }
  ],
  "total": 12,
  "counts": {
    "pending": 3,
    "running": 2,
    "completed": 6,
    "failed": 1
  }
}
```

**Response 5xx / network failure (UI expectation)**
- UI must show:
  - title/text indicating task data could not be loaded
  - captured error string (for example `TypeError: Failed to fetch`)
  - retry control that re-attempts fetch without page reload
- UI counters must not silently show misleading "0" as if success. They must either:
  - display a loading/unknown placeholder, or
  - be visually marked unavailable in error state

If response schema differs today, implementation may adapt mapping, but resulting UI behavior above is mandatory.

## Data Model (if applicable)

```yaml
TaskPageViewModel:
  properties:
    items:
      type: array
      items: TaskSummary
    counts:
      type: object
      required: [pending, running, completed]
      properties:
        pending: { type: integer, minimum: 0 }
        running: { type: integer, minimum: 0 }
        completed: { type: integer, minimum: 0 }
        failed: { type: integer, minimum: 0 }
    fetch_state:
      type: string
      enum: [loading, success, error]
    error_message:
      type: [string, "null"]
```

## Files to Create/Modify

- `web/app/tasks/page.tsx` - fetch flow, status/counter rendering, explicit error and retry behavior.
- `web/lib/api.ts` - API base resolution and same-origin/proxy-safe fetch behavior.
- `web/next.config.ts` - verify/adjust rewrite path consistency if mismatch exists.
- `web/tests/tasks-page.spec.ts` - integration/e2e scenarios for success, mismatch, and failure states.
- `api/app/routers/agent.py` - only if response count shape needs stabilization for deterministic UI mapping.

## Acceptance Tests

- `web/tests/tasks-page.spec.ts::renders_counts_and_items_from_api_success`
- `web/tests/tasks-page.spec.ts::shows_fetch_error_and_retry_on_network_failure`
- `web/tests/tasks-page.spec.ts::does_not_render_zero_state_when_fetch_failed`
- `api/tests/test_agent_tasks.py::test_list_tasks_includes_status_counts` (if API normalization is touched)

## Concurrency Behavior

- **Read operations**: `/tasks` fetches are idempotent and safe to run concurrently.
- **UI refresh**: when multiple fetches overlap (initial load + retry), only the latest successful response should update counters/list.
- **Error race**: a stale failure response must not overwrite a newer successful state.

## Verification

Acceptance criteria (must all pass):

1. With active tasks in API (`pending > 0` or `running > 0` or `completed > 0`), `/tasks` shows non-zero matching counters and visible list rows.
2. Browser network panel shows task data request as same-origin/proxy route (for example `/api/agent/tasks`), not a broken cross-origin URL.
3. Simulated network/API failure shows explicit error UI and retry action; counters are marked unavailable (not silently rendered as successful zeroes).
4. Triggering retry after transient failure successfully repopulates counters and list without full page reload.

Manual verification steps:

```bash
# API task data sanity
curl -s http://localhost:8000/api/agent/tasks | jq '.total, .counts'

# Web compile/type safety
cd web && npm run build

# Tasks page behavior tests
cd web && npm run test -- tasks-page
```

Expected behavior details:
- If API returns `total > 0`, rendered list length is `>= 1`.
- If API returns `counts.pending=3`, pending card displays `3` (same for running/completed).
- If fetch throws `TypeError: Failed to fetch`, error panel includes this text and retry button is enabled.

## Out of Scope

- Visual redesign of all dashboard cards and global navigation.
- Changes to task execution semantics or backend scheduling logic.
- New task filtering/sorting features beyond current behavior parity.

## Risks and Assumptions

- Assumes tasks API remains reachable through configured proxy/rewrite in all deployed environments.
- Assumes backend exposes enough status/count information (or can be derived deterministically) without breaking existing clients.
- Risk: environment-specific base URL logic (SSR vs CSR) can regress other pages; mitigation is shared API utility tests and same-origin assertions.
- Risk: temporary outages could still show error frequently; mitigation is clear retry and non-misleading counters.

## Known Gaps and Follow-up Tasks

- Add a lightweight health badge on `/tasks` (API reachable / degraded) to reduce ambiguity during outages.
- Add telemetry for task-page fetch failures (rate, error class, URL mode) to detect regressions early.
- Consider periodic auto-refresh interval once baseline reliability is restored.

## Failure/Retry Reflection

- Failure mode: wrong API base resolution in browser causes CORS/network failure.
- Blind spot: successful SSR checks mask CSR fetch path regressions.
- Next action: enforce client-side same-origin fetch assertions in tests and keep proxy path centralized.

## Decision Gates (if any)

- Confirm canonical response shape for task counts (`counts` object vs client-side aggregation) before implementation starts.
