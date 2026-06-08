---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-stdlib/native-mutation-side-effects.fk
    symbols: [nms-receipts-ddl-sql, nms-record-cache-invalidation, nms-repair-parent-edge, nms-audit-contributor-key, nms-record-rollback-receipt, nms-side-effects-sql-test]
  - file: docs/coherence-substrate/native-mutation-side-effect-ledger.form
    symbols: [native_mutation_side_effect_ledger, native_mutation_side_effect_recipe_shift]
  - file: form/form-stdlib/tests/native-mutation-side-effects-band.fk
    symbols: []
  - file: form/form-stdlib/integration/native-mutation-side-effects-live.fk
    symbols: []
  - file: form/scripts/native-mutation-side-effects-test.sh
    symbols: []
  - file: api/tests/test_native_mutation_side_effects_form.py
    symbols: [test_native_side_effects_band_executes_across_sibling_kernels, test_native_side_effects_live_db_script_runs_or_skips_when_pg_missing, test_route_forms_name_side_effect_execution_carrier_before_public_flip]
  - file: api/tests/test_native_mutation_side_effect_ledger.py
    symbols: [test_ledger_declares_anti_circular_decision_rule, test_python_parity_entries_cite_python_sources_and_form_carriers, test_gate_receipts_are_not_claimed_as_python_parity, test_audit_ledger_parity_is_carried_before_ordinary_flip]
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
  - "The side-effect ledger separates Python parity effects from reversible gate receipts so side-effect proof does not justify side effects."
done_when:
  - 'file_exists("form/form-stdlib/native-mutation-side-effects.fk")'
  - 'file_exists("docs/coherence-substrate/native-mutation-side-effect-ledger.form")'
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
service code. The companion ledger keeps this from becoming circular: side-effect
proof does not justify side effects; it only verifies carriers for rows already
classified as Python parity or reversible gate safety.

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
  public traffic on FastAPI until the deployed public-gate canary lands.
- [ ] **R5**: The A/B observation report's next evidence now names the deployed
  `X-Form-Native-Public-Gate` canary.
- [ ] **R6**: `native-mutation-side-effect-ledger.form` classifies each effect
  as primary mutation, Python parity effect, gate receipt, missing Python parity,
  or not carried, and states that rollback receipts are gate-local safety rather
  than Python parity.

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
- `docs/coherence-substrate/native-mutation-side-effect-ledger.form` -
  source-classified keep/delete ledger for mutable side effects.
- `api/tests/test_native_mutation_side_effects_form.py` - repository proof for
  carrier files, live harness, and route docs.
- `api/tests/test_native_mutation_side_effect_ledger.py` - repository proof that
  the ledger prevents circular side-effect claims.
- `deploy/kernel-router/mutation_ab_observation_harness.py` - updated next
  evidence wording.
- `docs/coherence-substrate/ideas-router.form` - ideas route state.
- `docs/coherence-substrate/spec-registry-router.form` - spec route state.
- `specs/native-mutation-side-effects.md` - this contract.

## Acceptance Tests

- `api/tests/test_native_mutation_side_effects_form.py::test_native_side_effects_band_executes_across_sibling_kernels`
- `api/tests/test_native_mutation_side_effects_form.py::test_native_side_effects_live_db_script_runs_or_skips_when_pg_missing`
- `api/tests/test_native_mutation_side_effects_form.py::test_route_forms_name_side_effect_execution_carrier_before_public_flip`
- `api/tests/test_native_mutation_side_effect_ledger.py::test_ledger_declares_anti_circular_decision_rule`
- `api/tests/test_native_mutation_side_effect_ledger.py::test_gate_receipts_are_not_claimed_as_python_parity`
- `api/tests/test_native_mutation_ab_observation.py::test_ab_gate_recommends_live_db_trial_after_full_confidence`
- Manual validation: `form/scripts/native-mutation-side-effects-test.sh`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/tests/native-mutation-side-effects-band.fk
cd .. && form/scripts/native-mutation-side-effects-test.sh
cd api && python3 -m pytest -q tests/test_native_mutation_side_effects_form.py tests/test_native_mutation_side_effect_ledger.py tests/test_native_mutation_ab_observation.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py
python3 scripts/validate_spec_quality.py --file specs/native-mutation-side-effects.md
```

## Out of Scope

- Production database writes.
- Ordinary public front-door mutation routing changes.
- Binding side-effect execution to preview or ordinary route traffic.
- Python in-memory cache flushing and resonance re-attunement.
- Using rollback receipts as an argument that domain side effects are needed.

## Gaps

- GAP-NMSE1: closed by `specs/native-mutation-route-side-effect-binding.md`. The
  proven side-effect carrier is now bound to Form-native route-runner execution
  with application graph writes in throwaway Postgres.
- GAP-NMSE2: closed by `specs/native-mutation-public-gate.md`. The public gate
  now carries a route-local rollback receipt in Form and production route
  selection.
- GAP-NMSE3 follow-up task: `native-mutation-deployed-public-canary`. Deploy and
  observe the `X-Form-Native-Public-Gate` canary before any no-header flip.
- GAP-NMSE4: closed by `specs/native-idea-valuation-audit-ledger.md`. The ledger
  now marks `idea_write_ops.update_idea` audit-ledger writes as carried
  Form-native parity.

## Risks and Assumptions

- The harness uses throwaway Postgres when available. In environments without
  `initdb`, it exits as SKIP rather than claiming live DB proof.
- Receipts prove durable execution, not Python process memory cache invalidation.
- The ledger states that rollback receipts are gate-local safety rather than Python parity.
- The carrier updates the fixture shape of `contributor_api_keys.last_used_at`;
  schema drift must be caught before route binding.
