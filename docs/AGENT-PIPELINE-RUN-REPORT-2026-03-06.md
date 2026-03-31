# Agent Pipeline Full Run Report — 2026-03-06

## Summary

- **Pipeline**: Local API + agent_runner + Cursor CLI (`agent`)
- **Completed run**: task_329f94d787967808 (impl — remote-ops refactor)
- **Files changed**: 7 new/modified files
- **Web build**: PASS
- **Spec task created**: task_a0689d958a5e54af (tracking-audit-anomaly-detection) — pending in queue

## Dependency Analysis For Follow-up Review

### Current conclusion

This report captures a real local agent execution, but it does **not** yet prove a valid end-to-end idea pipeline under the required dependency model.

### Why the proof is incomplete

- The runner executed an unrelated existing `impl` task before the newly created `spec` task for `tracking-audit-anomaly-detection`.
- That means the observed run does **not** satisfy the required chain `idea -> spec -> impl -> test -> review -> acceptance`.
- The completed `impl` run is therefore execution evidence only, not acceptance evidence for the target idea.

### Missing dependency guarantees identified

- `impl` must require an approved parent `spec`
- `test` must require completed target `impl` task(s)
- `review` must require the parent `spec`, relevant `impl` task(s), and passing `test` task(s)
- `acceptance` must require approved `review` plus validation artifacts
- Oversized `idea`, `spec`, or `impl` work must be split into bounded children before execution

### Required feedback loops identified

- `test -> impl_fix`: failing tests create a bounded implementation follow-up with exact failing evidence
- `review -> impl_fix|test_fix|spec_fix`: review findings must classify the issue and enqueue the smallest corrective task
- `multi-impl assembly -> integration test -> review -> acceptance`: when one spec needs multiple impl shards, completion must happen at the assembled spec level

### Finish criteria for this analysis item

Treat this analysis as complete only when all of the following are true:

- The scheduler blocks runnable tasks with unsatisfied dependencies
- Task records encode explicit ancestry and `depends_on` edges
- Large `idea` / `spec` / `impl` nodes can be split into bounded children
- `test` and `review` failures automatically create minimal corrective follow-up tasks
- `acceptance` is represented as a first-class task/artifact gate
- A fresh local run demonstrates the full ordered chain for one idea: `idea -> spec -> impl -> test -> review -> acceptance`

### Review checklist for the cheaper model's return

- Does it enforce hard dependency ordering instead of soft queue preference?
- Does it define splitting rules for oversized idea/spec/impl work?
- Does it define explicit retry loops from `test` and `review` back to corrective tasks?
- Does it include assembled completion for specs with multiple impl shards?
- Does it define acceptance artifacts separately from test success?
- Does it prevent claiming completion when predecessor nodes are missing?

### Review of cheaper model prompt

Assessment of the returned executor prompt against the checklist:

- **Hard dependency ordering**: **partial pass**. The prompt clearly blocks execution when `depends_on` tasks are missing or incomplete, but it defines executor behavior only. It does not yet define scheduler-side enforcement or invalid-task rejection at the queue level.
- **Splitting rules**: **pass**. The prompt explicitly defines `SPLIT_REQUIRED`, trigger conditions, and required child-task fields.
- **`test` / `review` retry loops**: **partial pass**. The prompt classifies review failures and points to corrective next actions, but it does not fully define loop orchestration policy such as retry limits, automatic follow-up creation, or rerun order.
- **Assembly for multi-impl specs**: **missing**. The prompt mentions child tasks and corrective tasks, but it does not explicitly define assembly-level integration testing and final spec-level review when multiple impl shards exist.
- **Acceptance artifacts distinct from test success**: **pass**. The prompt requires artifacts and evidence for `acceptance` rather than treating passing tests as sufficient.
- **Predecessor-missing completion prevention**: **pass**. The prompt is explicit that missing dependencies require `BLOCKED` and no work.

Overall assessment:

- The prompt is a strong **task executor contract**
- It is **not yet sufficient as the full project-management contract**
- The remaining gaps are primarily in **scheduler behavior**, **automatic loop orchestration**, and **multi-impl assembly**

Not-finished criteria remaining after this review:

- Add scheduler-level dependency enforcement so invalid tasks are never selected
- Add first-class ancestry / dependency fields to task persistence and APIs
- Add automatic follow-up task generation rules for `test` and `review` failures
- Add explicit assembled-spec flow for multiple impl tasks: shard impls -> shard tests -> integration test -> review -> acceptance
- Re-run one local idea through the full ordered chain after enforcement is implemented

Suggested next refinement to the executor prompt:

- add `assembly_target`
- add `retry_budget`
- add `rerun_after`
- add `blocking_task_types`
- add an explicit rule that `review` for a multi-impl spec is blocked until all required impl and integration-test children are complete
- add an explicit rule that the executor must reject a task whose persisted ancestry is inconsistent with its declared `depends_on`

---

## Agent Call 1: Impl (COMPLETED)

### Task

| Field | Value |
|-------|-------|
| **task_id** | task_329f94d787967808 |
| **task_type** | impl |
| **status** | completed |
| **duration** | 122.1 s |
| **exit_code** | 0 |

### Cursor CLI Command (actual)

```
agent --trust --print --output-format json "Role agent: dev-engineer. Task type: impl. Respect role boundaries, spec scope, and acceptance criteria. Direction: Split oversized implementation file 'web/app/remote-ops/page.tsx' into smaller reusable modules. Current line_count=567, target <= 450. Preserve behavior and validation coverage." --model auto --sandbox disabled
```

### Prompt (direction)

```
Split oversized implementation file 'web/app/remote-ops/page.tsx' into smaller reusable modules.
Current line_count=567, target <= 450.
Preserve behavior and validation coverage.
```

### Steps (from agent output)

1. Split `web/app/remote-ops/page.tsx` into modules
2. Read file structure, check tests and component patterns
3. Create task list and implement split
4. Fix queue section (Running = pipeline.running.length)
5. Remove unused API_URL, tokenProvided from ControlsSection
6. Write refactored page composing hook and section components
7. Verify build and initial data load
8. Summary: new modules + refactored page

### Result

| Field | Value |
|-------|-------|
| **output_len** | 2610 chars |
| **log_file** | api/logs/task_task_329f94d787967808.log |
| **usage** | inputTokens=463261, outputTokens=11922, cacheReadTokens=427008 |

### Files Changed

| File | Action | Lines |
|------|--------|-------|
| web/app/remote-ops/page.tsx | modified | 107 (was 567) |
| web/app/remote-ops/types.ts | created | 60 |
| web/app/remote-ops/utils.ts | created | 50 |
| web/app/remote-ops/use-remote-ops.ts | created | 290 |
| web/app/remote-ops/deployment-uptime-section.tsx | created | 56 |
| web/app/remote-ops/controls-section.tsx | created | 153 |
| web/app/remote-ops/queue-pipeline-section.tsx | created | 55 |

### Validation

| Check | CLI | Result |
|-------|-----|--------|
| Web build | `cd web && npm run build` | PASS |
| Remote-ops route | `/remote-ops` in build output | Present |
| Line count target | page.tsx ≤ 450 | 107 ✓ |

---

## Agent Call 2: Spec (CREATED, PENDING)

### Task

| Field | Value |
|-------|-------|
| **task_id** | task_a0689d958a5e54af |
| **task_type** | spec |
| **idea_id** | tracking-audit-anomaly-detection |
| **status** | pending |

### Cursor CLI Command (as would be run)

```
agent --trust --print --output-format json "Role agent: product-manager. Task type: spec. Scope: only spec-listed files. Minimize tokens, tool calls, and runtime. Output only requested keys. Required output: SPEC_PATH, JUDGE, VALIDATION Direction: Create spec for idea tracking-audit-anomaly-detection. Spec should enable anomaly detection in tracking/audit data. Include: Purpose, Requirements (>=3), Task Card, Files to Create/Modify, Acceptance Tests, Verification. Save to specs/ and run validate_spec_quality." --model auto --sandbox disabled
```

### Prompt (direction)

```
Create spec for idea tracking-audit-anomaly-detection.
Spec should enable anomaly detection in tracking/audit data.
Include: Purpose, Requirements (>=3), Task Card, Files to Create/Modify, Acceptance Tests, Verification.
Save to specs/ and run validate_spec_quality.
```

### Note

Task is queued. Runner selects from 20 pending tasks (scheduler may prefer measured/impl tasks). Run `cd api && .venv/bin/python scripts/agent_runner.py --once` repeatedly until this task executes.

---

## Validation Run (2026-03-06)

| Check | Result |
|-------|--------|
| Web build | PASS |
| API health | ok, uptime 51m |
| Task GET task_329f94d787967808 | status=completed |
| Metrics window_days | available (tracking-infrastructure-upgrade) |

---

## Local Services

| Service | Command | Port |
|---------|---------|------|
| API | `cd api && uvicorn app.main:app --reload --port 8000` | 8000 |
| Web | `cd web && npm run dev` | 3000 |

### Restart After Agent Changes

Agent-produced file changes (web/) do not require API restart. Web dev server hot-reloads. For a clean validation:

```bash
# Restart web to pick up new modules
cd web && npm run dev
# Or verify build
cd web && npm run build
```

---

## Validation Commands (full contract)

```bash
# 1. Web build (artifact check)
cd web && npm run build

# 2. API health
curl -s http://127.0.0.1:8000/api/health | jq .status

# 3. Metrics with window_days (tracking-infrastructure-upgrade)
curl -s 'http://127.0.0.1:8000/api/agent/metrics?window_days=1' | jq .window_days

# 4. Agent task status
curl -s "http://127.0.0.1:8000/api/agent/tasks/task_329f94d787967808" | jq '{id, status}'
```

---

## Task Context (from API)

| Field | Value |
|-------|-------|
| **idea_id** | portfolio-governance |
| **source** | asset_modularity_drift |
| **asset_id** | web/app/remote-ops/page.tsx |
| **metric** | line_count |
| **current_value** | 567 |
| **threshold** | 450 |
| **executor** | cursor |
| **route_decision** | cursor, cursor/auto, repo_executor_preference |
| **policy** | budget-aware-router-lite-v1 |
| **run_id** | run_df60329a1985 |
| **worker_id** | Urss-MacBook-Pro.local:42841 |

### Observer snapshots (state transitions)

1. `claim` → lease claimed at 23:05:22
2. `start` → command started, runner_state=running
3. `complete` → finalized, runner_state=idle, next_action=done

---

## Potential Payloads

### Task completion (PATCH response)

```json
{
  "id": "task_329f94d787967808",
  "status": "completed",
  "context": {
    "output": "...",
    "exit_code": 0,
    "duration_seconds": 122.1
  }
}
```

### Agent result (from task log)

```json
{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 120228,
  "result": "Splitting web/app/remote-ops/page.tsx... Summary of the refactor: ...",
  "usage": {
    "inputTokens": 463261,
    "outputTokens": 11922,
    "cacheReadTokens": 427008,
    "cacheWriteTokens": 36253
  }
}
```

### GET task (key fields)

```json
{
  "id": "task_329f94d787967808",
  "direction": "Split oversized implementation file 'web/app/remote-ops/page.tsx' into smaller reusable modules...",
  "task_type": "impl",
  "status": "completed",
  "model": "cursor/auto",
  "context": { "source": "asset_modularity_drift", "idea_id": "portfolio-governance", ... }
}
```

---

## Process tracker (avoid losing context)

*Last session: continued; verification again passed (24 tests, dry-run). Tracker current; next: full chain demo when ready.*

**Process status:** Implementation for dependency-aware planner and scheduler is **complete**. All Finish-criteria items are implemented (split/combine, ordering, depends_on_task_ids, acceptance gate, test/review corrective impl). The only remaining step is **full chain demo** (run API + agent_runner + PM and confirm one idea completes spec→impl→test→review→acceptance), which is **manual when ready**. Quick verification without API: `pytest api/tests/test_project_manager.py -q` and `python api/scripts/project_manager.py --dry-run --reset` both pass.

### Split/combine in project planner (2026-03-06)

| Step | Status | Notes |
|------|--------|--------|
| Split heuristics + state model in project_manager.py | Done | `is_too_large`, `split_item`, `split_parent` state |
| Wire into sequential `run()` | Done | Create split before task; on child complete advance or combine |
| **Ordering / depends_on** | Done | Each child can have `depends_on`; runnable = deps complete; default linear; signaled to sub-impls |
| Tests (split, combine, depends_on, next_runnable_in_parallel) | Done | 24 tests in test_project_manager.py |
| Dry-run + pytest | Done | Pass |
| Ruff on changed files | Done | Removed unused item_phase, phases_in_flight |
| Parallel mode split/combine | Done (spec only) | run_parallel(): spec split; combine on all children done |
| **Parallel mode ordering** | Done | split_done = list of completed indices; only runnable child created; on complete → enqueue next runnable |
| **Scheduler dependency gating** | Done | agent_runner: _task_dependencies_satisfied(); skip task if context.depends_on_task_ids not all completed |
| Task ancestry / depends_on in API | Done | PM sets context.depends_on_task_ids when creating impl (after spec), test (after impl), review (after test) in run() and run_parallel() |
| Scheduler dependency enforcement | Done | Runner gates; PM wires; full chain has depends_on_task_ids |
| **Acceptance gate** | Done | PHASES includes "acceptance"; after review passes → phase acceptance → _run_acceptance_gate() (pytest + evidence file) → advance item |
| **Test/review → corrective impl** | Done | On impl/test/review failure, PM creates impl retry with direction (output/fail_reason) and context.depends_on_task_ids = [triggering task_id] (sequential + parallel) |

### Sub-implementation ordering (depends_on)

- **Split decision is ordering-aware**: `split_with_ordering(node_type, item)` returns `(children_items, ordering)` where `ordering[i]` = depends_on for child i. Default = linear. The place that decides the split also decides the ordering.
- Ordering is **signaled to sub-impls**: (1) direction text gets a suffix via `format_ordering_signal()` (e.g. "Sub-impl 2 of 3; depends on sub-impl(s) 1. Complete only this part."); (2) task context gets `split_child_index`, `split_total_children`, `split_depends_on` so the runner/API can use them.
- Each child in state has **`depends_on`** from that ordering; **runnable** = not complete and all deps complete. Sequential run uses `get_next_runnable_index()` so only one child runs at a time in order.
- Custom DAGs: have `split_with_ordering` (or the caller) return a custom ordering list instead of linear.

### Scheduler dependency gating (agent_runner)

- **context.depends_on_task_ids**: optional list of task IDs that must be `completed` before this task is runnable.
- **agent_runner**: when building the runnable list, skips any pending task for which `_task_dependencies_satisfied()` is False (any dependency not completed).
- **Wiring**: project_manager sets `context.depends_on_task_ids = [task_id]` when creating impl (after spec), test (after impl), review (after test) in both sequential run() and run_parallel().

### Acceptance gate (first-class)

- **Phase**: `PHASES` includes `"acceptance"` after `"review"`. No agent task for acceptance; it runs in the planner.
- **Flow**: When review task completes and passes (pytest + review_ok), planner sets `phase = "acceptance"`. On next tick (no current task), planner runs `_run_acceptance_gate(idx, item_preview, log)`: runs pytest again, writes `api/logs/acceptance_evidence_item_{idx}.json` with backlog_idx, item_preview, pytest_ok, timestamp; then advances `backlog_index`, `phase = "spec"`.
- **Evidence**: Acceptance artifact is separate from test success; gate can be extended (e.g. more validations, docs/system_audit/).

### Test/review auto follow-up

- On **impl** failure: PM creates impl retry with `build_direction("impl", ..., iteration+1, output)` and `depends_on_task_ids=[task_id]`.
- On **test** or **review** failure: PM sets phase to impl, creates impl retry with fail_reason/output and `depends_on_task_ids=[task_id]`.
- Corrective task is thus explicitly linked to the task that triggered it; runner only runs it after the triggering task is completed (failed counts as completed).

### Clear queue before new flow

To ensure the next pipeline run only sees the new idea’s tasks and **order is respected** (spec → impl → test → review):

1. **Restart the API once** so it loads the `DELETE /api/agent/tasks` route (then use `--reload` as usual).
2. **Run the helper script** (clears queue and resets PM, then creates the spec task for item 0):
   ```bash
   ./scripts/clear_queue_and_start_flow.sh
   ```
   Or manually:
   - Clear queue: `curl -X DELETE "http://localhost:8000/api/agent/tasks?confirm=clear"`
   - Reset PM and create spec task: `cd api && .venv/bin/python scripts/project_manager.py --once -v --reset`
3. **Run the agent runner** so it executes the spec task (no deps). The runner **only runs tasks whose `depends_on_task_ids` are all completed**, so impl/test/review run in order after spec.
4. After spec completes, run **PM --once** again to create the impl task (with `depends_on_task_ids=[spec_task_id]`); then runner again, and so on.

### Full chain demo (when ready)

- **Quick verification (no API):** `cd api && .venv/bin/pytest tests/test_project_manager.py -q && .venv/bin/python scripts/project_manager.py --dry-run --reset` → both pass.
- **Live demo (API + runner + PM):**
1. Start API: `cd api && uvicorn app.main:app --reload --port 8000`
2. Start agent_runner: `cd api && .venv/bin/python scripts/agent_runner.py --once -v` (or leave running)
3. Run PM: `cd api && .venv/bin/python scripts/project_manager.py --once -v` (repeat or run with --interval)
4. Chain: backlog item → spec task (created) → runner runs spec → PM creates impl with depends_on_task_ids=[spec_id] → runner runs impl → … → review → acceptance gate → next item
5. Verify: `GET /api/agent/tasks` for status; `api/logs/acceptance_evidence_item_*.json` after an item passes review

### Next actions (in order)

1. ~~Fix ruff~~ Done
2. ~~Optionally add split/combine to run_parallel()~~ Done
3. ~~Use depends_on in parallel mode~~ Done
4. ~~Scheduler blocks tasks with unsatisfied dependencies~~ Done (runner filters by depends_on_task_ids)
5. ~~Wire project_manager to set depends_on_task_ids~~ Done
6. ~~Acceptance as first-class gate~~ Done
7. ~~Test/review auto follow-up~~ Done (corrective impl has depends_on_task_ids; direction includes output/fail_reason)
8. Full chain demo: run API + runner + PM and confirm one idea flows spec→impl→test→review→acceptance (manual when ready; quick verification without API: pytest + dry-run pass)

---

## Next Steps

1. Review the cheaper model's proposal against the checklist in `Dependency Analysis For Follow-up Review`
2. Implement dependency-aware scheduling before treating any future run as end-to-end idea proof
3. Run agent_runner until task_a0689d958a5e54af (spec for tracking-audit-anomaly-detection) executes
4. After spec completes: create dependency-linked impl, test, review, and acceptance tasks via API
5. Run the chain in order and record artifacts for the target idea only after the dependencies are enforced
