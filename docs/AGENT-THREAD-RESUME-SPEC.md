# Agent Thread Resume Spec

## Purpose

Define a durable Codex worker loop for implementation tasks so partial progress is never lost and a second worker can continue from a pushed checkpoint.

## Control Plane

- API task store remains the orchestration source of truth for `pending`/`running`/`failed`/`completed`.
  Use `AGENT_TASKS_DATABASE_URL` + `AGENT_TASKS_USE_DB=1` for shared multi-instance task visibility.
- Git branch state is the source of truth for code progress.
- Worker run state is mirrored to API lease endpoints (`/api/agent/run-state/*`) for cross-worker ownership.
- Worker run state is also persisted in `api/logs/agent_runner_runs.json` for local restart telemetry.

## Run Record Schema

Each attempt writes a run record keyed by `run_id` with these fields:

- `run_id`
- `task_id`
- `attempt`
- `status`
- `worker_id`
- `task_type`
- `direction`
- `branch`
- `repo_path`
- `started_at`
- `last_heartbeat_at`
- `completed_at`
- `head_sha`
- `checkpoint_sha`
- `failure_class`
- `next_action`

## Branch Strategy

- Branch name defaults to `codex/<task_id>`.
- If `origin/<branch>` exists, worker resumes from that branch head.
- If no remote branch exists, worker creates branch from `origin/main` (fallback local `main`).

## Failure Classes

- `usage_limit`
- `timeout`
- `killed`
- `command_failed`
- `branch_setup_failed`
- `claim_conflict`
- `claim_failed`
- `runner_exception`

## Checkpoint + Resume Contract

When PR-mode execution fails:

1. Stage all changes.
2. Commit checkpoint: `[checkpoint] task <id> run <run_id>: <reason>`.
3. Push branch to origin.
4. Patch task context with:
   - `resume_branch`
   - `resume_checkpoint_sha`
   - `resume_ready`
   - `resume_reason`
   - `resume_from_run_id`
   - `resume_attempts`
   - `last_failure_class`
   - `next_action`

## Requeue Policy

- Requeue automatically (`status=pending`) only when:
  - checkpoint push succeeded, and
  - failure class is `usage_limit` or `timeout`, and
  - `resume_attempts < max_resume_attempts`.
- Otherwise mark `failed` with checkpoint metadata for manual or explicit follow-up recovery.

## Runtime Controls

- `AGENT_TASK_TIMEOUT` hard upper bound.
- `AGENT_REPO_GIT_URL` optional clone source used when checkout path does not exist.
- `AGENT_TASKS_DATABASE_URL` optional explicit DB URL for shared task store (defaults to `DATABASE_URL`).
- `AGENT_TASKS_USE_DB` force-enable shared DB-backed task store.
- `AGENT_RUN_STATE_DATABASE_URL` optional explicit DB URL for shared lease/run-state storage (defaults to `DATABASE_URL`).
- Optional per-task `context.max_runtime_seconds`.
- `AGENT_MAX_RESUME_ATTEMPTS` default requeue budget for resumable failures.
- `AGENT_RUN_HEARTBEAT_SECONDS` run record heartbeat cadence.
- `AGENT_RUN_LEASE_SECONDS` lease TTL used by API run-state ownership checks.
- `AGENT_PERIODIC_CHECKPOINT_SECONDS` interval for automatic commit/push checkpoints during long runs.

## PR Completion Contract

After successful command execution:

1. Run local validation command (`AGENT_PR_LOCAL_VALIDATION_CMD`) unless skipped.
2. Commit and push branch changes.
3. Create/update PR.
4. Poll PR gate report.
5. Optionally auto-merge and optionally wait for public validation.
