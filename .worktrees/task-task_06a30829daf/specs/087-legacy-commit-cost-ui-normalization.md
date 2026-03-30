# Spec 087: Legacy Commit Cost UI Normalization

## Goal
Prevent legacy contribution rows from showing inflated historical cost values by deriving normalized effective cost from available metadata when normalized values are missing.

## Requirements
- [x] Contributions UI computes normalized effective cost from legacy metadata (`files_changed`, `lines_added`) when `normalized_cost_amount` is absent.
- [x] UI displays raw-to-normalized adjustment for both current normalized rows and legacy-derived rows.
- [x] Web build passes with the updated contributions UI.


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Contributions UI computes normalized effective cost from legacy metadata (`files_changed`, `lines_added`) when `norma...
  - UI displays raw-to-normalized adjustment for both current normalized rows and legacy-derived rows.
  - Web build passes with the updated contributions UI.
commands:
  - python3 -m pytest api/tests/test_contribution_cost_service.py -x -v
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Files To Modify (Allowed)
- `specs/087-legacy-commit-cost-ui-normalization.md`
- `web/app/contributions/page.tsx`
- `docs/system_audit/commit_evidence_2026-02-16_legacy-commit-cost-ui-normalization.json`

## Validation
```bash
cd web && npm run build
```

## Out of Scope
- Rewriting historical stored contribution records.
- Changing API contribution schemas in this follow-up slice.

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

See `api/tests/test_legacy_commit_cost_ui_normalization.py` for test cases covering this spec's requirements.


## Verification

```bash
python3 -m pytest api/tests/test_contribution_cost_service.py -x -v
```
