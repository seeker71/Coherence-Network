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
  - file: deploy/kernel-router/docker-compose.kernel-router.yml
    symbols: []
  - file: Dockerfile.kernel-router
    symbols: []
  - file: deploy/kernel-router/entrypoint.sh
    symbols: []
  - file: deploy/hostinger/auto-deploy.sh
    symbols: [ensure_kernel_router_canary]
  - file: scripts/verify_kernel_canary_public_gate.sh
    symbols: []
  - file: .github/workflows/hostinger-auto-deploy.yml
    symbols: []
  - file: .github/workflows/public-deploy-contract.yml
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
  - "The production route manifest exposes X-Form-Native-Public-Gate rows plus no-header native-default invitation rows for mutable ideas/spec routes; X-Form-Python-Fallback is the explicit refusal/control signal."
  - "The public-gate harness observes no-header native-default invitation, preview-header SQL preview, public-gate native selection, public-gate priority when both headers are present, and explicit Python fallback fanout."
  - "HTTP public-gate responses stay honest: the header/default gate executes native SQL through config_database_url -> pg_connect -> pg_exec -> pg_close, emits persistence readback evidence, and carries a rollback receipt shape."
  - "Native HTTP revision ids are derived from route prefix, node id, and revision number; fixed per-route revision ids are not valid for production traffic."
  - "Each public-gate HTTP response emits a compact decision receipt naming candidates, selected path, outcome, protocol, reversibility, and a signature so the gate can contradict intent with observable state."
  - "The deploy path exposes X-Form-Native-Public-Gate as a higher-priority Traefik witness and routes bounded no-header mutable ideas/spec method/path traffic to the kernel-router native default invitation with a mounted production config carrier."
  - "The side-effect ledger keeps rollback receipts as gate-local safety rather than Python parity, so side-effect proof does not justify side effects."
  - "The public-gate Form layer exposes an idea update runner over the native idea valuation audit-ledger carrier."
done_when:
  - 'file_exists("form/form-stdlib/native-mutation-public-gate.fk")'
  - 'file_exists("deploy/kernel-router/mutation_public_gate_harness.py")'
  - 'file_exists("scripts/verify_kernel_canary_public_gate.sh")'
  - 'pytest_passes("api/tests/test_native_mutation_public_gate.py")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/application-graph-node-port.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/native-mutation-route-side-effects.fk form-stdlib/native-mutation-public-gate.fk form-stdlib/tests/native-mutation-public-gate-band.fk && cd .. && form/scripts/native-mutation-public-gate-test.sh && python3 deploy/kernel-router/mutation_public_gate_harness.py --json && python3 deploy/kernel-router/mutation_ab_observation_harness.py --json && bash -n deploy/hostinger/auto-deploy.sh scripts/verify_kernel_canary_public_gate.sh && cd api && python3 -m pytest -q tests/test_native_mutation_public_gate.py tests/test_native_mutation_ab_observation.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py"
constraints:
  - "Do not execute against the production application database from local proof harnesses."
  - "Do not perform the all-traffic Host(api.coherencycoin.com) front-door flip; this release only promotes bounded mutable ideas/spec method/path routers."
  - "Keep preview routes as non-executing SQL previews."
---

# Spec: Native Mutation Public Gate

## Purpose

The native route runner can now perform graph mutations and side effects
together. This spec adds the reversible public movement: a public-gate header
that selects native mutation route rows and carries a route-local rollback
receipt, plus bounded no-header Traefik routers for mutable ideas/spec method
paths. No-header traffic on those promoted routes accepts the implicit native
invitation, and `X-Form-Python-Fallback` is the explicit refusal/control signal.
The broader all-traffic Host front door remains outside this spec's deploy flip.
The side-effect ledger is the constraint around this movement: rollback receipts
are reversible gate safety, not evidence that extra domain side effects belong.

## Requirements

- [ ] **R1**: `native-mutation-public-gate.fk` defines the
  `X-Form-Native-Public-Gate` header, a public-gate rollback receipt SQL shape,
  and idea/spec public-gate runner wrappers over the route-side-effect carrier.
- [ ] **R2**: The sibling-kernel band returns `11111111` for header, receipt,
  route-runner binding, exposed functions, and ordinary-traffic rollback state.
- [ ] **R3**: The live integration returns `111111111` after executing idea and
  spec public-gate runners, reading graph rows, revisions, public-gate rollback
  receipts, key audit, contract state, cleanup, and close from throwaway
  Postgres.
- [ ] **R4**: `production-routes.fk` exposes method-specific no-header
  native-default invitation rows plus `X-Form-Native-Public-Gate` rows for
  mutable ideas/spec routes, with public-gate priority above preview rows when
  both headers are present.
- [ ] **R5**: `mutation_public_gate_harness.py` observes all five mutation
  shapes as A no-header native-default invitation, B preview-header SQL preview,
  C public-gate native selection, and D explicit `X-Form-Python-Fallback`
  fanout.
- [ ] **R6**: Public-gate HTTP responses include a route-local rollback receipt,
  carry `executes:true`, `db_execution=performed-by-http-native-persistence`,
  `route_local_gate_executes:true`, and a `persistence` object with carrier,
  row-count, close-code, and error stage.
- [ ] **R7**: Route docs and tests link the side-effect ledger and keep
  public-gate receipts classified as gate receipts, not Python parity.
- [ ] **R8**: `native-mutation-public-gate.fk` exposes
  `nmpg-run-idea-update-public-gate` over the native idea valuation audit-ledger
  carrier.
- [ ] **R9**: Public-gate responses carry `decision_receipt` with
  `state=native-mutation-gate-decision-receipt`, selected path
  `X-Form-Native-Public-Gate`, candidate outcomes for implicit native
  invitation/preview/public gate/Python fallback, `can_contradict_intent=true`,
  and a compact signature.
- [ ] **R10**: The Hostinger deploy path runs a kernel-router service with
  `production-routes.fk`, a mounted config-file carrier at
  `/run/coherence-network/config.json`, Traefik header rules for
  `X-Form-Native-Preview: 1` and `X-Form-Native-Public-Gate: 1`, and bounded
  no-header method/path routers for `POST/PATCH /api/ideas` plus
  `POST/PATCH/DELETE /api/spec-registry`, while unlisted ordinary routes remain
  FastAPI-backed.
- [ ] **R11**: Public deployment verification probes
  `X-Form-Native-Public-Gate: 1` against `POST /api/ideas`, requires
  `202 + X-Form-Router:native-kernel + decision_receipt + executes:true`, then
  probes no-header `POST /api/ideas` and requires
  `native_default_invitation=true`, selected path `implicit-native-invitation`,
  native persistence readback, and an explicit `X-Form-Python-Fallback` probe
  with `X-Form-Router:fanout-python`.
- [ ] **R12**: The local public-gate harness includes a production-style
  revision-id collision probe: two no-header native-default creates and two
  `X-Form-Native-Public-Gate` creates run without schema reset and produce
  distinct graph-node revision ids.

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
- `deploy/kernel-router/docker-compose.kernel-router.yml` - bounded Traefik
  native mutation routers, header witnesses, and config-file mount.
- `Dockerfile.kernel-router` - non-secret config baseline for kernel config
  natives.
- `deploy/kernel-router/entrypoint.sh` - optional `serve --config` carrier.
- `deploy/hostinger/auto-deploy.sh` - deploy-time kernel-router bring-up and
  local public/default/fallback receipt probes.
- `scripts/verify_kernel_canary_public_gate.sh` - public treatment/default/fallback
  verifier for the deployed bounded native default.
- `.github/workflows/hostinger-auto-deploy.yml` - public kernel deploy and
  verification workflow.
- `.github/workflows/public-deploy-contract.yml` - trigger coverage for
  canary-related deploy files.
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
- `api/tests/test_native_mutation_public_gate.py::test_production_routes_expose_public_gate_with_native_default_invitation`
- `api/tests/test_native_mutation_public_gate.py::test_public_gate_harness_observes_public_gate_when_kernel_available`
- `api/tests/test_native_mutation_public_gate.py::test_route_forms_name_public_gate_default_evidence_boundary`
- `api/tests/test_native_mutation_public_gate.py::test_deploy_exposes_bounded_no_header_native_mutation_flip`
- `api/tests/test_native_idea_valuation_audit_ledger.py::test_ledger_and_route_forms_mark_audit_parity_carried`
- `api/tests/test_native_mutation_side_effect_ledger.py::test_gate_receipts_are_not_claimed_as_python_parity`
- `api/tests/test_native_mutation_side_effect_ledger.py::test_route_forms_and_specs_link_the_ledger_boundary`
- Manual validation: `python3 deploy/kernel-router/mutation_public_gate_harness.py --json`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/application-graph-node-port.fk form-stdlib/native-mutation-side-effects.fk form-stdlib/native-mutation-route-side-effects.fk form-stdlib/native-idea-valuation-audit-ledger.fk form-stdlib/native-mutation-public-gate.fk form-stdlib/tests/native-mutation-public-gate-band.fk
cd .. && form/scripts/native-mutation-public-gate-test.sh
python3 deploy/kernel-router/mutation_public_gate_harness.py --json
python3 deploy/kernel-router/mutation_ab_observation_harness.py --json
bash -n deploy/hostinger/auto-deploy.sh scripts/verify_kernel_canary_public_gate.sh
cd api && python3 -m pytest -q tests/test_native_mutation_public_gate.py tests/test_native_idea_valuation_audit_ledger.py tests/test_native_mutation_side_effect_ledger.py tests/test_native_mutation_ab_observation.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py
python3 scripts/validate_spec_quality.py --file specs/native-mutation-public-gate.md
```

Public post-deploy verification:

```bash
scripts/verify_kernel_canary_public_gate.sh https://api.coherencycoin.com
```

## Out of Scope

- Production application database writes from local proof harnesses.
- All-traffic public Traefik Host front-door routing changes.
- Treating public-gate receipts as Python parity or domain-side-effect evidence.

## Gaps

- GAP-NMPG1: closed by the kernel-router overlay, public verifier, local
  default-native invitation harness, native HTTP mutation persistence harness,
  and bounded public no-header mutable method/path routers.
- GAP-NMPG3: closed by `native-http-mutation-persistence-default`. The HTTP
  native mutation handler now carries production persistence semantics through
  the kernel config carrier and Form-native `pg_exec`.
- GAP-NMPG4: closed by `native-http-revision-id-fix`. Public deploy canary
  exposed that fixed route-level revision ids collide under repeated production
  creates. `production-routes.fk` now derives revision ids from route prefix,
  node id, and revision number, and `mutation_public_gate_harness.py` proves
  repeated no-header/default and public-gate creates without schema reset.
- GAP-NMPG2: closed by `specs/native-idea-valuation-audit-ledger.md`. Idea
  valuation audit-ledger parity is now carried Form-native and bound into an
  idea update public-gate runner.
- Follow-up task: promote the next route only after it has its own native
  carrier, public verifier, rollback signal, and production evidence.

## Risks and Assumptions

- The HTTP public gate now keeps DB execution honest with `executes:true`,
  `db_execution=performed-by-http-native-persistence`, and a persistence object
  when the config carrier is present; missing config answers as an observable
  persistence failure instead of silently claiming a write.
- Rollback receipts are gate-local safety rather than Python parity.
- Decision receipts are per-request gate witnesses: they record what branch was
  selected and enough signature detail to make the bounded native default
  observable after the no-header move.
- The public header witnesses rely on Traefik 3 `Header` matchers and explicit
  header value `1`; the bounded no-header routers rely on method/path matchers
  with lower priority than the explicit header witnesses.
- The ledger states that rollback receipts are gate-local safety rather than Python parity.
- `X-Form-Python-Fallback`, removing the default native route rows, or removing
  the bounded Traefik method/path routers is the reversible rollback path.
- No-header public mutation behavior for promoted ideas/spec method/path routes
  now enters native default; unpromoted public routes remain FastAPI-backed.
