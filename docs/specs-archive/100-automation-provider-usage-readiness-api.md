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


## Research Inputs

- Codebase analysis of existing implementation
- Related specs: none

## Task Card

```yaml
goal: Implement the functionality described in this spec
files_allowed:
  - # TBD — determine from implementation
done_when:
  - Usage endpoint returns normalized provider metrics and remaining capacity overview.
  - Snapshots endpoint returns persisted usage history with bounded `limit`.
  - Alerts endpoint returns threshold-based provider alerts.
  - Subscription estimator returns current-vs-next tier cost and ROI estimates.
  - Readiness endpoint reports required provider blocking status and supports explicit required-provider overrides.
commands:
  - - `cd api && pytest -v tests/test_automation_usage_api.py`
constraints:
  - changes scoped to listed files only
  - no schema migrations without explicit approval
```

## Files

- `api/app/routers/automation_usage.py`
- `api/app/services/automation_usage_service.py`
- `config/canonical_routes.json`
- `api/tests/test_automation_usage_api.py`

## Failure and Retry Behavior

- **Task failure**: Log error, mark task failed, advance to next item or pause for human review.
- **Retry logic**: Failed tasks retry up to 3 times with exponential backoff (initial 2s, max 60s).
- **Partial completion**: State persisted after each phase; resume from last checkpoint on restart.
- **External dependency down**: Pause pipeline, alert operator, resume when dependency recovers.
- **Timeout**: Individual task phases timeout after 300s; safe to retry from last phase.

## Risks and Known Gaps

- **No auth gate**: Endpoints unprotected until C1 auth middleware applied.
- **No rate limiting**: Subject to abuse until M1 rate limiter active.
- **Single-node only**: No distributed locking; concurrent access may race.
- **Follow-up**: Add distributed locking for multi-worker pipelines.

## Acceptance Tests

See `api/tests/test_automation_provider_usage_readiness_api.py` for test cases covering this spec's requirements.


## Verification

- `cd api && pytest -v tests/test_automation_usage_api.py`
- `cd api && pytest -v tests/test_inventory_api.py -k endpoint_traceability`

## Idea Traceability
- `idea_id`: `coherence-network-overall`
- Rationale: umbrella roadmap linkage for Coherence Network work.

## Known Gaps and Follow-up Tasks

- No known gaps at time of writing.
- Follow-up: review after initial implementation for completeness.
