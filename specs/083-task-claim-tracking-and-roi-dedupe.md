# Spec 083: Task Claim Tracking and ROI Auto-Pick De-duplication

## Goal
Prevent parallel contributors/agents from working the same ROI-ranked task at the same time. Track who started a task and ensure automatic ROI task generation skips work already in progress.

## Requirements
- [x] Task updates to `running` record claim ownership (`claimed_by`, `claimed_at`).
- [x] Starting a task already claimed by another worker returns `409` conflict.
- [x] Agent runner sends a stable worker identifier when claiming tasks.
- [x] ROI auto-pick flow detects active fingerprint-matched tasks and returns `task_already_active` instead of creating duplicates.
- [x] Implementation-request question sync uses active-task deduplication and task fingerprints.

## Files To Modify (Allowed)
- `specs/083-task-claim-tracking-and-roi-dedupe.md`
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
