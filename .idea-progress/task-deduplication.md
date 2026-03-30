# Idea Progress: task-deduplication

## Current task
- Phase: impl — COMPLETE

## Completed phases
### impl
- MAX_TASKS_PER_PHASE = 3 constant added
- Completed-phase guard (R1) and per-phase cap guard (R2) added
- Stuck detection threshold updated (R3)
- All verification checks pass

## Key decisions
- Guards placed after task_type determination so correct phase is checked
- R2 cap adds to _SEEDER_SKIP_CACHE; R1 does not (allows retry for other phases)
