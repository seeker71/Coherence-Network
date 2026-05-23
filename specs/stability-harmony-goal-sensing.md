---
id: stability-harmony-goal-sensing
idea_id: knowledge-and-resonance
status: active
source:
  - file: api/app/routers/energy_sensing.py
    symbols: [energy_recommendations]
  - file: api/app/services/energy_goal_recipe_service.py
    symbols: [goal_seeks_stability_or_harmony, stability_harmony_recipe, stability_harmony_invitation]
  - file: api/tests/test_flow_vitality.py
    symbols: [test_energy_invitations_and_fallback_witness_flow]
requirements:
  - "GET /api/energy/recommend accepts an optional current_goal query parameter without changing the default response shape"
  - "When current_goal asks for stability, harmony, coherence, calm, or steadiness, the sensing organ returns a stability-harmony recipe in form language"
  - "The goal-aware invitation stays warm and actionable, avoids warning language, and links back to the recipe id"
done_when:
  - "GET /api/energy/recommend?current_goal=create%20stability%20and%20harmony returns goal_recipe.id=stability-harmony"
  - "The recipe form includes breathe(longer_exhale) and source concepts from the Geometry of Stability ingest"
  - "api/tests/test_flow_vitality.py::test_energy_invitations_and_fallback_witness_flow passes"
  - 'file_exists("api/app/routers/energy_sensing.py")'
  - 'symbol_in_file("api/app/routers/energy_sensing.py", "energy_recommendations")'
  - 'file_exists("api/app/services/energy_goal_recipe_service.py")'
  - 'symbol_in_file("api/app/services/energy_goal_recipe_service.py", "goal_seeks_stability_or_harmony")'
  - 'symbol_in_file("api/app/services/energy_goal_recipe_service.py", "stability_harmony_recipe")'
  - 'symbol_in_file("api/app/services/energy_goal_recipe_service.py", "stability_harmony_invitation")'
  - 'file_exists("api/tests/test_flow_vitality.py")'
  - 'symbol_in_file("api/tests/test_flow_vitality.py", "test_energy_invitations_and_fallback_witness_flow")'
  - 'pytest_passes("api/tests/test_flow_vitality.py::test_energy_invitations_and_fallback_witness_flow")'
test: "cd api && python -m pytest -q tests/test_flow_vitality.py::test_energy_invitations_and_fallback_witness_flow"
constraints:
  - "Default recommendations remain available when current_goal is omitted"
  - "Do not make clinical or guaranteed-regulation claims"
  - "Keep private relational context out of the API response"
---

# Spec: Stability Harmony Goal Sensing

## Purpose

The sensing organ already notices energy, harmony, and dissonance. This spec lets the organ respond when the current goal itself asks for stability or harmony. Instead of returning only general invitations, the route can translate that goal into a form-language recipe: sense the field, notice the pattern, pause, breathe, ask what structure is reacting, choose a response, and transmit steadiness.

This carries the Geometry of Stability ingest into runtime without exposing private context. The pattern becomes the recipe, and the recipe remains a practical invitation rather than a promise of control.

## Requirements

- [ ] **R1**: `GET /api/energy/recommend` accepts optional `current_goal` and preserves existing behavior when it is omitted.
- [ ] **R2**: Goals containing stability, harmony, coherence, calm, regulation, or steadiness return `goal_recipe.id == "stability-harmony"`.
- [ ] **R3**: The recipe contains a `form` string in form language, ordered `steps`, a `sensing` summary from computed harmonies, and `source_concepts` from the Geometry of Stability ingest.
- [ ] **R4**: The first invitation for a matched goal has `signal_id == "stability_harmony_goal"` and points to the recipe with `recipe_id`.
- [ ] **R5**: Invitation language remains warm and actionable, with no `ERROR` or `WARNING` framing.

## Research Inputs

- `2026-05-21` - Geometry of Stability Loraine Jezak ingest — contributes relational scaffolding, spiral pivot coherence, field-stabilizing transmission, and expansion-not-ladder as runtime source concepts.
- `api/app/routers/energy_sensing.py` — existing sensing organ for internal, community, external, harmony, dissonance, and invitation surfaces.

## API Contract

### `GET /api/energy/recommend?current_goal=create%20stability%20and%20harmony`

**Response 200**
```json
{
  "current_goal": "create stability and harmony",
  "goal_recipe": {
    "id": "stability-harmony",
    "goal_match": "stability_harmony",
    "form": "sense(field) |> notice(pattern) |> pause() |> breathe(longer_exhale) |> ask('what structure is reacting?') |> choose(response_without_control) |> transmit(steadiness)",
    "source_concepts": [
      "concept:relational-scaffolding",
      "concept:spiral-pivot-coherence",
      "concept:field-stabilizing-transmission",
      "concept:expansion-not-ladder"
    ],
    "steps": [],
    "sensing": {
      "overall_energy": 0.5,
      "overall_vitality": "resting",
      "dissonance_count": 0,
      "focus_pair": "whole field"
    }
  },
  "invitations": [
    {
      "scale": "goal",
      "signal_id": "stability_harmony_goal",
      "recipe_id": "stability-harmony"
    }
  ]
}
```

## Files to Create/Modify

- `api/app/routers/energy_sensing.py` — goal-aware recipe and invitation helpers.
- `api/app/services/energy_goal_recipe_service.py` — stability/harmony goal matching and recipe composition.
- `api/tests/test_flow_vitality.py` — regression coverage for stability/harmony goal sensing.
- `specs/stability-harmony-goal-sensing.md` — this contract.

## Acceptance Tests

- `api/tests/test_flow_vitality.py::test_energy_invitations_and_fallback_witness_flow`

## Verification

```bash
cd api && python -m pytest -q tests/test_flow_vitality.py::test_energy_invitations_and_fallback_witness_flow
```

## Out of Scope

- New persistence for goal recipes.
- UI controls for setting the current goal.
- Clinical or therapeutic claims about regulation.

## Risks and Assumptions

- The keyword trigger is intentionally simple. If goal routing becomes broader, it should move into a dedicated intent classifier with tests.
- The recipe is an invitation surface; it does not guarantee a particular state change.

## Known Gaps

- Follow-up task: add a persistent current-goal store when a UI or agent loop needs goal continuity across requests.
- Follow-up task: replace the keyword trigger with a dedicated intent classifier if goal routing expands beyond the stability/harmony family.
