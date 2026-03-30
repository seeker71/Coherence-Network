# Spec: API Request Logging Middleware

## Purpose

Add structured access-log middleware that records every API request with method, path, status code, and duration. This provides a consistent, queryable request log for debugging, performance monitoring, and audit trails. Without it, operators must piece together information from multiple log sources or rely solely on the slow-request threshold logger, which misses normal-latency requests entirely.

## Requirements

- [ ] Every HTTP request produces exactly one structured log line after the response is sent.
- [ ] Each log line includes: HTTP method, request path, response status code, and request duration in milliseconds.
- [ ] Log level is `INFO` for 2xx/3xx responses and `WARNING` for 4xx/5xx responses.
- [ ] Health-check endpoints (`/api/health`, `/healthz`) are excluded from logging to avoid noise.
- [ ] The middleware is configurable via an environment variable `API_ACCESS_LOG_ENABLED` (default `"1"`; set to `"0"` to disable).
- [ ] Log output uses key=value structured format for machine parseability (e.g., `method=GET path=/api/ideas status=200 duration_ms=12.3`).
- [ ] The middleware does not interfere with existing `RequestDurationMiddleware` or `capture_runtime_metrics`.

## Research Inputs (Required)

- `2025-01-01` - [Starlette BaseHTTPMiddleware](https://www.starlette.io/middleware/) - existing middleware pattern used in this codebase
- `2025-01-01` - [FastAPI Middleware docs](https://fastapi.tiangolo.com/tutorial/middleware/) - framework middleware conventions
- Codebase analysis: `api/app/middleware/request_duration.py` logs only slow requests; `capture_runtime_metrics` is telemetry-focused with DB writes — neither serves as a general access log.

## Task Card (Required)

```yaml
goal: Add structured access-log middleware that logs method, path, status code, and duration for every API request.
files_allowed:
  - api/app/middleware/request_logging.py
  - api/app/main.py
  - api/tests/test_request_logging.py
done_when:
  - Every non-excluded request produces one structured log line with method, path, status, and duration_ms.
  - Health-check paths are excluded from logging.
  - Log level is INFO for success responses and WARNING for error responses.
  - Setting API_ACCESS_LOG_ENABLED=0 disables the middleware.
  - Existing middleware (RequestDurationMiddleware, capture_runtime_metrics) continues to function.
  - All tests in api/tests/test_request_logging.py pass.
commands:
  - cd api && python -m pytest tests/test_request_logging.py -q
constraints:
  - Changes scoped to listed files only.
  - Must use BaseHTTPMiddleware pattern consistent with existing middleware.
  - No external dependencies added.
```

## API Contract

N/A - no API contract changes in this spec. This is internal middleware; it does not add or modify any API endpoints.

## Data Model (if applicable)

N/A - no model changes in this spec.

## Files to Create/Modify

- `api/app/middleware/request_logging.py` - new middleware module
- `api/app/main.py` - register the middleware via `app.add_middleware(RequestLoggingMiddleware)`
- `api/tests/test_request_logging.py` - unit tests

## Acceptance Tests

- `api/tests/test_request_logging.py::test_logs_method_path_status_duration` — verify a normal request emits a structured log line with all four fields.
- `api/tests/test_request_logging.py::test_health_check_excluded` — verify `/api/health` does not produce a log line.
- `api/tests/test_request_logging.py::test_warning_level_on_error` — verify 4xx/5xx responses log at WARNING level.
- `api/tests/test_request_logging.py::test_disabled_via_env` — verify setting `API_ACCESS_LOG_ENABLED=0` suppresses logging.

## Concurrency Behavior

- **Read operations**: The middleware is stateless and safe for concurrent access.
- **Write operations**: N/A — logs are written to stdout/stderr via Python logging; no shared mutable state.
- **Recommendation**: No concurrency concerns.

## Verification

```bash
cd api && python -m pytest tests/test_request_logging.py -q
```

## Out of Scope

- Request/response body logging (privacy and size concerns).
- Log aggregation, shipping, or external log storage configuration.
- Replacing or modifying the existing `RequestDurationMiddleware` or `capture_runtime_metrics`.
- Structured JSON logging format (can be a follow-up if needed).

## Risks and Assumptions

- **Risk**: High-traffic deployments may see increased log volume. **Mitigation**: The `API_ACCESS_LOG_ENABLED` env var allows disabling, and health-check exclusion reduces noise.
- **Assumption**: Python's standard `logging` module is sufficient for structured log output; no external logging library is required.
- **Assumption**: The existing middleware stack order in `main.py` allows adding this middleware without side effects.

## Known Gaps and Follow-up Tasks

- Structured JSON log format (e.g., for log aggregation tools) is not included; can be added as a follow-up.
- Request ID correlation (tying logs to `RequestIDMiddleware` output) is not in scope but would be a natural enhancement.

## Failure/Retry Reflection

- **Failure mode**: Middleware raises an unhandled exception, causing 500 errors on all requests.
- **Blind spot**: Edge cases in `call_next` (e.g., streaming responses, WebSocket upgrades).
- **Next action**: Wrap the logging logic in a try/except so failures in logging never break the request pipeline.

## Decision Gates (if any)

- None — this is a straightforward observability addition with no architectural trade-offs requiring approval.
