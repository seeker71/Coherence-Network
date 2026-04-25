---
idea_id: agent-pipeline
status: done
source:
  - file: api/scripts/project_manager.py
    symbols: [spec/impl/test/review cycle, split_item(), is_too_large()]
  - file: api/app/services/pipeline_advance_service.py
    symbols: [_extract_partial_work(), _find_spec_file()]
  - file: api/app/services/agent_service_pipeline_status.py
    symbols: [get_pipeline_status()]
requirements:
  - "Orchestrator finds the next task from a backlog (specs/, docs/PLAN.md, or config)"
  - "For each task, runs phases in order: spec → impl → test → review"
  - "After review, validates: pytest passes and review output indicates pass"
  - "If validation fails: loops back to impl (fix), then test, then review until all pass or max iterations"
  - "If validation passes: advances to next task, starts with spec phase"
  - "On needs_decision: orchestrator pauses, does not create new tasks until human /reply"
  - "State persists across restarts (backlog index, current phase, iteration)"
  - "Uses local models for spec/test/impl/review; HEAL only for CI fixes when needed"
  - "PM complete: : Running the project manager with `--dry-run` exits 0 and logs deterministic preview (backlog index, phase, next item)."
  - "E2E smoke test: : A test runs the project manager in a mode that verifies end-to-end behavior (e.g. subprocess `--dry-run` exit 0, or `-"
done_when:
  - "Orchestrator finds the next task from a backlog (specs/, docs/PLAN.md, or config)"
  - "For each task, runs phases in order: spec → impl → test → review"
  - "After review, validates: pytest passes and review output indicates pass"
  - "If validation fails: loops back to impl (fix), then test, then review until all pass or max iterations"
  - "If validation passes: advances to next task, starts with spec phase"
test: "cd api && python -m pytest api/tests/test_project_manager_pipeline.py -q"
constraints:
  - "changes scoped to listed files only"
  - "no schema migrations without explicit approval"
---

> **Parent idea**: [agent-pipeline](../ideas/agent-pipeline.md)
> **Source**: [`api/scripts/project_manager.py`](../api/scripts/project_manager.py) | [`api/app/services/pipeline_advance_service.py`](../api/app/services/pipeline_advance_service.py) | [`api/app/services/agent_service_pipeline_status.py`](../api/app/services/agent_service_pipeline_status.py)

# Spec: Project Manager Pipeline

## Purpose

Implement a project manager orchestrator that automates the full spec-driven cycle: find the next work item, design (spec), implement, test, review, and validate against the spec until all passes, then advance to the next task. The project manager replaces ad-hoc impl-only runs with a structured spec → impl → test → review loop.

## Requirements

- [x] Orchestrator finds the next task from a backlog (specs/, docs/PLAN.md, or config)
- [x] For each task, runs phases in order: spec → impl → test → review
- [x] After review, validates: pytest passes and review output indicates pass
- [x] If validation fails: loops back to impl (fix), then test, then review until all pass or max iterations
- [x] If validation passes: advances to next task, starts with spec phase
- [x] On needs_decision: orchestrator pauses, does not create new tasks until human /reply
- [x] State persists across restarts (backlog index, current phase, iteration)
- [x] Uses local models for spec/test/impl/review; HEAL only for CI fixes when needed
- [x] **PM complete**: Running the project manager with `--dry-run` exits 0 and logs deterministic preview (backlog index, phase, next item). Running with `--once` and API available completes one cycle without unhandled exception; state advances or remains consistent.
- [x] **E2E smoke test**: A test runs the project manager in a mode that verifies end-to-end behavior (e.g. subprocess `--dry-run` exit 0, or `--once` with live API) and asserts no crash and consistent state. Test lives in `api/tests/` and is run by CI.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: 002, 006

## Task Card

```yaml
goal: Implement a project manager orchestrator that automates the full spec-driven cycle: find the next work item, design (spec), implement, test, review, and validate against the spec until all passes, then advance to the next task.
files_allowed:
  - api/scripts/project_manager.py
  - specs/backlog.md
  - docs/AGENT-ARCHITECTURE.md
  - api/tests/test_project_manager_pipeline.py
done_when:
  - Orchestrator finds the next task from a backlog (specs/, docs/PLAN.md, or config)
  - For each task, runs phases in order: spec → impl → test → review
  - After review, validates: pytest passes and review output indicates pass
  - If validation fails: loops back to impl (fix), then test, then review until all pass or max iterations
  - If validation passes: advances to next task, starts with spec phase
commands:
  - cd api && python -m pytest api/tests/test_project_manager_pipeline.py -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

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


## Verification (PM complete)

- **Dry-run**: `python api/scripts/project_manager.py --dry-run` must exit 0; output reflects current state and what would be done (no HTTP calls).
- **Once with API**: With API running and backlog present, `python api/scripts/project_manager.py --once` completes one tick (create task or poll/advance); exit 0 and no unhandled exception.
- **State consistency**: After any run, `api/logs/project_manager_state.json` is valid JSON and contains expected keys (backlog_index, phase, etc.).

## Pipeline Phases

| Phase | task_type | Subagent | Purpose |
|-------|-----------|----------|---------|
| spec | spec | product-manager | Design: write or expand spec for the work item |
| impl | impl | dev-engineer | Implement per spec |
| test | test | qa-engineer | Write/run tests, report failures |
| review | review | reviewer | Check correctness, security, spec compliance |

Validation: `cd api && pytest -v` exit 0 and review output contains "pass" (or equivalent). If either fails, loop to impl with direction "Fix the issues: [review feedback or test failures]. Implement only per spec."

## Backlog

Primary source: `specs/backlog.md` (created by this spec) — list of work items, one per line or in structured format. Fallback: scan specs/ for uncompleted items, or use docs/PLAN.md Sprint items. Alternate backlog: `specs/overnight-backlog.md` via `--backlog`.

## API Contract

No new API endpoints. Uses existing:

- `POST /api/agent/tasks` — create task with task_type and direction
- `GET /api/agent/tasks?status=pending` — check for pending
- `GET /api/agent/tasks?status=needs_decision` — check if blocked
- `GET /api/agent/tasks/{id}` — poll task until completed/failed/needs_decision
- `GET /api/health` — used at startup to verify API reachable


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model

Orchestrator state (file: `api/logs/project_manager_state.json`):

```json
{
  "backlog_index": 0,
  "current_task_id": "task_xxx",
  "phase": "spec|impl|test|review",
  "iteration": 1,
  "blocked": false
}
```

## Files to Create/Modify

- `api/scripts/project_manager.py` — orchestrator script (replaces overnight_orchestrator.py behavior)
- `specs/backlog.md` — backlog of work items
- `docs/AGENT-ARCHITECTURE.md` — add section on project manager pipeline
- `api/tests/test_project_manager_pipeline.py` or `api/tests/test_project_manager.py` — add E2E smoke test (subprocess or in-process run of PM with --dry-run or --once; assert exit 0 and state/log consistency)

## Acceptance Tests

- [x] Run `python api/scripts/project_manager.py --once --verbose`: creates spec task for first backlog item (or pauses on needs_decision)
- [x] After spec completes, creates impl task with direction referencing that spec
- [x] After impl completes, creates test task
- [x] After test completes, creates review task
- [x] If pytest fails after review, creates impl task with fix direction
- [x] When needs_decision task exists, orchestrator does not create new tasks
- [x] Run `python api/scripts/project_manager.py --dry-run`: exits 0, no HTTP calls, logs preview
- [x] **E2E smoke test**: A test in `api/tests/` runs `project_manager.py --dry-run` (subprocess or equivalent) and asserts exit code 0 and no unhandled exception; CI runs this test. Optionally, with API available, a smoke test runs `--once` and asserts state file is valid and process exits 0.

See `api/tests/test_project_manager.py` and `api/tests/test_project_manager_pipeline.py` — all tests must pass.

## Out of Scope

- Human-in-the-loop task selection (backlog is predefined)
- HEAL integration (separate; HEAL for CI only)
- Web UI for pipeline status
- Parallel tasks (one pipeline at a time; spec 028 covers parallel mode separately)

## See also

- [002-agent-orchestration-api.md](agent-orchestration-api.md) — API used by orchestrator
- [006-overnight-backlog.md](../docs/planning/006-overnight-backlog.md) — overnight backlog format (archived)

## Decision Gates

- Backlog format and content: human maintains specs/backlog.md
- needs_decision: human must /reply before pipeline resumes

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
