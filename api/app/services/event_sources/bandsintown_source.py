"""Bandsintown source — extract events from JSON-LD on artist pages.

Bandsintown publishes Schema.org ``MusicEvent`` items inside one or
more ``<script type="application/ld+json">`` blocks on every artist
page. Each event has ``name``, ``startDate``, ``location.name``, and
``url`` — the four fields the graph needs.

Match predicate: ``bandsintown.com`` host with at least one path
segment (so the home page and search pages don't match — only
artist or event pages).
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse

import httpx

from .base import EventSource, ImportedEvent

log = logging.getLogger(__name__)

USER_AGENT = "Coherence-Network-GatheringsImporter/1.0 (+https://coherencycoin.com)"
FETCH_TIMEOUT = 8.0

_JSONLD_RE = re.compile(
    r'<script[^>]+type="application/ld\+json"[^>]*>(.+?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _walk_jsonld_events(payload: Any) -> list[dict[str, Any]]:
    """Yield every Event-shaped dict from a JSON-LD payload.

    The payload may be a single object, a list of objects, an
    ``@graph`` wrapping list, or nested under ``mainEntity``. Walks
    everything; collects anything whose ``@type`` ends with ``Event``
    (matches ``Event``, ``MusicEvent``, ``EducationEvent``, etc.).
    """
    found: list[dict[str, Any]] = []

    def _is_event(node: dict[str, Any]) -> bool:
        t = node.get("@type")
        if isinstance(t, list):
            return any(isinstance(x, str) and x.endswith("Event") for x in t)
        return isinstance(t, str) and t.endswith("Event")

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if _is_event(node):
                found.append(node)
            for v in node.values():
                _walk(v)
        elif isinstance(node, list):
            for v in node:
                _walk(v)

    _walk(payload)
    return found


def _location_string(loc: Any) -> str | None:
    """Render a Schema.org Place / location into a single-line string."""
    if not loc:
        return None
    if isinstance(loc, str):
        return loc.strip() or None
    if isinstance(loc, list):
        for item in loc:
            s = _location_string(item)
            if s:
                return s
        return None
    if isinstance(loc, dict):
        name = (loc.get("name") or "").strip()
        addr = loc.get("address")
        addr_str = ""
        if isinstance(addr, dict):
            parts = [
                addr.get("streetAddress"),
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("addressCountry"),
            ]
            addr_str = ", ".join(p.strip() for p in parts if isinstance(p, str) and p.strip())
        elif isinstance(addr, str):
            addr_str = addr.strip()
        if name and addr_str:
            return f"{name}, {addr_str}"
        return name or addr_str or None
    return None


def jsonld_events_from_html(html: str) -> list[ImportedEvent]:
    """Pull every Event JSON-LD block out of an HTML page.

    Public for the html_scraper plugin to share without a circular
    import; both Bandsintown and the generic scraper use the same
    Schema.org shape.
    """
    if not html:
        return []
    out: list[ImportedEvent] = []
    seen: set[tuple[str, str, str | None]] = set()
    for raw in _JSONLD_RE.findall(html):
        try:
            payload = json.loads(raw.strip())
        except (ValueError, TypeError):
            continue
        for ev in _walk_jsonld_events(payload):
            name = (ev.get("name") or "").strip()
            when = (ev.get("startDate") or ev.get("start_date") or "").strip()
            if not name or not when:
                continue
            where = _location_string(ev.get("location"))
            url = ev.get("url") if isinstance(ev.get("url"), str) else None
            description = ev.get("description") if isinstance(ev.get("description"), str) else None
            key = (name, when, where)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                ImportedEvent(
                    name=name,
                    when=when,
                    where=where,
                    url=url,
                    description=description,
                )
            )
    return out


class BandsintownSource:
    """Plugin: ``bandsintown.com/<artist>``."""

    name = "bandsintown"

    def matches(self, url: str) -> bool:
        if not url:
            return False
        host = (urlparse(url).netloc or "").lower()
        path = (urlparse(url).path or "").strip("/")
        return host.endswith("bandsintown.com") and bool(path)

    def fetch(self, url: str) -> list[ImportedEvent]:
        from app.services.inspired_by_service import _is_public_target  # noqa: PLC0415

        if not _is_public_target(url):
            return []
        try:
            with httpx.Client(
                timeout=FETCH_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
            ) as client:
                r = client.get(url)
                if not _is_public_target(str(r.url)):
                    return []
                if r.status_code >= 400:
                    return []
                return jsonld_events_from_html(r.text)
        except httpx.HTTPError as exc:
            log.debug("bandsintown fetch failed for %s: %s", url, exc)
            return []
