# Spec 163 — Pipeline Data Flow: Code Must Reach origin/main Before Phase Advancement

**Spec ID**: task_99ebbbbf852dfff6
**Status**: draft
**Author**: product-manager agent
**Date**: 2026-03-28
**Priority**: Critical

---

## Summary

The Coherence Network pipeline operates across multiple distributed nodes: a provider (sandboxed
AI agent) writes code in a worktree, the runner merges and deploys it, and a verifier confirms
production availability. Without tight coordination at each handoff, code can stay trapped on a
single node and never reach production. This spec defines 7 explicit fixes that close the gaps
in the data flow, with observable proof criteria for each fix.

The 7 fixes are:
1. `git fetch origin/main` before worktree creation — prevent stale base
2. Capture `git diff` after provider execution — not just stdout text
3. Push to `origin/main` after merge — not just local merge
4. Block phase advancement until push succeeds
5. Keep worktree until push is confirmed — don't delete the only copy of the code
6. Deploy phase = runner action (has SSH) not provider action (sandboxed)
7. Verify phase = runner runs curl scenarios, not provider hallucinating results

---

## Problem Statement

The pipeline lifecycle is: `spec → impl → test → code-review → deploy → verify`. Each phase
runs on a potentially different node. Code written in the `impl` phase must travel through git
to be available to all subsequent phases. Without explicit handoff guarantees, code stays local.

### Observed failure modes (before fixes)

| # | Failure mode | Symptom |
|---|-------------|---------|
| 1 | Stale worktree base | impl writes on old commit; merge conflicts block code-review |
| 2 | Diff not captured | Runner sees "success" in stdout but no code was committed; phase advances on a lie |
| 3 | Local-only merge | code-review passes and merges locally; push to origin silently fails; deploy fetches old code |
| 4 | Phase advances before push | deploy starts with stale code because runner advanced the phase when push was in flight |
| 5 | Worktree deleted too early | push fails; the only copy of the code was in the worktree; irrecoverable loss |
| 6 | Provider tries SSH deploy | provider is sandboxed; SSH fails; deploy is recorded as failed but nothing was deployed |
| 7 | Provider hallucinates verify | provider reports "endpoint returns 200" without actually running curl; verify passes on a lie |

---

## Requirements

### R1 — Fetch before worktree creation

Before calling `git worktree add`, the runner MUST run:
```
git fetch origin --quiet
```
and use `origin/main` (not `main`) as the base reference. This ensures the worktree starts
from the current remote state even if the local `main` ref is behind.

**Current state**: `_create_worktree()` already does this (lines 4082–4090 of local_runner.py).
This requirement is SATISFIED. The spec must verify it stays this way and is not regressed.

### R2 — Capture git diff, not just stdout

After a provider task completes, the runner MUST call `_capture_worktree_diff()` which runs
`git add -A && git diff --cached` inside the worktree, not parse the provider's stdout for
file mentions. The diff is the ground truth — stdout is an unverified claim.

The diff MUST be:
- Stored in `context.diff_content` (up to 10KB)
- Used to gate the "produced code" check: no diff → no code, even if stdout says otherwise
- Passed forward to retry tasks so partial work survives timeout

**Current state**: `_run_task_in_worktree()` captures the diff (Fix 2, confirmed). This
requirement verifies no regression.

### R3 — Push origin/main after merge (not just local)

After `code-review` passes and `_merge_branch_to_main()` runs, the function MUST push to
`origin/main`:
```
git push origin main
```
If the push fails, `_merge_branch_to_main()` MUST return `False`.

**Current state**: `_merge_branch_to_main()` already pushes (lines 4321–4340). SATISFIED.

### R4 — Block phase advancement until push succeeds

After impl/test phases: the runner MUST check `pushed = _push_branch_to_origin(...)`. If
`pushed` is `False`, phase advancement MUST NOT happen. The worker code must treat
`pushed == False` as equivalent to `ok == False` for the purpose of phase gating.

After code-review: `merged = _merge_branch_to_main(...)`. If `merged` is `False`, no `deploy`
task must be created.

This is the critical gate. Phase advancement happens in `_post_task_hook()` which checks the
task completion status. The worker sets `pushed = False` to signal the push failed. The
`complete_task()` call must include `push_succeeded: False` in the context so the hook can
distinguish "task ok but push failed" from "task ok and push ok".

**Gap identified**: Currently the worker may call `complete_task(task_id, output, ok=True)`
even when `pushed == False` for impl tasks, allowing the hook to advance the phase. This MUST
be fixed: if `ok and not pushed` for impl/test, the task must be completed as `ok=False` or
a special `push_failed` status must gate the phase.

**Acceptance criteria**:
- `pushed == False` → next phase is NOT created
- Log line `BRANCH_PUSH_FAILED` appears in runner log
- Task remains in `failed` or `push_pending` state — not `completed`

### R5 — Keep worktree until push is confirmed

The worktree is the only copy of the written code until `_push_branch_to_origin()` succeeds.
The runner MUST NOT call `_cleanup_worktree()` until either:
- Push succeeded (`pushed == True`), OR
- Task failed and there is no code to preserve

The `finally` block in the worker MUST implement this guard:
```python
# Only clean up if push succeeded or task failed entirely (no code)
if wt and (pushed or not ok):
    _cleanup_worktree(task_id)
elif wt and not pushed:
    log.warning("KEEPING_WORKTREE — push failed, code preserved in %s", wt_path)
```

**Current state**: This logic exists (Fix 5, lines 4584–4589). SATISFIED. Must not regress.

### R6 — Deploy phase is a runner action, not a provider task

The `deploy` phase MUST be executed by the runner using `_runner_deploy_phase()` which SSHes
to the VPS. A provider (sandboxed AI) cannot perform SSH operations. If a `deploy` task is
routed to a provider, the deploy will fail silently.

Implementation:
```python
if task_type == "deploy":
    ok = _runner_deploy_phase(task)
    pushed = True  # deploy handles its own git (push to main already done)
```

This guard MUST be in the worker execution path, not a flag in the task that a provider could
override.

**Current state**: The `if task_type == "deploy"` guard exists (lines 4503–4507). SATISFIED.

### R7 — Verify phase is a runner action, not a provider task

The `verify` phase MUST be executed by the runner using `_runner_verify_phase()` which calls
`curl` or equivalent against the live production API (`https://api.coherencycoin.com`).

A provider asked to "verify production" will either:
- Make up results (hallucinate), or
- Succeed in a sandboxed environment that doesn't reflect production

Implementation:
```python
elif task_type == "verify":
    ok = _runner_verify_phase(task)
    pushed = True  # verify is read-only
```

**Current state**: The `elif task_type == "verify"` guard exists. SATISFIED.

---

## Observable Proof Criteria

The core question from the task brief is: **how do we show this is working, and make that proof
clearer over time?**

### P1 — Log corpus

Every data-flow event MUST produce a structured log line with a stable prefix that can be
grepped:

| Log prefix | When it fires |
|-----------|--------------|
| `WORKTREE_CREATED` | Worktree created from `origin/main` |
| `WORKTREE_DIFF` | Diff captured after provider runs |
| `BRANCH_PUSHED` | Branch pushed to origin successfully |
| `BRANCH_PUSH_FAILED` | Branch push failed — phase will not advance |
| `MERGED_TO_MAIN` | Branch merged and pushed to origin/main |
| `MAIN_PUSH_FAILED` | Push of merged main to origin failed |
| `KEEPING_WORKTREE` | Worktree kept because push failed |
| `WORKTREE_CLEANED` | Worktree deleted after push confirmed |
| `DEPLOY_RUNNER_START` | Deploy started by runner (not provider) |
| `VERIFY_RUNNER_START` | Verify started by runner (not provider) |

These log lines allow operators to trace a task through the pipeline by grepping `task=<slug>`.

### P2 — Runner health API

The runner's health endpoint (`GET /api/health`) SHOULD report data flow statistics:
```json
{
  "pipeline": {
    "tasks_with_code_pushed_24h": 12,
    "push_failures_24h": 1,
    "tasks_deployed_24h": 8,
    "tasks_verified_24h": 7,
    "worktrees_kept_on_push_fail": 0
  }
}
```
This gives an at-a-glance view of whether code is flowing end-to-end.

### P3 — Task context carries proof

Every completed impl/test task MUST have in its `context`:
```json
{
  "branch_pushed": true,
  "push_target": "origin/task/<slug>",
  "diff_size": 1240,
  "base_ref": "origin/main"
}
```
Every completed code-review task MUST have:
```json
{
  "merged_to_main": true,
  "push_target": "origin/main",
  "merged_sha": "abc1234"
}
```
This allows the runner to audit whether code actually reached origin, not just "the task said so".

---

## Files to Modify

| File | Change |
|------|--------|
| `api/scripts/local_runner.py` | Fix R4 gap: ensure `ok=False` when `pushed==False` for impl/test; add context fields from P3 |
| `api/scripts/local_runner.py` | Add `DEPLOY_RUNNER_START` and `VERIFY_RUNNER_START` log lines (P1) |
| `api/scripts/local_runner.py` | Ensure `_push_branch_to_origin` stores `push_target` in context patch |

---

## Verification Scenarios

### Scenario 1 — Impl task produces code and branch is pushed

**Setup**: A pending `impl` task exists in the API for an idea. Runner is running.

**Action**:
```bash
# Watch runner logs for the task
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'docker logs coherence-network-api-1 2>&1 | grep "BRANCH_PUSHED\|BRANCH_PUSH_FAILED" | tail -10'
```

**Expected result**: Within the task's execution window, log shows:
```
BRANCH_PUSHED task=<16-char-slug> branch=task/<slug>
```
Not: `BRANCH_PUSH_FAILED`

**Edge case**: If push fails, log shows `BRANCH_PUSH_FAILED` and the next phase (`test`) is NOT
created. Verify with:
```bash
curl -s https://api.coherencycoin.com/api/agent/tasks?idea_id=<idea_id>&task_type=test
# Must return empty list or 404 when impl push failed
```

---

### Scenario 2 — Worktree is preserved when push fails

**Setup**: Simulate a push failure by temporarily blocking network access (or use a task with a
broken push config in a test environment).

**Action**: Check runner log for `KEEPING_WORKTREE`:
```bash
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'docker logs coherence-network-api-1 2>&1 | grep "KEEPING_WORKTREE" | tail -5'
```

**Expected result**:
```
KEEPING_WORKTREE task=<slug> (push failed, code preserved)
```
The worktree directory still exists at `/docker/coherence-network/repo/.worktrees/task-<slug>/`.

**Edge case**: If push succeeds, `WORKTREE_CLEANED` appears instead. Worktree directory is
absent. No `KEEPING_WORKTREE` line.

---

### Scenario 3 — Code-review merge reaches origin/main

**Setup**: An `impl` task has completed and a `code-review` task passes.

**Action**:
```bash
# After code-review task completes, check origin/main
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'cd /docker/coherence-network/repo && git fetch origin && git log origin/main --oneline -5'
```

**Expected result**: The merged commit appears in `origin/main` within 60 seconds of
`code-review` task completion. Log shows:
```
MERGED_TO_MAIN task=<slug>
```

**Edge case**: If merge conflicts, log shows `MERGE_CONFLICT task=<slug>`. The `deploy` phase
task is NOT created. Verify:
```bash
curl -s https://api.coherencycoin.com/api/agent/tasks?task_type=deploy | jq '.[] | select(.context.auto_phase_advanced_from=="code-review")'
# Returns empty when merge failed
```

---

### Scenario 4 — Deploy and Verify phases are executed by runner, not provider

**Setup**: A task with `task_type=deploy` exists in the queue.

**Action**:
```bash
# Check runner logs for deploy execution
ssh -i ~/.ssh/hostinger-openclaw root@187.77.152.42 \
  'docker logs coherence-network-api-1 2>&1 | grep "DEPLOY_RUNNER_START\|VERIFY_RUNNER_START" | tail -10'
```

**Expected result**: Lines appear confirming runner executed deploy/verify:
```
DEPLOY_RUNNER_START task=<slug>
VERIFY_RUNNER_START task=<slug>
```
No provider is assigned to these task types (they are handled in the `if task_type == "deploy"`
branch before provider dispatch).

**Edge case**: If a deploy task somehow reaches a provider, the provider will return
`DEPLOY_FAILED: SSH not available in sandboxed environment`. The runner must detect this and
not advance to verify.

---

### Scenario 5 — End-to-end data flow trace for a single idea

**Setup**: Pick an idea that has recently completed the full pipeline.

**Action**:
```bash
# Get the idea's tasks
IDEA_ID="<idea_id>"
curl -s https://api.coherencycoin.com/api/ideas/$IDEA_ID/tasks | \
  jq '.groups[] | {phase: .task_type, status: .status_counts, context_keys: [.tasks[0].context | keys]}'
```

**Expected result**: Each phase task's context contains proof of the handoff:
- `impl` task context: `branch_pushed: true`, `diff_size > 0`, `base_ref: "origin/main"`
- `code-review` task context: `merged_to_main: true`, `merged_sha: "<sha>"`
- `deploy` task context: `deployed_sha: "<sha>"`, `health_check: "passed"`
- `verify` task context: `scenarios_passed: N`, `scenarios_failed: 0`

**Edge case**: If any context field is missing or `false`, that specific fix is not yet
implemented. The missing field is the gap.

---

## Risks and Assumptions

| Risk | Mitigation |
|------|-----------|
| `git push origin main` fails due to concurrent pushes from two nodes | Implement retry with exponential backoff (3 retries, 2s/4s/8s). If all fail, mark code-review as failed and let the pipeline retry. |
| Worktrees accumulate if push never recovers | `_sweep_stale_worktrees(max_age_hours=2)` already handles this. Ensure it runs even when a push-failed task is keeping a worktree. |
| Provider returns `DEPLOY_PASSED` in stdout without actually deploying | R6 guard prevents provider from executing deploy; the runner's `_runner_deploy_phase` is the canonical executor. |
| Network latency causes push timeout to look like failure | Use 60s timeout for push. Log the exit code and stderr to distinguish timeout from auth failure. |
| Two nodes pick up the same code-review task | Task claiming is idempotent via API. Only one node can claim a task; the other gets a 409. |

---

## Known Gaps and Follow-up Tasks

1. **Push retry logic**: `_push_branch_to_origin` does not retry on transient failure. A
   follow-up task should add retry with backoff (max 3 attempts).

2. **Context patch for `merged_sha`**: `_merge_branch_to_main` does not currently capture the
   SHA of the merged commit and write it to the task context. A follow-up impl task should
   capture `git rev-parse HEAD` after merge and include it in a context patch.

3. **Health API data flow stats**: The `/api/health` endpoint does not yet return pipeline
   push/deploy/verify counts. Follow-up spec to add `pipeline` section to health payload.

4. **Stale worktree alert**: If a worktree has been kept for > 1 hour (push-failed), an alert
   should be sent via `cc msg broadcast` so operators can investigate the push failure.

5. **Deploy phase SSH key rotation**: The deploy phase uses the VPS SSH key hardcoded in
   runner config. If the key rotates, all deploy phases will fail silently. Add a preflight
   SSH connectivity check at runner startup.

---

## Acceptance Criteria Summary

| # | Criterion | Verifiable |
|---|-----------|-----------|
| AC-1 | Worktree base is always `origin/main` (fetched before create) | `WORKTREE_CREATED` log shows `base=origin/main` |
| AC-2 | Diff captured after provider run, not inferred from stdout | Task context has `diff_size > 0` for all impl tasks that changed files |
| AC-3 | Branch pushed to origin after impl/test completes | `BRANCH_PUSHED` log line, branch visible on GitHub |
| AC-4 | Phase does NOT advance if push failed | No `test` task created when `BRANCH_PUSH_FAILED` appears for `impl` |
| AC-5 | Worktree NOT deleted until push confirmed | `KEEPING_WORKTREE` log when push fails; directory exists |
| AC-6 | Deploy runs via runner SSH, not provider | `DEPLOY_RUNNER_START` log; provider never receives a `deploy` task |
| AC-7 | Verify runs via runner curl, not provider | `VERIFY_RUNNER_START` log; provider never receives a `verify` task |
| AC-8 | Task context carries data-flow proof fields | See Scenario 5 for specific fields per phase |
