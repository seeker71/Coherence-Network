"""HTTP probes — one shared round-trip per upstream, fanned out to organs.

We are gentle on the network we watch. Rather than hitting six endpoints to
get six organ samples, we hit a small set of upstreams and apply each
organ's extractor to the shared response. Each organ declares its own
upstream; the probe dispatcher groups organs by upstream and issues one
GET per group, so duplicate organs cost nothing.

Each upstream result carries the response status, the parsed JSON body
(when the upstream is JSON-shaped), the raw response text (when the
upstream is HTML-shaped), and the latency. Extractors receive the full
UpstreamResult so they can check whatever they need — status, body
shape, or rendered text markers.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

from pulse_app.organs import (
    ORGANS,
    Organ,
    organs_for_upstream,
    upstreams_in_use,
)
from pulse_app.storage import Sample, iso_utc


# Per-upstream result of one probe attempt, shared across organs.
@dataclass(frozen=True)
class UpstreamResult:
    status: int                   # HTTP status, or 0 on network error
    body: dict[str, Any] | None   # Parsed JSON when kind=json, else None
    text: str | None              # Raw response text when kind=text, else None
    latency_ms: int
    error: str | None             # Transport error text, or None
    headers: dict[str, str] = field(default_factory=dict)  # response headers,
                                  # keys lowercased. Extractors and _apply read
                                  # these for carrier-path checks (x-form-router).


async def _probe_upstream(
    client: httpx.AsyncClient,
    url: str,
    kind: str,
    method: str = "GET",
    json_body: dict[str, Any] | None = None,
) -> UpstreamResult:
    """Fetch one upstream once, return a shared UpstreamResult.

    `kind` is one of "json" (parse body into dict) or "text" (keep raw
    response text for content-marker checks). JSON responses for
    "text" upstreams still parse successfully; that's fine.

    `method` defaults to GET. Pass "POST" with `json_body` for endpoints
    that need a request payload (e.g. the substrate Form evaluator).

    We swallow all exceptions deliberately: a probe failure is a signal,
    not an error in the monitor.
    """
    start = time.perf_counter()
    try:
        if method == "POST":
            resp = await client.post(url, json=json_body)
        else:
            resp = await client.get(url)
        elapsed = int((time.perf_counter() - start) * 1000)
        headers = {k.lower(): v for k, v in resp.headers.items()}
        body: dict[str, Any] | None = None
        text: str | None = None
        if kind == "json":
            try:
                raw = resp.json()
                if isinstance(raw, dict):
                    body = raw
            except Exception:
                body = None
        else:  # "text"
            try:
                text = resp.text
            except Exception:
                text = None
        return UpstreamResult(
            status=resp.status_code,
            body=body,
            text=text,
            latency_ms=elapsed,
            error=None,
            headers=headers,
        )
    except httpx.HTTPError as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        return UpstreamResult(
            status=0, body=None, text=None, latency_ms=elapsed, error=_short_error(exc)
        )
    except Exception as exc:  # pragma: no cover — defensive
        elapsed = int((time.perf_counter() - start) * 1000)
        return UpstreamResult(
            status=0, body=None, text=None, latency_ms=elapsed, error=_short_error(exc)
        )


def _short_error(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    return text[:200]


_SLOW_PREFIX = "slow: "

# Native-promoted routes stamp their response with an `x-form-router` header
# naming the carrier that served them: "native-kernel" (the Form kernel-router,
# the body's actual carrier) or "fanout-python" (the Python fan-out fallback).
# When the kernel-router container is unhealthy, Traefik fails over to the
# Python `api` container, which still returns 200 with a valid body — so a
# native-route regression (e.g. the boolean::bigint 500 fixed in #3087) is
# invisible to status+shape checks alone: the witness probes the Python 200 and
# reads "breathing" while the native route is down. An organ that declares
# `expected_router` makes _apply compare the carrier seen and flag a strain
# when the route was served by anything but its native carrier. Strain, not
# silence: the surface still breathes, and a brief deploy-window failover
# self-heals without scarring uptime.
_FORM_ROUTER_HEADER = "x-form-router"
_FALLBACK_PREFIX = "fell back: "
_PUBLIC_API_BASE = "https://api.coherencycoin.com"
_PUBLIC_WEB_BASE = "https://coherencycoin.com"
_DOCKER_API_HOSTS = frozenset({"api"})
_DOCKER_WEB_HOSTS = frozenset({"web"})


def _host(base: str) -> str:
    return (urlparse(base).hostname or "").lower()


def _public_api_base(api_base: str) -> str:
    """Return the public API origin when the configured base is Docker-local.

    The witness often runs beside the app in docker-compose. Internal aliases
    such as ``http://api:8000`` bypass the public Traefik/native-router path.
    This witness exists to sense what visitors see, so Docker-local aliases are
    lifted to the public origin before any probe URL is built.
    """
    return _PUBLIC_API_BASE if _host(api_base) in _DOCKER_API_HOSTS else api_base


def _public_web_base(web_base: str) -> str:
    return _PUBLIC_WEB_BASE if _host(web_base) in _DOCKER_WEB_HOSTS else web_base


def _router_fallback_detail(organ: Organ, result: UpstreamResult) -> str | None:
    """Strain detail when a native-promoted route was served off its carrier.

    Returns None when the organ declares no expected router or the carrier the
    response named matches. Otherwise returns a "fell back: " strain detail
    naming the actual carrier seen, so status_from_last_sample reads 'strained'
    while uptime stays whole. A missing header counts as a fallback too — the
    native carrier didn't stamp the response.
    """
    expected = organ.expected_router
    if not expected:
        return None
    seen = result.headers.get(_FORM_ROUTER_HEADER)
    if seen == expected:
        return None
    seen_label = seen if seen else "no router header"
    return f"{_FALLBACK_PREFIX}expected {expected}, got {seen_label}"


def _apply(organ: Organ, result: UpstreamResult, ts: str) -> Sample:
    if result.error is not None:
        return Sample(
            ts=ts,
            organ=organ.name,
            ok=False,
            latency_ms=result.latency_ms,
            detail=result.error,
        )
    verdict = organ.extractor(result)
    detail = verdict.detail
    # Post-verdict strain checks: a probe that passed content assertions can
    # still be degraded — detail is set but ok stays True. The current status
    # then reads as "strained" via status_from_last_sample while historical
    # uptime stays at 100% (nothing failed, just strained). Carrier-path
    # fallback takes precedence over slowness: a native route served by the
    # Python fan-out is the more significant signal (and is usually slower
    # anyway).
    if verdict.ok:
        fallback = _router_fallback_detail(organ, result)
        if fallback is not None:
            detail = fallback
        elif (
            organ.latency_threshold_ms
            and result.latency_ms > organ.latency_threshold_ms
        ):
            detail = (
                f"{_SLOW_PREFIX}{result.latency_ms}ms > {organ.latency_threshold_ms}ms threshold"
            )
    return Sample(
        ts=ts,
        organ=organ.name,
        ok=verdict.ok,
        latency_ms=result.latency_ms,
        detail=detail,
    )


def _build_url(
    upstream: str, api_base: str, web_base: str
) -> tuple[str, str, str, dict[str, Any] | None]:
    """Map an upstream label to (url, kind, method, json_body).

    See organs.py for the labels. Most entries are GETs and keep
    json_body=None; the substrate Form evaluator needs a POST with a
    known-good expression so the witness keeps tension on it.
    """
    api = _public_api_base(api_base).rstrip("/")
    web = _public_web_base(web_base).rstrip("/")
    mapping: dict[str, tuple[str, str, str, dict[str, Any] | None]] = {
        "api_health": (f"{api}/api/health", "json", "GET", None),
        "api_ready": (f"{api}/api/ready", "json", "GET", None),
        "api_ideas": (
            f"{api}/api/ideas?limit=1&offset=0&sort=marginal_cc",
            "json",
            "GET",
            None,
        ),
        "api_vitality": (
            f"{api}/api/workspaces/coherence-network/vitality", "json", "GET", None,
        ),
        "web_root": (f"{web}/", "text", "GET", None),
        "web_pulse": (f"{web}/pulse", "text", "GET", None),
        "web_vitality": (f"{web}/vitality", "text", "GET", None),
        # Substrate badge resolver — the surface that broke silently on
        # every page (the user noticed via mobile on the home page). Probe
        # the home route specifically because it's the most-visited and
        # the resolver's simplest path; if `/` doesn't resolve, none do.
        "api_substrate_page": (
            f"{api}/api/substrate/page?route=/", "json", "GET", None,
        ),
        # Substrate Form evaluator — the playground's primary surface.
        # The known-good expression is one that any healthy lattice
        # carries (lc-pulse is the Living Collective root). A 4xx/5xx
        # here means the structural evaluator regressed or the cell
        # disappeared from the body — either is a real silence.
        "api_substrate_form": (
            f"{api}/api/substrate/form",
            "json",
            "POST",
            {"expression": "@concept(lc-pulse).blueprint"},
        ),
    }
    if upstream not in mapping:
        raise ValueError(f"unknown upstream label: {upstream}")
    return mapping[upstream]


async def probe_all(
    api_base: str, web_base: str, client: httpx.AsyncClient | None = None
) -> list[Sample]:
    """Run one round of probes for every organ.

    Returns a list of samples in ORGANS order, all tagged with the same ts.
    Each upstream is fetched exactly once even if multiple organs share it.
    """
    ts = iso_utc()
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=True,
            headers={"User-Agent": "pulse-monitor/0.2 (+https://coherencycoin.com)"},
        )
    try:
        results: dict[str, UpstreamResult] = {}
        for upstream in upstreams_in_use():
            url, kind, method, json_body = _build_url(upstream, api_base, web_base)
            results[upstream] = await _probe_upstream(
                client, url, kind, method=method, json_body=json_body
            )

        return [_apply(o, results[o.upstream], ts) for o in ORGANS]
    finally:
        if owns_client:
            await client.aclose()
