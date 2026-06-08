---
idea_id: idea-realization-engine
status: done
source:
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [idea_route_shape, idea_route_recipe_shape, ideas_router_structure, browse_ideas_recipe, sense_governance_recipe, choose_next_idea_recipe, mutate_idea_recipe, question_answer_recipe, link_idea_recipe, translate_idea_recipe, invest_in_idea_recipe, rollup_super_idea_recipe, inspect_idea_recipe]
  - file: form/form-stdlib/graph-node-port.fk
    symbols: [gn-create-node, gn-replace-node, gn-delete-node]
  - file: form/form-stdlib/auth-port.fk
    symbols: [auth-require-api-key]
  - file: form/form-stdlib/tests/auth-port-band.fk
    symbols: []
  - file: form/form-stdlib/application-graph-node-port.fk
    symbols: [agn-create-node, agn-update-node, agn-delete-node]
  - file: form/form-stdlib/tests/application-graph-node-port-band.fk
    symbols: []
  - file: form/form-stdlib/tests/graph-node-mutation-carrier-band.fk
    symbols: []
  - file: deploy/kernel-router/production-routes.fk
    symbols: []
  - file: Dockerfile.kernel-router
    symbols: []
  - file: scripts/runtime_surface_report.py
    symbols: [kernel_first_capable_routes]
  - file: api/app/routers/ideas.py
    symbols: [list_ideas, create_idea, update_idea, get_idea]
  - file: api/tests/test_ideas_router_form.py
    symbols: [test_ideas_router_form_declares_route_shapes_and_whole_structure, test_ideas_router_form_names_shifted_recipe_families, test_ideas_router_form_keeps_python_as_carrier_with_gap_named, test_ideas_router_form_describes_live_router_carrier, test_ideas_router_form_has_native_structure_route, test_ideas_router_form_has_native_source_index_route, test_ideas_router_form_has_native_source_portfolio_route, test_ideas_router_form_has_native_graph_projection_route, test_ideas_router_form_names_native_mutation_carrier]
  - file: api/tests/test_native_mutation_route_bindings.py
    symbols: [test_native_mutation_preview_routes_are_method_and_header_gated, test_native_mutation_preview_handlers_emit_application_graph_sql]
  - file: api/tests/test_runtime_surface_native_routes.py
    symbols: [test_real_manifest_native_routes_are_served_zero_and_include_ideas_structure]
requirements:
  - "The ideas router has a high-level Form artifact naming its route shape, route recipe shape, whole structure, and shifted recipe families."
  - "The Form artifact names api/app/routers/ideas.py as the FastAPI carrier while preserving existing HTTP behavior."
  - "The kernel-router production manifest exposes native /api/ideas/router-structure, /api/ideas/source-index, /api/ideas/source-portfolio, and /api/ideas/graph-projection routes for the Form-declared router structure, repo-backed idea source index, source-backed curated portfolio, and fixture-backed graph projection preview."
  - "The Form artifact names the native graph-node mutation carrier for create, replace, and delete while keeping the public mutable front-door gap explicit."
  - "The Form artifact names the native auth decision carrier for API-key/contributor-key parity and the application graph table SQL carrier for graph_nodes/revisions/edge cleanup."
  - "The production manifest binds header-gated method-specific native SQL preview rows for POST/PATCH /api/ideas without changing default public behavior."
  - "The kernel-router image carries the ideas source directory so the source-index route is deployable when production routes are selected."
  - "The proof tests verify the Form structure, shifted recipes, Python-carrier boundary, native structure/source routes, and router-to-Form link."
done_when:
  - 'file_exists("docs/coherence-substrate/ideas-router.form")'
  - 'file_contains("docs/coherence-substrate/ideas-router.form", "defn ideas_router_structure()")'
  - 'file_contains("docs/coherence-substrate/ideas-router.form", "route_source: \"api/app/routers/ideas.py\"")'
  - 'file_contains("deploy/kernel-router/production-routes.fk", "(list \"/api/ideas/router-structure\"    route_ideas_router_structure)")'
  - 'file_contains("deploy/kernel-router/production-routes.fk", "(list \"/api/ideas/source-index\"        route_ideas_source_index)")'
  - 'file_contains("deploy/kernel-router/production-routes.fk", "(list \"/api/ideas/source-portfolio\"    route_ideas_source_portfolio)")'
  - 'file_contains("deploy/kernel-router/production-routes.fk", "(list \"/api/ideas/graph-projection\"    route_ideas_graph_projection)")'
  - 'file_contains("docs/coherence-substrate/ideas-router.form", "mutable service calls -> Form-native graph-node mutation carrier")'
  - 'pytest_passes("api/tests/test_ideas_router_form.py")'
test: "cd api && python3 -m pytest -q tests/test_ideas_router_form.py tests/test_runtime_surface_native_routes.py"
constraints:
  - "Do not change existing ideas endpoint paths, response schemas, or service behavior."
  - "Do not add a parallel Python business-logic service for this slice."
  - "Keep the remaining mutable ideas data-route native-front-door gap explicit."
---

# Spec: Ideas Router as Form Expression

## Purpose

`api/app/routers/ideas.py` had the behavior of a living portfolio surface but only the Python carrier named the shape. This spec gives the router a high-level Form expression so contributors can read the ideas surface as route recipes before dropping into FastAPI implementation details. The result keeps the existing API stable while making the north star visible: ideas move from promise to real contribution through evidence, relation, value flow, and closure.

## Requirements

- [ ] **R1**: `docs/coherence-substrate/ideas-router.form` declares `idea_route_shape`, `idea_route_recipe_shape`, `ideas_router_structure()`, and `ideas_router_reading()`.
- [ ] **R2**: The Form artifact names the shifted route recipe families: browse, sense, choose, mutate, question-answer, link, translate, invest, rollup, and inspect.
- [ ] **R3**: The Form artifact names `api/app/routers/ideas.py` as the route carrier and tests confirm the live router still carries the described route surface.
- [ ] **R4**: `deploy/kernel-router/production-routes.fk` binds `/api/ideas/router-structure` to a native Form handler that returns the router's high-level source-backed structure.
- [ ] **R5**: `deploy/kernel-router/production-routes.fk` binds `/api/ideas/source-index` to a native Form handler that reads `ideas/INDEX.md` and returns source-backed idea counts.
- [ ] **R6**: `deploy/kernel-router/production-routes.fk` binds `/api/ideas/source-portfolio` to a native Form handler that reads `ideas/INDEX.md` and returns the curated super-idea portfolio response shape.
- [ ] **R7**: `deploy/kernel-router/production-routes.fk` binds `/api/ideas/graph-projection` to a native Form handler that returns a fixture-backed `IdeaPortfolioResponse`-shaped body.
- [ ] **R8**: The Form artifact names the native graph-node mutation carrier for create, replace, and delete while keeping the live-front-door auth/Postgres boundary explicit.
- [ ] **R9**: The production manifest binds header-gated method-specific native SQL preview rows for `POST /api/ideas` and `PATCH /api/ideas/*`.
- [ ] **R10**: Tests prove the Form structure, recipe families, Python-carrier boundary, native structure/source/projection routes, native mutation carrier, native preview binding, named remaining live-front-door gap, and router-to-Form link.

## Research Inputs

- `2026-06-08` - User direction: rewrite `ideas.py` into a high-level Form/BML expression and show the shifted structure and recipes.
- `docs/shared/agent-start-packet.md` - current Form-first guidance: grammar and recipe before carrier.
- `docs/coherence-substrate/active-recipe-tracing.form` - established pattern for putting a behavioral shape in `.form` with Python tests as proof.
- `api/app/routers/ideas.py` - live FastAPI carrier for the ideas portfolio routes.
- `deploy/kernel-router/production-routes.fk` - native kernel-router manifest for whole-request Form routes.
- `ideas/INDEX.md` - canonical super-idea source index.
- `form/form-stdlib/graph-node-port.fk` - native graph-node read and mutation carrier.
- `form/form-stdlib/tests/graph-node-mutation-carrier-band.fk` - memory/file proof for create, replace, and delete.
- `specs/method-specific-native-mutation-preview-bindings.md` - method-specific preview route binding contract.

## Files to Create/Modify

- `docs/coherence-substrate/ideas-router.form` - high-level route expression and shifted recipe families.
- `form/form-stdlib/graph-node-port.fk` - native graph-node mutation carrier functions.
- `form/form-stdlib/tests/graph-node-mutation-carrier-band.fk` - native mutation proof band.
- `deploy/kernel-router/production-routes.fk` - native structure route for the high-level ideas router reading.
- `Dockerfile.kernel-router` - carries the production route manifest and idea source files into the kernel-router image.
- `scripts/runtime_surface_report.py` - honest capable-route wording for native structure routes without CPython twins.
- `api/tests/test_ideas_router_form.py` - focused proof for the Form expression and carrier link.
- `api/tests/test_runtime_surface_native_routes.py` - runtime-surface proof that the ideas structure route is kernel-first capable.
- `specs/ideas-router-form-expression.md` - this contract.

## Acceptance Tests

- `api/tests/test_ideas_router_form.py::test_ideas_router_form_declares_route_shapes_and_whole_structure`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_names_shifted_recipe_families`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_keeps_python_as_carrier_with_gap_named`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_describes_live_router_carrier`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_has_native_structure_route`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_has_native_source_index_route`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_has_native_source_portfolio_route`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_has_native_graph_projection_route`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_names_native_mutation_carrier`
- `api/tests/test_native_mutation_route_bindings.py::test_native_mutation_preview_routes_are_method_and_header_gated`
- `api/tests/test_runtime_surface_native_routes.py::test_real_manifest_native_routes_are_served_zero_and_include_ideas_structure`

## Verification

```bash
cd api && python3 -m pytest -q tests/test_ideas_router_form.py tests/test_native_mutation_route_bindings.py tests/test_runtime_surface_native_routes.py
python3 scripts/validate_spec_quality.py --file specs/ideas-router-form-expression.md
```

## Out of Scope

- Changing API response schemas or endpoint paths.
- Moving service-layer persistence or scoring logic to a new Python module.
- Flipping ordinary public mutable, DB-backed ideas traffic to native execution before live DB execution, response projection, cache invalidation, and side-effect proof.

## Gaps

- GAP-I1 follow-up task: `ideas-native-mutation-live-db-proof`. `/api/ideas/router-structure`, `/api/ideas/source-index`, `/api/ideas/source-portfolio`, and `/api/ideas/graph-projection` are kernel-first capable. `graph-node-port.fk` exposes create/replace/delete over the storage port, `auth-port.fk` preserves API-key/contributor-key decision parity, `application-graph-node-port.fk` emits direct `graph_nodes` / `graph_node_revisions` / `graph_edges` SQL, and `POST/PATCH /api/ideas` now have `X-Form-Native-Preview` header-gated native SQL preview rows. Public mutable DB-backed portfolio routes still enter through FastAPI by default until live DB execution, response projection, cache invalidation, parent/edge side effects, and contributor-key audit side effects are proven.
- GAP-I2 follow-up task: `ideas-live-graph-storage-carrier`. Connect `/api/ideas/graph-projection` to a live application graph storage carrier on top of `form/form-stdlib/ideas-graph-projection.fk`.

## Risks and Assumptions

- The Form artifact plus native structure/source routes is not a DB-backed replacement for the full ideas router.
- A later native route lift can consume this route recipe now that the graph-node read carrier, mutation carrier, auth carrier, application-table SQL carrier, and idea schema projection shapes exist; manifest binding and live DB execution proof remain the next boundary.
