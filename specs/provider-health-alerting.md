---
idea_id: pipeline-optimization
status: done
source:
  - file: api/app/services/automation_usage_service.py
    symbols: [provider health evaluation]
  - file: api/app/services/collective_health_service.py
    symbols: [health aggregation]
  - file: api/app/routers/agent_status_routes.py
    symbols: [health endpoints]
requirements:
  - "Compute provider health from execution outcomes using a fixed `last_5` window and trigger only when `last_5_success_rate"
  - "Automatically write a friction event when the threshold is breached, with provider identity and evidence in event notes."
  - "De-duplicate repeated friction writes while the provider remains degraded; create a new event only on a fresh degradatio"
  - "Support optional outbound notification through existing channels (Telegram adapter) behind configuration flags, with no "
  - "Keep usage/readiness alert payloads aligned with the health state so API consumers can observe degraded providers withou"
done_when:
  - "Provider health transition to degraded is detected from a strict last-5 success-rate check (<0.50)."
  - "A single friction event is created per degradation transition with provider and last-5 evidence."
  - "Optional Telegram notification is emitted only when enabled and only on newly-created health events."
test: "cd api && pytest -q tests/test_friction_api.py -k \"provider_health\""
constraints:
  - "no new notification providers; use existing adapter/service only"
  - "no schema migrations without explicit approval"
  - "preserve current usage/readiness endpoint paths"
---

> **Parent idea**: [pipeline-optimization](../ideas/pipeline-optimization.md)
> **Source**: [`api/app/services/automation_usage_service.py`](../api/app/services/automation_usage_service.py) | [`api/app/services/collective_health_service.py`](../api/app/services/collective_health_service.py) | [`api/app/routers/agent_status_routes.py`](../api/app/routers/agent_status_routes.py)

# Spec: Provider Health Alerting from Last-5 Success Rate

## Purpose

Provider reliability can degrade quickly while still appearing "configured" and partially functional. This spec adds a deterministic health alerting contract so when a provider's last-5 execution success rate drops below 50%, the system automatically records a friction event and can optionally push a notification through existing channels, reducing silent failure loops and response latency.

## Requirements

- [ ] Compute provider health from execution outcomes using a fixed `last_5` window and trigger only when `last_5_success_rate < 0.50`.
- [ ] Automatically write a friction event when the threshold is breached, with provider identity and evidence in event notes.
- [ ] De-duplicate repeated friction writes while the provider remains degraded; create a new event only on a fresh degradation transition.
- [ ] Support optional outbound notification through existing channels (Telegram adapter) behind configuration flags, with no new notification subsystem.
- [ ] Keep usage/readiness alert payloads aligned with the health state so API consumers can observe degraded providers without reading internal logs.

## Research Inputs (Required)

- `2026-03-21` - [Spec 096: Provider Readiness Contract Automation](https://github.com/seeker71/Coherence-Network/blob/main/specs/provider-readiness-contract-automation.md) - establishes provider readiness and validation patterns this alerting must extend.
- `2026-03-21` - [Spec 100: Automation Provider Usage and Readiness API](https://github.com/seeker71/Coherence-Network/blob/main/specs/automation-provider-usage-readiness-api.md) - defines current usage/readiness surfaces where health alert visibility must remain consistent.
- `2026-03-21` - [automation_usage_service.py](https://github.com/seeker71/Coherence-Network/blob/main/api/app/services/automation_usage_service.py) - current source of last-5 execution metric and degraded-note behavior.
- `2026-03-21` - [friction_service.py](https://github.com/seeker71/Coherence-Network/blob/main/api/app/services/friction_service.py) - existing friction-event persistence mechanism to reuse.
- `2026-03-21` - [telegram_adapter.py](https://github.com/seeker71/Coherence-Network/blob/main/api/app/services/telegram_adapter.py) - existing outbound channel for optional notifications.

## Task Card (Required)

```yaml
goal: Automatically raise provider health friction when last-5 success drops below 50%, with optional notification via existing channels.
files_allowed:
  - specs/provider-health-alerting.md
  - api/app/services/automation_usage_service.py
  - api/app/services/friction_service.py
  - api/app/models/automation_usage.py
  - api/tests/test_automation_usage_api.py
  - api/tests/test_friction_api.py
done_when:
  - Provider health transition to degraded is detected from a strict last-5 success-rate check (<0.50).
  - A single friction event is created per degradation transition with provider and last-5 evidence.
  - Optional Telegram notification is emitted only when enabled and only on newly-created health events.
commands:
  - cd api && pytest -q tests/test_automation_usage_api.py -k "provider_health or usage_alerts"
  - cd api && pytest -q tests/test_friction_api.py -k "provider_health"
  - python3 scripts/validate_spec_quality.py --file specs/provider-health-alerting.md
constraints:
  - no new notification providers; use existing adapter/service only
  - no schema migrations without explicit approval
  - preserve current usage/readiness endpoint paths
```

## API Contract (if applicable)

N/A - no new API routes are introduced in this spec.

## Data Model (if applicable)

```yaml
ProviderHealthAlertState:
  description: Derived runtime state from provider execution telemetry.
  properties:
    provider: { type: string }
    window: { type: string, enum: [last_5] }
    success_rate: { type: number, minimum: 0.0, maximum: 1.0 }
    threshold: { type: number, const: 0.5 }
    is_degraded: { type: boolean }
    triggered_at: { type: string, format: date-time }
FrictionEvent (existing, extended usage):
  required_behavior:
    block_type: provider_health_degraded
    stage: provider_health_monitor
    status: open
```

## Files to Create/Modify

- `specs/provider-health-alerting.md` - defines alerting behavior, scope, and verification.
- `api/app/services/automation_usage_service.py` - detect threshold breach, trigger friction creation, and optional notification dispatch.
- `api/app/services/friction_service.py` - add helper(s) to support transition-safe provider-health event dedupe/lookups.
- `api/app/models/automation_usage.py` - extend alert metadata only if needed to expose provider health signal consistently.
- `api/tests/test_automation_usage_api.py` - verify degraded transition, dedupe, and usage-alert visibility.
- `api/tests/test_friction_api.py` - verify friction event contents and provider-health block typing.

## Acceptance Tests

- `api/tests/test_automation_usage_api.py::test_provider_health_creates_friction_event_on_last5_drop_below_half`
- `api/tests/test_automation_usage_api.py::test_provider_health_dedupes_friction_while_still_degraded`
- `api/tests/test_automation_usage_api.py::test_provider_health_optional_telegram_notification_respects_flag`
- `api/tests/test_friction_api.py::test_provider_health_friction_event_shape`

## Concurrency Behavior

- **Read operations**: Safe for concurrent access; health evaluation reads runtime history and snapshots only.
- **Write operations**: Event creation is append-only; dedupe check must be idempotent under near-simultaneous evaluations.
- **Recommendation**: Treat provider-health event writes as transition-based state changes (healthy -> degraded) to avoid alert storms.

## Verification

```bash
python3 scripts/validate_spec_quality.py --file specs/provider-health-alerting.md
cd api && pytest -q tests/test_automation_usage_api.py -k "provider_health or usage_alerts"
cd api && pytest -q tests/test_friction_api.py -k "provider_health"
```

## Out of Scope

- Adding new notification backends (email, Slack, PagerDuty, etc.).
- Redesigning provider routing/executor policy.
- Replacing the current last-5 window with adaptive/statistical anomaly detection.

## Risks and Assumptions

- Risk: noisy telemetry or sparse execution history can create false positives; mitigation is enforcing a strict `last_5` window and transition-based dedupe.
- Risk: notification bursts can create alert fatigue; mitigation is optional notification flag plus existing Telegram suppression controls.
- Assumption: execution outcome telemetry is available and trustworthy for each provider being monitored.

## Known Gaps and Follow-up Tasks

- Follow-up task: `task_provider_health_recovery_signal_001` to emit an explicit recovery event/notification when a degraded provider returns above threshold.
- Follow-up task: `task_provider_health_ui_surface_002` to add first-class web UI presentation for provider health transitions.

## Failure/Retry Reflection

- Failure mode: degradation state repeatedly toggles due to low sample quality near threshold.
- Blind spot: assuming every provider has steady execution volume in short windows.
- Next action: add hysteresis or minimum-cadence guard only if real telemetry proves alert flapping.

## Decision Gates (if any)

- Confirm whether notification default is `off` (opt-in) or `on` for production environments.
- Confirm canonical `block_type` naming (`provider_health_degraded`) before implementation lock.
