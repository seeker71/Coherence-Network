---
idea_id: idea-realization-engine
status: done
source:
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [idea_route_shape, idea_route_recipe_shape, ideas_router_structure, browse_ideas_recipe, sense_governance_recipe, choose_next_idea_recipe, mutate_idea_recipe, question_answer_recipe, link_idea_recipe, translate_idea_recipe, invest_in_idea_recipe, rollup_super_idea_recipe, inspect_idea_recipe]
  - file: deploy/kernel-router/production-routes.fk
    symbols: []
  - file: Dockerfile.kernel-router
    symbols: []
  - file: scripts/runtime_surface_report.py
    symbols: [kernel_first_capable_routes]
  - file: api/app/routers/ideas.py
    symbols: [list_ideas, create_idea, update_idea, get_idea]
  - file: api/tests/test_ideas_router_form.py
    symbols: [test_ideas_router_form_declares_route_shapes_and_whole_structure, test_ideas_router_form_names_shifted_recipe_families, test_ideas_router_form_keeps_python_as_carrier_with_gap_named, test_ideas_router_form_describes_live_router_carrier, test_ideas_router_form_has_native_structure_route, test_ideas_router_form_has_native_source_index_route]
  - file: api/tests/test_runtime_surface_native_routes.py
    symbols: [test_real_manifest_native_routes_are_served_zero_and_include_ideas_structure]
requirements:
  - "The ideas router has a high-level Form artifact naming its route shape, route recipe shape, whole structure, and shifted recipe families."
  - "The Form artifact names api/app/routers/ideas.py as the FastAPI carrier while preserving existing HTTP behavior."
  - "The kernel-router production manifest exposes native /api/ideas/router-structure and /api/ideas/source-index routes for the Form-declared router structure and repo-backed idea source index."
  - "The kernel-router image carries the ideas source directory so the source-index route is deployable when production routes are selected."
  - "The proof tests verify the Form structure, shifted recipes, Python-carrier boundary, native structure/source routes, and router-to-Form link."
done_when:
  - 'file_exists("docs/coherence-substrate/ideas-router.form")'
  - 'file_contains("docs/coherence-substrate/ideas-router.form", "defn ideas_router_structure()")'
  - 'file_contains("docs/coherence-substrate/ideas-router.form", "route_source: \"api/app/routers/ideas.py\"")'
  - 'file_contains("deploy/kernel-router/production-routes.fk", "(list \"/api/ideas/router-structure\"    route_ideas_router_structure)")'
  - 'file_contains("deploy/kernel-router/production-routes.fk", "(list \"/api/ideas/source-index\"        route_ideas_source_index)")'
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
- [ ] **R6**: Tests prove the Form structure, recipe families, Python-carrier boundary, native structure/source routes, named remaining DB data-route gap, and router-to-Form link.

## Research Inputs

- `2026-06-08` - User direction: rewrite `ideas.py` into a high-level Form/BML expression and show the shifted structure and recipes.
- `docs/shared/agent-start-packet.md` - current Form-first guidance: grammar and recipe before carrier.
- `docs/coherence-substrate/active-recipe-tracing.form` - established pattern for putting a behavioral shape in `.form` with Python tests as proof.
- `api/app/routers/ideas.py` - live FastAPI carrier for the ideas portfolio routes.
- `deploy/kernel-router/production-routes.fk` - native kernel-router manifest for whole-request Form routes.
- `ideas/INDEX.md` - canonical super-idea source index.

## Files to Create/Modify

- `docs/coherence-substrate/ideas-router.form` - high-level route expression and shifted recipe families.
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
- `api/tests/test_runtime_surface_native_routes.py::test_real_manifest_native_routes_are_served_zero_and_include_ideas_structure`

## Verification

```bash
cd api && python3 -m pytest -q tests/test_ideas_router_form.py tests/test_runtime_surface_native_routes.py
python3 scripts/validate_spec_quality.py --file specs/ideas-router-form-expression.md
```

## Out of Scope

- Changing API response schemas or endpoint paths.
- Moving service-layer persistence or scoring logic to a new Python module.
- Moving mutable, DB-backed ideas data routes to native dispatch.

## Gaps

- GAP-I1: `/api/ideas/router-structure` and `/api/ideas/source-index` are kernel-first capable in the production route manifest. Mutable DB-backed portfolio routes still enter through FastAPI until the proven `ideas-graph-projection.fk` read shape is bound into the route manifest and a live storage carrier.
- Follow-up: lift one graph-node-backed ideas read route on top of `form/form-stdlib/ideas-graph-projection.fk`.

## Risks and Assumptions

- The Form artifact plus native structure/source routes is not a DB-backed replacement for the full ideas router.
- A later native route lift can consume this route recipe now that the graph-node read carrier and idea schema projection shapes exist; manifest binding and live storage remain the next boundary.
