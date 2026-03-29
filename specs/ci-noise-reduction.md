# Spec: CI Noise Reduction — Scheduled Workflows to Daily, Failure-Only Notifications

## Purpose

The CI pipeline was generating ~44 runs/day across scheduled workflows, creating notification
fatigue and making real failures invisible. This spec covers:

1. Consolidating scheduled CI runs from per-push + per-schedule to daily-only
2. Configuring GitHub notification settings to send email only on failures
3. Disabling PR push notifications that fire on every commit
4. Adding a status badge so the current CI state is always visible at a glance

After this change the target is ≤12 CI runs/day with zero noise on green runs.

---

## Current State

`.github/workflows/` contains multiple workflow files. Common sources of excess runs:
- `on: push` triggers on every commit to main (including merge commits from runner)
- `on: pull_request` triggers on every PR commit (runner creates many small PRs)
- Some workflows have both `push` and `schedule` triggers, doubling the run count
- GitHub email notifications default to "Participating and @mentions" which includes every CI run

Estimated breakdown of 44 runs/day:
- ~20 from runner-merged PRs (each triggers `on: push` on main)
- ~14 from PR commits (runner pushes feature branches)
- ~10 from scheduled jobs

---

## Required Changes

### 1. Audit `.github/workflows/*.yml` — move to daily schedule

For each workflow that runs on `push` to `main` AND has a non-critical purpose
(e.g., dependency scans, code quality, coverage reports), change:

```yaml
# Before
on:
  push:
    branches: [main]
  schedule:
    - cron: '0 */6 * * *'  # every 6 hours

# After
on:
  schedule:
    - cron: '0 6 * * *'  # once daily at 6am UTC
  workflow_dispatch:       # keep manual trigger
```

Keep `on: push` ONLY for:
- `test.yml` (unit + integration tests) — must run on every PR merge
- `deploy.yml` (production deploy) — triggered by merge to main

### 2. PR workflows — skip on runner-generated branches

Add a filter so workflows don't trigger on runner's `worker/` branches:

```yaml
on:
  pull_request:
    branches: [main]
    paths-ignore:
      - 'specs/**'
      - '*.md'
  push:
    branches: [main]
    paths-ignore:
      - 'specs/**'
      - '*.md'
```

### 3. GitHub notification settings (user-level, documented in RUNBOOK)

Add to `docs/RUNBOOK.md` under "CI Setup":
```
GitHub notification tuning (one-time per contributor):
  Settings → Notifications → GitHub Actions:
    - Email: "Only failures, cancellations, and requests to approve"
    - Web: "Send notifications for failed workflows only"
  Settings → Notifications → Pull Requests:
    - "Only notify me for pull requests that need my review"
```

### 4. README status badge

Add to `README.md` after the project header:
```markdown
[![CI](https://github.com/seeker71/Coherence-Network/actions/workflows/test.yml/badge.svg)](https://github.com/seeker71/Coherence-Network/actions/workflows/test.yml)
```

---

## Files to Modify

| File | Change |
|---|---|
| `.github/workflows/*.yml` | Remove `on: push` from non-critical workflows; add `workflow_dispatch` |
| `.github/workflows/test.yml` | Add `paths-ignore` for `specs/**` and `*.md` |
| `docs/RUNBOOK.md` | Add GitHub notification tuning instructions |
| `README.md` | Add CI status badge |

---

## Verification Scenarios

### Scenario 1: Run count drops after change
- **Setup**: Merge 5 commits to main over 1 hour
- **Action**: Check `gh run list --limit 20 --json status,name,createdAt`
- **Expected**: Only `test.yml` triggered (not dependency scan, not coverage report)
- **Edge**: `workflow_dispatch` still allows manual trigger of any workflow

### Scenario 2: Spec-only commits don't trigger tests
- **Setup**: Merge a commit that only changes `specs/` files
- **Action**: Observe GitHub Actions tab
- **Expected**: No test workflow triggered (paths-ignore filter)
- **Edge**: A commit touching both `specs/` and `api/` does trigger tests

### Scenario 3: Daily scheduled jobs still run
- **Action**: Check `gh run list --workflow=dependency-scan.yml --limit 5`
- **Expected**: One run per day, at 06:00 UTC

### Scenario 4: Status badge visible
- **Action**: Open `README.md` on GitHub
- **Expected**: Green CI badge visible in the header
- **Edge**: Badge shows "failing" correctly when tests are broken

### Scenario 5: Total daily runs ≤ 12
- **Setup**: Normal day of runner activity (10–20 PR merges)
- **Action**: `gh run list --created $(date +%Y-%m-%d) --json name | python3 -c "import sys,json; r=json.load(sys.stdin); print(len(r))"`
- **Expected**: Count ≤ 12

---

## Risks and Assumptions

- **Critical workflows**: `test.yml` and `deploy.yml` must keep `on: push` — removing them
  would mean broken code reaches main undetected.
- **Existing workflow names**: Some workflows may be referenced by other jobs; changing
  triggers must not break `needs:` dependencies.
- **Notification settings are per-user**: The RUNBOOK documents them; they cannot be
  enforced org-wide on free GitHub plan.
- **`paths-ignore` and required status checks**: If `test.yml` is a required status check
  for PR merges, skipping it on spec-only commits may block merges. Use `paths-ignore`
  with care or add a bypass job.

---

## Known Gaps and Follow-up Tasks

- **Concurrency limits**: Add `concurrency: ci-${{ github.ref }}` to cancel in-progress
  runs when a new push supersedes them — reduces wasted runner minutes.
- **Runner-generated PRs**: The runner creates many PRs for small ideas; consider batching
  small spec tasks to reduce PR volume at the source.
- **Cost tracking**: GitHub Actions minutes are limited; add a monthly usage check to
  `docs/RUNBOOK.md`.
