"""Cooperative pacing middleware.

The organism serves flow. Its inner circle — loopback, private networks,
federation peers, test clients, same-process callers, internal paths — is
trusted without limit, because those callers ARE the organism reaching for
itself. The outer circle is paced cooperatively when a single caller bursts
sharply: a brief delay lets the request through rather than a refusal.

A last-resort ceiling remains for runaway loops (a single IP sustaining
~30 req/sec for a full minute). That ceiling exists as a backstop only —
upstream layers (Cloudflare, Traefik) catch adversarial traffic before it
reaches here. Inside this layer the posture is trust and flow.

NOTE: Returns JSONResponse directly instead of raising HTTPException because
Starlette's BaseHTTPMiddleware wraps pre-call_next exceptions in ExceptionGroups,
turning 429s into 500s. Returning a response avoids the ASGI double-send bug.
"""
import asyncio
import ipaddress
import logging
import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config_loader import get_bool, get_str

_log = logging.getLogger("coherence.rate_limit")

# Cooperative pacing — the organism takes a brief breath when a single caller
# in the outer circle bursts sharply, rather than refusing the request.
BURST_WINDOW_SECONDS = 1
BURST_SOFT_LIMIT = 12           # cooperative delay begins here
BURST_HARD_LIMIT = 48           # longer delay here, still serves
SOFT_DELAY_SECONDS = 0.15       # one gentle breath
HARD_DELAY_SECONDS = 0.45       # a longer breath for sharper bursts

# Runaway ceiling — only engages if a single IP sustains ~30 req/sec for
# an entire minute. Legitimate callers never approach this; adversarial
# callers are caught upstream long before they get here.
LONG_WINDOW_SECONDS = 60
LONG_WINDOW_CEILING = 1800      # 30 req/sec sustained for a full minute

# Paths internal to the organism that bypass all pacing.
_EXEMPT_PATHS = {
    "/api/agent/tasks/",        # activity posts, task updates
    "/api/federation/nodes",    # heartbeats, registration
    "/api/pipeline/",           # pulse, bootstrap
}

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Human-readable ceiling response — describes what IS (the organism is
# taking a longer breath) rather than refusing.
_CEILING_BODY = {
    "detail": "The organism is taking a longer breath. Try again in a moment.",
}


def _testing_mode_enabled() -> bool:
    return get_bool("api", "testing", False) or get_str("server", "environment", "development") in (
        "test",
        "testing",
    )


def _is_test_client_request(request: Request) -> bool:
    client_ip = request.client.host if request.client else ""
    if client_ip == "testclient":
        return True
    if request.headers.get("host", "").split(":", 1)[0].lower() == "test":
        return True
    user_agent = request.headers.get("user-agent", "")
    return "testclient" in user_agent.lower()


def _is_inner_circle(ip: str) -> bool:
    """Loopback and private networks are part of the organism — trust them.

    Private networks include docker, kubernetes, home/office LANs, and any
    address the organism routes through internally. These callers are the
    body reaching for itself and deserve unlimited service.
    """
    if not ip or ip in ("unknown", "localhost"):
        return True
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return addr.is_loopback or addr.is_private or addr.is_link_local


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = LONG_WINDOW_CEILING):
        super().__init__(app)
        self.rpm = requests_per_minute
        self._burst_counters: dict[str, list[float]] = defaultdict(list)
        self._window_counters: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        if _testing_mode_enabled() or _is_test_client_request(request):
            return await call_next(request)
        if request.headers.get("x-endpoint-exerciser") == "1":
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PATHS):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"

        # Inner circle — loopback, private networks, the organism itself.
        # Served without limit.
        if _is_inner_circle(client_ip):
            return await call_next(request)

        now = time.time()
        burst_window_start = now - BURST_WINDOW_SECONDS
        long_window_start = now - LONG_WINDOW_SECONDS

        # Sense burst and long-window usage for this caller.
        self._burst_counters[client_ip] = [
            t for t in self._burst_counters[client_ip] if t > burst_window_start
        ]
        burst_count = len(self._burst_counters[client_ip])
        self._burst_counters[client_ip].append(now)

        self._window_counters[client_ip] = [
            t for t in self._window_counters[client_ip] if t > long_window_start
        ]
        long_count = len(self._window_counters[client_ip])
        self._window_counters[client_ip].append(now)

        # Runaway ceiling — only engages for pathological sustained loops.
        if long_count >= self.rpm:
            _log.warning(
                "RATE_PAUSE ip=%s long_count=%d over %d req/min ceiling",
                client_ip,
                long_count,
                self.rpm,
            )
            return JSONResponse(
                status_code=429,
                content=_CEILING_BODY,
                headers={"Retry-After": "20"},
            )

        # Cooperative pacing — a brief breath instead of refusal.
        if burst_count >= BURST_HARD_LIMIT:
            await asyncio.sleep(HARD_DELAY_SECONDS)
        elif burst_count >= BURST_SOFT_LIMIT:
            await asyncio.sleep(SOFT_DELAY_SECONDS)

        return await call_next(request)
