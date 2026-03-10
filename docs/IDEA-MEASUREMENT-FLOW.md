# Idea Measurement Flow

This document explains how a new idea should move from estimate-first planning to measured outcomes.

## 1) Estimate-first is allowed (and expected)

When an idea/spec is created, start with:
- `potential_value`
- `estimated_cost`
- `confidence`

These are planning inputs, not final truth. They are used to rank and prioritize work before measurement exists.

## 2) Where estimators live

- Task output attribution parser:
  - `api/app/services/agent_execution_metrics.py`
  - `attribution_values_from_output(...)` parses `actual_value`, `estimated_value`, `estimated_cost`, `confidence`.

- Runtime/external cost estimator:
  - `api/app/services/agent_execution_service.py`
  - `_runtime_cost_usd(...)`, `_external_provider_cost_usd(...)`
  - Inputs can be tuned via `RUNTIME_COST_PER_SECOND`, `AGENT_EXTERNAL_INPUT_COST_PER_1K`, `AGENT_EXTERNAL_OUTPUT_COST_PER_1K`.

- ROI normalization + calibration:
  - `api/app/services/inventory_service.py`
  - `sync_roi_progress_tasks(...)`
  - `_normalize_roi_fields(...)` fills missing estimate floors.
  - `_calibrate_estimated_cost_toward_actual(...)` moves estimate toward observed reality using `calibration_alpha`.

- Commit cost estimator (separate contribution accounting surface):
  - `api/app/services/contribution_cost_service.py`

## 3) How measurement replaces estimates

Record measured values through API surfaces:

- Idea actuals:
  - `PATCH /api/ideas/{idea_id}`
  - fields: `actual_value`, `actual_cost`, `confidence`, `manifestation_status`

- Question measurement:
  - `POST /api/ideas/{idea_id}/questions/answer`
  - field: `measured_delta`

- Spec actuals:
  - `PATCH /api/spec-registry/{spec_id}`
  - fields include `actual_value`, `actual_cost`

Once actuals are present, cards/feeds move to measured-oriented state and ROI signals.

## 4) How the system guides next measurement work

- `POST /api/inventory/questions/next-highest-roi-task`:
  - picks follow-up work from answered questions using `answer_roi = measured_delta / estimated_cost`.

- `POST /api/inventory/roi/sync-progress`:
  - proposes or creates progress tasks across idea/spec/implementation categories.
  - optional normalization and calibration keep estimates from drifting too far from actuals.

## 5) How to improve the estimators safely

1. Keep formulas explicit and versioned (do not hide magic constants).
2. Add/adjust tests before changing formulas:
   - `api/tests/test_agent_execute_endpoint.py`
   - `api/tests/test_inventory_api.py`
3. Prefer calibration against observed outcomes over manual constant tweaks.
4. Preserve API patch contract for ideas/specs; internal services may evolve estimator internals.

## 6) Implementation note

Internal service updates may adjust idea estimate fields (`potential_value`, `estimated_cost`) during attribution/calibration, while public API patch remains intentionally limited to measured progress fields.
