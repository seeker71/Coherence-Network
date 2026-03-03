# Spec 086: Normalize GitHub Commit Cost Estimation

## Goal
Fix inflated per-commit contribution cost values by replacing the high-multiplier estimator with a bounded normalized model and enforcing normalization server-side.

## Requirements
- [x] GitHub contribution ingestion computes normalized commit cost from metadata (`files_changed`, `lines_added`) with bounded range.
- [x] Submitted raw cost is retained in metadata for auditability while normalized cost is stored as the effective contribution cost.
- [x] Auto-track GitHub workflow uses the same normalized estimator model to reduce inflated payload values.
- [x] Contributions web page displays effective normalized cost and highlights raw-to-normalized adjustment when present.
- [x] Tests cover estimator behavior and GitHub contribution route normalization.

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
