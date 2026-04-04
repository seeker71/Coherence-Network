# Spec: Pipeline Data Flow Fixes

## Purpose

Code that never reaches `origin/main` does not exist for other nodes, for deployment, or for
the audit trail. The local runner's pipeline has seven documented failure modes that can silently
drop code, advance phases on failed pushes, or delegate SSH-gated actions to providers that have
no SSH access. This spec audits the current state of each fix and closes the remaining gaps so
every path from provider output to `origin/main` is observable, gated, and recoverable.

## Current State Assessment

The following table reflects the actual code in `api/scripts/local_runner.py` as of 2026-03-28.

| # | Fix | Status | Evidence |
|---|-----|--------|----------|
| 1 | `git fetch` before worktree creation | **DONE** | `_create_worktree` runs `git fetch origin --quiet` (line 4871) before computing `base_ref`; fetch failure is logged but non-fatal |
| 2 | Capture git diff after provider execution | **DONE** | `_run_task_in_worktree` calls `_capture_worktree_diff` and returns `(ok, diff)` (lines 5148–5151) |
| 3 | Push `origin/main` after merge, not just local merge | **DONE** | `_merge_branch_to_main` does `git push origin main` after local merge (lines 5118–5129); returns `False` on push failure |
| 4 | Block phase advancement until push succeeds | **PARTIAL GAP** | `_worker_loop` checks `pushed` before calling `_merge_branch_to_main` (line 5315), but `run_one` calls `_run_phase_auto_advance_hook` internally (line 3347) before `_worker_loop` evaluates `pushed`. For `impl`/`test` tasks the auto-advance fires inside `run_one` before the worktree push is attempted. |
| 5 | Keep worktree until push confirmed | **DONE** | `_worker_loop` finally block preserves worktree when `pushed=False` and `ok=True` (lines 5381–5384) |
| 6 | Deploy phase executed by runner, not delegated to provider | **DONE** | `_worker_loop` intercepts `task_type == "deploy"` and calls `_runner_deploy_phase` directly (lines 5295–5297); `_deploy_to_vps` uses SSH key on the runner host |
| 7 | Provider output visible in task record | **PARTIAL GAP** | `run_one` calls `complete_task(task_id, output, ...)` with provider stdout (line 3335), but in the worktree path the task was already claimed by `run_one` at line 3005, which may double-report status if `_worker_loop` also calls `complete_task` externally. Additionally `_complete_task_with_status` hardcodes `error_category="execution_error"` for push failures — there is no distinct `error_category=push_failed` value. |

## Requirements

- [ ] **R-4a**: For `impl` and `test` task types, `_run_phase_auto_advance_hook` MUST NOT be called inside `run_one` when the task will subsequently require a worktree push. The auto-advance call must be deferred until after `_push_branch_to_origin` returns `True` in `_worker_loop`.
- [ ] **R-4b**: If `_push_branch_to_origin` returns `False` for an `impl` or `test` task, the task record MUST be updated with `status=failed` and `error_category=push_failed` before the worker releases the idea lock. No downstream phase task may be created for that idea until the push failure is resolved.
- [ ] **R-7a**: When a push failure is recorded via `complete_task`, the `error_category` field in the PATCH body MUST be set to `"push_failed"` (distinct from `"execution_error"`). This allows operators and the API to filter and diagnose push failures independently.
- [ ] **R-7b**: The provider's full stdout (up to 50 000 chars) captured in `run_one` MUST appear in the `output` field of `GET /api/tasks/{id}` for any completed `impl` or `test` task. No code path may overwrite a non-empty provider output with an empty string.
- [ ] **R-1-obs**: Fetch failures in `_create_worktree` are currently logged as warnings and treated as non-fatal. This is acceptable for network flakiness, but the fetch error detail MUST be included in the task context patch so operators can detect persistent fetch failures without reading raw logs.

## Research Inputs (Required)

- `2026-03-28` - Source code audit of `api/scripts/local_runner.py` — direct inspection of `_create_worktree` (line 4821), `_push_branch_to_origin` (line 4985), `_merge_branch_to_main` (line 5080), `_run_task_in_worktree` (line 5138), `_runner_deploy_phase` (line 5165), `_worker_loop` (line 5228), `run_one` (line 2998), and `complete_task` (line 1111).

## Task Card (Required)

```yaml
goal: Close fix-4 and fix-7 gaps so phase advancement and push_failed error category are
      correctly gated and labelled in api/scripts/local_runner.py.
files_allowed:
  - api/scripts/local_runner.py
done_when:
  - run_one does not call _run_phase_auto_advance_hook for impl/test task types
  - _worker_loop calls _run_phase_auto_advance_hook for impl/test only after pushed=True
  - complete_task called with error_category="push_failed" when _push_branch_to_origin returns False
  - GET /api/tasks/{id} returns non-empty output for any completed impl/test task
  - fetch failure detail appears in task context patch when _create_worktree fetch fails
commands:
  - grep -n "_run_phase_auto_advance_hook" api/scripts/local_runner.py
  - grep -n "push_failed" api/scripts/local_runner.py
  - python3 -c "import ast; ast.parse(open('api/scripts/local_runner.py').read()); print('syntax OK')"
constraints:
  - Do not change the public signature of complete_task, _push_branch_to_origin, or run_one
  - Do not modify any test files
  - Scope is limited to api/scripts/local_runner.py only
```

## API Contract

N/A - no API contract changes in this spec.

The `error_category` field is an existing free-text field on the task record; adding a new
value (`"push_failed"`) does not change the schema. Filtering by `error_category` is already
supported via the task query API.

## Data Model

N/A - no model changes in this spec.

The `error_category` string value `"push_failed"` is additive and requires no schema migration.

## Files to Create/Modify

- `api/scripts/local_runner.py` — targeted changes in four functions:
  - `run_one`: remove or gate the `_run_phase_auto_advance_hook` call for `impl`/`test` task types
  - `_worker_loop`: add `_run_phase_auto_advance_hook` call after confirmed push for `impl`/`test`; call `complete_task` with `error_category="push_failed"` when push fails
  - `complete_task`: ensure `error_category` parameter is passed through and not overwritten with a default when a caller supplies a non-default value (verify no regression)
  - `_create_worktree`: include fetch error detail in the returned worktree context so it can be patched onto the task

## Acceptance Tests

The following tests are to be written by QA. They are stated here as verifiable scenarios:

1. **Worktree branches from latest `origin/main` SHA** (`test_worktree_branches_from_origin_main`)
   - Arrange: local `main` is 3 commits behind `origin/main`
   - Act: call `_create_worktree(task_id)`
   - Assert: `git merge-base --is-ancestor <local-main-sha> <wt-HEAD>` fails; `git merge-base origin/main <wt-HEAD>` succeeds, confirming worktree HEAD is a descendant of the fetched `origin/main`

2. **Push failure blocks phase advancement and sets `error_category=push_failed`** (`test_push_failure_blocks_phase_advance`)
   - Arrange: mock `_push_branch_to_origin` to return `False`; task type is `impl`
   - Act: run `_worker_loop` iteration to completion
   - Assert: `_run_phase_auto_advance_hook` was not called; the final PATCH to `/api/agent/tasks/{id}` contains `"status": "failed"` and `"error_category": "push_failed"`

3. **Worktree preserved until push confirmed** (`test_worktree_kept_on_push_failure`)
   - Arrange: provider succeeds (`ok=True`), push fails (`pushed=False`)
   - Act: worker loop finally block executes
   - Assert: the worktree directory still exists on disk after the finally block; `_cleanup_worktree` was not called

4. **Provider output visible in task record after completed impl** (`test_impl_task_output_in_record`)
   - Arrange: execute an `impl` task end-to-end with a stub provider that returns stdout `"wrote 3 files"`
   - Act: call `GET /api/tasks/{id}` after completion
   - Assert: response body `output` field contains `"wrote 3 files"`; field is not empty or overwritten

5. **Deploy task uses runner SSH, not a provider** (`test_deploy_executed_by_runner`)
   - Arrange: create a task with `task_type="deploy"`; mock `_deploy_to_vps` to record whether it was called and return `"Deploy successful: abc -> def"`
   - Act: run one `_worker_loop` iteration
   - Assert: `_deploy_to_vps` was called exactly once; `select_provider` was not called; `execute_with_provider` was not called

## Concurrency Behavior

- **Phase auto-advance** is protected by the `_active_idea_ids` lock: only one worker holds a
  given idea at a time, so deferring `_run_phase_auto_advance_hook` to after the push check does
  not introduce a race.
- **Worktree cleanup** happens in the finally block of the same thread that held the idea lock,
  so no concurrent access to the worktree directory is possible after the lock is released.

## Verification

```bash
# Syntax check after changes
python3 -c "import ast; ast.parse(open('api/scripts/local_runner.py').read()); print('syntax OK')"

# Confirm push_failed is used in the file
grep -n "push_failed" api/scripts/local_runner.py

# Confirm auto-advance is not called unconditionally inside run_one for impl/test
# (manual: search for _run_phase_auto_advance_hook calls and verify impl/test guard)
grep -n "_run_phase_auto_advance_hook" api/scripts/local_runner.py

# Run existing unit tests (must not regress)
cd api && python3 -m pytest tests/ -q 2>&1 | tail -20
```

If no automated test exists for the push-failure scenario, the implementer must verify manually
by injecting a temporary `return False` at the top of `_push_branch_to_origin`, running a single
`impl` task through the loop, and confirming:
- No test task was created in `/api/ideas/{id}/tasks`
- The task record shows `status=failed`, `error_category=push_failed`
- The worktree directory is still present on disk

## Out of Scope

- Retry logic for push failures (automatic re-push after transient network errors) — follow-up task
- Fetch failure as a hard blocker (currently non-fatal by design for network resilience)
- Changes to the phase sequencing logic or `_PHASE_SEQUENCE` ordering
- Modifying how `_merge_branch_to_main` gates the deploy phase (that path already blocks correctly)
- Any changes outside `api/scripts/local_runner.py`

## Risks and Assumptions

- **Risk**: Removing the `_run_phase_auto_advance_hook` call from `run_one` for `impl`/`test` may break the non-worktree fallback path in `_worker_loop` (line 5369) where `run_one` is called directly and `pushed` is set to `True` unconditionally. The implementer must ensure the advance hook is still called in that fallback path.
- **Risk**: `run_one` is also invoked for `spec`, `review`, and `code-review` tasks via the fallback path. The guard must be type-specific — only suppress the hook for `impl` and `test` inside `run_one`; all other task types should continue advancing as before.
- **Assumption**: The API's `PATCH /api/agent/tasks/{id}` endpoint accepts `error_category` as a free-text field and stores any value passed. If the field is validated against an enum, `"push_failed"` must be added to that enum (out of scope for this spec; escalate as a `needs-decision` if blocked).
- **Assumption**: The SSH key `~/.ssh/hostinger-openclaw` is present on the runner host. `_deploy_to_vps` already handles the missing-key case with a graceful skip message — this behaviour is unchanged.

## Known Gaps and Follow-up Tasks

- **Gap**: Fix 1 (fetch failure) is non-fatal. If `git fetch` fails consistently (e.g. DNS, auth), tasks silently branch from a stale local HEAD. A follow-up should add a fetch-failure counter per worker and pause idea claiming after N consecutive failures.
- **Gap**: Fix 4 only partially covers the standalone `run_one` path (no worktree). In that path, `pushed=True` is set unconditionally, so auto-advance fires even if the text output was garbage. The quality gate (minimum output length) partially mitigates this, but the guard is not push-based. Tracked as a separate concern.
- **Follow-up task**: Add `error_category=push_failed` filtering to the ops dashboard so push failure rates are visible without log scraping.
- **Follow-up task**: Automatic re-push retry (exponential backoff, max 3 attempts) for transient network errors before marking `push_failed`.

## Failure/Retry Reflection

- Failure mode: implementer moves the auto-advance call but forgets the non-worktree fallback path — spec tasks stop advancing entirely.
- Blind spot: `run_one` is called from both `_run_task_in_worktree` and the fallback branch in `_worker_loop`; treating them uniformly would break the fallback.
- Next action: after the change, run a dry-run spec task through the loop and confirm a test task is created; that confirms the advance still fires for spec/text-only phases.

- Failure mode: `error_category` PATCH is ignored by the API (field not stored).
- Blind spot: the field may be silently dropped if the Pydantic model has `model_config = ConfigDict(extra="ignore")`.
- Next action: call `GET /api/tasks/{id}` immediately after the failing push and assert `error_category` equals `"push_failed"` in the response body.

## Decision Gates (if any)

- If `error_category` on the task model is an enum (not free text), adding `"push_failed"` requires a DB migration and a schema version bump. This must be confirmed before implementation begins. Escalate as `needs-decision` if the field is enum-typed.
