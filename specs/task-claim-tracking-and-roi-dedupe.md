---
idea_id: value-attribution
status: done
source:
  - file: api/app/services/contribution_cost_service.py
    symbols: [estimate_commit_cost_with_provenance()]
requirements:
  - "Task updates to `running` record claim ownership (`claimed_by`, `claimed_at`)."
  - "Starting a task already claimed by another worker returns `409` conflict."
  - "Agent runner sends a stable worker identifier when claiming tasks."
  - "ROI auto-pick flow detects active fingerprint-matched tasks and returns `task_already_active` instead of creating duplic"
  - "Implementation-request question sync uses active-task deduplication and task fingerprints."
done_when:
  - "Task updates to `running` record claim ownership (`claimed_by`, `claimed_at`)."
  - "Starting a task already claimed by another worker returns `409` conflict."
  - "Agent runner sends a stable worker identifier when claiming tasks."
  - "ROI auto-pick flow detects active fingerprint-matched tasks and returns `task_already_active` instead of creating dup..."
  - "Implementation-request question sync uses active-task deduplication and task fingerprints."
test: "python3 -m pytest api/tests/test_agent_task_claims.py -x -v"
constraints:
  - "changes scoped to listed files only"
  - "no schema migrations without explicit approval"
---

> **Parent idea**: [value-attribution](../ideas/value-attribution.md)
> **Source**: [`api/app/services/contribution_cost_service.py`](../api/app/services/contribution_cost_service.py)

# Task Claim Tracking and ROI Auto-Pick De-duplication

## Goal
Prevent parallel contributors/agents from working the same ROI-ranked task at the same time. Track who started a task and ensure automatic ROI task generation skips work already in progress.

## Requirements
- [x] Task updates to `running` record claim ownership (`claimed_by`, `claimed_at`).
- [x] Starting a task already claimed by another worker returns `409` conflict.
- [x] Agent runner sends a stable worker identifier when claiming tasks.
- [x] ROI auto-pick flow detects active fingerprint-matched tasks and returns `task_already_active` instead of creating duplicates.
- [x] Implementation-request question sync uses active-task deduplication and task fingerprints.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Task updates to `running` record claim ownership (`claimed_by`, `claimed_at`).
  - Starting a task already claimed by another worker returns `409` conflict.
  - Agent runner sends a stable worker identifier when claiming tasks.
  - ROI auto-pick flow detects active fingerprint-matched tasks and returns `task_already_active` instead of creating dup...
  - Implementation-request question sync uses active-task deduplication and task fingerprints.
commands:
  - python3 -m pytest api/tests/test_agent_task_claims.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Files To Modify (Allowed)
- `specs/task-claim-tracking-and-roi-dedupe.md`
- `api/app/models/agent.py`
- `api/app/routers/agent.py`
- `api/app/services/agent_service.py`
- `api/app/services/inventory_service.py`
- `api/scripts/agent_runner.py`
- `api/tests/test_agent_task_claims.py`
- `api/tests/test_inventory_api.py`
- `docs/system_audit/commit_evidence_2026-02-16_task-claim-tracking-roi-dedupe.json`

## Validation
```bash
cd api && pytest -q tests/test_agent_task_claims.py tests/test_inventory_api.py tests/test_contributions.py
```

## Failure and Retry Behavior

- **Invalid input**: Return 422 with field-level validation errors.
- **Resource not found**: Return 404 with descriptive message.
- **Database unavailable**: Return 503; client should retry with exponential backoff (initial 1s, max 30s).
- **Concurrent modification**: Last write wins; no optimistic locking required for MVP.
- **Timeout**: Operations exceeding 30s return 504; safe to retry.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Review coverage and add missing edge-case tests.

## Acceptance Tests

See `api/tests/test_agent_task_claims.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_agent_task_claims.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
