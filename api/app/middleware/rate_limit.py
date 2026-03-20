"""Simple in-memory rate limiter.

Limits requests per IP per minute. Uses a sliding window counter.
For production, replace with Redis-backed limiter.
"""
import os
import time
from collections import defaultdict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

_TESTING = os.environ.get("COHERENCE_ENV", "development") in ("test", "testing")

# TODO: Add endpoint-specific limits for federation and governance endpoints (30/min).
# Currently all endpoints share the same per-IP limit. A follow-up should inspect
# request.url.path and apply tighter limits for /api/federation/* and /api/governance/*.

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 600):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._counters: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if _TESTING:
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = now - 60

        # Clean old entries
        self._counters[client_ip] = [t for t in self._counters[client_ip] if t > window]

        if len(self._counters[client_ip]) >= self.rpm:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        self._counters[client_ip].append(now)
        return await call_next(request)
