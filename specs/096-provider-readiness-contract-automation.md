# Spec: Provider Readiness Contract Automation

## Purpose

Provider integrations currently drift between configured, partially configured, and operational states without a single contract that enforces real execution proof and usage evidence. This spec defines a provider readiness contract so the system can safely route work, detect costly provider failures early, and keep machine and human visibility aligned on what is actually usable.

## Requirements

- [ ] Define required readiness checks per active provider: configuration present, auth probe succeeds, safe execution probe succeeds, and usage telemetry is written.
- [ ] Expose provider readiness and failure history through API and web with machine-queryable status, timestamps, error class, and last successful execution evidence.
- [ ] Enforce routing policy: use cheap executor by default and escalate only when retry/failure thresholds are reached, with decision evidence persisted.

## API Contract (if applicable)

### `POST /api/automation/usage/provider-validation/run`

**Request**
- Optional `providers`: array of provider ids
- Optional `mode`: `quick` | `full` (default `full`)

**Response 200**
```json
{
  "status": "ok",
  "run_id": "prv_2026_02_17T00_00_00Z",
  "providers": [
    {
      "provider": "github",
      "configured": true,
      "auth_probe_passed": true,
      "execution_probe_passed": true,
      "usage_event_written": true,
      "last_error_class": null
    }
  ]
}
```

### `GET /api/automation/usage/provider-validation`

**Response 200**
```json
{
  "required_providers": ["github", "railway", "openai_codex", "claude"],
  "summary": {
    "ready": 4,
    "not_ready": 0
  },
  "providers": [
    {
      "provider": "railway",
      "ready": true,
      "last_validated_at": "2026-02-17T00:00:00Z",
      "last_successful_execution_at": "2026-02-17T00:00:00Z",
      "last_failure_at": null,
      "failure_rate_24h": 0.0
    }
  ]
}
```

## Data Model (if applicable)

```yaml
ProviderValidationRun:
  properties:
    run_id: { type: string }
    started_at: { type: string, format: date-time }
    completed_at: { type: string, format: date-time }
    mode: { type: string }
ProviderValidationResult:
  properties:
    provider: { type: string }
    configured: { type: boolean }
    auth_probe_passed: { type: boolean }
    execution_probe_passed: { type: boolean }
    usage_event_written: { type: boolean }
    ready: { type: boolean }
    last_error_class: { type: string, nullable: true }
    retry_count_24h: { type: integer }
    escalation_count_24h: { type: integer }
```

## Files to Create/Modify

- `specs/096-provider-readiness-contract-automation.md` - contract definition and acceptance gates
- `api/app/services/provider_validation_service.py` - normalized readiness evaluation and policy decision logging
- `api/app/services/automation_usage_service.py` - persist provider probe outcomes and retry/escalation evidence
- `api/app/routers/automation_usage.py` - readiness endpoints and result schemas
- `web/app/providers/page.tsx` - human-readable readiness, failures, and escalation traces
- `.github/workflows/provider-readiness-contract.yml` - scheduled + push enforcement and evidence artifact upload

## Acceptance Tests

- `api/tests/test_automation_usage_api.py::test_provider_validation_run_records_execution_evidence`
- `api/tests/test_automation_usage_api.py::test_provider_validation_lists_required_provider_readiness`
- `api/tests/test_automation_usage_api.py::test_provider_policy_uses_cheap_executor_before_escalation`
- Manual validation: open `/providers` on public web and confirm provider readiness and failure traces match API output.

## Verification

```bash
cd api && pytest -q tests/test_automation_usage_api.py -k "provider_validation or cheap_executor"
cd api && python scripts/validate_spec_quality.py --file specs/096-provider-readiness-contract-automation.md
curl -fsS -X POST https://coherence-network-production.up.railway.app/api/automation/usage/provider-validation/run | jq .
curl -fsS https://coherence-network-production.up.railway.app/api/automation/usage/provider-validation | jq .
```

## Out of Scope

- New provider onboarding flows for providers not currently in active use.
- Subscription billing ingestion beyond currently available provider usage records.

## Risks and Assumptions

- Risk: live probes can fail due to transient external outages and create noise; mitigation is retry windows with explicit failure class tracking.
- Assumption: each active provider exposes at least one safe, low-cost operation suitable for automated execution probes.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_provider_probe_cost_calibration_001` to tune probe frequency against observed value and provider limits.
- Follow-up task: `task_provider_subscription_usage_ingest_002` to replace estimated usage with provider-native metering feeds where available.

## Decision Gates (if any)

- Approve required provider list and per-provider safe probe operation before hard-fail enforcement in CI.
