"""HTTP probes — one shared round-trip per upstream, fanned out to organs.

We are gentle on the network we watch. Rather than hitting six endpoints to
get six organ samples, we hit three upstreams (/api/health, /api/ready, /)
and apply each organ's extractor to the shared response.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from pulse_app.organs import (
    ORGANS,
    UPSTREAM_API_HEALTH,
    UPSTREAM_API_READY,
    UPSTREAM_WEB_ROOT,
    Organ,
    organs_for_upstream,
)
from pulse_app.storage import Sample, iso_utc


# Per-upstream result of one probe attempt, shared across organs.
@dataclass(frozen=True)
class UpstreamResult:
    status: int              # HTTP status, or 0 on network error
    body: dict[str, Any] | None
    latency_ms: int
    error: str | None        # transport error text, or None


async def _probe_upstream(
    client: httpx.AsyncClient, url: str, parse_json: bool
) -> UpstreamResult:
    """Fetch one upstream once, return a shared UpstreamResult.

    We swallow all exceptions deliberately: a probe failure is a signal,
    not an error in the monitor.
    """
    start = time.perf_counter()
    try:
        resp = await client.get(url)
        elapsed = int((time.perf_counter() - start) * 1000)
        body: dict[str, Any] | None = None
        if parse_json:
            try:
                raw = resp.json()
                if isinstance(raw, dict):
                    body = raw
            except Exception:
                body = None
        return UpstreamResult(
            status=resp.status_code, body=body, latency_ms=elapsed, error=None
        )
    except httpx.HTTPError as exc:
        elapsed = int((time.perf_counter() - start) * 1000)
        return UpstreamResult(
            status=0, body=None, latency_ms=elapsed, error=_short_error(exc)
        )
    except Exception as exc:  # pragma: no cover — defensive
        elapsed = int((time.perf_counter() - start) * 1000)
        return UpstreamResult(
            status=0, body=None, latency_ms=elapsed, error=_short_error(exc)
        )


def _short_error(exc: BaseException) -> str:
    text = str(exc) or exc.__class__.__name__
    return text[:200]


def _apply(organ: Organ, result: UpstreamResult, ts: str) -> Sample:
    if result.error is not None:
        return Sample(
            ts=ts,
            organ=organ.name,
            ok=False,
            latency_ms=result.latency_ms,
            detail=result.error,
        )
    verdict = organ.extractor(result.status, result.body)
    return Sample(
        ts=ts,
        organ=organ.name,
        ok=verdict.ok,
        latency_ms=result.latency_ms,
        detail=verdict.detail,
    )


async def probe_all(
    api_base: str, web_base: str, client: httpx.AsyncClient | None = None
) -> list[Sample]:
    """Run one round of probes for every organ.

    Returns a list of samples in ORGANS order, all tagged with the same ts.
    """
    ts = iso_utc()
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, connect=5.0),
            follow_redirects=True,
            headers={"User-Agent": "pulse-monitor/0.1 (+https://coherencycoin.com)"},
        )
    try:
        api_health_url = f"{api_base.rstrip('/')}/api/health"
        api_ready_url = f"{api_base.rstrip('/')}/api/ready"
        web_root_url = f"{web_base.rstrip('/')}/"

        # Only call upstreams that actually have organs pointing at them.
        results: dict[str, UpstreamResult] = {}
        if organs_for_upstream(UPSTREAM_API_HEALTH):
            results[UPSTREAM_API_HEALTH] = await _probe_upstream(
                client, api_health_url, parse_json=True
            )
        if organs_for_upstream(UPSTREAM_API_READY):
            results[UPSTREAM_API_READY] = await _probe_upstream(
                client, api_ready_url, parse_json=True
            )
        if organs_for_upstream(UPSTREAM_WEB_ROOT):
            results[UPSTREAM_WEB_ROOT] = await _probe_upstream(
                client, web_root_url, parse_json=False
            )

        return [_apply(o, results[o.upstream], ts) for o in ORGANS]
    finally:
        if owns_client:
            await client.aclose()
