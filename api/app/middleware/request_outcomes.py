"""Rolling request-outcome counters for the pulse witness to read.

The witness probes `/api/health` every 30 seconds. That tells it whether
the synthetic call succeeded, but it says nothing about the hundreds of
other requests that might be failing for real users between probe rounds.

This middleware keeps a tiny in-memory bucket of per-minute outcomes,
grouped by status-code class (2xx / 3xx / 4xx / 5xx), and exposes them
via `recent_outcomes_snapshot()`. The health endpoint includes the
snapshot in its response body, so pulse's api organ sees real traffic
shape without needing any new probe targets.

Design notes:
- Tumbling one-minute buckets keyed by epoch minute. When the window
  rolls, old buckets are dropped from the left. Lock-free: one dict
  append per request plus an occasional prune, no shared-state
  contention worth worrying about.
- Buckets drop paths entirely — we only record status class and count.
  Path-level slicing would be valuable but also noisy and private; if a
  specific path needs monitoring, add a synthetic outcome organ for it
  (see pulse_app/organs.py).
- Health endpoint probes are excluded from the counter. Pulse itself
  hits /api/health every 30s, and we don't want the witness to be its
  own biggest caller in the counter.
"""

from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Any

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


# Paths we don't count — they're noise from the monitor itself or from
# readiness/liveness probes that aren't real user traffic.
_EXCLUDED_PATHS = frozenset(
    [
        "/api/health",
        "/api/ready",
        "/api/ping",
        "/api/version",
        "/health",
        "/",
    ]
)

# How many minutes of history to keep. The counter exposes "last 1 min"
# and "last 5 min" by summing the rightmost buckets.
_RETENTION_MINUTES = 5


# Shared state: { epoch_minute: { "2xx": int, "3xx": int, "4xx": int, "5xx": int } }
_buckets: dict[int, dict[str, int]] = {}
_lock = Lock()


def _class_for(status: int) -> str:
    if 200 <= status < 300:
        return "2xx"
    if 300 <= status < 400:
        return "3xx"
    if 400 <= status < 500:
        return "4xx"
    return "5xx"


def _now_minute() -> int:
    return int(time.time() // 60)


def _prune_locked(now_min: int) -> None:
    """Drop buckets older than the retention window. Caller holds _lock."""
    cutoff = now_min - _RETENTION_MINUTES
    for key in [k for k in _buckets if k <= cutoff]:
        del _buckets[key]


def record_outcome(status: int) -> None:
    """Increment the bucket for the current minute + status class."""
    now_min = _now_minute()
    cls = _class_for(status)
    with _lock:
        _prune_locked(now_min)
        bucket = _buckets.setdefault(now_min, {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0})
        bucket[cls] += 1


def recent_outcomes_snapshot() -> dict[str, Any]:
    """Return an aggregate over the last-1-minute and last-5-minute windows.

    Shape (designed to be stable enough for pulse extractors to read):

        {
          "last_1m":  {"2xx": int, "3xx": int, "4xx": int, "5xx": int, "total": int},
          "last_5m":  {"2xx": int, "3xx": int, "4xx": int, "5xx": int, "total": int},
          "as_of_minute": int,   # epoch minute of the snapshot
        }
    """
    now_min = _now_minute()
    with _lock:
        _prune_locked(now_min)
        one_min_keys = [now_min]
        five_min_keys = [now_min - i for i in range(_RETENTION_MINUTES)]

        def _sum(keys: list[int]) -> dict[str, int]:
            out = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}
            for k in keys:
                b = _buckets.get(k)
                if not b:
                    continue
                for cls in out:
                    out[cls] += b.get(cls, 0)
            out["total"] = sum(out.values())
            return out

        return {
            "last_1m": _sum(one_min_keys),
            "last_5m": _sum(five_min_keys),
            "as_of_minute": now_min,
        }


def _reset_for_tests() -> None:  # pragma: no cover — test helper
    with _lock:
        _buckets.clear()


class RequestOutcomesMiddleware(BaseHTTPMiddleware):
    """Record the outcome of every non-excluded request."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path not in _EXCLUDED_PATHS:
            try:
                record_outcome(response.status_code)
            except Exception:
                # Never let the counter break a request.
                pass
        return response
