# Spec: Heal Completion → Issue Resolution

**Idea ID**: 047-heal-completion-issue-resolution
**Status**: Ready for Implementation
**Last Updated**: 2026-03-28

---

## Summary

When a heal task completes and the related monitor condition clears on the next check, the pipeline must
record that resolution for effectiveness measurement and, optionally, persist the resolution in
`monitor_issues.json` so operators and APIs can see which issues were resolved (and whether a heal task
was attributed). This closes the loop between "monitor created heal" and "condition cleared" and supports
`heal_resolved_count` and auditability.

---

## Goal

Close the failure → heal → resolution loop by:

1. Ensuring resolution records always carry the originating `heal_task_id` (when present) into `monitor_resolutions.jsonl`.
2. Optionally persisting a capped `resolved` array in `monitor_issues.json` when `MONITOR_PERSIST_RESOLVED=1`.
3. Exposing that `resolved` array through `GET /api/agent/monitor-issues` so downstream effectiveness
   measurement (Spec 115) and dashboards can attribute resolved conditions to specific heal tasks.

---

## Requirements

- [ ] **R1 — Resolution record includes heal_task_id**: When the monitor runs and a previously reported
  condition is no longer present, and that previous issue had a `heal_task_id`, the monitor **must** pass
  that `heal_task_id` into the resolution record appended to `api/logs/monitor_resolutions.jsonl`.

- [ ] **R2 — JSONL resolution record format**: Each line in `monitor_resolutions.jsonl`:
  ```json
  { "condition": "<string>", "resolved_at": "<ISO8601 UTC>", "heal_task_id": "<string or omitted>" }
  ```

- [ ] **R3 — Optional auto-resolve in monitor_issues.json**: When `MONITOR_PERSIST_RESOLVED=1` (env var),
  when a condition clears the monitor persists the resolution in `monitor_issues.json` by appending a
  resolved entry to a `resolved` array. Array fields per entry:
  - `condition` (required, string)
  - `resolved_at` (required, ISO8601 UTC string)
  - `heal_task_id` (optional, string)
  - `issue_id` (optional, string)

- [ ] **R4 — Cap resolved array**: The `resolved` array in `monitor_issues.json` is capped at the last
  50 entries to avoid unbounded growth.

- [ ] **R5 — GET /api/agent/monitor-issues passes through resolved**: When `monitor_issues.json` contains
  a `resolved` field, the API response includes it. When absent, the response continues to return
  `{ "issues": [], "last_check": null }` without error.

- [ ] **R6 — Open issues semantics unchanged**: The `issues` array remains the current list of conditions
  currently firing. Resolved entries are for audit/recent-resolution visibility only.

---

## API Contract

### `GET /api/agent/monitor-issues`

**Response 200 — base shape (unchanged)**:
```json
{
  "issues": [ ... ],
  "last_check": "2026-03-28T06:00:00Z",
  "history": [ ... ],
  "resolved_since_last": [ "condition_name" ]
}
```

**Response 200 — with optional persist-resolved enabled**:
```json
{
  "issues": [ ... ],
  "last_check": "2026-03-28T06:00:00Z",
  "history": [ ... ],
  "resolved_since_last": [ "condition_name" ],
  "resolved": [
    {
      "condition": "stale_running_tasks",
      "resolved_at": "2026-03-28T06:00:00Z",
      "heal_task_id": "task_abc123",
      "issue_id": "issue_xyz"
    }
  ]
}
```

**Response 404**: `monitor_issues.json` does not exist → `{ "issues": [], "last_check": null }`.
**Response 422**: Invalid query parameters (not applicable; no query params).

### Resolution Record (`api/logs/monitor_resolutions.jsonl`)

Each newline-delimited JSON entry:
```json
{ "condition": "stale_running_tasks", "resolved_at": "2026-03-28T06:00:00Z", "heal_task_id": "task_abc123" }
```
When no `heal_task_id` exists, the field is omitted (not null).

---

## Data Model

**monitor_issues.json** (persisted by monitor pipeline):

```yaml
issues:
  - id: string
    condition: string
    severity: string
    priority: string
    message: string
    suggested_action: string
    created_at: ISO8601
    resolved_at: null         # null = open
    heal_task_id: string?     # optional

last_check: string | null
history:
  - at: ISO8601
    condition: string
    severity: string
resolved_since_last: [string]   # condition names cleared this run

resolved:                        # NEW OPTIONAL field (when MONITOR_PERSIST_RESOLVED=1)
  - condition: string
    resolved_at: ISO8601
    heal_task_id: string?
    issue_id: string?
    # array capped at last 50 entries
```

---

## Files to Create/Modify

| File | Change |
|------|--------|
| `api/scripts/monitor_pipeline.py` | Ensure `_record_resolution()` always includes `heal_task_id` from previous issue when condition clears; add optional persistence of resolved entries to `monitor_issues.json` (`resolved` array, capped at 50) when `MONITOR_PERSIST_RESOLVED=1`. |
| `docs/PIPELINE-MONITORING-AUTOMATED.md` | Document resolution recording, optional persist-resolved behavior, env var `MONITOR_PERSIST_RESOLVED`, and updated response shape. |

No schema migrations. No new database tables. Filesystem only.

---

## Verification Scenarios

> These scenarios are the acceptance contract. The reviewer will run them against the production API
> and the monitor pipeline. Failure of any scenario = feature not done.

### Scenario 1 — Resolution record written with heal_task_id

**Setup**: `api/logs/monitor_issues.json` exists with one open issue:
```json
{
  "issues": [{ "id": "i1", "condition": "stale_running_tasks", "heal_task_id": "task_abc123", "resolved_at": null }],
  "last_check": "2026-03-28T05:00:00Z",
  "resolved_since_last": []
}
```
`api/logs/monitor_resolutions.jsonl` exists (possibly empty).

**Action**: Run monitor pipeline so `stale_running_tasks` condition is no longer detected.
Simulated in tests via `api/tests/test_auto_heal_service.py` with a mocked condition check that returns
no issues on the second pass.

**Expected**:
- A new line appended to `monitor_resolutions.jsonl`:
  ```json
  { "condition": "stale_running_tasks", "resolved_at": "<ISO8601>", "heal_task_id": "task_abc123" }
  ```
- `resolved_at` is a valid ISO 8601 UTC timestamp (ends with `Z` or `+00:00`).
- `heal_task_id` equals `"task_abc123"`.

**Edge — no heal_task_id**: If the previous issue had no `heal_task_id`, the resolution record must be
written **without** a `heal_task_id` field (field omitted, not `null`).

---

### Scenario 2 — Optional persist-resolved writes to monitor_issues.json

**Setup**: `MONITOR_PERSIST_RESOLVED=1` is set. `monitor_issues.json` has one open issue with
`heal_task_id: "task_def456"` for condition `"no_task_running"`. The `resolved` array does not yet exist.

**Action**: Monitor runs and `no_task_running` condition clears.

**Expected**:
- `monitor_issues.json` now contains a `resolved` array with one entry:
  ```json
  { "condition": "no_task_running", "resolved_at": "<ISO8601>", "heal_task_id": "task_def456" }
  ```
- The `issues` array no longer contains `no_task_running`.

**Edge — cap at 50**: If `resolved` already contains 50 entries and a new condition clears, the array
length stays at 50 (oldest entry dropped, newest appended).

---

### Scenario 3 — GET /api/agent/monitor-issues passes through resolved array

**Setup**: `monitor_issues.json` on the API server has:
```json
{
  "issues": [],
  "last_check": "2026-03-28T06:00:00Z",
  "resolved": [
    { "condition": "stale_running_tasks", "resolved_at": "2026-03-28T06:00:00Z", "heal_task_id": "task_abc123" }
  ]
}
```

**Action**:
```bash
API=https://api.coherencycoin.com
curl -s "$API/api/agent/monitor-issues"
```

**Expected**:
- HTTP 200
- Response JSON contains `"resolved"` array with at least one entry.
- Entry has `condition`, `resolved_at`, and `heal_task_id` fields matching the file content.
- `issues` is an empty array (no open issues).

**Edge — no resolved field**: If `monitor_issues.json` has no `resolved` key:
```bash
curl -s "$API/api/agent/monitor-issues"
```
Response is HTTP 200 with `{ "issues": [], "last_check": ..., "history": [...] }` — no `"resolved"` key,
no error, no 500.

---

### Scenario 4 — Full create-read cycle with attribution

**Setup**: No monitor_issues.json. No monitor_resolutions.jsonl. `MONITOR_PERSIST_RESOLVED=1`.

**Step 1 — condition fires**: Run monitor pipeline with a detected condition `"high_queue_depth"`.
Verify `monitor_issues.json` has `issues` array with one entry for `high_queue_depth`, `resolved_at: null`.

**Step 2 — heal task created**: Monitor creates a heal task via `POST /api/agent/tasks`.
Verify `monitor_issues.json` has the issue with `heal_task_id` set.

**Step 3 — condition clears**: Run monitor pipeline with no conditions detected.
Verify:
```bash
# monitor_resolutions.jsonl has the resolution
tail -1 api/logs/monitor_resolutions.jsonl | python3 -c "import sys,json; r=json.load(sys.stdin); assert r['condition']=='high_queue_depth'; assert 'heal_task_id' in r; print('PASS')"

# monitor_issues.json has resolved entry
python3 -c "import json; d=json.load(open('api/logs/monitor_issues.json')); assert any(r['condition']=='high_queue_depth' for r in d.get('resolved',[])); print('PASS')"
```

**Step 4 — API read**: `GET /api/agent/monitor-issues` returns `issues: []` and `resolved` contains
`high_queue_depth` entry with correct `heal_task_id` and valid `resolved_at`.

**Edge — duplicate resolution on re-trigger**: If monitor runs again and condition fires again then
clears again, a new entry is appended to `resolved` (deduplication not required; entries are time-stamped).

---

### Scenario 5 — Error handling: missing file and bad state

**Setup 1 — file missing**: `monitor_issues.json` does not exist.
**Action**: `GET /api/agent/monitor-issues`
**Expected**: HTTP 200, `{ "issues": [], "last_check": null }`. No 500 error.

**Setup 2 — corrupted file**: `monitor_issues.json` contains `{ "not": "valid json issues" }` (wrong shape).
**Action**: `GET /api/agent/monitor-issues`
**Expected**: HTTP 200 with graceful fallback — either `{ "issues": [], "last_check": null }` or whatever
the file contains as-is. Must not return HTTP 500.

**Setup 3 — monitor_resolutions.jsonl unwritable**: Permissions on `monitor_resolutions.jsonl` set to
read-only (mode 444).
**Action**: Monitor runs and a condition clears.
**Expected**: Monitor logs a warning (`"Could not record resolution: ..."`) and continues without crashing.
The next monitor run completes normally. No unhandled exception propagates.

---

## Acceptance Tests

```bash
python3 -m pytest api/tests/test_auto_heal_service.py -x -v
```

All existing tests must pass. Do not modify tests to force passing behavior.

New tests may be added to `api/tests/test_auto_heal_service.py` or a new file
`api/tests/test_monitor_resolution.py` covering:

- Resolution record includes `heal_task_id` when previous issue had one.
- Resolution record omits `heal_task_id` when previous issue had none.
- `MONITOR_PERSIST_RESOLVED=1` writes `resolved` array to `monitor_issues.json`.
- Cap at 50 entries is enforced.
- API `GET /api/agent/monitor-issues` passes through `resolved` field when present.
- API returns 200 with fallback when `monitor_issues.json` is absent.

---

## Out of Scope

- Changing how heal tasks are created or how conditions are detected.
- Webhook or callback when a heal task completes (resolution is detected on next monitor check only).
- Changing `heal_resolved_count` formula or effectiveness response shape beyond exposing optional
  `resolved` in monitor-issues response.
- UI changes for resolved issue display.
- Database storage of resolutions (filesystem only for MVP).

---

## Upstream Dependencies

- **Spec 114** ([114-auto-heal-from-diagnostics.md](114-auto-heal-from-diagnostics.md)) — Auto-generates
  heal tasks from failed task error classifications. The `heal_task_id` tracked in this spec's resolution
  records originates from Spec 114's `maybe_create_heal_task()`.
- **Spec 115** ([115-grounded-cost-value-measurement.md](115-grounded-cost-value-measurement.md)) — Uses
  `heal_attempt` and `heal_succeeded` as value signals. Resolution tracking from this spec feeds back into
  Spec 115's grounded value computation.

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| File write race conditions on `monitor_issues.json` | MVP: last-write-wins; document known limitation |
| `resolved` array growing unbounded if cap not enforced | Cap enforced at write time (keep last 50) |
| `heal_task_id` attribution misfire if condition recurs | Entries are timestamped; no deduplication assumed |
| New env var `MONITOR_PERSIST_RESOLVED` requires documentation | Document in `docs/PIPELINE-MONITORING-AUTOMATED.md` and RUNBOOK |
| No auth on monitor-issues endpoint | Known gap; tracked under auth middleware milestone |

---

## Known Gaps and Follow-up Tasks

- [ ] Distributed locking for multi-worker deployments (currently last-write-wins).
- [ ] Rate limiting on `GET /api/agent/monitor-issues`.
- [ ] Auth gate (`MONITOR_PERSIST_RESOLVED` feature is internal; endpoint exposure needs auth).
- [ ] Expose `heal_resolved_count` in `GET /api/agent/effectiveness` using `resolved` records as source.
- [ ] Consider `MONITOR_PERSIST_RESOLVED` default-on after stabilization (currently opt-in).

---

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required for reads.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

---

## Failure and Retry Behavior

- **Resolution write failure**: Log warning via `log.debug("Could not record resolution: ...")`, continue
  pipeline execution without crash.
- **File permission error**: Caught and logged; monitor pipeline continues to next condition check.
- **Malformed `monitor_issues.json`**: Monitor reads with try/except; initializes fresh data structure on
  parse failure.

---

## See Also

- [007-meta-pipeline-backlog.md](007-meta-pipeline-backlog.md) — Item 2 (this spec); Item 5 (heal task effectiveness tracking / heal_resolved_count).
- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — `GET /api/agent/monitor-issues`, `GET /api/agent/effectiveness`.
- [114-auto-heal-from-diagnostics.md](114-auto-heal-from-diagnostics.md) — Source of heal tasks tracked here.
- [docs/PIPELINE-MONITORING-AUTOMATED.md](../docs/PIPELINE-MONITORING-AUTOMATED.md) — Monitor flow, resolution tracking, issue shape.
