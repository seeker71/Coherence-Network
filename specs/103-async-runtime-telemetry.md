# Spec 103: Async Runtime Telemetry (Non-Blocking)

## Summary

Make runtime telemetry recording non-blocking for API requests by dispatching
`runtime_service.record_event(...)` asynchronously (thread offload) so slow DB
writes cannot inflate endpoint latency.

## Motivation

We have observed very slow API request durations across multiple endpoints.
Runtime telemetry currently writes synchronously on the request path, and since
it uses SQLAlchemy (sync) it can block the event loop and/or extend handler
latency when the DB is slow.

## Design

In `api/app/main.py` middleware:

- Add env `RUNTIME_TELEMETRY_ASYNC` (default `1`).
- When enabled:
  - Create the `RuntimeEventCreate` payload as today.
  - Dispatch `runtime_service.record_event(payload)` via `asyncio.to_thread(...)`
    wrapped in `asyncio.create_task(...)`.
  - Never await the task; add a done-callback to swallow exceptions.
  - Record `telemetry_async=true` in metadata and set `telemetry_ms=0.0` since we
    don’t measure it on the request path.
- When disabled:
  - Keep current synchronous behavior (and measure `telemetry_ms`).

## Testing

Add a test in `api/tests/test_runtime_api.py` that monkeypatches
`runtime_service.record_event` to sleep, enables async telemetry, and asserts
that an API request returns quickly (does not wait on telemetry).

## Files Allowed To Change

- `api/app/main.py`
- `api/tests/test_runtime_api.py`

