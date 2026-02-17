# Spec: Disable Vercel PR Deployments

## Purpose

Stop Vercel preview deployments from running on pull requests to avoid hitting Vercel deployment rate limits too early.

## Background

The repo has a Vercel-connected web app (root directory `web/`). Vercel preview deployments are triggered for non-production branches, including PR branches, and can exhaust deployment quotas quickly.

## Requirements

- Vercel must only auto-deploy from the production branch (`main`).
- Non-`main` branches must not trigger deployments (including PRs).
- The policy must be checked locally via a repo script.
- Deployment guidance must mention the policy so it is not accidentally undone.

## Files To Create/Modify

- `web/vercel.json`
- `scripts/validate_vercel_deployment_policy.py`
- `docs/DEPLOY.md`
- `docs/system_audit/commit_evidence_2026-02-17_disable-vercel-pr-deploys.json`

## Acceptance Tests

```bash
python3 scripts/validate_vercel_deployment_policy.py
```

## Out of Scope

- Changing Vercel dashboard settings directly.
- Disabling other CI workflows or providers.
