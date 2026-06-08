---
idea_id: idea-realization-engine
status: done
source:
  - file: deploy/kernel-router/mutation_ab_observation_harness.py
    symbols: [ObservationCase, HTTPObservation, CaseObservation, CASES, evaluate_case, build_gate_report, run_observation]
  - file: deploy/kernel-router/production-routes.fk
    symbols: []
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
  - file: api/tests/test_native_mutation_ab_observation.py
    symbols: [test_ab_observation_cases_cover_all_native_mutation_preview_routes, test_ab_observation_case_passes_only_when_a_fanout_and_b_native_preview, test_ab_gate_blocks_flip_when_any_observation_fails, test_ab_gate_recommends_live_db_trial_after_full_confidence]
requirements:
  - "The native mutation flip is expressed as an A/B observation gate before any public traffic moves."
  - "Variant A proves ordinary no-header mutation requests still fan out to FastAPI."
  - "Variant B proves explicit preview-header mutation requests return native SQL previews."
  - "The gate emits confidence, pass/fail observations, and a recommendation that can promote only to a live-DB trial, not an ordinary-traffic flip."
done_when:
  - 'file_exists("deploy/kernel-router/mutation_ab_observation_harness.py")'
  - 'file_contains("deploy/kernel-router/mutation_ab_observation_harness.py", "ordinary_traffic_flip_performed")'
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
`fanout-python` and B `native-kernel` preview, score the evidence, and only
recommend the next bounded trial when every case passes.

## Requirements

- [ ] **R1**: `deploy/kernel-router/mutation_ab_observation_harness.py` starts a
  mock CPython upstream and the production kernel-router manifest on local
  loopback ports.
- [ ] **R2**: The observation corpus covers all native mutation preview shapes:
  `POST /api/ideas`, `PATCH /api/ideas/*`, `POST /api/spec-registry`,
  `PATCH /api/spec-registry/*`, and `DELETE /api/spec-registry/*`.
- [ ] **R3**: For each case, variant A omits `X-Form-Native-Preview` and must
  return `X-Form-Router: fanout-python` from the mock upstream with the same
  method, path, and body.
- [ ] **R4**: For each case, variant B sends `X-Form-Native-Preview` and must
  return `X-Form-Router: native-kernel`, `status=202`, `executes:false`, the
  expected operation/node id, and SQL carrying the required application graph
  table semantics.
- [ ] **R5**: The gate report computes confidence and explicitly leaves
  `ordinary_traffic_flip_performed=false` and `ordinary_traffic_flip_allowed=false`.

## Research Inputs

- `deploy/kernel-router/shadow_proof_harness.py` - existing local shadow proof
  pattern.
- `deploy/kernel-router/production-routes.fk` - method-specific native preview
  route rows.
- `specs/method-specific-native-mutation-preview-bindings.md` - preview binding
  contract.
- `2026-06-08` - User direction: A/B test until confidence and turn the flip
  into observation before performing it.

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
- `api/tests/test_native_mutation_ab_observation.py::test_ab_observation_case_passes_only_when_a_fanout_and_b_native_preview`
- `api/tests/test_native_mutation_ab_observation.py::test_ab_gate_blocks_flip_when_any_observation_fails`
- `api/tests/test_native_mutation_ab_observation.py::test_ab_gate_recommends_live_db_trial_after_full_confidence`
- Manual validation: `python3 deploy/kernel-router/mutation_ab_observation_harness.py --json`

## Verification

```bash
python3 deploy/kernel-router/mutation_ab_observation_harness.py --json
cd api && python3 -m pytest -q tests/test_native_mutation_ab_observation.py tests/test_native_mutation_route_bindings.py
python3 scripts/validate_spec_quality.py --file specs/native-mutation-ab-observation-gate.md
```

## Out of Scope

- Public front-door routing changes.
- PostgreSQL execution of preview SQL.
- Response projection parity with `IdeaWithScore` or `SpecRegistryEntry`.
- Cache invalidation, parent/edge repair, resonance re-attunement, or
  contributor-key audit side effects.

## Gaps

- GAP-NMAOG1 follow-up task: `native-graph-mutation-live-db-proof`. Run the same
  observation shape against a rollback-safe application schema and verify writes,
  revisions, and edge cleanup.
- GAP-NMAOG2 follow-up task: `native-mutation-response-projection`. Add response
  projection parity to the B-side observation.
- GAP-NMAOG3 follow-up task: `native-mutation-public-flip-gate`. Only after live
  DB execution, response projection, cache invalidation, and side effects pass
  should ordinary traffic be eligible for a reversible flip.

## Risks and Assumptions

- The local A/B harness uses a mock upstream, so it proves route mechanics and
  preview SQL shape. It does not prove live service semantics.
- Confidence is strict by default: every mutation case must pass.
- A passing gate recommends `promote_to_live_db_trial`, not a production flip.
