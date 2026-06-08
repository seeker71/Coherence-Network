---
idea_id: idea-realization-engine
status: done
source:
  - file: deploy/kernel-router/production-routes.fk
    symbols: []
  - file: scripts/runtime_surface_report.py
    symbols: [kernel_first_capable_routes]
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [ideas_router_structure, mutate_idea_recipe]
  - file: docs/coherence-substrate/spec-registry-router.form
    symbols: [spec_registry_router_structure, mutate_specs_recipe]
  - file: api/tests/test_native_mutation_route_bindings.py
    symbols: [test_native_mutation_preview_routes_are_method_and_header_gated, test_native_mutation_preview_handlers_emit_application_graph_sql, test_native_mutation_preview_uses_live_spec_node_id_convention, test_idea_and_spec_forms_name_method_specific_preview_bindings]
  - file: api/tests/test_runtime_surface_native_routes.py
    symbols: [test_parser_reads_bindings_not_comments, test_real_manifest_native_routes_are_served_zero_and_include_ideas_structure]
requirements:
  - "The kernel-router production manifest binds method-specific native preview rows for idea/spec mutations."
  - "Preview rows require X-Form-Native-Preview so ordinary public mutations still fan out to FastAPI."
  - "Preview handlers bind JSON request bodies and wildcard path ids to application graph SQL for graph_nodes, graph_node_revisions, and graph_edges."
  - "Runtime-surface reporting counts method-specific KernelHTTPRoute rows without collapsing PATCH and DELETE wildcard routes into one path."
done_when:
  - 'file_contains("deploy/kernel-router/production-routes.fk", "(kh-route \"ideas-create-native-preview\" \"POST\" \"/api/ideas\"")'
  - 'file_contains("deploy/kernel-router/production-routes.fk", "X-Form-Native-Preview")'
  - 'pytest_passes("api/tests/test_native_mutation_route_bindings.py")'
test: "cd api && python3 -m pytest -q tests/test_native_mutation_route_bindings.py tests/test_runtime_surface_native_routes.py"
constraints:
  - "Do not make normal public POST/PATCH/DELETE mutations execute natively in this slice."
  - "Do not execute SQL against the live application database in this slice."
  - "Do not claim cache invalidation, response projection, parent/edge side effects, or contributor-key audit side effects are complete."
---

# Spec: Method-Specific Native Mutation Preview Bindings

## Purpose

The mutable idea and spec routes already had native graph mutation vocabulary,
native auth decisions, and application table SQL. The missing route-level piece
was a method-specific binding that could receive the real public HTTP shape
without taking ordinary production writes away from FastAPI. This spec adds that
binding as an explicit native preview surface.

## Requirements

- [ ] **R1**: `deploy/kernel-router/production-routes.fk` declares native
  `POST /api/ideas`, `PATCH /api/ideas/*`, `POST /api/spec-registry`,
  `PATCH /api/spec-registry/*`, and `DELETE /api/spec-registry/*` preview rows.
- [ ] **R2**: Each preview row is a `KernelHTTPRoute` with method, path pattern,
  required `X-Form-Native-Preview` header, and a pressure budget that admits only
  matching explicit preview requests.
- [ ] **R3**: Preview handlers emit application graph SQL for create, update,
  and delete over `graph_nodes`, `graph_node_revisions`, and `graph_edges`.
- [ ] **R4**: Preview handlers return `executes:false` and name the remaining
  live execution, response projection, cache invalidation, and audit side-effect
  gap.
- [ ] **R5**: `scripts/runtime_surface_report.py` counts method-specific
  `kh-route` and raw `43004` route rows as kernel-first capable without reading
  comments or collapsing duplicate wildcard paths.

## Research Inputs

- `2026-06-08` - User direction: expose graph-node functions so mutable surfaces
  can move toward Form native without waiting at the Python boundary.
- `form/form-stdlib/kernel-http.fk` - `kh-route` method/pattern/header/pressure
  route shape.
- `form/form-kernel-rust/src/main.rs` - kernel-router method, wildcard, header,
  body, and fanout behavior.
- `form/form-stdlib/application-graph-node-port.fk` - application graph SQL
  carrier semantics.
- `api/app/services/spec_registry_service.py` - live spec node id convention:
  `spec-{spec_id}`.

## Files to Create/Modify

- `deploy/kernel-router/production-routes.fk` - method-specific preview routes
  and Form handlers.
- `scripts/runtime_surface_report.py` - method-specific route parsing.
- `api/tests/test_native_mutation_route_bindings.py` - route binding proof.
- `api/tests/test_runtime_surface_native_routes.py` - method route parser proof.
- `docs/coherence-substrate/ideas-router.form` - high-level ideas route state.
- `docs/coherence-substrate/spec-registry-router.form` - high-level spec route
  state.
- `specs/method-specific-native-mutation-preview-bindings.md` - this contract.

## Acceptance Tests

- `api/tests/test_native_mutation_route_bindings.py::test_native_mutation_preview_routes_are_method_and_header_gated`
- `api/tests/test_native_mutation_route_bindings.py::test_native_mutation_preview_handlers_emit_application_graph_sql`
- `api/tests/test_native_mutation_route_bindings.py::test_native_mutation_preview_uses_live_spec_node_id_convention`
- `api/tests/test_native_mutation_route_bindings.py::test_idea_and_spec_forms_name_method_specific_preview_bindings`
- `api/tests/test_runtime_surface_native_routes.py::test_parser_reads_bindings_not_comments`
- Manual validation: run the kernel-router manifest and curl one preview request
  with `X-Form-Native-Preview` plus one mutation request without it.

## Verification

```bash
cd api && python3 -m pytest -q tests/test_native_mutation_route_bindings.py tests/test_runtime_surface_native_routes.py
python3 scripts/validate_spec_quality.py --file specs/method-specific-native-mutation-preview-bindings.md
cd form/form-kernel-rust && ./target/release/form-kernel-rust serve --host 127.0.0.1 --port 19215 --workers 1 --routes ../../deploy/kernel-router/production-routes.fk --stdlib ../form-stdlib --upstream http://127.0.0.1:9
curl -sS -i -X POST http://127.0.0.1:19215/api/spec-registry -H 'Content-Type: application/json' -H 'X-Form-Native-Preview: 1' --data '{"spec_id":"native-bind","title":"Native Bind"}'
curl -sS -i -X POST http://127.0.0.1:19215/api/spec-registry -H 'Content-Type: application/json' --data '{"spec_id":"native-bind","title":"Native Bind"}'
```

## Out of Scope

- Executing preview SQL against PostgreSQL.
- Returning the final `IdeaWithScore` or `SpecRegistryEntry` mutation response.
- Cache invalidation, parent/child repair, relation side effects, resonance
  re-attunement, or contributor-key `last_used_at` updates.
- Public front-door mutation flip for normal traffic.

## Gaps

- GAP-MSNMPB1 follow-up task: `native-graph-mutation-live-db-proof`. Execute the
  generated SQL against the application schema and prove revision rows plus edge
  cleanup.
- GAP-MSNMPB2 follow-up task: `native-mutation-response-projection`. Project
  mutation results into `IdeaWithScore` and `SpecRegistryEntry` without FastAPI.
- GAP-MSNMPB3 follow-up task: `native-mutation-side-effects`. Carry cache
  invalidation, parent/edge repair, resonance re-attunement, and contributor-key
  audit updates natively before public mutation traffic moves.

## Risks and Assumptions

- The preview SQL assumes request bodies are valid JSON objects. Invalid bodies
  are still preview strings here; live execution proof must add structured
  validation before any public flip.
- Wildcard route rows need pressure budget `25` because wildcard path matching
  contributes path pressure even when the method and header match.
- Header-gated preview routes are a capability signal, not a live mutation
  contract. Ordinary public mutation behavior remains FastAPI.
