# Spec 102: Request Logging Middleware + Health Perf Debug

## Summary

Add production-safe request logging for the API service and an opt-in performance debug mode for `/api/health` so we can:

- See consistent method/path/status/duration/request_id in Railway container logs (not only Railway HTTP logs).
- When a request is slow, capture a breakdown that distinguishes handler time vs telemetry overhead.
- When debugging health specifically, emit step-level timing inside the health handler to identify whether the slowness is inside the endpoint or elsewhere.

## Motivation

We have observed very slow request durations (tens of seconds to minutes) even for lightweight endpoints. Railway's HTTP logs
show durations but are not always accessible for programmatic analysis and don't provide breakdown timing.

## Design

### Request Logging (always-on, safe)

In the existing API middleware (`api/app/main.py:capture_runtime_metrics`):

- Generate/propagate a `request_id`:
  - Prefer `x-request-id`, then `x-railway-request-id`, else generate `req_<12hex>`.
  - Attach it to `request.state.request_id`.
  - Add response header `x-request-id` with the chosen id.
- Measure timings:
  - `handler_ms`: duration of `await call_next(request)`.
  - `telemetry_ms`: duration of `runtime_service.record_event(...)` (best-effort; should never break responses).
  - `total_ms`: `handler_ms + telemetry_ms` (approximate end-to-end server time).
- Log one line per request (INFO) when enabled:
  - `api_request method=... path=... status=... handler_ms=... telemetry_ms=... total_ms=... request_id=...`

Config:

- `REQUEST_LOG_ENABLED` (default `1`) disables request log lines when `0/false`.

### Slow Request Logs (detailed, only when slow)

If `handler_ms >= RUNTIME_SLOW_REQUEST_MS` (default from existing env, fallback 2000ms), log an additional line (WARN):

- `api_slow_request ... query_keys=... route=...`

No query values, no request bodies, no auth headers.

### Health Perf Debug (opt-in)

In `api/app/routers/health.py`:

- If `PERF_DEBUG_ENDPOINTS` contains `/api/health` (comma-separated list), emit step-level INFO logs:
  - time to compute now/uptime
  - time to construct response model

This should be extremely low; if it’s not, we have evidence the slowness is inside the endpoint.

## Testing

Add tests in `api/tests/test_runtime_api.py`:

- Middleware still records runtime events when enabled.
- `REQUEST_LOG_ENABLED=0` does not break requests.
- `PERF_DEBUG_ENDPOINTS=/api/health` does not break `/api/health` response.

## Files Allowed To Change

- `api/app/main.py`
- `api/app/routers/health.py`
- `api/tests/test_runtime_api.py`

