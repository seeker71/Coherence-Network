# Spec 058: Evidence Contract and Automated ROI Questioning

## Goal

Require each subsystem to continuously answer the right question: what claim is being made, what evidence proves it, what falsifies it, and who acts when it drifts.

## Requirements

1. `GET /api/inventory/system-lineage` includes `evidence_contract` with per-subsystem checks.
2. Each check contains:
   - subsystem id
   - standing question
   - claim
   - evidence metrics
   - falsifier
   - threshold
   - owner role
   - auto action
   - review cadence
   - status
3. Inventory must expose `violations` and `violations_count`.
4. Add machine scan endpoint:
   - `POST /api/inventory/evidence/scan`
   - optional `create_tasks=true` creates deduped heal tasks for violations.
5. Pipeline monitor must include evidence-scan output as issues each cycle.
6. Portfolio UI must show evidence contract violations for human inspection and intervention.

## Validation

- API tests verify:
  - evidence contract exists in inventory
  - violation appears when duplicate-question falsifier is triggered
  - evidence scan endpoint can create and dedupe tasks
- Monitor script compiles with evidence scan integration.
- Web build passes with evidence contract UI section.
