# Spec 087: Legacy Commit Cost UI Normalization

## Goal
Prevent legacy contribution rows from showing inflated historical cost values by deriving normalized effective cost from available metadata when normalized values are missing.

## Requirements
- [x] Contributions UI computes normalized effective cost from legacy metadata (`files_changed`, `lines_added`) when `normalized_cost_amount` is absent.
- [x] UI displays raw-to-normalized adjustment for both current normalized rows and legacy-derived rows.
- [x] Web build passes with the updated contributions UI.

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
