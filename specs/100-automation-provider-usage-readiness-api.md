# Spec 100 - Automation Provider Usage and Readiness API

## Goal

Track automation provider usage and expose readiness/upgrade guidance so pipeline operations can identify blocking provider gaps early.

## Scope

- `GET /api/automation/usage`
- `GET /api/automation/usage/snapshots`
- `GET /api/automation/usage/alerts`
- `GET /api/automation/usage/subscription-estimator`
- `GET /api/automation/usage/readiness`

## Requirements

- [x] Usage endpoint returns normalized provider metrics and remaining capacity overview.
- [x] Snapshots endpoint returns persisted usage history with bounded `limit`.
- [x] Alerts endpoint returns threshold-based provider alerts.
- [x] Subscription estimator returns current-vs-next tier cost and ROI estimates.
- [x] Readiness endpoint reports required provider blocking status and supports explicit required-provider overrides.
- [x] Endpoints are registered in canonical routes and trace back to this spec.

## Files

- `api/app/routers/automation_usage.py`
- `api/app/services/automation_usage_service.py`
- `config/canonical_routes.json`
- `api/tests/test_automation_usage_api.py`

## Verification

- `cd api && pytest -v tests/test_automation_usage_api.py`
- `cd api && pytest -v tests/test_inventory_api.py -k endpoint_traceability`

## Idea Traceability
- `idea_id`: `coherence-network-overall`
- Rationale: umbrella roadmap linkage for Coherence Network work.
