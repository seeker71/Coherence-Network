# Spec: Pipeline Full Automation

## Purpose

Close the loop on autonomous operation: auto-commit progress so work persists to git, and auto-generate meta-pipeline tasks from failure patterns so the system improves itself. Enables fully unattended runs with measurable, committed progress toward the overall goal.

## Requirements

### Auto-Commit
- [ ] When `PIPELINE_AUTO_COMMIT=1`, pipeline commits file changes after each completed task (spec/impl/test/review; not heal).
- [ ] Commit runs from project root; message format: `[pipeline] {task_type} {task_id}: {short_direction}`.
- [ ] Skip commit when no changes (`git status --porcelain` empty); skip when not a git repo.
- [ ] Optional `PIPELINE_AUTO_PUSH=1` runs `git push` after commit (default off; use with caution).
- [ ] Agent runner invokes commit after PATCH returns for completed tasks when env is set.

### Auto-Generate Meta Tasks
- [ ] When monitor detects `low_success_rate`, create heal task (in addition to issue) when auto-fix enabled.
- [ ] Heal task direction for repeated_failures includes: "Suggest meta-pipeline item to specs/007-meta-pipeline-backlog.md if root cause identified."
- [ ] When monitor detects `low_success_rate`, heal task direction: "Analyze 7d success rate; suggest prompt/model/meta improvements."

### Wiring
- [ ] run_overnight_pipeline.sh and run_autonomous.sh document PIPELINE_AUTO_COMMIT and PIPELINE_AUTO_PUSH in logs when set.
- [ ] Docs (RUNBOOK, PIPELINE-ATTENTION) describe auto-commit behavior.

## Files to Create/Modify

- `api/scripts/agent_runner.py` — call commit helper after completed task when PIPELINE_AUTO_COMMIT=1
- `api/scripts/commit_progress.py` — new: git add, commit, optional push; no-op when no changes
- `api/scripts/monitor_pipeline.py` — add heal task for low_success_rate; enhance repeated_failures direction
- `docs/RUNBOOK.md` — add auto-commit section
- `docs/PIPELINE-ATTENTION.md` — add auto-commit env vars

## Additional Automation (run_autonomous)

- **API restart on metrics 404:** When API is up but GET /api/agent/metrics returns 404, autonomous loop restarts API to load new routes.
- **Pipeline restart when runner hung:** When no_task_running for 10+ min, monitor writes restart_requested; watchdog restarts pipeline.

## Out of Scope

- Auto-push in CI (separate concern; spec 027 covers CI).
- Modifying SPEC-COVERAGE/STATUS from pipeline (handled by update_spec_coverage.py in CI).
- Automated PR creation.

## Decision Gates

- `PIPELINE_AUTO_COMMIT` default off in .env.example; enable in autonomous runs via run_autonomous.
- `PIPELINE_AUTO_PUSH` default off; human enables only when confident in pipeline quality.
