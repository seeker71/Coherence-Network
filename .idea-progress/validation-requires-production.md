# Idea Progress: validation-requires-production

## Current task
Task ID: task_93dc79b98d1d1865 (impl phase)
Status: COMPLETE

## Completed phases
### impl (task_93dc79b98d1d1865)
- Created `api/app/services/production_verification_service.py`
- Modified `api/app/services/pipeline_advance_service.py` — `_set_idea_validated()` now runs production 404 check before promoting
- If any claimed endpoint returns 404, idea stays `partial` not `validated`

## Key decisions
- Endpoints extracted from spec files (regex for `/api/` paths) and task output
- Path parameters (`{id}`) resolved to probe values for GET check
- Network errors are NOT treated as 404s — only explicit 404 responses block validation
- No endpoints found = passes (backwards compatible for ideas without API endpoints)

## Blockers
None
