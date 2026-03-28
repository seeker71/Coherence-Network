# Progress — 037-post-tasks-invalid-task-type-422

## Completed phases

- **037 impl**: Added `test_post_task_invalid_task_type_returns_422` in `api/tests/test_agent.py` — POST `/api/agent/tasks` with invalid `task_type` (`foo`) and valid `direction`; asserts 422, JSON `detail` is a list of validation objects with `loc`, `msg`, `type`, and `task_type` appears in at least one `loc`.

## Current task

(done — pending local pytest + DIF + commit if runner picks up)

## Key decisions

- Reused same AsyncClient/ASGITransport pattern as other tests in `test_agent.py`.
- Used `"foo"` as invalid `task_type` per spec examples; assertion that `task_type` is in `loc` matches 009/contract.

## Blockers

- Session could not run shell (pytest, DIF curl, git); verify locally before merge.
