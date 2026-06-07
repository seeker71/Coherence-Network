---
idea_id: idea-realization-engine
status: done
source:
  - file: docs/coherence-substrate/ideas-router.form
    symbols: [idea_route_shape, idea_route_recipe_shape, ideas_router_structure, browse_ideas_recipe, sense_governance_recipe, choose_next_idea_recipe, mutate_idea_recipe, question_answer_recipe, link_idea_recipe, translate_idea_recipe, invest_in_idea_recipe, rollup_super_idea_recipe, inspect_idea_recipe]
  - file: api/app/routers/ideas.py
    symbols: [list_ideas, create_idea, update_idea, get_idea]
  - file: api/tests/test_ideas_router_form.py
    symbols: [test_ideas_router_form_declares_route_shapes_and_whole_structure, test_ideas_router_form_names_shifted_recipe_families, test_ideas_router_form_keeps_python_as_carrier_with_gap_named, test_ideas_router_form_describes_live_router_carrier]
requirements:
  - "The ideas router has a high-level Form artifact naming its route shape, route recipe shape, whole structure, and shifted recipe families."
  - "The Form artifact names api/app/routers/ideas.py as the FastAPI carrier while preserving existing HTTP behavior."
  - "The proof test verifies the Form structure, the shifted recipes, the Python-carrier boundary, and the router-to-Form link."
done_when:
  - 'file_exists("docs/coherence-substrate/ideas-router.form")'
  - 'file_contains("docs/coherence-substrate/ideas-router.form", "defn ideas_router_structure()")'
  - 'file_contains("docs/coherence-substrate/ideas-router.form", "route_source: \"api/app/routers/ideas.py\"")'
  - 'pytest_passes("api/tests/test_ideas_router_form.py")'
test: "cd api && python -m pytest -q tests/test_ideas_router_form.py"
constraints:
  - "Do not change existing ideas endpoint paths, response schemas, or service behavior."
  - "Do not add a parallel Python business-logic service for this slice."
  - "Keep the remaining native-front-door route dispatch gap explicit."
---

# Spec: Ideas Router as Form Expression

## Purpose

`api/app/routers/ideas.py` had the behavior of a living portfolio surface but only the Python carrier named the shape. This spec gives the router a high-level Form expression so contributors can read the ideas surface as route recipes before dropping into FastAPI implementation details. The result keeps the existing API stable while making the north star visible: ideas move from promise to real contribution through evidence, relation, value flow, and closure.

## Requirements

- [ ] **R1**: `docs/coherence-substrate/ideas-router.form` declares `idea_route_shape`, `idea_route_recipe_shape`, `ideas_router_structure()`, and `ideas_router_reading()`.
- [ ] **R2**: The Form artifact names the shifted route recipe families: browse, sense, choose, mutate, question-answer, link, translate, invest, rollup, and inspect.
- [ ] **R3**: The Form artifact names `api/app/routers/ideas.py` as the route carrier and tests confirm the live router still carries the described route surface.
- [ ] **R4**: Tests prove the Form structure, recipe families, Python-carrier boundary, named native dispatch gap, and router-to-Form link.

## Research Inputs

- `2026-06-08` - User direction: rewrite `ideas.py` into a high-level Form/BML expression and show the shifted structure and recipes.
- `docs/shared/agent-start-packet.md` - current Form-first guidance: grammar and recipe before carrier.
- `docs/coherence-substrate/active-recipe-tracing.form` - established pattern for putting a behavioral shape in `.form` with Python tests as proof.
- `api/app/routers/ideas.py` - live FastAPI carrier for the ideas portfolio routes.

## Files to Create/Modify

- `docs/coherence-substrate/ideas-router.form` - high-level route expression and shifted recipe families.
- `api/tests/test_ideas_router_form.py` - focused proof for the Form expression and carrier link.
- `specs/ideas-router-form-expression.md` - this contract.

## Acceptance Tests

- `api/tests/test_ideas_router_form.py::test_ideas_router_form_declares_route_shapes_and_whole_structure`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_names_shifted_recipe_families`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_keeps_python_as_carrier_with_gap_named`
- `api/tests/test_ideas_router_form.py::test_ideas_router_form_describes_live_router_carrier`

## Verification

```bash
cd api && python -m pytest -q tests/test_ideas_router_form.py
python3 scripts/validate_spec_quality.py --file specs/ideas-router-form-expression.md
```

## Out of Scope

- Changing API response schemas or endpoint paths.
- Moving service-layer persistence or scoring logic to a new Python module.
- Native kernel front-door dispatch for the ideas routes.

## Gaps

- GAP-I1: front-door dispatch still enters through FastAPI. The Form route recipe gives native kernel route dispatch a source shape to consume later, but this task does not lift the ideas routes to the kernel front door.

## Risks and Assumptions

- The Form artifact is structural proof, not a new runtime dispatcher.
- A later native route lift can consume this route recipe once the front-door kernel carrier is ready.
