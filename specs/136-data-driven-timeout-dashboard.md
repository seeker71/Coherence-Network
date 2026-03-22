# Spec: Data-Driven Timeout Dashboard

## Purpose

Provider timeout tuning is currently difficult to reason about because operators must infer safe timeout values from scattered logs and telemetry. This spec defines a unified dashboard surface that shows per-provider p90 latency, a computed timeout recommendation, and recent timeout events so operators can make fast, evidence-based timeout decisions and reduce retry waste.

## Requirements

- [ ] Add a dashboard page or section that lists each provider with `p90`, `suggested_timeout_ms`, and recent timeout-event count.
- [ ] Use a deterministic recommendation formula so identical provider telemetry always yields the same suggested timeout.
- [ ] Show recent timeout events per provider (latest events with timestamp and short reason) to explain why recommendations changed.
- [ ] Support time-window filtering (for example `24h`, `7d`) with consistent behavior across API and UI.
- [ ] Expose clear empty/degraded states when telemetry is missing or stale.

## Research Inputs (Required)

- `2026-03-21` - [Spec 096: Provider Readiness Contract Automation](https://github.com/seeker71/Coherence-Network/blob/main/specs/096-provider-readiness-contract-automation.md) - establishes provider-readiness metrics patterns this dashboard should align with.
- `2026-03-21` - [Spec 100: Automation Provider Usage and Readiness API](https://github.com/seeker71/Coherence-Network/blob/main/specs/100-automation-provider-usage-readiness-api.md) - defines existing automation telemetry surfaces that should remain compatible.
- `2026-03-21` - [Spec 113: Provider Usage Coalescing + Timeout Resilience](https://github.com/seeker71/Coherence-Network/blob/main/specs/113-provider-usage-coalescing-timeout-resilience.md) - provides timeout-resilience context and provider-family normalization constraints.
- `2026-03-21` - [Spec 135: Provider Health Alerting from Last-5 Success Rate](https://github.com/seeker71/Coherence-Network/blob/main/specs/135-provider-health-alerting.md) - defines recent provider-health event patterns and friction integration relevant to timeout-event display.

## Task Card (Required)

```yaml
goal: Provide a data-driven timeout dashboard showing per-provider p90 latency, suggested timeout, and recent timeout events.
files_allowed:
  - specs/136-data-driven-timeout-dashboard.md
  - api/app/routers/automation_usage.py
  - api/app/services/automation_usage_service.py
  - api/app/models/automation_usage.py
  - api/tests/test_automation_usage_api.py
  - web/app/automation/usage/page.tsx
  - web/components/automation/timeout-dashboard.tsx
  - web/lib/api.ts
  - web/tests/automation-timeout-dashboard.test.tsx
done_when:
  - API returns per-provider timeout recommendations including p90, suggested timeout, and recent timeout events for a requested window.
  - Web dashboard renders provider rows, sortable suggested timeout values, and recent timeout events with stable empty/degraded states.
  - Validation and targeted tests pass for API and web timeout dashboard flows.
commands:
  - python3 scripts/validate_spec_quality.py --file specs/136-data-driven-timeout-dashboard.md
  - cd api && pytest -q tests/test_automation_usage_api.py -k "timeout_dashboard or timeout_recommendation"
  - cd web && npm run build
constraints:
  - no new provider-specific branching outside existing executor/automation service patterns
  - no new persistence backend; derive from existing telemetry and friction/runtime event sources
  - preserve existing automation usage/readiness endpoint behavior for current clients
```

## API Contract (if applicable)

### `GET /api/automation/timeout-dashboard`

**Request**
- `window`: string (query, optional; allowed values: `24h`, `7d`; default `24h`)
- `limit_events`: integer (query, optional; default `5`, min `1`, max `20`)

**Response 200**
```json
{
  "generated_at": "2026-03-21T12:00:00Z",
  "window": "24h",
  "providers": [
    {
      "provider": "openai",
      "p90_latency_ms": 4200,
      "suggested_timeout_ms": 6500,
      "recommendation_basis": "max(p90*1.5, floor_ms=3000)",
      "timeout_events": [
        {
          "at": "2026-03-21T11:42:03Z",
          "stage": "automation_usage_refresh",
          "reason": "live usage probe exceeded timeout budget"
        }
      ],
      "timeout_event_count": 3,
      "data_freshness_seconds": 95
    }
  ]
}
```

**Response 422**
```json
{ "detail": "Invalid window. Allowed: 24h, 7d" }
```

Behavioral rules:
- `suggested_timeout_ms` is deterministic and computed as `max(round(p90_latency_ms * 1.5), 3000)` with an upper clamp of `20000`.
- Providers with insufficient telemetry are returned with `p90_latency_ms: null`, `suggested_timeout_ms: null`, and a non-empty explanation in `recommendation_basis`.

## Data Model (if applicable)

```yaml
TimeoutDashboardResponse:
  properties:
    generated_at: { type: string, format: date-time }
    window: { type: string, enum: [24h, 7d] }
    providers:
      type: array
      items: { $ref: "#/components/schemas/ProviderTimeoutRecommendation" }

ProviderTimeoutRecommendation:
  properties:
    provider: { type: string }
    p90_latency_ms: { type: [integer, "null"], minimum: 0 }
    suggested_timeout_ms: { type: [integer, "null"], minimum: 0 }
    recommendation_basis: { type: string }
    timeout_events:
      type: array
      items: { $ref: "#/components/schemas/TimeoutEventSummary" }
    timeout_event_count: { type: integer, minimum: 0 }
    data_freshness_seconds: { type: integer, minimum: 0 }

TimeoutEventSummary:
  properties:
    at: { type: string, format: date-time }
    stage: { type: string }
    reason: { type: string }
```

## Files to Create/Modify

- `specs/136-data-driven-timeout-dashboard.md` - defines dashboard requirements, API contract, and delivery constraints.
- `api/app/routers/automation_usage.py` - add timeout-dashboard endpoint and request validation.
- `api/app/services/automation_usage_service.py` - compute p90, deterministic suggestions, and join recent timeout events.
- `api/app/models/automation_usage.py` - add response models for timeout dashboard payload.
- `api/tests/test_automation_usage_api.py` - API tests for formula, window validation, and missing-telemetry behavior.
- `web/app/automation/usage/page.tsx` - integrate timeout dashboard section or route-level page rendering.
- `web/components/automation/timeout-dashboard.tsx` - dashboard table/cards and empty/degraded state presentation.
- `web/lib/api.ts` - typed client function for timeout dashboard endpoint.
- `web/tests/automation-timeout-dashboard.test.tsx` - rendering and state tests for dashboard behavior.

## Acceptance Tests

- `api/tests/test_automation_usage_api.py::test_timeout_dashboard_returns_per_provider_recommendations`
- `api/tests/test_automation_usage_api.py::test_timeout_dashboard_uses_deterministic_p90_formula`
- `api/tests/test_automation_usage_api.py::test_timeout_dashboard_window_validation_422`
- `api/tests/test_automation_usage_api.py::test_timeout_dashboard_handles_missing_provider_telemetry`
- `web/tests/automation-timeout-dashboard.test.tsx::renders_timeout_recommendations_and_events`
- `web/tests/automation-timeout-dashboard.test.tsx::shows_empty_state_when_no_timeout_data`

## Concurrency Behavior

- **Read operations**: Safe for concurrent requests; dashboard data is derived from existing telemetry/events and has no direct mutation path.
- **Write operations**: None in dashboard endpoint; source systems may append telemetry/events concurrently without requiring dashboard-level locking.
- **Recommendation**: Compute from a single collection snapshot per request to avoid mixed-window artifacts across providers.

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/136-data-driven-timeout-dashboard.md
cd api && pytest -q tests/test_automation_usage_api.py -k "timeout_dashboard or timeout_recommendation"
cd web && npm run build
```

Manual validation:
1. Open the automation usage page/section in the web app.
2. Confirm provider rows include p90, suggested timeout, and timeout events.
3. Switch window (`24h`/`7d`) and verify values and event counts update consistently.

## Out of Scope

- Automatic runtime mutation of provider timeout settings from recommendations.
- New alert channels or notification transport changes.
- Replacing existing readiness/usage APIs with dashboard-specific persistence.

## Risks and Assumptions

- Risk: sparse telemetry can create unstable p90 estimates; mitigation is null-safe recommendations and explicit missing-data messaging.
- Risk: timeout-event reason strings may be noisy/inconsistent across sources; mitigation is short normalized reason mapping in service layer.
- Assumption: existing telemetry includes enough timing samples per provider for at least one configured window.
- Assumption: recent timeout events are available from existing runtime/friction event records without schema migration.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_timeout_dashboard_auto_tune_guardrails_001` to evaluate optional "apply recommendation" workflow with human approval gates.
- Follow-up task: `task_timeout_dashboard_trend_sparkline_002` to add p50/p90 trend visualization once baseline table usability is validated.

## Failure/Retry Reflection

- Failure mode: dashboard shows stale values when event ingestion lags.
- Blind spot: assuming freshness is uniform across providers and data sources.
- Next action: add per-provider staleness badges and fallback note before enabling stricter operational usage.

## Decision Gates (if any)

- Confirm whether timeout dashboard should be a dedicated page (`/automation/timeout-dashboard`) or a section inside existing automation usage page.
- Confirm canonical timeout-event source precedence if both runtime events and friction events are available for the same provider/time.
