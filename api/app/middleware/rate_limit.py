"""Simple in-memory rate limiter.

Limits requests per IP per minute. Uses a sliding window counter.
Write endpoints (POST/PUT/PATCH/DELETE) get a tighter limit than reads.
For production, replace with Redis-backed limiter.
"""
import os
import time
from collections import defaultdict

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

_TESTING = os.environ.get("COHERENCE_ENV", "development") in ("test", "testing")

# Per-IP limits
WINDOW_SECONDS = 60
MAX_WRITE_REQUESTS = 30   # 30 req/min per IP for write endpoints
MAX_READ_REQUESTS = 120   # 120 req/min per IP for read endpoints

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._read_counters: dict[str, list[float]] = defaultdict(list)
        self._write_counters: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if _TESTING:
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = now - WINDOW_SECONDS

        is_write = request.method in _WRITE_METHODS

        if is_write:
            self._write_counters[client_ip] = [
                t for t in self._write_counters[client_ip] if t > window
            ]
            if len(self._write_counters[client_ip]) >= MAX_WRITE_REQUESTS:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please wait a moment.",
                )
            self._write_counters[client_ip].append(now)
        else:
            self._read_counters[client_ip] = [
                t for t in self._read_counters[client_ip] if t > window
            ]
            if len(self._read_counters[client_ip]) >= MAX_READ_REQUESTS:
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please wait a moment.",
                )
            self._read_counters[client_ip].append(now)

        return await call_next(request)
