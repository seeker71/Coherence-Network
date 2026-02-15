# Spec 070: ROI Estimator and Measurement Feedback Loop

## Goal
Expose ROI estimator and realized ROI measurements as first-class API assets so the system can continuously calibrate estimation against observed outcomes.

## Requirements
1. Provide API endpoint to inspect estimator formula, weights, observations, and calibration history.
2. Provide API endpoint to record realized measurements for ideas/questions with provenance.
3. Provide API endpoint to calibrate estimator weights from observed data.
4. Provide API endpoint to manually patch estimator weights.
5. Persist estimator state and measurement history to file-backed storage.
6. Expose estimator summary in system lineage inventory.
7. Keep existing ROI workflows backward compatible.

## API Contract
- `GET /api/inventory/roi/estimator`
- `POST /api/inventory/roi/estimator/measurements`
- `POST /api/inventory/roi/estimator/calibrate`
- `PATCH /api/inventory/roi/estimator/weights`

## Validation
- `api/tests/test_inventory_api.py::test_roi_estimator_endpoint_exposes_weights_and_observations`
- `api/tests/test_inventory_api.py::test_roi_measurement_and_calibration_updates_estimator`
- `api/tests/test_inventory_api.py::test_system_lineage_inventory_includes_core_sections`
