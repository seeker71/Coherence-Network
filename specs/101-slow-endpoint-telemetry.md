# Spec 101: Slow Endpoint Telemetry And Diagnosis

## Summary

Add first-class visibility into slow API endpoints by:

- Recording additional per-request runtime metadata (safe, non-PII) into runtime events.
- Exposing percentile-based endpoint summaries (p50/p95/max) for awareness.
- Adding API query filters to retrieve runtime events for a specific endpoint and runtime threshold for diagnosis.
- Adding a "slow endpoints" report endpoint that highlights endpoints exceeding a configurable threshold.

This is intended to make slow endpoints visible (awareness) and actionable (diagnosis) without relying on external APM.

## Motivation

Production incidents can present as browser/proxy errors (e.g. Cloudflare 5xx) while the root cause is a slow endpoint.
We already persist runtime events, but summaries do not surface percentiles and there is no easy way to pull "slow event"
slices for debugging.

## Non-Goals

- Full distributed tracing across services.
- Capturing full query strings, request bodies, or sensitive headers.
- Storing response bodies or stack traces in runtime telemetry.

## Design

### Runtime Event Metadata (API middleware)

Extend the API runtime telemetry middleware to include safe metadata:

- `request_id`: `x-request-id` if present, else generated.
- `query_keys`: list of query parameter keys only (no values).
- `user_agent`: user-agent truncated to a small bound.
- `content_length`: request `Content-Length` if present and parseable.
- `slow`: boolean when runtime exceeds `RUNTIME_SLOW_REQUEST_MS` (default 2000ms).
- `slow_threshold_ms`: threshold used when `slow=true`.

### Endpoint Summaries

Extend `EndpointRuntimeSummary` with:

- `p50_runtime_ms`
- `p95_runtime_ms`
- `max_runtime_ms`

Compute over the runtime events within the requested window.

### Diagnosis Endpoints

1. Enhance `GET /api/runtime/events` to support optional filters:
   - `endpoint` (canonical endpoint template string)
   - `method`
   - `min_runtime_ms`
   - `status_code`
   - `limit`

2. Add `GET /api/runtime/endpoints/slow`:
   - Inputs: `seconds` (window), `threshold_ms` (default env `RUNTIME_SLOW_REQUEST_MS`), `limit`
   - Output: endpoints whose `p95_runtime_ms >= threshold_ms` (or `max_runtime_ms >= threshold_ms`), sorted by p95.

### Configuration

- `RUNTIME_TELEMETRY_ENABLED` already gates runtime telemetry.
- Add `RUNTIME_SLOW_REQUEST_MS` (default `2000`).

## Testing

Add unit/integration tests in `api/tests/test_runtime_api.py`:

- Percentiles appear in `/api/runtime/endpoints/summary` and are computed correctly for a known dataset.
- `/api/runtime/events` filtering works for `endpoint` + `min_runtime_ms`.
- `/api/runtime/endpoints/slow` returns the expected endpoint when runtime data exceeds threshold.

## Files Allowed To Change

- `api/app/main.py`
- `api/app/models/runtime.py`
- `api/app/services/runtime_service.py`
- `api/app/routers/runtime.py`
- `api/tests/test_runtime_api.py`

