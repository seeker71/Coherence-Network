# Spec: Standing Questions, ROI Fields, and Next-Task Generation

## Purpose

Enforce continuous ROI-driven discovery by ensuring each idea always has a standing improvement/measurement question, exposing ROI on questions and answers, and generating the next highest-ROI task from answered questions.

## Requirements

- [ ] Every idea includes the standing improvement/measurement question.
- [ ] Inventory exposes `question_roi` and `answer_roi` for question rows.
- [ ] API can suggest and optionally create the next highest-ROI task from answered questions.

## API Contract

### `POST /api/inventory/questions/next-highest-roi-task?create_task=false`

Returns the highest-ROI answered question follow-up and task direction.

### `POST /api/inventory/questions/next-highest-roi-task?create_task=true`

Creates a task in the agent task store and returns task metadata.

## Validation Contract

- `api/tests/test_inventory_api.py::test_standing_question_exists_for_every_idea`
- `api/tests/test_inventory_api.py::test_next_highest_roi_task_generation_from_answered_questions`
- `api/tests/test_inventory_api.py::test_system_lineage_inventory_includes_core_sections` (ROI fields present)

## Downstream Consumers

- **Spec 115** ([115-grounded-cost-value-measurement.md](115-grounded-cost-value-measurement.md)) — Reads `idea_service.get_idea()` to collect `actual_value` and `potential_value` for computing value realization percentage (`actual_value / potential_value`). This feeds into the grounded value formula as an economic signal. As specs 112-115 record real measurements, the ROI fields exposed by this spec become increasingly grounded rather than estimated.

## Files

- `api/app/services/idea_service.py`
- `api/app/services/inventory_service.py`
- `api/app/routers/inventory.py`
- `api/tests/test_inventory_api.py`

## Verification

```bash
python3 -m pytest api/tests/test_ideas.py -x -v
```
