# Idea Progress: runner-auto-contribution

## Current task
**Phase**: impl (COMPLETE)
**Task ID**: task_5828ee235ec411d3

## Completed phases
- **impl** (2026-03-30): Created auto_contribution_service.py, integrated into completion hooks. 12 tests passing.

## Key decisions
- CC tiered by task type: impl=3, test=2, spec=1
- Failed tasks earn 20% of success reward
- Long-running (>5min) gets +1 CC bonus
- Contributor ID: runner:{worker_id}
- Uses existing contribution_ledger_service

## Blockers
None.
