"""Simple in-memory rate limiter.

Limits requests per IP per minute. Uses a sliding window counter.
Write endpoints (POST/PUT/PATCH/DELETE) get a tighter limit than reads.
For production, replace with Redis-backed limiter.

NOTE: Returns JSONResponse directly instead of raising HTTPException because
Starlette's BaseHTTPMiddleware wraps pre-call_next exceptions in ExceptionGroups,
turning 429s into 500s.  Returning a response avoids the ASGI double-send bug.
"""
import json
import logging
import os
import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_TESTING = os.environ.get("COHERENCE_ENV", "development") in ("test", "testing")
_log = logging.getLogger("coherence.rate_limit")

# Per-IP limits — generous defaults; excitement is not abuse
WINDOW_SECONDS = 60
MAX_WRITE_REQUESTS = 60    # 60 req/min per IP for write endpoints
MAX_READ_REQUESTS = 300    # 300 req/min per IP for read endpoints
BURST_WINDOW_SECONDS = 1
BURST_LIMIT = 10           # Allow 10 requests in 1 second before throttling

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths exempt from rate limiting (federation/runner internal traffic)
_EXEMPT_PATHS = {
    "/api/agent/tasks/",        # activity posts, task updates
    "/api/federation/nodes",    # heartbeats, registration
    "/api/pipeline/",           # pulse, bootstrap
}

_429_BODY = {"detail": "Too many requests. Please wait a moment."}


def _rate_limited_response(client_ip: str, reason: str, retry_after: int = 5) -> JSONResponse:
    _log.warning("RATE_LIMITED ip=%s reason=%s retry_after=%ds", client_ip, reason, retry_after)
    return JSONResponse(
        status_code=429,
        content=_429_BODY,
        headers={"Retry-After": str(retry_after)},
    )


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 300):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._read_counters: dict[str, list[float]] = defaultdict(list)
        self._write_counters: dict[str, list[float]] = defaultdict(list)
        self._burst_counters: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if _TESTING:
            return await call_next(request)
        if request.headers.get("x-endpoint-exerciser") == "1":
            return await call_next(request)
        # Exempt federation/runner paths from rate limiting
        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PATHS):
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = now - WINDOW_SECONDS
        burst_window = now - BURST_WINDOW_SECONDS

        # Burst check — don't punish fast page loads, but cap 1-second bursts
        self._burst_counters[client_ip] = [
            t for t in self._burst_counters[client_ip] if t > burst_window
        ]
        if len(self._burst_counters[client_ip]) >= BURST_LIMIT:
            return _rate_limited_response(client_ip, "burst", retry_after=2)
        self._burst_counters[client_ip].append(now)

        is_write = request.method in _WRITE_METHODS

        if is_write:
            self._write_counters[client_ip] = [
                t for t in self._write_counters[client_ip] if t > window
            ]
            if len(self._write_counters[client_ip]) >= MAX_WRITE_REQUESTS:
                return _rate_limited_response(client_ip, "write_rpm", retry_after=10)
            self._write_counters[client_ip].append(now)
        else:
            self._read_counters[client_ip] = [
                t for t in self._read_counters[client_ip] if t > window
            ]
            if len(self._read_counters[client_ip]) >= MAX_READ_REQUESTS:
                return _rate_limited_response(client_ip, "read_rpm", retry_after=5)
            self._read_counters[client_ip].append(now)

        return await call_next(request)
