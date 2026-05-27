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


_SLOW_PREFIX = "slow: "


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
    # Post-verdict threshold check: a probe that passed content assertions
    # can still be "slow" — detail is set but ok stays True. The current
    # status then reads as "strained" via status_from_last_sample while
    # the historical uptime stays at 100% (nothing was wrong, just slow).
    if (
        verdict.ok
        and organ.latency_threshold_ms
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
    api = api_base.rstrip("/")
    web = web_base.rstrip("/")
    mapping: dict[str, tuple[str, str, str, dict[str, Any] | None]] = {
        "api_health": (f"{api}/api/health", "json", "GET", None),
        "api_ready": (f"{api}/api/ready", "json", "GET", None),
        "api_ideas": (f"{api}/api/ideas", "json", "GET", None),
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
