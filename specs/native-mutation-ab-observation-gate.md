---
idea_id: idea-realization-engine
status: done
source:
  - file: deploy/kernel-router/mutation_ab_observation_harness.py
    symbols: [ObservationCase, HTTPObservation, CaseObservation, CASES, evaluate_case, build_gate_report, run_observation]
  - file: deploy/kernel-router/production-routes.fk
    symbols: []
  - file: form/form-stdlib/native-mutation-trust-envelope.fk
    symbols: [nmte-trust-envelope-json]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
  - file: api/tests/test_native_mutation_ab_observation.py
    symbols: [test_ab_observation_cases_cover_all_native_mutation_preview_routes, test_ab_observation_case_passes_with_native_default_preview_and_fallback, test_ab_gate_blocks_flip_when_any_observation_fails, test_ab_gate_recommends_live_db_trial_after_full_confidence]
requirements:
  - "The native mutation flip is expressed as an A/B/C observation gate before public Traefik default moves."
  - "Variant A proves no-header mutation requests that reach the kernel accept the implicit native invitation."
  - "Variant B proves explicit preview-header mutation requests return native SQL previews."
  - "Variant C proves X-Form-Python-Fallback fans out to FastAPI as the explicit refusal/control signal."
  - "The gate emits confidence, pass/fail observations, and a recommendation that can promote only to persistence-preserving native HTTP execution, not a blind public Traefik default flip."
  - "Variant B carries the trust envelope with prediction residual, choice protocol markers, side-effect intents, and reversible gate state."
done_when:
  - 'file_exists("deploy/kernel-router/mutation_ab_observation_harness.py")'
  - 'file_contains("deploy/kernel-router/mutation_ab_observation_harness.py", "ordinary_traffic_flip_performed")'
  - 'file_contains("deploy/kernel-router/mutation_ab_observation_harness.py", "treatment_prediction_error_carried")'
  - 'pytest_passes("api/tests/test_native_mutation_ab_observation.py")'
test: "python3 deploy/kernel-router/mutation_ab_observation_harness.py --json && cd api && python3 -m pytest -q tests/test_native_mutation_ab_observation.py"
constraints:
  - "Do not perform the public front-door flip in this slice."
  - "Do not execute SQL against PostgreSQL in this slice."
  - "Do not treat a passing preview observation as equivalent to live mutation parity."
---

# Spec: Native Mutation A/B Observation Gate

## Purpose

The mutation flip wants confidence, not bravery. This spec turns the public
front-door move into an observation loop: run each mutation shape as A
no-header native-default invitation, B `native-kernel` preview, and C explicit
`X-Form-Python-Fallback` fanout, score the evidence, and only recommend the next
bounded trial when every case passes.

## Requirements

- [ ] **R1**: `deploy/kernel-router/mutation_ab_observation_harness.py` starts a
  mock CPython upstream and the production kernel-router manifest on local
  loopback ports.
- [ ] **R2**: The observation corpus covers all native mutation preview shapes:
  `POST /api/ideas`, `PATCH /api/ideas/*`, `POST /api/spec-registry`,
  `PATCH /api/spec-registry/*`, and `DELETE /api/spec-registry/*`.
- [ ] **R3**: For each case, variant A omits native mutation headers and must
  return `X-Form-Router: native-kernel`, `status=202`,
  `native_default_invitation=true`, `required_header=null`, selected path
  `implicit-native-invitation`, and SQL carrying the required application graph
  table semantics.
- [ ] **R4**: For each case, variant B sends `X-Form-Native-Preview` and must
  return `X-Form-Router: native-kernel`, `status=202`, `executes:false`, the
  expected operation/node id, and SQL carrying the required application graph
  table semantics.
- [ ] **R5**: Variant C sends `X-Form-Python-Fallback` and must return
  `X-Form-Router: fanout-python` from the mock upstream with the same method,
  path, and body.
- [ ] **R6**: The gate report computes confidence and carries
  `ordinary_traffic_flip_performed=true`, `ordinary_traffic_flip_allowed=true`,
  and `python_fallback_header=X-Form-Python-Fallback` when every case passes.
- [ ] **R7**: Variant B must include a trust envelope carrying
  `prediction_error="carried_as_residual"`, `choice_success=1`,
  silence/protocol/fail/stop/BMA markers, side-effect intents, and reversible
  gate state.
- [ ] **R8**: When every case passes, the next evidence names public Traefik
  default routing to kernel-router, native HTTP mutation persistence semantics,
  and separate counting for explicit fallback/refusal signal.

## Research Inputs

- `deploy/kernel-router/shadow_proof_harness.py` - existing local shadow proof
  pattern.
- `deploy/kernel-router/production-routes.fk` - method-specific native preview
  route rows.
- `form/form-stdlib/native-mutation-trust-envelope.fk` - trust envelope recipe
  carried by variant B.
- `specs/method-specific-native-mutation-preview-bindings.md` - preview binding
  contract.
- `2026-06-08` - User direction: A/B test until confidence and turn the flip
  into observation before performing it.
- `2026-06-09` - User direction: not knowing becomes an offer to know, and
  refusal to speak native is signal.

## Files to Create/Modify

- `deploy/kernel-router/mutation_ab_observation_harness.py` - local A/B
  observation gate.
- `api/tests/test_native_mutation_ab_observation.py` - gate scoring and corpus
  proof.
- `docs/coherence-substrate/ideas-router.form` - ideas route state names the
  observation gate.
- `docs/coherence-substrate/spec-registry-router.form` - spec route state names
  the observation gate.
- `specs/native-mutation-ab-observation-gate.md` - this contract.

## Acceptance Tests

- `api/tests/test_native_mutation_ab_observation.py::test_ab_observation_cases_cover_all_native_mutation_preview_routes`
- `api/tests/test_native_mutation_ab_observation.py::test_ab_observation_case_passes_with_native_default_preview_and_fallback`
- `api/tests/test_native_mutation_ab_observation.py::test_ab_gate_blocks_flip_when_any_observation_fails`
- `api/tests/test_native_mutation_ab_observation.py::test_ab_gate_recommends_live_db_trial_after_full_confidence`
- `api/tests/test_native_mutation_ab_observation.py::test_ab_observation_case_passes_with_native_default_preview_and_fallback`
- Manual validation: `python3 deploy/kernel-router/mutation_ab_observation_harness.py --json`

## Verification

```bash
python3 deploy/kernel-router/mutation_ab_observation_harness.py --json
cd api && python3 -m pytest -q tests/test_native_mutation_ab_observation.py tests/test_native_mutation_route_bindings.py
python3 scripts/validate_spec_quality.py --file specs/native-mutation-ab-observation-gate.md
```

## Out of Scope

- Public Traefik front-door routing changes.
- PostgreSQL execution of preview SQL.
- Cache invalidation, parent/edge repair, resonance re-attunement, or
  contributor-key audit side effects.

## Gaps

- GAP-NMAOG1: closed by `specs/native-graph-mutation-live-db-proof.md`. The
  Form-native application graph mutation wrappers now run against a rollback-safe
  throwaway Postgres and verify writes, revisions, and edge cleanup.
- GAP-NMAOG2: closed by `specs/native-mutation-response-projection.md`. Form
  response projection now covers `IdeaWithScore` and `SpecRegistryEntry` rows
  after live DB mutation readback.
- GAP-NMAOG3: closed by `specs/native-mutation-trust-envelope.md`. The B arm now
  carries prediction residual, choice protocol markers, side-effect intents, and
  reversible gate state.
- GAP-NMAOG4: closed by `specs/native-mutation-side-effects.md`. The carried
  side-effect intents now have a Form-native execution carrier with throwaway
  Postgres readback for cache-invalidation receipt, parent-edge repair,
  contributor-key audit, and rollback receipt.
- GAP-NMAOG5: closed by `specs/native-mutation-route-side-effect-binding.md`.
  Native route runners now bind application graph mutation execution to
  side-effect execution in throwaway Postgres.
- GAP-NMAOG6: closed by `specs/native-mutation-public-gate.md`. The native
  public gate now has a Form-live rollback receipt proof and a production
  manifest header gate.
- GAP-NMAOG7 follow-up task: `native-http-mutation-persistence-default`. Carry
  production persistence semantics in the HTTP native mutation handler before
  public Traefik no-header default routes through kernel-router.

## Risks and Assumptions

- The local A/B harness uses a mock upstream, so it proves route mechanics and
  preview SQL shape. It does not prove live service semantics.
- Confidence is strict by default: every mutation case must pass, including
  envelope checks.
- A passing gate reports `preview_confidence_complete`, not a public Traefik
  production default flip.
