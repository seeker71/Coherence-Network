# Spec: Silent Failure Detection

## Purpose

Every task failure is a learning signal. When a task goes from `running` to `failed` without
a structured `error_category` or a readable `error_summary`, that signal is lost: retry budget
is consumed, the runner does not know what broke, and operators cannot triage at scale. This
spec closes the set of paths through `_worker_loop` where failures are swallowed or partially
recorded, and introduces an enforced enum for `error_category` so that failure data is
machine-queryable rather than freeform. The goal is that every failed task teaches the system
something — blind failures are a tax that compounds across every retry cycle.

## Current State

`api/scripts/local_runner.py` has two intentional failure paths:

- `_fail_task(task_id, output, error_category, error_summary)` — PATCHes task to failed with
  error fields. Called by the reaper and by `_complete_task` on hollow output.
- `_complete_task` hollow-output gate — checks `len(output) < MIN_OUTPUT_CHARS[task_type]`
  and delegates to `_fail_task` with `error_category="hollow_completion"`.

Observed gaps (9 tasks in production with `error_summary=None` and/or `error_category=None`):

1. When a provider subprocess exits with a non-zero code, `stderr` is captured locally but is
   not reliably written to `error_summary` before the PATCH.
2. When the API returns 5xx during result submission, the error body is printed to console but
   the task is not PATCHed to failed — it may remain stuck in `running`.
3. When `subprocess.TimeoutExpired` is raised, the timeout duration is logged but
   `error_summary` may be empty if stdout was also empty at that point.
4. Some tasks arrive at `status=failed` with `error_category=None`, meaning the failure path
   skipped `_fail_task` entirely (unhandled exception branch or early return).
5. `error_category` is a freeform string at the API model layer — no enum validation — so
   callers have used inconsistent spellings that cannot be grouped in queries.

## Requirements

- [ ] R1: On subprocess non-zero exit, always store the first 400 characters of `stderr` in
  `error_summary` and set `error_category="execution_error"` before calling `_fail_task`.
- [ ] R2: On `subprocess.TimeoutExpired`, set `error_category="timeout"` and store a human-
  readable duration string (e.g., `"timed out after 300s; stdout was 0 chars"`) in
  `error_summary`.
- [ ] R3: When an API call to submit task output returns a 5xx status, call `_fail_task` with
  `error_category="api_error"` and store the first 400 characters of the response body in
  `error_summary`.
- [ ] R4: Every `except` clause inside `_worker_loop` must call `_fail_task` before re-raising
  or continuing. No exception path may leave the task in `running`.
- [ ] R5: Add a validated `error_category` enum to `TaskUpdate` (and `Task`) in
  `api/app/models/task.py`. Accepted values: `hollow_completion`, `timeout`,
  `execution_error`, `stale_reaped`, `api_error`, `push_failed`. The field remains optional
  (nullable) to allow non-failed tasks.
- [ ] R6: `GET /api/tasks?status=failed` must return zero tasks where `error_category` is
  `null` for any task whose `failed_at` timestamp is after this spec ships. (Pre-existing rows
  are exempt from backfill.)

## Research Inputs

- `2026-03-28` — Codebase analysis of `api/scripts/local_runner.py` lines 1100–1145 and
  3280–3345 — primary source for gap identification.
- `2026-03-28` — Production query showing 9 tasks with `error_summary=None` — motivates R1–R4.
- Related specs: `specs/074-tool-failure-awareness.md` — adjacent friction telemetry;
  `specs/013-logging-audit.md` — structured log contract.

## Task Card

```yaml
goal: Guarantee every task failure records a structured error_category and non-null error_summary
files_allowed:
  - api/scripts/local_runner.py
  - api/app/models/task.py
  - api/app/services/task_service.py
done_when:
  - TaskUpdate.error_category is a Literal enum; passing a value outside the enum raises 422
  - Provider subprocess non-zero exit stores stderr slice in error_summary on the task record
  - subprocess.TimeoutExpired stores duration string in error_summary on the task record
  - 5xx API response during output submission triggers _fail_task with error_category=api_error
  - Every except clause in _worker_loop calls _fail_task before continuing
  - pytest api/tests/test_silent_failure_detection.py passes with zero skips
commands:
  - cd api && python3 -m pytest tests/test_silent_failure_detection.py -x -v
  - cd api && python3 -m pytest tests/test_task_model.py -x -v -k error_category
constraints:
  - No schema migrations for pre-existing rows; only new rows must satisfy the non-null rule
  - error_category field remains Optional (nullable) in the model — do not mark it required
  - changes scoped to listed files only
  - no new external dependencies
```

## API Contract

### `PATCH /api/tasks/{id}`

Extending the existing contract. The `error_category` field is now validated against a fixed
enum when present.

**Request body (partial — only changed fields shown)**

```json
{
  "status": "failed",
  "error_category": "execution_error",
  "error_summary": "Traceback (most recent call last):\n  ...\nValueError: bad token [truncated]"
}
```

**Validation rules**

- `error_category`: one of `hollow_completion | timeout | execution_error | stale_reaped | api_error | push_failed`, or `null`. Any other string returns `422 Unprocessable Entity`.
- `error_summary`: free text, max 2000 characters. Truncate at 400 characters before storing when sourced from stderr or response body.

**Response 200** — unchanged task schema with updated fields reflected.

**Response 422**

```json
{
  "detail": [
    {
      "loc": ["body", "error_category"],
      "msg": "value is not a valid enumeration member",
      "type": "type_error.enum"
    }
  ]
}
```

### `GET /api/tasks`

No new query parameters. Existing `?status=failed` filter already supported. After this spec,
callers may assert that `error_category` is non-null for tasks created post-ship.

## Data Model

```yaml
TaskErrorCategory:
  type: string enum
  values:
    - hollow_completion   # output below MIN_OUTPUT_CHARS threshold
    - timeout             # subprocess.TimeoutExpired
    - execution_error     # subprocess exited with non-zero return code
    - stale_reaped        # reaper killed the task for exceeding max age
    - api_error           # 5xx returned by the API during result submission
    - push_failed         # git push or deploy step failed after generation

Task:
  properties:
    error_category:
      type: TaskErrorCategory | null
      nullable: true
      description: Structured failure classification; null for non-failed tasks
    error_summary:
      type: string | null
      nullable: true
      maxLength: 2000
      description: Human-readable failure detail; first 400 chars of stderr or response body
```

## Files to Create/Modify

- `api/app/models/task.py` — add `TaskErrorCategory` `Literal` type alias (or `Enum`); apply
  to `error_category` field on `TaskBase`, `TaskUpdate`, and `TaskResponse`.
- `api/app/services/task_service.py` — validate `error_category` on update; no logic change
  needed beyond model enforcement if Pydantic validation is used.
- `api/scripts/local_runner.py` — patch every exception handler in `_worker_loop` to call
  `_fail_task`; capture stderr slice and duration string in the appropriate handlers.
- `api/tests/test_silent_failure_detection.py` — new test file (QA authors; listed here for
  traceability).

## Acceptance Tests

Each scenario maps to a concrete test case in `api/tests/test_silent_failure_detection.py`.
QA owns authoring; the scenarios below define the required coverage.

1. **Execution error** — Simulate a provider subprocess that exits with code 1 and writes
   `"fatal: bad object"` to stderr. Assert the resulting task record has
   `error_category="execution_error"` and `error_summary` contains `"fatal: bad object"`.

2. **Timeout** — Simulate `subprocess.TimeoutExpired` with a 300-second limit. Assert the
   task record has `error_category="timeout"` and `error_summary` contains `"300"` (the
   timeout duration).

3. **Hollow completion** — Simulate provider output of 3 characters where the minimum is 50.
   Assert `error_category="hollow_completion"` and `error_summary` references the character
   count discrepancy.

4. **Reaped task** — Trigger the stale-task reaper against a task running longer than
   `MAX_TASK_AGE`. Assert `error_category="stale_reaped"` and `error_summary` contains the
   reap diagnosis string.

5. **API 5xx on submission** — Stub the PATCH response to return HTTP 500 with body
   `"Internal Server Error"`. Assert the task is subsequently PATCHed to failed with
   `error_category="api_error"` and `error_summary` contains the response body substring.

6. **Enum validation gate** — Send `PATCH /api/tasks/{id}` with
   `error_category="unknown_value"`. Assert HTTP 422 is returned.

7. **Bulk non-null invariant** — Seed 5 failed tasks through the patched runner (covering all
   five category types). Query `GET /api/tasks?status=failed&limit=20`. Assert every returned
   task has a non-null `error_category`.

## Concurrency Behavior

- **`_fail_task` calls**: Each worker thread calls `_fail_task` independently for its own
  task. No shared state is mutated; the API PATCH is the synchronization point.
- **Reaper**: Runs in a separate thread; calls `_fail_task` after acquiring the task ID from
  its own poll. No locking required between reaper and worker for distinct task IDs.
- **Recommendation**: If the same task ID could be reaped and worker-failed simultaneously,
  last-write-wins semantics apply. The reaper should check task status before patching to
  avoid overwriting a more-specific `error_category` already set by the worker.

## Verification

```bash
# Unit and integration tests for this spec
cd api && python3 -m pytest tests/test_silent_failure_detection.py -x -v

# Confirm enum validation in the task model tests
cd api && python3 -m pytest tests/test_task_model.py -x -v -k error_category

# Confirm no pre-existing tests broken by model change
cd api && python3 -m pytest tests/ -q --tb=short

# Spot-check production: every recently-failed task should have error_category set
curl -s "https://api.coherencycoin.com/api/tasks?status=failed&limit=20" \
  | python3 -c "
import sys, json
tasks = json.load(sys.stdin)
items = tasks.get('items', tasks) if isinstance(tasks, dict) else tasks
null_cat = [t['id'] for t in items if t.get('error_category') is None]
print('Tasks missing error_category:', null_cat)
assert len(null_cat) == 0, 'FAIL: silent failures still present'
print('OK')
"
```

## Out of Scope

- Backfilling `error_category` on the 9 pre-existing failed tasks with `null` values.
- Alerting or paging on specific error categories (covered by spec 074 friction events).
- Per-provider error parsing beyond stderr truncation (e.g., structured JSON error payloads
  from OpenRouter).
- Retry scheduling based on `error_category` value (a follow-up task).
- `push_failed` handling — the enum value is reserved but no implementation is required for
  this spec iteration.

## Risks and Assumptions

- **Risk — Double-PATCH race**: If a worker thread and the reaper both detect failure for the
  same task at the same instant, two `_fail_task` calls may race. Mitigation: the reaper
  already checks `status != running` before acting; the worker should do the same after
  catching an exception. Last-write-wins is acceptable for MVP.
- **Risk — stderr truncation loses critical context**: Capping at 400 characters may cut off
  the actionable part of a long stack trace. Mitigation: store the last 400 characters rather
  than the first if the stderr exceeds 400 characters, capturing the terminal error line.
  Decision deferred to implementer; either approach satisfies the spec.
- **Risk — Pydantic enum breaks existing callers**: Any runner version prior to this spec that
  sends a freeform `error_category` string will receive a 422. Mitigation: deploy API change
  before runner change; runner change only adds values from the new enum.
- **Assumption**: `_worker_loop` is the canonical execution path for all task types. If any
  task type bypasses `_worker_loop`, its exception handling is out of scope for this spec.
- **Assumption**: `MIN_OUTPUT_CHARS` thresholds are already correct and are not being changed
  by this spec.

## Known Gaps and Follow-up Tasks

- Follow-up task: Implement retry routing based on `error_category` — e.g., `api_error` tasks
  retry sooner; `hollow_completion` tasks get a different prompt variant.
- Follow-up task: Surface `error_category` breakdown in the pipeline status API
  (`GET /api/pipeline/status`) so the monitor can raise targeted issues per category.
- Follow-up task: Evaluate storing the last 400 chars of stderr (tail) vs. first 400 chars
  (head) and document the chosen convention in the runner module docstring.
- Follow-up task: Add `push_failed` detection when the deploy step in the runner exits
  non-zero, using the same `_fail_task` pathway.
- Known gap: Pre-existing tasks with `error_category=null` will remain unclassified. A
  one-time backfill script is not in scope but should be tracked as a data-hygiene task.

## Failure/Retry Reflection

- Failure mode: Implementer wraps the subprocess call in a broad `except Exception` that
  captures stderr but forgets to call `_fail_task` before re-raising.
  Blind spot: The test suite may not cover every branch of the exception handler.
  Next action: Add a test that injects an unexpected exception type (e.g., `MemoryError`)
  and asserts the task ends up in `failed` state.

- Failure mode: API enum validation is added to `TaskUpdate` but not to `TaskResponse`, so
  reading back a legacy row with a freeform category string raises a deserialization error.
  Blind spot: Read path not tested separately from the write path.
  Next action: Add a test that reads a task seeded with a legacy freeform `error_category`
  and asserts it is returned as-is (the read model should use `str | None`, not the enum).

## Decision Gates

- The implementer must decide whether `error_category` on the read model (`TaskResponse`)
  uses the strict `TaskErrorCategory` enum or a plain `str | None`. Using the strict enum
  would break reads of legacy rows. Recommendation: use `str | None` on reads, enum on writes
  (`TaskUpdate`). This decision must be made before the `api/app/models/task.py` change is
  merged.
