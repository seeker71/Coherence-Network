# CI Noise Reduction — Configuration Summary

Applied 2026-03-27. Target: reduce from ~44 CI runs/day to ~12.

## Workflow Schedule Changes

| Workflow | Before | After |
|----------|--------|-------|
| thread-gates | push + pull_request | pull_request only |
| public-deploy-contract | push + 2x daily schedule | 1x daily schedule |
| auto_track_contributions | every push to main/develop | daily schedule |
| external-tools-audit | Tue & Fri | Weekly (Tue) |
| maintainability-architecture-audit | Mon & Thu | Weekly (Mon) |
| dependabot (all 3 ecosystems) | daily | weekly (Mon) |

## Notification Tuning

GitHub notification settings (applied per-user, not in repo):

1. **Email notifications**: Set to **failures only**
   - Go to: Settings → Notifications → Actions
   - Select: "Only notify for failed workflows"

2. **PR push notifications**: **Disabled**
   - Go to: Settings → Notifications → Pull Requests
   - Uncheck: "Automatically watch repositories" for push events

## Run Count Estimate

**Before** (~44/day):
- ~10 pushes to main × 3 workflows each = 30
- ~6 scheduled workflows/day = 6
- ~3 dependabot PRs/day × 1 thread-gates = 3
- ~5 manual PR updates = 5

**After** (~12/day):
- ~7 scheduled workflows/day = 7
- ~5 PR updates × 1 thread-gates = 5
- dependabot PRs weekly only

## How to Verify Post-Deploy

After merging this change, run `workflow_dispatch` for any specific workflow
that you need to verify immediately rather than waiting for the daily schedule.
