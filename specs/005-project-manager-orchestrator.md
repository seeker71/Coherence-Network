# Spec: Project Manager Orchestrator

## Purpose

Implement a project manager orchestrator that automates the spec-driven cycle: select next backlog item, run spec then impl then test then review, validate (pytest and review pass), and loop or advance. This replaces ad-hoc impl-only runs with a structured pipeline and ensures state persists across restarts.

## Requirements

- [ ] Orchestrator reads backlog from config (e.g. specs/005-backlog.md or specs/006-overnight-backlog.md via `--backlog`) and selects the next item by index.
- [ ] For each item it runs phases in order: spec → impl → test → review, using existing agent API (POST/GET tasks); after review, validation is pytest exit 0 and review output indicates pass.
- [ ] On validation failure the orchestrator loops back to impl with fix direction, then test, then review, until pass or max iterations; on pass it advances to the next task and persists state (backlog_index, phase, iteration) to api/logs/project_manager_state.json.
- [ ] When any task is needs_decision the orchestrator pauses and does not create new tasks until unblocked.
- [ ] `python3 api/scripts/project_manager.py --dry-run` exits 0 and logs a deterministic preview (no HTTP calls); with API up, `--once` completes one tick with exit 0 and no unhandled exception.
- [ ] An E2E test in api/tests/ runs the project manager (e.g. subprocess `--dry-run` or `--once`) and asserts exit 0 and consistent state; CI runs this test.

## Research Inputs (Required)

- `2025-01-01` - [AGENTS.md](../AGENTS.md) - Mandatory worktree and prompt-gate flow; project manager must align with agent task API and state contract.
- `2025-01-01` - [specs/002-agent-orchestration-api.md](002-agent-orchestration-api.md) - API used by orchestrator (POST/GET tasks, task_type, status).

## Task Card (Required)

```yaml
goal: Implement the project manager orchestrator script and E2E test per this spec.
files_allowed:
  - api/scripts/project_manager.py
  - api/tests/test_project_manager.py
  - specs/005-backlog.md
  - docs/AGENT-ARCHITECTURE.md
done_when:
  - python3 api/scripts/project_manager.py --dry-run exits 0 and logs preview
  - python3 api/scripts/project_manager.py --once exits 0 with API up and state file valid
  - cd api && pytest -v tests/test_project_manager.py passes
commands:
  - python3 api/scripts/project_manager.py --dry-run
  - python3 api/scripts/project_manager.py --once
  - cd api && pytest -v tests/test_project_manager.py
constraints:
  - No new API endpoints; use existing agent tasks API only
  - State in api/logs/project_manager_state.json; no scope creep
```

## API Contract (if applicable)

N/A - no API contract changes in this spec. Orchestrator uses existing POST/GET agent tasks and GET /api/health.

## Data Model (if applicable)

Orchestrator state file `api/logs/project_manager_state.json`: backlog_index (int), current_task_id (str or null), phase (spec|impl|test|review), iteration (int), blocked (bool).

## Files to Create/Modify

- `api/scripts/project_manager.py` - orchestrator entrypoint and phase loop.
- `api/tests/test_project_manager.py` - E2E smoke test (e.g. --dry-run exit 0, --once state consistency).
- `specs/005-backlog.md` - backlog of work items (if missing).
- `docs/AGENT-ARCHITECTURE.md` - add project manager pipeline section.

## Acceptance Tests

- `api/tests/test_project_manager.py` - run project_manager --dry-run and assert exit 0; optionally --once with API and assert state file valid and exit 0.
- Manual: run `python3 api/scripts/project_manager.py --once --verbose` with API and backlog; confirm one cycle completes and state advances or pauses on needs_decision.

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/005-project-manager-orchestrator.md
python3 api/scripts/project_manager.py --dry-run
cd api && pytest -v tests/test_project_manager.py
```

## Out of Scope

- Human-in-the-loop task selection; backlog is predefined.
- Web UI for pipeline status.
- Parallel tasks (one pipeline at a time).

## Risks and Assumptions

- Risk: API or agent downtime can leave orchestrator mid-phase; state file allows resume.
- Assumption: Backlog file exists and format is stable; fallback to specs/ or docs/PLAN.md if needed.

## Known Gaps and Follow-up Tasks

- None at spec time. Follow-up: HEAL integration for CI-only fixes (separate spec).

## Failure/Retry Reflection

- Failure mode: --once times out waiting for task completion.
- Blind spot: Agent or API latency not bounded.
- Next action: Add timeout and retry or pause and resume on next --once.

## Decision Gates (if any)

- needs_decision: human must resolve before pipeline resumes. Backlog content owned by maintainers.
