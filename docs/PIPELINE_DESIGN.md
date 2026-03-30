# Pipeline Design — Authoritative Contract

> Last updated: 2026-03-30
> This document is the single source of truth for how the runner pipeline works.
> Every bug fix and feature change to `local_runner.py` MUST update this document.
> Do not patch code without first updating the design here.

---

## 1. Core Invariants

These invariants must hold at all times. Any violation is a pipeline bug.

| # | Invariant |
|---|-----------|
| I-1 | A task transitions through exactly one phase at a time. Phase order is `spec → impl → test → code-review → merge → deploy → verify → reflect`. |
| I-2 | No task is seeded for phase N+1 unless phase N has a **completed** task with **non-empty output** for the same idea. |
| I-3 | `test` and `code-review` tasks MUST have `impl_branch` in context. Without it, they always fail — no exceptions. |
| I-4 | Every failure MUST set `error_category` and `error_summary` before marking `status=failed`. |
| I-5 | The pipeline direction string must not exceed 4900 characters (5000 is the API limit; 100-char safety buffer). |
| I-6 | Every spec task completion MUST attempt to advance to `impl` (not `test`). |
| I-7 | Provider capability gate is a hard block, not a fallback. If no provider can satisfy task requirements, the task is rejected before seeding. |
| I-8 | The circuit breaker fires after 10 consecutive failures or >80% failure rate in last 20 tasks. When tripped, no new tasks are seeded. |

---

## 2. Phase Sequence

```
spec → impl → test → code-review → merge → deploy → verify → reflect
```

**Phase prerequisites** (seeder must verify before creating):

| Phase | Prerequisite |
|-------|-------------|
| impl | spec completed with non-empty output AND spec file exists in `specs/` |
| test | impl completed with `impl_branch` in context |
| code-review | impl completed with `impl_branch` OR `pr_number` in context |
| merge | code-review or review completed with passing output |
| deploy | merge completed |
| verify | deploy completed |
| reflect | verify completed |

---

## 3. Seeder Phase Ladder (Canonical)

The seeder reads `completed_phases` from the idea's task history and picks the **next uncompleted phase**:

```python
# Correct phase ladder (invariant I-2):
if review_phase_completed and review_passed:
    task_type = "merge"
elif "impl" in completed_phases:
    task_type = "code-review"   # was incorrectly "review" in some versions
elif "spec" in completed_phases:
    task_type = "impl"          # CRITICAL: spec done → impl, NOT test
elif idea has no tasks:
    task_type = "spec"
```

**Known bug (fixed 2026-03-30):** Seeder had `spec done → test` which violated I-1/I-2.
Root cause: Phase order was changed from `spec→test→impl` to `spec→impl→test` but the seeder's
elif chain was not updated. The `test` step now requires `impl_branch` which only exists after
`impl` runs — so `test` tasks seeded without `impl` always fail immediately at the hard gate.

---

## 4. Direction Overflow — 5000-Character Limit

The API enforces a 5000-character limit on `direction`. The auto-phase advance hook builds direction by combining:
- Idea scope header (~150 chars)
- Phase-specific instruction (~800 chars)
- For `impl`: spec file content (was 3000 chars, **now capped at 1200**)
- Description (capped at 300 chars)
- Failure context (capped at 600 chars × 2 failures)

**Fixed 2026-03-30:** Added hard defensive cap (`direction = direction[:4900]`) before every `POST /api/agent/tasks` in `_run_phase_auto_advance_hook`. Also reduced spec_content read from 3000 to 1200 chars.

**Design rule:** Any code that builds a `direction` string MUST enforce `len(direction) <= 4900` before submission. The spec content belongs in context (as `spec_path`), not inline in direction.

---

## 5. Error Classification

Every failure path must set a specific `error_category`. Generic `execution_error` is a fallback of last resort.

| Failure Scenario | `error_category` |
|-----------------|-----------------|
| No `impl_branch` for test/review | `impl_branch_missing` |
| Worktree creation failed | `worktree_failed` |
| Provider push failed | `push_failed` |
| No code changes produced | `no_diff` |
| Task timed out | `timeout` |
| Stale task reaped on startup | `stale_task_reaped` |
| Generic execution error | `execution_error` |
| Direction too long (422) | `direction_overflow` — seeder should retry with truncated direction |

**Gap identified 2026-03-30:** Tasks failed at the `impl_branch_missing` gate were reporting `error_category: None` in the API because the previous session's tasks didn't have the fix. New tasks correctly get `impl_branch_missing` category.

---

## 6. Task Isolation Model

Each task gets its own git worktree at `.worktrees/task-{task_id}`:

1. **Worktree creation**: `git worktree add -b task/{slug} {path} origin/main`
2. For `test`/`code-review`: base branch is `impl_branch` (the PR branch), not `origin/main`
3. Worktree is cleaned up after task completion (success or failure)
4. If worktree creation fails → task is immediately failed with `error_category=worktree_failed`

**Hard rule:** There are NO fallbacks for missing worktrees or missing `impl_branch`. Fallbacks mask bugs.

---

## 7. Circuit Breaker

```
_CircuitBreaker(window_size=20, trip_threshold=10, cooldown_seconds=600)
```

- Trips when: 10 consecutive failures OR >80% failure rate in last 20 tasks
- When tripped: `allow_seeding()` returns `False` — no new tasks are seeded
- Reset: `cc cmd mac resume` sends a message to the runner to reset the breaker
- Cooldown: 10 minutes, then auto-resets

**Gap identified 2026-03-30:** The circuit breaker correctly tripped on `impl_branch_missing` failures
(3 test tasks). However, these failures were caused by the **seeder phase ladder bug** (seeding `test`
before `impl`). The circuit breaker fired on a symptom, not the root cause. Fix: the circuit breaker
should NOT count `impl_branch_missing` failures against itself — those are seeder logic errors, not
provider execution failures.

---

## 8. Hollow Completion Detection

A task is "hollow" if it completes with `output` null or len < 50. Hollow completions mean the provider
ran successfully (rc=0) but produced no meaningful output.

**Observed 2026-03-30:** spec tasks completed with `output: None` even though the provider wrote files
to the worktree. Root cause: the runner sets output from provider's stdout, but spec tasks write to files
(not stdout). The runner should set output to the spec file path + first 200 chars of the spec.

**Design rule:** After any file-writing task (spec, impl, test), if stdout output is empty, set output
to `"FILES_WRITTEN: {list of changed files}"` from `git diff --name-only`.

---

## 9. Provider Assignment Rules

Providers are assigned by the `select_provider()` capability gate:

| Provider | Capabilities |
|----------|-------------|
| claude | file_write, git, tools (full code capabilities) |
| codex | file_write, git, tools |
| gemini | file_write, git, tools |
| cursor | file_write, git, tools |
| ollama-local | text_only (NO code tasks) |
| ollama-cloud | text_only (NO code tasks) |
| openrouter | DISABLED (hollow completions, no PR capability) |

**Hard rule:** If no provider has the required capabilities, raise `RuntimeError`. Never fall back to a provider that can't do the job.

---

## 10. Design Gaps Registry

| Gap ID | Discovered | Status | Description |
|--------|-----------|--------|-------------|
| DG-001 | 2026-03-30 | FIXED | Seeder phase ladder: spec→test instead of spec→impl |
| DG-002 | 2026-03-30 | FIXED | Direction overflow: spec content pushed impl direction > 5000 chars |
| DG-003 | 2026-03-30 | IN PROGRESS | Hollow spec output: provider writes files but output field = None |
| DG-004 | 2026-03-29 | FIXED | Parallel mode not seeding: main loop skipped seeder in parallel mode |
| DG-005 | 2026-03-29 | FIXED | Worktree symlinks: references/ pointed outside repo, broke git clone --local |
| DG-006 | 2026-03-29 | FIXED | openrouter selected for code tasks: no capability check |
| DG-007 | 2026-03-29 | FIXED | Merge via git push: no auth token, always 403 |
| DG-008 | 2026-03-29 | FIXED | impl never created PRs: no _create_pr_for_branch() call |
| DG-009 | 2026-03-29 | FIXED | Exponential backoff using _SEEDER_SKIP_CACHE: permanently blacklisted ideas |
| DG-010 | 2026-03-30 | OPEN | Circuit breaker counts seeder-logic failures (impl_branch_missing) as provider failures |
| DG-011 | 2026-03-30 | OPEN | Test tasks for wrong phase consume worker slots before circuit breaker trips |
| DG-012 | 2026-03-30 | FIXED | `impl_branch` never propagated to test tasks — set in impl task context immediately after branch push in runner, and forwarded by `pipeline_advance_service.maybe_advance()` to downstream tasks. PR creation failure no longer blocks phase advancement. |
| DG-013 | 2026-03-30 | FIXED | Global _REPO_DIR mutated by worker thread, race condition breaks all subsequent worktree creation in parallel mode |
| DG-014 | 2026-03-30 | FIXED | Evidence check used fuzzy full-text GitHub PR search — spec/doc PRs mentioning idea names marked them as "implemented", blocking them from ever being seeded for impl |
| DG-015 | 2026-03-30 | FIXED | `error_category` and `error_summary` never persisted — API router received them but didn't pass to `update_task()`, service didn't accept them, store didn't write them, `_row_to_payload` didn't load them. All 4 broken links fixed. |
| DG-016 | 2026-03-30 | FIXED | `maybe_retry()` created retries for `impl_branch_missing` and `worktree_failed` — structural prerequisite failures that retrying cannot fix. Each retry also failed instantly, triggering another retry, creating an infinite cascade that consumed all task slots. Fixed: skip retry for non-retriable error categories; also propagate `impl_branch`/`pr_url` in retry context so valid retries don't lose branch ref. |

---

## 11. Monitoring

The pipeline is monitored every 20 minutes. Each cycle:
1. Fetch `running`, `failed`, `completed` task counts
2. Classify failures by `error_category`
3. Detect instant failures (< 5 sec) — always indicates a structural bug, not a provider failure
4. Detect hollow completions (output len < 50)
5. Root-cause any new failure patterns and add to DG registry
6. Update this document with new gaps found
7. Implement structural fixes (not patches) that match updated design

---

## 12. Key Files

| File | Purpose |
|------|---------|
| `api/scripts/local_runner.py` | The entire pipeline engine |
| `api/config/model_routing.json` | Provider routing configuration |
| `specs/` | Idea specifications |
| `.worktrees/` | Active git worktrees per task |
| `/tmp/runner.log` | Runner log (current session) |
| `~/.coherence-network/keys.json` | API keys (never in git) |
