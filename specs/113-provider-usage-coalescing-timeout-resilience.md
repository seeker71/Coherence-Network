# Spec: Provider Usage Coalescing + Timeout Resilience

## Purpose

Automation usage responses currently expose provider-family duplicates (for example `openai` with `openai-codex`, and `claude` with `claude-code`), often show `usage_remaining` as null even when quota metrics exist, and can timeout under slow provider probes. This spec unifies family-level provider reporting, improves remaining-quota selection, and guarantees fast fallback behavior when live collection exceeds endpoint latency budgets.

## Requirements

- [ ] `GET /api/automation/usage` returns one row per provider family (`openai`, `claude`) instead of duplicate family variants.
- [ ] Provider snapshots set `usage_remaining` from the best quota-bearing summary metric when available, even if the primary usage metric is runtime-only.
- [ ] `GET /api/automation/usage` avoids long hangs by returning a valid fallback payload when live collection exceeds a configurable timeout.

## API Contract (if applicable)

### `GET /api/automation/usage`

**Request**
- `force_refresh`: boolean (query, optional)
- `compact`: boolean (query, optional)
- `include_raw`: boolean (query, optional)

**Response 200**
```json
{
  "generated_at": "2026-02-28T00:00:00Z",
  "providers": [
    {
      "provider": "openai",
      "status": "ok",
      "actual_current_usage": 120.0,
      "usage_remaining": 880.0
    }
  ],
  "tracked_providers": 1,
  "unavailable_providers": []
}
```

Behavioral updates:
- Provider-family aliases are coalesced in usage output.
- Endpoint may serve a snapshot-based fallback payload on live-collection timeout.

## Data Model (if applicable)

N/A - no model schema changes.

## Files to Create/Modify

- `api/app/services/automation_usage_service.py` - provider-family coalescing, summary metric remaining selection, snapshot fallback builder.
- `api/app/routers/automation_usage.py` - timeout-guarded usage endpoint flow with fallback.
- `api/tests/test_automation_usage_api.py` - regression tests for coalescing, remaining metric selection, and timeout fallback behavior.

## Acceptance Tests

- `api/tests/test_automation_usage_api.py::test_finalize_snapshot_uses_summary_metric_for_usage_remaining`
- `api/tests/test_automation_usage_api.py::test_automation_usage_endpoint_coalesces_provider_families`
- `api/tests/test_automation_usage_api.py::test_automation_usage_endpoint_times_out_to_snapshot_fallback`

## Verification

```bash
cd api && pytest -q tests/test_automation_usage_api.py -k "finalize_snapshot_uses_summary_metric_for_usage_remaining or coalesces_provider_families or times_out_to_snapshot_fallback"
cd api && pytest -q tests/test_automation_usage_api.py -k "automation_usage_endpoint_returns_normalized_providers or daily_summary"
```

## Out of Scope

- Changing provider-validation probe semantics for `claude-code` and `openai-codex`.
- Reworking upstream provider APIs or transport-level network reliability.

## Risks and Assumptions

- Risk: Coalescing could hide useful sub-provider details. Mitigation: preserve merged notes/metrics in coalesced rows.
- Assumption: Snapshot fallback data exists in store for degraded timeout paths.

## Known Gaps and Follow-up Tasks

- None at spec time.

## Decision Gates (if any)

- None.
