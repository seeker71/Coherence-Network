---
idea_id: idea-realization-engine
status: done
source:
  - file: form/form-stdlib/native-mutation-trust-envelope.fk
    symbols: [nmte-trust-envelope-json, nmte-side-effect-intents-json, nmte-reversible-gate-json, nmte-test]
  - file: form/form-stdlib/tests/native-mutation-trust-envelope-band.fk
    symbols: []
  - file: deploy/kernel-router/production-routes.fk
    symbols: [mpv-trust-envelope-json, mpv-side-effect-intents-json, mpv-reversible-gate-json]
  - file: deploy/kernel-router/mutation_ab_observation_harness.py
    symbols: [evaluate_case, build_gate_report]
  - file: api/tests/test_native_mutation_route_bindings.py
    symbols: [test_native_mutation_preview_handlers_emit_application_graph_sql]
  - file: api/tests/test_native_mutation_ab_observation.py
    symbols: [test_ab_observation_case_passes_only_when_a_fanout_and_b_native_preview, test_ab_gate_recommends_live_db_trial_after_full_confidence]
  - file: api/tests/test_ideas_router_form.py
    symbols: [test_ideas_router_form_names_native_mutation_carrier]
  - file: api/tests/test_spec_registry_router_form.py
    symbols: [test_spec_registry_router_form_describes_live_and_native_carriers]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure]
requirements:
  - "Native mutation preview responses include a Form-native trust envelope instead of reducing the remaining work to an unstructured gap string."
  - "The trust envelope carries prediction error as residual, not as ignored uncertainty."
  - "The envelope exposes choice_success=1 plus silence, protocol, fail, stop, and BMA markers for the reversible preview choice."
  - "The envelope carries side-effect intents for cache invalidation, parent-edge repair, contributor-key audit, and rollback receipt."
  - "The reversible gate keeps ordinary_traffic_flip_allowed=false and ordinary_traffic_flip_performed=false while default traffic remains fanout-python."
done_when:
  - 'file_exists("form/form-stdlib/native-mutation-trust-envelope.fk")'
  - 'file_contains("deploy/kernel-router/production-routes.fk", "\"choice_success\":1")'
  - 'file_contains("deploy/kernel-router/production-routes.fk", "\"prediction_error\":\"carried_as_residual\"")'
  - 'pytest_passes("api/tests/test_native_mutation_route_bindings.py")'
test: "cd form && ./validate.sh form-stdlib/core.fk form-stdlib/native-mutation-trust-envelope.fk form-stdlib/tests/native-mutation-trust-envelope-band.fk && cd ../api && python3 -m pytest -q tests/test_native_mutation_route_bindings.py tests/test_native_mutation_ab_observation.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py"
constraints:
  - "Do not perform the ordinary public mutation traffic flip in this slice."
  - "This slice does not claim side-effect execution; the later side-effect carrier proof must remain separately named."
  - "Do not ignore prediction residuals or hide rollback state outside the response."
---

# Spec: Native Mutation Trust Envelope

## Purpose

The native mutation preview had route bindings, SQL, live DB proof, response
projection, and A/B observation, but the remaining boundary was still named as a
generic gap. This spec makes the boundary form-native: every preview response
returns a trust envelope that names the successful choice, the carried residual,
the deferred side effects, and the reversible gate that keeps ordinary traffic
on the Python fanout path.

## Requirements

- [ ] **R1**: `form/form-stdlib/native-mutation-trust-envelope.fk` defines a
  reusable envelope recipe that returns JSON with operation, node id, state, and
  `choice_success=1`.
- [ ] **R2**: The envelope carries `prediction_error="carried_as_residual"` and
	  a residual sentence naming that side effects are held as intent while fanout
	  remains default.
- [ ] **R3**: The envelope carries the choice protocol markers:
  `silence="fanout-default"`, `protocol="X-Form-Native-Preview"`,
  `fail="rollback-to-fanout"`, `stop="ordinary-traffic-unflipped"`, and
  `bma="native-mutation-trust-envelope"`.
- [ ] **R4**: The envelope carries side-effect intents for cache invalidation,
  parent-edge repair, contributor-key audit, and rollback receipt.
- [ ] **R5**: The envelope carries a reversible gate with default route
  `fanout-python`, native route `X-Form-Native-Preview`,
  `ordinary_traffic_flip_allowed=false`, and
  `ordinary_traffic_flip_performed=false`.
- [ ] **R6**: `deploy/kernel-router/production-routes.fk` embeds this envelope
  in each method-specific native mutation preview response.
- [ ] **R7**: The A/B observation harness treats the envelope as part of the B
  arm contract and now names the deployed public-gate canary as the next
  evidence.
- [ ] **R8**: The idea and spec route Form docs name the trust envelope as part
  of the current mutable-route state before any no-header public flip.

## Research Inputs

- `2026-06-08` - User direction: treat `0`, `1`, silence, protocol, fail, stop,
  and BMA as known choice state.
- `specs/method-specific-native-mutation-preview-bindings.md` - preview route
  binding contract.
- `specs/native-mutation-ab-observation-gate.md` - A/B gate before public
  mutation traffic moves.
- `specs/native-mutation-response-projection.md` - Form response projection
  after live DB mutation readback.

## Files to Create/Modify

- `form/form-stdlib/native-mutation-trust-envelope.fk` - reusable trust envelope
  recipe.
- `form/form-stdlib/tests/native-mutation-trust-envelope-band.fk` - sibling
  kernel proof.
- `deploy/kernel-router/production-routes.fk` - preview response envelope.
- `deploy/kernel-router/mutation_ab_observation_harness.py` - B-arm envelope
  checks and next evidence.
- `api/tests/test_native_mutation_route_bindings.py` - route response contract.
- `api/tests/test_native_mutation_ab_observation.py` - observation contract.
- `api/tests/test_ideas_router_form.py` - ideas route wording proof.
- `api/tests/test_spec_registry_router_form.py` - spec route wording proof.
- `docs/coherence-substrate/ideas-router.form` - ideas route state.
- `docs/coherence-substrate/spec-registry-router.form` - spec route state.
- `specs/native-mutation-trust-envelope.md` - this contract.

## Acceptance Tests

- `form/form-stdlib/tests/native-mutation-trust-envelope-band.fk` returns
  `11111` across sibling kernels.
- `api/tests/test_native_mutation_route_bindings.py::test_native_mutation_preview_handlers_emit_application_graph_sql`
- `api/tests/test_native_mutation_ab_observation.py::test_ab_observation_case_passes_only_when_a_fanout_and_b_native_preview`
- `api/tests/test_native_mutation_ab_observation.py::test_ab_gate_recommends_live_db_trial_after_full_confidence`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_names_native_mutation_carrier`
- `api/tests/test_spec_registry_router_form.py::test_spec_registry_router_form_describes_live_and_native_carriers`

## Verification

```bash
cd form && ./validate.sh form-stdlib/core.fk form-stdlib/native-mutation-trust-envelope.fk form-stdlib/tests/native-mutation-trust-envelope-band.fk
cd api && python3 -m pytest -q tests/test_native_mutation_route_bindings.py tests/test_native_mutation_ab_observation.py tests/test_ideas_router_form.py tests/test_spec_registry_router_form.py
python3 scripts/validate_spec_quality.py --file specs/native-mutation-trust-envelope.md
```

## Out of Scope

- Ordinary public traffic flip for mutable idea/spec routes.
- Native execution of cache invalidation, parent-edge repair, contributor-key
  audit updates, or rollback receipt persistence; that proof lives in
  `specs/native-mutation-side-effects.md`.
- Claiming numeric provider or model trust metrics.

## Gaps

- GAP-NMTE1: closed by `specs/native-mutation-side-effects.md`. The carried
  side-effect intents now have a Form-native execution carrier with throwaway
  Postgres readback for cache-invalidation receipt, parent-edge repair,
  contributor-key audit, and rollback receipt.
- GAP-NMTE2: closed by `specs/native-mutation-route-side-effect-binding.md`. The
  proven side-effect carrier is now bound to Form-native route-runner execution.
- GAP-NMTE3: closed by `specs/native-mutation-public-gate.md`. The narrow
  public gate now carries a route-local rollback receipt.
- GAP-NMTE4 follow-up task: `native-mutation-deployed-public-canary`. Deploy and
  observe the `X-Form-Native-Public-Gate` canary before any no-header flip.

## Risks and Assumptions

- The envelope is a JSON-shaped response contract; it is not yet persisted as a
  dedicated audit row.
- The preview header remains a non-executing SQL preview entry point.
- The public-gate header remains explicit and reversible; ordinary no-header
  mutation traffic stays on FastAPI until deployment canary evidence lands.
