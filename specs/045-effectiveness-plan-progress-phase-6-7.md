# Spec: GET /api/agent/effectiveness — Plan Progress (Phase 6/7 Completion)

## Purpose

Measure progress toward PLAN.md goals by exposing Phase 6 and Phase 7 completion in GET /api/agent/effectiveness. Data is derived from project manager state and the overnight backlog (006), so monitors and dashboards can report how much of the product-critical and polish work remains.

## Requirements

- [ ] **plan_progress present:** GET /api/agent/effectiveness returns a `plan_progress` object (existing behavior retained).
- [ ] **Phase 6/7 completion:** `plan_progress` includes Phase 6 and Phase 7 completion derived from PM state and backlog (006): at least `phase_6` and `phase_7`, each with `completed`, `total`, and optionally `pct` (0–100).
- [ ] **Phase boundaries:** Phase 6 = Product-Critical (backlog items 56–57 per 006). Phase 7 = Remaining Specs & Polish (items 58–74 per 006). Boundaries are defined by specs/006-overnight-backlog.md section headers.
- [ ] **Data source:** Completion is computed from PM state (`backlog_index` in project_manager_state.json or project_manager_state_overnight.json) and total counts per phase from parsing 006-overnight-backlog.md (or equivalent backlog file).
- [ ] **Test:** A test in `api/tests/test_agent.py` calls GET /api/agent/effectiveness and asserts response includes `plan_progress` with `phase_6` and `phase_7`, each having `completed` (int), `total` (int), and that Phase 6 total is 2 and Phase 7 total is 17 when 006 is used (or equivalent when backlog changes).


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 002, 006, 007

## Task Card

```yaml
goal: Measure progress toward PLAN.
files_allowed:
  - api/app/services/effectiveness_service.py
  - api/tests/test_agent.py
done_when:
  - plan_progress present: GET /api/agent/effectiveness returns a `plan_progress` object (existing behavior retained).
  - Phase 6/7 completion: `plan_progress` includes Phase 6 and Phase 7 completion derived from PM state and backlog (006)...
  - Phase boundaries: Phase 6 = Product-Critical (backlog items 56–57 per 006). Phase 7 = Remaining Specs & Polish (items...
  - Data source: Completion is computed from PM state (`backlog_index` in project_manager_state.json or project_manager_s...
  - Test: A test in `api/tests/test_agent.py` calls GET /api/agent/effectiveness and asserts response includes `plan_prog...
commands:
  - cd api && python -m pytest api/tests/test_agent.py -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

### `GET /api/agent/effectiveness`

**Request**
- None (no query or path parameters).

**Response 200**

Existing fields (throughput, success_rate, issues, progress, goal_proximity, heal_resolved_count, top_issues_by_priority) unchanged. Extend or retain `plan_progress` as follows:

```json
{
  "throughput": { "completed_7d": 0, "tasks_per_day": 0 },
  "success_rate": 0.0,
  "issues": { "open": 0, "resolved_7d": 0 },
  "progress": { "spec": 0, "impl": 0, "test": 0, "review": 0, "heal": 0 },
  "plan_progress": {
    "index": 0,
    "total": 74,
    "pct": 0,
    "state_file": "project_manager_state.json",
    "phase_6": { "completed": 0, "total": 2, "pct": 0 },
    "phase_7": { "completed": 0, "total": 17, "pct": 0 }
  },
  "goal_proximity": 0,
  "heal_resolved_count": 0,
  "top_issues_by_priority": []
}
```

- `plan_progress.index`: current backlog index (from PM state).
- `plan_progress.total`: total backlog items (from 006).
- `plan_progress.pct`: round(100 * index / total, 1) when total > 0, else 0.
- `plan_progress.state_file`: basename of state file used, or empty string if none.
- `plan_progress.phase_6`: Phase 6 (Product-Critical) completion: `completed` = number of Phase 6 items with backlog index already passed (item number ≤ current index); `total` = 2; `pct` = round(100 * completed / total, 1).
- `plan_progress.phase_7`: Phase 7 (Remaining Specs & Polish) completion: `completed` = number of Phase 7 items with backlog index already passed; `total` = 17; `pct` = round(100 * completed / total, 1).

When backlog file is missing or unparseable, `plan_progress` may omit `phase_6`/`phase_7` or set totals to 0; `index`, `total`, `pct`, `state_file` behavior remains best-effort as today.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

```yaml
plan_progress:
  index: integer
  total: integer
  pct: number
  state_file: string
  phase_6:
    completed: integer
    total: integer
    pct: number
  phase_7:
    completed: integer
    total: integer
    pct: number
```

Phase boundaries (006): Phase 6 = items 56–57 (inclusive). Phase 7 = items 58–74 (inclusive). If 006 changes item counts, implementation parses section headers to derive totals or uses documented constants updated with backlog.

## Files to Create/Modify

- `api/app/services/effectiveness_service.py` — extend `_plan_progress()` (or equivalent) to compute Phase 6 and Phase 7 completed/total from PM state and backlog; add `phase_6` and `phase_7` to returned dict.
- `api/tests/test_agent.py` — add or retain test that GET /api/agent/effectiveness returns 200 and response includes `plan_progress.phase_6` and `plan_progress.phase_7` with `completed`, `total`; assert Phase 6 total is 2 and Phase 7 total is 17 when using default 006 backlog (or document and assert equivalent constants).

## Acceptance Tests

See `api/tests/test_agent.py`. Test name suggestion: `test_effectiveness_plan_progress_includes_phase_6_and_phase_7`. All existing effectiveness tests must continue to pass.

## Verification Scenarios

These scenarios are executable against the live API and must pass for this spec to be considered complete.

---

### Scenario 1 — Baseline: phase_6 and phase_7 present in response

**Setup:** API is running with no project_manager_state file present (cold start, or state file deleted).

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/agent/effectiveness | python3 -m json.tool
```

**Expected result:**
- HTTP 200
- Response contains `plan_progress` object
- `plan_progress.phase_6` is present with keys `completed` (int ≥ 0), `total` (int = 2), `pct` (number 0–100)
- `plan_progress.phase_7` is present with keys `completed` (int ≥ 0), `total` (int = 17), `pct` (number 0–100)
- `plan_progress.index` = 0 (no state file means index defaults to 0)
- `plan_progress.phase_6.completed` = 0 (no items completed when index = 0)
- `plan_progress.phase_7.completed` = 0

**Edge case:** If 006-overnight-backlog.md is missing, `plan_progress` must still return without 500; `total` may be 0.

---

### Scenario 2 — Phase 6 partially complete (backlog_index = 56)

**Setup:** Create a minimal PM state file so `backlog_index = 56` (Phase 6 item 1 done, item 2 not):
```bash
echo '{"backlog_index": 56}' > api/logs/project_manager_state.json
```

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/agent/effectiveness \
  | python3 -c "import sys,json; d=json.load(sys.stdin); pp=d['plan_progress']; print('phase_6:', pp['phase_6']); print('phase_7:', pp['phase_7'])"
```

**Expected result:**
- `phase_6.completed` = 1 (item 56 passed, item 57 not yet)
- `phase_6.total` = 2
- `phase_6.pct` = 50.0
- `phase_7.completed` = 0 (Phase 7 starts at item 58, not yet reached)
- `phase_7.total` = 17
- `phase_7.pct` = 0.0

**Edge case:** State file has `backlog_index = null` — should be treated as index 0, completed = 0 for both phases.

---

### Scenario 3 — Phase 6 fully complete, Phase 7 in progress (backlog_index = 65)

**Setup:** Set `backlog_index = 65` (Phase 6 done, 8 of 17 Phase 7 items done: items 58–65):
```bash
echo '{"backlog_index": 65}' > api/logs/project_manager_state.json
```

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/agent/effectiveness \
  | python3 -c "import sys,json; d=json.load(sys.stdin); pp=d['plan_progress']; print(json.dumps(pp, indent=2))"
```

**Expected result:**
- `phase_6.completed` = 2, `phase_6.total` = 2, `phase_6.pct` = 100.0
- `phase_7.completed` = 8, `phase_7.total` = 17, `phase_7.pct` = 47.1 (round(100 * 8/17, 1))
- `plan_progress.index` = 65
- `plan_progress.pct` = round(100 * 65 / 74, 1) = 87.8

**Edge case:** State file contains non-integer `backlog_index` (e.g. `"abc"`) — API must return 200 with `index = 0`, not 500.

---

### Scenario 4 — Full completion (backlog_index = 74 or beyond)

**Setup:** Set `backlog_index = 74` (all phases done):
```bash
echo '{"backlog_index": 74}' > api/logs/project_manager_state.json
```

**Action:**
```bash
curl -s https://api.coherencycoin.com/api/agent/effectiveness \
  | python3 -c "import sys,json; d=json.load(sys.stdin); pp=d['plan_progress']; print('p6:', pp['phase_6']['pct'], 'p7:', pp['phase_7']['pct'])"
```

**Expected result:**
- `phase_6.completed` = 2, `phase_6.pct` = 100.0
- `phase_7.completed` = 17, `phase_7.pct` = 100.0
- `plan_progress.pct` = 100.0

**Edge case:** `backlog_index = 200` (beyond total 74) — completed values are clamped to `total`; pct stays 100.0 for each phase.

---

### Scenario 5 — Error handling: corrupted state file

**Setup:** Write invalid JSON to the PM state file:
```bash
echo '{NOT VALID JSON' > api/logs/project_manager_state.json
```

**Action:**
```bash
curl -s -o /dev/null -w "%{http_code}" https://api.coherencycoin.com/api/agent/effectiveness
```

**Expected result:**
- HTTP 200 (not 500)
- `plan_progress.index` = 0 (graceful degradation)
- `plan_progress.state_file` = "" (no valid state loaded)
- `plan_progress.phase_6` and `plan_progress.phase_7` still present with `completed = 0`

**Edge case:** Both state files (`project_manager_state_overnight.json` and `project_manager_state.json`) missing — identical graceful 200 with zero values.

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add distributed locking for multi-worker pipelines.


## Out of Scope

- Changing goal_proximity formula or other effectiveness fields.
- Adding new API endpoints or query parameters.
- Persisting phase completion elsewhere; computation is from existing PM state and backlog file only.
- Backlog alignment check (spec 007 item 4) or meta-questions (007 item 3).

## Decision Gates (if any)

- If backlog phase boundaries or item ranges change in 006, update implementation (and optionally this spec) to match; no new dependency or resource.

## Verification

Executable commands to validate this spec:

```bash
# Unit tests
cd api && python -m pytest api/tests/test_agent.py -q -k "effectiveness"

# Live API check (requires running API)
export API=https://api.coherencycoin.com
curl -s $API/api/agent/effectiveness | python3 -c "
import sys, json
d = json.load(sys.stdin)
pp = d['plan_progress']
assert 'phase_6' in pp, 'phase_6 missing'
assert 'phase_7' in pp, 'phase_7 missing'
assert pp['phase_6']['total'] == 2, f\"phase_6.total={pp['phase_6']['total']} expected 2\"
assert pp['phase_7']['total'] == 17, f\"phase_7.total={pp['phase_7']['total']} expected 17\"
print('PASS: phase_6.total=', pp['phase_6']['total'], 'phase_7.total=', pp['phase_7']['total'])
print('PASS: phase_6.pct=', pp['phase_6']['pct'], 'phase_7.pct=', pp['phase_7']['pct'])
"
```

## See also

- [007-meta-pipeline-backlog.md](007-meta-pipeline-backlog.md) — item 1: Progress toward PLAN metric
- [006-overnight-backlog.md](006-overnight-backlog.md) — Phase 6 (56–57), Phase 7 (58–74)
- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — GET /api/agent/effectiveness context
- docs/PLAN.md — goals and roadmap
