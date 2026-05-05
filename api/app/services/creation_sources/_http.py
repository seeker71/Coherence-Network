"""Shared HTTP discipline for creation-source plugins.

Every source uses the same User-Agent, the same 10-second timeout,
and the same per-host throttle (one request per host per second).
4xx and 5xx responses return ``None`` silently — a creation source
never raises on a failed fetch, the worker just gets fewer
creations from that source.

The throttle is process-local. The full worker run normally pulls
from many distinct hosts, so the throttle only bites when the
same source is invoked twice in close succession (e.g. the
Bandcamp source pivoting from a redirect to ``/music``). It's a
gentle sleep, not a hard rate-limit, so tests that mock
``safe_get`` are unaffected.
"""
from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

import httpx


log = logging.getLogger(__name__)

USER_AGENT = (
    "Coherence-Network-CreationsImporter/1.0 (+https://coherencycoin.com)"
)
TIMEOUT_SECONDS = 10.0
PER_HOST_SLEEP_SECONDS = 1.0


# Last fetch timestamp per host so successive same-host calls space
# themselves at least PER_HOST_SLEEP_SECONDS apart.
_LAST_HIT: dict[str, float] = {}


def _throttle(host: str) -> None:
    last = _LAST_HIT.get(host)
    now = time.monotonic()
    if last is not None:
        elapsed = now - last
        if elapsed < PER_HOST_SLEEP_SECONDS:
            time.sleep(PER_HOST_SLEEP_SECONDS - elapsed)
    _LAST_HIT[host] = time.monotonic()


def safe_get(url: str, *, accept: str = "text/html,*/*;q=0.8") -> tuple[str, str] | None:
    """Fetch ``url`` and return ``(final_url, body)`` or ``None``.

    Silent on every failure — 4xx, 5xx, network errors, redirect to
    a host we can't resolve. The worker's job is to absorb fewer
    creations on a bad source, not to surface stack traces.

    SSRF-safe: the URL host is resolved against ``_is_public_target``
    (the same guard the inspired-by resolver uses) before AND after
    redirect, so an attacker who plants ``http://169.254.169.254``
    (cloud metadata) on their own presence node can't drive the
    FastAPI host into fetching internal endpoints. Imported lazily so
    the symbol stays close to its single canonical source."""
    from app.services.inspired_by_service import _is_public_target  # noqa: PLC0415

    if not _is_public_target(url):
        log.debug("creation-source rejected non-public target: %s", url)
        return None
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return None
    if host:
        _throttle(host)
    try:
        with httpx.Client(
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": accept,
            },
        ) as client:
            r = client.get(url)
            # Re-check after redirects — a 302 to 169.254.169.254 must
            # still be refused.
            if not _is_public_target(str(r.url)):
                log.debug("creation-source rejected post-redirect target: %s", r.url)
                return None
            if r.status_code >= 400:
                return None
            return str(r.url), r.text
    except httpx.HTTPError as exc:
        log.debug("creation-source fetch failed: %s (%s)", url, exc)
        return None


def reset_throttle_for_tests() -> None:
    """Clear the per-host throttle. Tests that simulate many fetches
    against the same host want to skip the real-world sleep."""
    _LAST_HIT.clear()
