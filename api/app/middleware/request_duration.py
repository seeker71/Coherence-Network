"""Middleware that logs requests exceeding a duration threshold."""

from __future__ import annotations

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("coherence.api.duration")

_DEFAULT_SLOW_THRESHOLD_S = 1.0


class RequestDurationMiddleware(BaseHTTPMiddleware):
    """Log a warning for any request that takes longer than *threshold_seconds*."""

    def __init__(self, app, threshold_seconds: float = _DEFAULT_SLOW_THRESHOLD_S):
        super().__init__(app)
        self.threshold_seconds = max(0.0, threshold_seconds)

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start

        if duration >= self.threshold_seconds:
            logger.warning(
                "slow_request method=%s path=%s status=%s duration_s=%.3f threshold_s=%.1f",
                request.method,
                request.url.path,
                response.status_code,
                duration,
                self.threshold_seconds,
            )

        return response
