# 088 — Spec-Process-Implementation-Validation Flow Visibility

## Summary

Expose a first-class machine and human view of the tracked delivery chain:

`idea -> spec -> process -> implementation -> validation -> contributors -> contributions`.

The API must aggregate existing evidence and runtime signals; the web UI must render that aggregate so humans can inspect what is tracked versus missing.

## Problem

Current endpoints expose parts of the system independently (`ideas`, `specs`, `value-lineage`, `runtime`, contributor registries), but there is no single contract that shows whether each idea has:

1. Spec tracking
2. Process tracking
3. Implementation tracking
4. Validation tracking
5. Contributor attribution
6. Contribution/value evidence

## Requirements

1. Add `GET /api/inventory/flow` under the inventory router.
2. Support optional `idea_id` filter and runtime window parameter.
3. Build flow rows per idea by joining:
   - `ideas` portfolio
   - `value_lineage` links and usage events
   - runtime summaries
   - commit evidence (`docs/system_audit/commit_evidence_*.json`)
4. Each row must include sections:
   - `spec`
   - `process`
   - `implementation`
   - `validation`
   - `contributors`
   - `contributions`
   - `chain` statuses
5. Add a human page `/flow` that renders these sections clearly.
6. Ensure navigation and page lineage include `/flow`.
7. Add automated tests for the API contract and page lineage route coverage.

## Non-goals

1. Replacing existing `ideas`, `specs`, `usage`, or contributor endpoints.
2. Reworking graph-store schemas.
3. Defining payout policy changes.

## Validation

1. `cd api && pytest -q tests/test_inventory_api.py`
2. `cd web && npm run build`

