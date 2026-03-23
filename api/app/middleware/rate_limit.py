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

# Per-IP limits — generous defaults; excitement is not abuse
WINDOW_SECONDS = 60
MAX_WRITE_REQUESTS = 60    # 60 req/min per IP for write endpoints
MAX_READ_REQUESTS = 300    # 300 req/min per IP for read endpoints
BURST_WINDOW_SECONDS = 1
BURST_LIMIT = 10           # Allow 10 requests in 1 second before throttling

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


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
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = now - WINDOW_SECONDS
        burst_window = now - BURST_WINDOW_SECONDS

        # Burst check — don't punish fast page loads, but cap 1-second bursts
        self._burst_counters[client_ip] = [
            t for t in self._burst_counters[client_ip] if t > burst_window
        ]
        if len(self._burst_counters[client_ip]) >= BURST_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please wait a moment.",
            )
        self._burst_counters[client_ip].append(now)

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
