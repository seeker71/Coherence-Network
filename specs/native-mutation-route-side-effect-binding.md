---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-stdlib/native-mutation-route-side-effects.fk
    symbols: [nmrs-bind-common-side-effects, nmrs-run-idea-create-with-side-effects, nmrs-run-spec-update-with-side-effects, nmrs-route-side-effects-binding-test]
  - file: form/form-stdlib/native-idea-valuation-audit-ledger.fk
    symbols: [nival-run-idea-update-with-valuation-audit]
  - file: docs/coherence-substrate/native-mutation-side-effect-ledger.form
    symbols: [native_mutation_side_effect_ledger, native_mutation_side_effect_recipe_shift]
  - file: form/form-stdlib/tests/native-mutation-route-side-effects-band.fk
    symbols: []
  - file: form/form-stdlib/integration/native-mutation-route-side-effects-live.fk
    symbols: []
  - file: form/scripts/native-mutation-route-side-effects-test.sh
    symbols: []
  - file: api/tests/test_native_mutation_route_side_effect_binding.py
    symbols: [test_route_side_effect_binding_band_executes_across_sibling_kernels, test_route_side_effect_binding_live_script_runs_or_skips_when_pg_missing, test_ab_gate_next_evidence_is_deployed_canary_after_public_gate]
  - file: api/tests/test_native_mutation_side_effect_ledger.py
    symbols: [test_gate_receipts_are_not_claimed_as_python_parity, test_audit_ledger_parity_is_carried_before_ordinary_flip]
  - file: deploy/kernel-router/mutation_ab_observation_harness.py
    symbols: [build_gate_report]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
requirements:
  - "A Form-native route runner composes application graph mutation execution with native side-effect execution."
  - "The route-runner proof executes idea and spec mutation shapes against rollback-safe throwaway Postgres."
  - "The A/B observation gate now names the deployed public-gate canary as the remaining boundary."
  - "Ordinary public mutation traffic remains on FastAPI and preview rows remain executes:false."
  - "The route binding consumes only source-classified side effects; side-effect proof does not justify side effects."
  - "Idea update route-runner audit parity is carried by native-idea-valuation-audit-ledger.fk."
done_when:
  - 'file_exists("form/form-stdlib/native-mutation-route-side-effects.fk")'
  - 'file_exists("form/scripts/native-mutation-route-side-effects-test.sh")'
  - 'pytest_passes("api/tests/test_native_mutation_route_side_effect_binding.py")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/application-graph-node-port.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/native-mutation-route-side-effects.fk form-stdlib/tests/native-mutation-route-side-effects-band.fk && cd .. && form/scripts/native-mutation-route-side-effects-test.sh && cd api && python3 -m pytest -q tests/test_native_mutation_route_side_effect_binding.py tests/test_native_mutation_ab_observation.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py"
constraints:
  - "Use a throwaway local PostgreSQL database or caller-supplied test DSN only."
  - "Do not execute against the production application database."
  - "Do not move ordinary public mutation traffic in this slice."
  - "Do not change preview route responses from executes:false."
---

# Spec: Native Mutation Route Side-Effect Binding

## Purpose

The side-effect carrier could execute, but the route shape still had a gap
between graph mutation and side-effect execution. This spec binds those two
native pieces into route-runner functions and proves them together against live
Postgres fixture tables. The binding is constrained by
`native-mutation-side-effect-ledger.form`: rollback receipts are gate-local
safety rather than Python parity, and the idea valuation audit ledger is now
carried before ordinary no-header movement.

## Requirements

- [ ] **R1**: `native-mutation-route-side-effects.fk` defines common side-effect
  binding over the proven `nms-*` carrier.
- [ ] **R2**: The same module defines an idea create route runner that calls
  `agn-create-node` and then executes cache receipt, parent-edge repair,
  contributor-key audit, and rollback receipt.
- [ ] **R3**: The same module defines a spec update route runner that calls
  `agn-update-node` and then executes cache receipt, contributor-key audit, and
  rollback receipt.
- [ ] **R4**: The sibling-kernel band returns `11111` for route-runner binding
  shape evidence across Go, Rust, and TypeScript kernels.
- [ ] **R5**: The live integration returns `1111111` after executing both route
  runners, reading graph rows, revisions, receipts, edge repair, and key audit
  back from throwaway Postgres, cleaning up, and closing the connection.
- [ ] **R6**: Route docs and A/B observation evidence name the deployed
  `X-Form-Native-Public-Gate` canary as the next boundary.
- [ ] **R7**: Route docs and tests link the side-effect ledger so route binding
  cannot use execution proof as a circular reason to add effects.

## Research Inputs

- `2026-06-08` - User direction: continue walking toward the north star without
  stopping at carried side-effect intent.
- `specs/native-mutation-side-effects.md` - native side-effect carrier proof.
- `specs/native-graph-mutation-live-db-proof.md` - application graph mutation
  carrier proof.
- `specs/native-mutation-ab-observation-gate.md` - public flip stays observed
  and reversible before movement.

## Files to Create/Modify

- `form/form-stdlib/native-mutation-route-side-effects.fk` - route-runner binding
  recipes.
- `form/form-stdlib/tests/native-mutation-route-side-effects-band.fk` -
  sibling-kernel proof.
- `form/form-stdlib/integration/native-mutation-route-side-effects-live.fk` -
  live Postgres route-runner integration.
- `form/scripts/native-mutation-route-side-effects-test.sh` - throwaway Postgres
  harness.
- `docs/coherence-substrate/native-mutation-side-effect-ledger.form` -
  source-classified keep/delete ledger for mutable side effects.
- `api/tests/test_native_mutation_route_side_effect_binding.py` - repository
  proof for carrier, live harness, A/B gate, and route docs.
- `api/tests/test_native_mutation_side_effect_ledger.py` - repository proof that
  route docs and specs carry the anti-circular ledger boundary.
- `deploy/kernel-router/mutation_ab_observation_harness.py` - remaining evidence
  wording.
- `docs/coherence-substrate/ideas-router.form` - ideas route state.
- `docs/coherence-substrate/spec-registry-router.form` - spec route state.
- `specs/native-mutation-route-side-effect-binding.md` - this contract.

## Acceptance Tests

- `api/tests/test_native_mutation_route_side_effect_binding.py::test_route_side_effect_binding_band_executes_across_sibling_kernels`
- `api/tests/test_native_mutation_route_side_effect_binding.py::test_route_side_effect_binding_live_script_runs_or_skips_when_pg_missing`
- `api/tests/test_native_mutation_route_side_effect_binding.py::test_ab_gate_next_evidence_is_public_gate_after_route_binding`
- `api/tests/test_native_mutation_side_effect_ledger.py::test_route_forms_and_specs_link_the_ledger_boundary`
- `api/tests/test_native_mutation_ab_observation.py::test_ab_gate_recommends_live_db_trial_after_full_confidence`
- Manual validation: `form/scripts/native-mutation-route-side-effects-test.sh`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/application-graph-node-port.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/native-mutation-route-side-effects.fk form-stdlib/tests/native-mutation-route-side-effects-band.fk
cd .. && form/scripts/native-mutation-route-side-effects-test.sh
cd api && python3 -m pytest -q tests/test_native_mutation_route_side_effect_binding.py tests/test_native_mutation_side_effect_ledger.py tests/test_native_mutation_ab_observation.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py
python3 scripts/validate_spec_quality.py --file specs/native-mutation-route-side-effect-binding.md
```

## Out of Scope

- Production database writes.
- Ordinary public front-door mutation routing changes.
- Changing preview route responses from `executes:false`.
- Python in-memory cache flushing and resonance re-attunement.
- Treating rollback receipts as Python parity.

## Gaps

- GAP-NMRSB1: closed by `specs/native-mutation-public-gate.md`. A narrow
  `X-Form-Native-Public-Gate` route now carries route-local rollback receipt
  proof while no-header traffic remains fanout.
- GAP-NMRSB2 follow-up task: `native-mutation-deployed-public-canary`. Deploy
  and observe the public-gate header path before ordinary mutable traffic moves.
- GAP-NMRSB3: closed by `specs/native-idea-valuation-audit-ledger.md`. Idea
  update valuation audit-ledger writes now have a Form-native route-runner
  carrier.

## Risks and Assumptions

- The harness uses throwaway Postgres when available. In environments without
  `initdb`, it exits as SKIP rather than claiming live DB proof.
- Route-runner binding proves the native flow, not public route activation.
- Route-runner binding uses the side-effect ledger as constraint: rollback
  receipts are reversible gate safety, not domain parity.
- The ledger states that rollback receipts are gate-local safety rather than Python parity.
- The public manifest remains no-header fanout by default, so ordinary clients
  do not observe native mutation execution until a deployed public-gate canary
  lands and is explicitly promoted.
