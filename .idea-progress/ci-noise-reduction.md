# Idea Progress — ci-noise-reduction

## Current task
impl phase — COMPLETE

## Completed phases
### impl (task_b78a4ea10396a492)
- Moved auto_track_contributions.yml from per-push to daily schedule (06:41 UTC)
- Moved public-deploy-contract.yml from twice-daily + per-push to daily-only (06:17 UTC)
- Added paths-ignore to thread-gates.yml PR trigger (specs/**, *.md, docs/**)
- Created scripts/ci_run_count.py measurement script (run-count verification)
- Added CI noise reduction section to docs/RUNBOOK.md (notification tuning guide, workflow schedule table)
- README badge already existed (thread-gates)

## Key decisions
- Kept thread-gates.yml PR trigger (needed for PR checks) but added paths-ignore
- Removed on:push from public-deploy-contract entirely (deploy verification runs daily, not on every push)
- auto_track_contributions moved to daily — can reconstruct contributions from git log on scheduled runs

## Blockers
- None
