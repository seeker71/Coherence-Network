# Spec: Project Manager Pipeline

## Purpose

Implement a project manager orchestrator that automates the full spec-driven cycle: find the next work item, design (spec), implement, test, review, and validate against the spec until all passes, then advance to the next task. The project manager orchestrator replaces ad-hoc impl-only runs with a structured spec → impl → test → review loop.

## Requirements

- [x] Orchestrator finds the next task from a backlog (specs/, docs/PLAN.md, or config)
- [x] For each task, runs phases in order: spec → impl → test → review
- [x] After review, validates: pytest passes and review output indicates pass
- [x] If validation fails: loops back to impl (fix), then test, then review until all pass or max iterations
- [x] If validation passes: advances to next task, starts with spec phase
- [x] On needs_decision: orchestrator pauses, does not create new tasks until human /reply
- [x] State persists across restarts (backlog index, current phase, iteration)
- [x] Uses local models for spec/test/impl/review; HEAL only for CI fixes when needed

## Pipeline Phases

| Phase | task_type | Subagent | Purpose |
|-------|-----------|----------|---------|
| spec | spec | product-manager | Design: write or expand spec for the work item |
| impl | impl | dev-engineer | Implement per spec |
| test | test | qa-engineer | Write/run tests, report failures |
| review | review | reviewer | Check correctness, security, spec compliance |

Validation: `cd api && pytest -v` exit 0 and review output contains "pass" (or equivalent). If either fails, loop to impl with direction "Fix the issues: [review feedback or test failures]. Implement only per spec."

## Backlog

Primary source: `specs/005-backlog.md` (created by this spec) — list of work items, one per line or in structured format. Fallback: scan specs/ for uncompleted items, or use docs/PLAN.md Sprint items.

## API Contract

No new API endpoints. Uses existing:
- `POST /api/agent/tasks` — create task with task_type and direction
- `GET /api/agent/tasks?status=pending` — check for pending
- `GET /api/agent/tasks?status=needs_decision` — check if blocked
- `GET /api/agent/tasks/{id}` — poll task until completed/failed/needs_decision

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
- `specs/005-backlog.md` — backlog of work items
- `docs/AGENT-ARCHITECTURE.md` — add section on project manager pipeline

## Acceptance Tests

- [x] Run `python api/scripts/project_manager.py --once --verbose`: creates spec task for first backlog item (or pauses on needs_decision)
- [x] After spec completes, creates impl task with direction referencing that spec
- [x] After impl completes, creates test task
- [x] After test completes, creates review task
- [x] If pytest fails after review, creates impl task with fix direction
- [x] When needs_decision task exists, orchestrator does not create new tasks

## Out of Scope

- Human-in-the-loop task selection (backlog is predefined)
- HEAL integration (separate; HEAL for CI only)
- Web UI for pipeline status
- Parallel tasks (one pipeline at a time)

## See also

- [002-agent-orchestration-api.md](002-agent-orchestration-api.md) — API used by orchestrator
- [006-overnight-backlog.md](006-overnight-backlog.md) — overnight backlog format

## Decision Gates

- Backlog format and content: human maintains specs/005-backlog.md
- needs_decision: human must /reply before pipeline resumes