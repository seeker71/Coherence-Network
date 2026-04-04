# Spec 086: Normalize GitHub Commit Cost Estimation

## Goal
Fix inflated per-commit contribution cost values by replacing the high-multiplier estimator with a bounded normalized model and enforcing normalization server-side.

## Requirements
- [x] GitHub contribution ingestion computes normalized commit cost from metadata (`files_changed`, `lines_added`) with bounded range.
- [x] Submitted raw cost is retained in metadata for auditability while normalized cost is stored as the effective contribution cost.
- [x] Auto-track GitHub workflow uses the same normalized estimator model to reduce inflated payload values.
- [x] Contributions web page displays effective normalized cost and highlights raw-to-normalized adjustment when present.
- [x] Tests cover estimator behavior and GitHub contribution route normalization.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - GitHub contribution ingestion computes normalized commit cost from metadata (`files_changed`, `lines_added`) with bou...
  - Submitted raw cost is retained in metadata for auditability while normalized cost is stored as the effective contribu...
  - Auto-track GitHub workflow uses the same normalized estimator model to reduce inflated payload values.
  - Contributions web page displays effective normalized cost and highlights raw-to-normalized adjustment when present.
  - Tests cover estimator behavior and GitHub contribution route normalization.
commands:
  - python3 -m pytest api/tests/test_contribution_cost_service.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Files To Modify (Allowed)
- `specs/086-normalize-github-commit-cost-estimation.md`
- `api/app/services/contribution_cost_service.py`
- `api/app/routers/contributions.py`
- `api/tests/test_contribution_cost_service.py`
- `api/tests/test_contributions.py`
- `.github/workflows/auto_track_contributions.yml`
- `web/app/contributions/page.tsx`
- `docs/system_audit/commit_evidence_2026-02-16_normalized-commit-cost-estimator.json`

## Validation
```bash
cd api && pytest -q tests/test_contribution_cost_service.py tests/test_contributions.py
cd web && npm ci --cache .npm-cache && npm run build
```

## Out of Scope
- Backfilling historical contribution records already persisted with inflated cost values.
- Redesigning payout/distribution weighting formulas.

## Failure and Retry Behavior

- **Render error**: Show fallback error boundary with retry action.
- **API failure**: Display user-friendly error message; retry fetch on user action or after 5s.
- **Network offline**: Show offline indicator; queue actions for replay on reconnect.
- **Asset load failure**: Retry asset load up to 3 times; show placeholder on permanent failure.
- **Timeout**: API calls timeout after 10s; show loading skeleton until resolved or failed.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add end-to-end browser tests for critical paths.

## Acceptance Tests

See `api/tests/test_normalize_github_commit_cost_estimation.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_contribution_cost_service.py -x -v
```

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
