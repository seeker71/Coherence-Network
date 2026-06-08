---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-stdlib/native-mutation-side-effects.fk
    symbols: [nms-receipts-ddl-sql, nms-record-cache-invalidation, nms-repair-parent-edge, nms-audit-contributor-key, nms-record-rollback-receipt, nms-side-effects-sql-test]
  - file: form/form-stdlib/tests/native-mutation-side-effects-band.fk
    symbols: []
  - file: form/form-stdlib/integration/native-mutation-side-effects-live.fk
    symbols: []
  - file: form/scripts/native-mutation-side-effects-test.sh
    symbols: []
  - file: api/tests/test_native_mutation_side_effects_form.py
    symbols: [test_native_side_effects_band_executes_across_sibling_kernels, test_native_side_effects_live_db_script_runs_or_skips_when_pg_missing, test_route_forms_name_side_effect_execution_carrier_before_public_flip]
  - file: deploy/kernel-router/mutation_ab_observation_harness.py
    symbols: [build_gate_report]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
requirements:
  - "Form-native side-effect recipes execute durable cache-invalidation and rollback receipts."
  - "Form-native side-effect recipes execute parent-edge repair and contributor-key audit updates against throwaway Postgres."
  - "The proof keeps ordinary public mutation traffic on FastAPI and leaves preview executes:false unchanged."
  - "Route docs and the A/B observation gate name route binding as a separate follow-up boundary."
done_when:
  - 'file_exists("form/form-stdlib/native-mutation-side-effects.fk")'
  - 'file_exists("form/scripts/native-mutation-side-effects-test.sh")'
  - 'pytest_passes("api/tests/test_native_mutation_side_effects_form.py")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/tests/native-mutation-side-effects-band.fk && cd .. && form/scripts/native-mutation-side-effects-test.sh && cd api && python3 -m pytest -q tests/test_native_mutation_side_effects_form.py tests/test_native_mutation_ab_observation.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py"
constraints:
  - "Use a throwaway local PostgreSQL database or caller-supplied test DSN only."
  - "Do not execute against the production application database."
  - "Do not bind native side effects to ordinary public mutation traffic in this slice."
  - "Do not claim Python in-memory cache flushing or resonance re-attunement."
---

# Spec: Native Mutation Side Effects

## Purpose

The trust envelope named side-effect intents, but names alone did not execute
anything. This spec gives those intents a Form-native carrier with live
Postgres evidence: receipts persist, parent edges repair, contributor-key audit
timestamps update, and rollback receipts are written without calling Python
service code.

## Requirements

- [ ] **R1**: `native-mutation-side-effects.fk` defines SQL builders and `pg_exec`
  wrappers for cache-invalidation receipt, parent-edge repair,
  contributor-key audit, and rollback receipt.
- [ ] **R2**: The sibling-kernel band returns `11111` for SQL shape evidence
  across Go, Rust, and TypeScript kernels.
- [ ] **R3**: The live integration returns `11111111` after executing every
  side-effect wrapper, reading each effect back from throwaway Postgres, cleaning
  up fixture tables, and closing the connection.
- [ ] **R4**: Route Form docs name the carrier as proven while keeping ordinary
  public traffic on FastAPI until route binding and a reversible public gate land.
- [ ] **R5**: The A/B observation report's next evidence moves from "execute
  side effects" to binding the proven carrier to the mutation route runner.

## Research Inputs

- `2026-06-08` - User direction: move mutable surfaces form-native and continue
  walking until Python dependency is released.
- `specs/native-mutation-trust-envelope.md` - side-effect intents carried in the
  preview trust envelope.
- `specs/native-mutation-response-projection.md` - previous native response
  projection boundary.
- `api/app/services/idea_write_ops.py` - Python parent-edge and side-effect
  behavior that the carrier approaches.
- `api/app/services/contributor_key_store.py` - contributor-key audit timestamp
  behavior.

## Files to Create/Modify

- `form/form-stdlib/native-mutation-side-effects.fk` - durable side-effect SQL
  builders and `pg_exec` wrappers.
- `form/form-stdlib/tests/native-mutation-side-effects-band.fk` - sibling-kernel
  SQL-shape proof.
- `form/form-stdlib/integration/native-mutation-side-effects-live.fk` - live
  Postgres readback integration.
- `form/scripts/native-mutation-side-effects-test.sh` - throwaway Postgres
  harness.
- `api/tests/test_native_mutation_side_effects_form.py` - repository proof for
  carrier files, live harness, and route docs.
- `deploy/kernel-router/mutation_ab_observation_harness.py` - updated next
  evidence wording.
- `docs/coherence-substrate/ideas-router.form` - ideas route state.
- `docs/coherence-substrate/spec-registry-router.form` - spec route state.
- `specs/native-mutation-side-effects.md` - this contract.

## Acceptance Tests

- `api/tests/test_native_mutation_side_effects_form.py::test_native_side_effects_band_executes_across_sibling_kernels`
- `api/tests/test_native_mutation_side_effects_form.py::test_native_side_effects_live_db_script_runs_or_skips_when_pg_missing`
- `api/tests/test_native_mutation_side_effects_form.py::test_route_forms_name_side_effect_execution_carrier_before_public_flip`
- `api/tests/test_native_mutation_ab_observation.py::test_ab_gate_recommends_live_db_trial_after_full_confidence`
- Manual validation: `form/scripts/native-mutation-side-effects-test.sh`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/tests/native-mutation-side-effects-band.fk
cd .. && form/scripts/native-mutation-side-effects-test.sh
cd api && python3 -m pytest -q tests/test_native_mutation_side_effects_form.py tests/test_native_mutation_ab_observation.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py
python3 scripts/validate_spec_quality.py --file specs/native-mutation-side-effects.md
```

## Out of Scope

- Production database writes.
- Ordinary public front-door mutation routing changes.
- Binding side-effect execution to preview or ordinary route traffic.
- Python in-memory cache flushing and resonance re-attunement.

## Gaps

- GAP-NMSE1: closed by `specs/native-mutation-route-side-effect-binding.md`. The
  proven side-effect carrier is now bound to Form-native route-runner execution
  with application graph writes in throwaway Postgres.
- GAP-NMSE2 follow-up task: `native-mutation-public-flip-gate`. Add a narrow
  reversible public gate with route-local rollback receipt.

## Risks and Assumptions

- The harness uses throwaway Postgres when available. In environments without
  `initdb`, it exits as SKIP rather than claiming live DB proof.
- Receipts prove durable execution, not Python process memory cache invalidation.
- The carrier updates the fixture shape of `contributor_api_keys.last_used_at`;
  schema drift must be caught before route binding.
