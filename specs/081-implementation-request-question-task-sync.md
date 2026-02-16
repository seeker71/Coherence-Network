# Spec 081: Implementation Request Questions -> Task Sync

## Goal
Ensure implementation-request questions are never dropped by converting them into explicit `impl` tasks as soon as they are discovered. The sync must deduplicate by question fingerprint so repeated runs do not flood the task queue.

## Requirements
- [x] Add `POST /api/inventory/questions/sync-implementation-tasks` to scan inventory questions and create tasks for implementation-request questions.
- [x] Mark synced tasks with machine-readable context (`source=implementation_request_question`, fingerprint, idea id, ROI fields).
- [x] Deduplicate creation so rerunning sync does not create duplicate tasks for the same idea/question pair.
- [x] Run this sync before `POST /api/inventory/questions/next-highest-roi-task` returns a suggestion.

## Files To Modify (Allowed)
- `specs/081-implementation-request-question-task-sync.md`
- `api/app/routers/inventory.py`
- `api/app/services/inventory_service.py`
- `api/tests/test_inventory_api.py`

## Validation
```bash
cd api && pytest -q tests/test_inventory_api.py
```
