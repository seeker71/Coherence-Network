---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-stdlib/native-mutation-public-gate.fk
    symbols: [nmpg-public-gate-header, nmpg-public-gate-rollback-receipt-sql, nmpg-run-idea-create-public-gate, nmpg-run-idea-update-public-gate, nmpg-run-spec-update-public-gate, nmpg-public-gate-test]
  - file: form/form-stdlib/native-idea-valuation-audit-ledger.fk
    symbols: [nival-run-idea-update-with-valuation-audit]
  - file: docs/coherence-substrate/native-mutation-side-effect-ledger.form
    symbols: [native_mutation_side_effect_ledger, native_mutation_side_effect_recipe_shift]
  - file: form/form-stdlib/tests/native-mutation-public-gate-band.fk
    symbols: []
  - file: form/form-stdlib/integration/native-mutation-public-gate-live.fk
    symbols: []
  - file: form/scripts/native-mutation-public-gate-test.sh
    symbols: []
  - file: deploy/kernel-router/production-routes.fk
    symbols: []
  - file: deploy/kernel-router/mutation_public_gate_harness.py
    symbols: [PublicGateCase, evaluate_case, build_gate_report, run_observation]
  - file: api/tests/test_native_mutation_public_gate.py
    symbols: [test_public_gate_band_executes_across_sibling_kernels, test_public_gate_live_script_runs_or_skips_when_pg_missing, test_public_gate_harness_observes_public_gate_when_kernel_available]
  - file: api/tests/test_native_mutation_side_effect_ledger.py
    symbols: [test_gate_receipts_are_not_claimed_as_python_parity, test_audit_ledger_parity_is_carried_before_ordinary_flip, test_route_forms_and_specs_link_the_ledger_boundary]
  - file: api/tests/test_native_idea_valuation_audit_ledger.py
    symbols: [test_ledger_and_route_forms_mark_audit_parity_carried]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
requirements:
  - "A Form-native public gate persists route-local rollback receipts while composing the native route-side-effect runner."
  - "The production route manifest exposes X-Form-Native-Public-Gate rows for mutable ideas/spec routes without changing no-header traffic."
  - "The public-gate harness observes no-header fanout, preview-header SQL preview, public-gate native selection, and public-gate priority when both headers are present."
  - "HTTP public-gate responses stay honest: the header gate executes and emits a rollback receipt shape, while DB execution remains proven in the Form live fixture rather than claimed by the HTTP route."
  - "Each public-gate HTTP response emits a compact decision receipt naming candidates, selected path, outcome, protocol, reversibility, and a signature so the gate can contradict intent with observable state."
  - "The next boundary is a deployed X-Form-Native-Public-Gate canary before any ordinary no-header flip."
  - "The side-effect ledger keeps rollback receipts as gate-local safety rather than Python parity, so side-effect proof does not justify side effects."
  - "The public-gate Form layer exposes an idea update runner over the native idea valuation audit-ledger carrier."
done_when:
  - 'file_exists("form/form-stdlib/native-mutation-public-gate.fk")'
  - 'file_exists("deploy/kernel-router/mutation_public_gate_harness.py")'
  - 'pytest_passes("api/tests/test_native_mutation_public_gate.py")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/application-graph-node-port.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/native-mutation-route-side-effects.fk form-stdlib/native-mutation-public-gate.fk form-stdlib/tests/native-mutation-public-gate-band.fk && cd .. && form/scripts/native-mutation-public-gate-test.sh && python3 deploy/kernel-router/mutation_public_gate_harness.py --json && cd api && python3 -m pytest -q tests/test_native_mutation_public_gate.py tests/test_native_mutation_ab_observation.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py"
constraints:
  - "Do not execute against the production application database."
  - "Do not flip ordinary no-header public mutation traffic."
  - "Keep preview routes as non-executing SQL previews."
---

# Spec: Native Mutation Public Gate

## Purpose

The native route runner can now perform graph mutations and side effects
together. This spec adds the next reversible movement: a public-gate header that
selects native mutation route rows and carries a route-local rollback receipt,
while ordinary no-header traffic continues to fan out to FastAPI. The
side-effect ledger is the constraint around this movement: rollback receipts are
reversible gate safety, not evidence that extra domain side effects belong.

## Requirements

- [ ] **R1**: `native-mutation-public-gate.fk` defines the
  `X-Form-Native-Public-Gate` header, a public-gate rollback receipt SQL shape,
  and idea/spec public-gate runner wrappers over the route-side-effect carrier.
- [ ] **R2**: The sibling-kernel band returns `111111` for header, receipt,
  route-runner binding, exposed functions, and ordinary-traffic rollback state.
- [ ] **R3**: The live integration returns `11111111` after executing idea and
  spec public-gate runners, reading graph rows, revisions, public-gate rollback
  receipts, key audit, contract state, cleanup, and close from throwaway
  Postgres.
- [ ] **R4**: `production-routes.fk` exposes method-specific
  `X-Form-Native-Public-Gate` rows for mutable ideas/spec routes with higher
  priority than preview rows when both headers are present.
- [ ] **R5**: `mutation_public_gate_harness.py` observes all five mutation
  shapes as A no-header fanout, B preview-header SQL preview, and C public-gate
  native selection.
- [ ] **R6**: Public-gate HTTP responses include a route-local rollback receipt,
  keep `executes:false` for HTTP-side DB honesty, and carry
  `route_local_gate_executes:true`.
- [ ] **R7**: Route docs and tests link the side-effect ledger and keep
  public-gate receipts classified as gate receipts, not Python parity.
- [ ] **R8**: `native-mutation-public-gate.fk` exposes
  `nmpg-run-idea-update-public-gate` over the native idea valuation audit-ledger
  carrier.
- [ ] **R9**: Public-gate responses carry `decision_receipt` with
  `state=native-mutation-gate-decision-receipt`, selected path
  `X-Form-Native-Public-Gate`, candidate outcomes for fanout/preview/public
  gate, `can_contradict_intent=true`, and a compact signature.

## Research Inputs

- `specs/native-mutation-route-side-effect-binding.md` - route runner binding
  proof that graph mutation and side effects execute together.
- `specs/native-mutation-side-effects.md` - side-effect carrier proof.
- `specs/native-mutation-ab-observation-gate.md` - preview A/B observation
  proof and ordinary traffic rollback discipline.
- `2026-06-08` - User direction: move the mutable surfaces closer to Form-native
  with reversible gating and embodied trust.

## Files to Create/Modify

- `form/form-stdlib/native-mutation-public-gate.fk` - public-gate receipt and
  runner recipes.
- `form/form-stdlib/native-idea-valuation-audit-ledger.fk` - idea update
  audit-ledger parity carrier consumed by the public gate.
- `form/form-stdlib/tests/native-mutation-public-gate-band.fk` - sibling-kernel
  proof.
- `form/form-stdlib/integration/native-mutation-public-gate-live.fk` - live
  Postgres proof.
- `form/scripts/native-mutation-public-gate-test.sh` - throwaway Postgres
  harness.
- `deploy/kernel-router/production-routes.fk` - public-gate route rows and
  response envelope.
- `deploy/kernel-router/mutation_public_gate_harness.py` - local HTTP selection
  harness.
- `docs/coherence-substrate/native-mutation-side-effect-ledger.form` -
  source-classified keep/delete ledger for mutable side effects.
- `api/tests/test_native_mutation_public_gate.py` - repository proof.
- `api/tests/test_native_mutation_side_effect_ledger.py` - repository proof that
  rollback receipts are not claimed as Python parity.
- `docs/coherence-substrate/ideas-router.form` - ideas route state.
- `docs/coherence-substrate/spec-registry-router.form` - spec route state.
- `specs/native-mutation-public-gate.md` - this contract.

## Acceptance Tests

- `api/tests/test_native_mutation_public_gate.py::test_public_gate_band_executes_across_sibling_kernels`
- `api/tests/test_native_mutation_public_gate.py::test_public_gate_live_script_runs_or_skips_when_pg_missing`
- `api/tests/test_native_mutation_public_gate.py::test_production_routes_expose_public_gate_without_no_header_flip`
- `api/tests/test_native_mutation_public_gate.py::test_public_gate_harness_observes_public_gate_when_kernel_available`
- `api/tests/test_native_mutation_public_gate.py::test_route_forms_name_public_gate_before_deployed_canary`
- `api/tests/test_native_idea_valuation_audit_ledger.py::test_ledger_and_route_forms_mark_audit_parity_carried`
- `api/tests/test_native_mutation_side_effect_ledger.py::test_gate_receipts_are_not_claimed_as_python_parity`
- `api/tests/test_native_mutation_side_effect_ledger.py::test_route_forms_and_specs_link_the_ledger_boundary`
- Manual validation: `python3 deploy/kernel-router/mutation_public_gate_harness.py --json`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/application-graph-node-port.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/native-mutation-route-side-effects.fk form-stdlib/native-idea-valuation-audit-ledger.fk form-stdlib/native-mutation-public-gate.fk form-stdlib/tests/native-mutation-public-gate-band.fk
cd .. && form/scripts/native-mutation-public-gate-test.sh
python3 deploy/kernel-router/mutation_public_gate_harness.py --json
cd api && python3 -m pytest -q tests/test_native_mutation_public_gate.py tests/test_native_idea_valuation_audit_ledger.py tests/test_native_mutation_side_effect_ledger.py tests/test_native_mutation_ab_observation.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py
python3 scripts/validate_spec_quality.py --file specs/native-mutation-public-gate.md
```

## Out of Scope

- Production application database writes.
- Ordinary no-header front-door mutation routing changes.
- Claiming HTTP-side DB execution before a deployed carrier supplies the DSN and
  observes the receipt.
- Treating public-gate receipts as Python parity or domain-side-effect evidence.

## Gaps

- GAP-NMPG1 follow-up task: `native-mutation-deployed-public-canary`. Deploy and
  observe an `X-Form-Native-Public-Gate` canary before any ordinary no-header
  mutation traffic flip.
- GAP-NMPG2: closed by `specs/native-idea-valuation-audit-ledger.md`. Idea
  valuation audit-ledger parity is now carried Form-native and bound into an
  idea update public-gate runner.

## Risks and Assumptions

- The HTTP public gate deliberately keeps DB execution honest with
  `executes:false`; the receipt persistence proof lives in the Form live-PG
  harness.
- Rollback receipts are gate-local safety rather than Python parity.
- Decision receipts are per-request gate witnesses: they record what branch was
  selected and enough signature detail to make the gate observable before the
  no-header flip.
- The ledger states that rollback receipts are gate-local safety rather than Python parity.
- Removing the public-gate header or route row is the reversible rollback for
  the header-gated canary path.
- No-header public mutation behavior remains FastAPI until the deployed canary
  has evidence.
