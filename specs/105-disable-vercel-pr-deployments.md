# Spec: Disable Vercel PR Deployments

## Purpose

Prevent Vercel preview deployments from running on pull requests to avoid hitting Vercel deployment rate limits too early.

## Requirements

- [ ] Vercel auto-deploy must be enabled only for the `main` branch (repo root or `web/` root-directory configurations).
- [ ] Non-`main` branches must not trigger Vercel deployments (including PR branches).
- [ ] A repo-local validation command must fail if the Vercel deploy policy is misconfigured.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Prevent Vercel preview deployments from running on pull requests to avoid hitting Vercel deployment rate limits too early.
files_allowed:
  - vercel.json
  - web/vercel.json
  - scripts/validate_vercel_deployment_policy.py
  - docs/DEPLOY.md
  - docs/system_audit/commit_evidence_2026-02-17_disable-vercel-pr-deploys.json
done_when:
  - Vercel auto-deploy must be enabled only for the `main` branch (repo root or `web/` root-directory configurations).
  - Non-`main` branches must not trigger Vercel deployments (including PR branches).
  - A repo-local validation command must fail if the Vercel deploy policy is misconfigured.
commands:
  - cd api && python -m pytest tests/ -q
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## API Contract (if applicable)

N/A - no API contract changes in this spec.


### Input Validation

- All string fields: min_length=1, max_length=1000
- Numeric fields: appropriate min/max bounds
- Required fields validated; missing returns 422
- Unknown fields rejected (Pydantic extra="forbid" where applicable)

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `vercel.json`
- `web/vercel.json`
- `scripts/validate_vercel_deployment_policy.py`
- `docs/DEPLOY.md`
- `docs/system_audit/commit_evidence_2026-02-17_disable-vercel-pr-deploys.json`

## Acceptance Tests

- `python3 scripts/validate_vercel_deployment_policy.py`

Manual validation (post-merge expectation):

- Open a PR from a non-`main` branch and confirm no new Vercel deployment is created for the PR branch.

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; no locking required.
- **Write operations**: Last-write-wins semantics; no optimistic locking for MVP.
- **Recommendation**: Clients should not assume atomic read-modify-write without explicit ETag support.

## Failure and Retry Behavior

- **Render error**: Show fallback error boundary with retry action.
- **API failure**: Display user-friendly error message; retry fetch on user action or after 5s.
- **Network offline**: Show offline indicator; queue actions for replay on reconnect.
- **Asset load failure**: Retry asset load up to 3 times; show placeholder on permanent failure.
- **Timeout**: API calls timeout after 10s; show loading skeleton until resolved or failed.


## Verification

```bash
python3 scripts/validate_vercel_deployment_policy.py
python3 scripts/validate_commit_evidence.py --file docs/system_audit/commit_evidence_2026-02-17_disable-vercel-pr-deploys.json
```

## Out of Scope

- Changing Vercel dashboard settings directly.
- Disabling other CI workflows or providers.

## Risks and Assumptions

- Assumption: the Vercel project is configured to use `web/` as its root directory so it reads `web/vercel.json`.
- Risk: if Vercel ignores repo config for this project, deployments may still trigger; mitigation is to enforce the same rule in Vercel project settings.

## Known Gaps and Follow-up Tasks

- None at spec time.

## Decision Gates (if any)

None.
