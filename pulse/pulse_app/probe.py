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
from dataclasses import dataclass
from typing import Any, Iterable

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


async def _probe_upstream(
    client: httpx.AsyncClient, url: str, kind: str
) -> UpstreamResult:
    """Fetch one upstream once, return a shared UpstreamResult.

    `kind` is one of "json" (parse body into dict) or "text" (keep raw
    response text for content-marker checks). JSON responses for
    "text" upstreams still parse successfully; that's fine.

    We swallow all exceptions deliberately: a probe failure is a signal,
    not an error in the monitor.
    """
    start = time.perf_counter()
    try:
        resp = await client.get(url)
        elapsed = int((time.perf_counter() - start) * 1000)
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
    return Sample(
        ts=ts,
        organ=organ.name,
        ok=verdict.ok,
        latency_ms=result.latency_ms,
        detail=verdict.detail,
    )


def _build_url(upstream: str, api_base: str, web_base: str) -> tuple[str, str]:
    """Map an upstream label to (url, kind). See organs.py for the labels."""
    api = api_base.rstrip("/")
    web = web_base.rstrip("/")
    mapping: dict[str, tuple[str, str]] = {
        "api_health": (f"{api}/api/health", "json"),
        "api_ready": (f"{api}/api/ready", "json"),
        "api_ideas": (f"{api}/api/ideas", "json"),
        "api_vitality": (f"{api}/api/workspaces/coherence-network/vitality", "json"),
        "web_root": (f"{web}/", "text"),
        "web_pulse": (f"{web}/pulse", "text"),
        "web_vitality": (f"{web}/vitality", "text"),
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
            url, kind = _build_url(upstream, api_base, web_base)
            results[upstream] = await _probe_upstream(client, url, kind)

        return [_apply(o, results[o.upstream], ts) for o in ORGANS]
    finally:
        if owns_client:
            await client.aclose()
