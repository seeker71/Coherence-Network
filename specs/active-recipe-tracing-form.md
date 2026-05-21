---
id: active-recipe-tracing-form
idea_id: knowledge-and-resonance
status: active
source:
  - file: docs/coherence-substrate/active-recipe-tracing.form
    symbols: [recipe_state_shape, recipe_cell_shape, recipe_choice_shape, available_recipes, active_recipes, keep_or_choose]
  - file: api/tests/test_active_recipe_tracing_form.py
    symbols: [test_active_recipe_trace_form_declares_state_library_and_choice, test_active_recipe_trace_form_library_can_keep_or_choose, test_active_recipe_trace_form_points_trace_persistence_to_existing_gap]
requirements:
  - "Active recipe tracing is expressed in docs/coherence-substrate/active-recipe-tracing.form, not as a Python endpoint or service"
  - "The Form file declares state, recipe library, active recipe, candidate selection, and keep-or-choose choice shapes"
  - "The Form file names the future trace-index query for hydrating active recipes from witness traces"
done_when:
  - "active-recipe-tracing.form contains recipe_state_shape, available_recipes(), active_recipes(state), and keep_or_choose(state)"
  - "The library includes stability-harmony, connection-density, attention-flow, and external-listening recipes"
  - "api/tests/test_active_recipe_tracing_form.py passes"
test: "cd api && python -m pytest -q tests/test_active_recipe_tracing_form.py"
constraints:
  - "Do not add an API endpoint or Python business-logic service for this slice"
  - "Keep trace persistence as a named Form gap until the witness trace index exists"
  - "Do not surface private relational context"
---

# Spec: Active Recipe Tracing in Form

## Purpose

The sensing organ needs to know which recipes are active, what recipes are available, and whether the current active recipe still fits the desired state. That movement belongs at substrate altitude first. Form can name the state, library, active set, and choice relation without prematurely binding it to a Python API.

This spec adds the active-recipe tracing recipe as a `.form` artifact. Python only verifies that the Form body carries the required definitions; it does not become the place where the recipe logic lives.

## Requirements

- [ ] **R1**: `docs/coherence-substrate/active-recipe-tracing.form` declares `recipe_state_shape`, `recipe_cell_shape`, and `recipe_choice_shape`.
- [ ] **R2**: The Form file declares `available_recipes()`, `active_recipes(state)`, `candidate_recipes(state)`, `preferred_recipe(state)`, and `keep_or_choose(state)`.
- [ ] **R3**: The recipe library includes stability/harmony, connection density, attention flow, and external listening as available recipes.
- [ ] **R4**: The Form file can express both outcomes: `keep_active_recipe` when the active recipe matches `desired_state`, and `choose_recipe` when another library recipe fits better.
- [ ] **R5**: The Form file names the future trace query for hydrating active recipes from witness traces and points it to the existing trace-index gap.

## Research Inputs

- `2026-05-21` - User direction: active recipe tracing should use Form, not Python.
- `docs/coherence-substrate/traces-teach-the-recipe.form` - existing witness-trace and recipe-efficacy gap where active-recipe trace indexing belongs.
- `docs/coherence-substrate/recipe-branching-sense.form` - existing Form pattern for choosing a recipe branch from current sense.

## Files to Create/Modify

- `docs/coherence-substrate/active-recipe-tracing.form` - substrate-native recipe state, library, and choice relation.
- `api/tests/test_active_recipe_tracing_form.py` - proof that the Form artifact carries the required definitions.
- `specs/active-recipe-tracing-form.md` - this contract.

## Acceptance Tests

- `api/tests/test_active_recipe_tracing_form.py`

## Verification

```bash
cd api && python -m pytest -q tests/test_active_recipe_tracing_form.py
python3 scripts/validate_spec_quality.py --file specs/active-recipe-tracing-form.md
```

## Out of Scope

- Runtime API endpoint for active recipe choice.
- Persistent active-recipe store.
- Witness trace ORM/index implementation.

## Risks and Assumptions

- The Form artifact is structural until the trace-index gap closes.
- Python tests verify the artifact shape but do not execute the Form recipe.

## Known Gaps

- Follow-up task: implement `?active_recipe_traces @cell since current_breath` after the witness trace index from `traces-teach-the-recipe.form` GAP-W1 exists.
- Follow-up task: add a UI or agent-loop transport only after Form is the source of truth for recipe choice.
