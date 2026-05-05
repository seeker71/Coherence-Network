"""Eventbrite source — JSON-LD on organizer and event pages.

Eventbrite serves Schema.org ``Event`` markup on every ``/e/...`` and
``/o/...`` URL. Organizer pages list the upcoming events; event pages
detail one. Both forms parse via the same JSON-LD extractor as
Bandsintown, so this plugin re-uses
:func:`jsonld_events_from_html`.

Match predicate: ``eventbrite.com`` (or country variants) with a path
that begins with ``/e/`` or ``/o/``.
"""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx

from .bandsintown_source import jsonld_events_from_html
from .base import EventSource, ImportedEvent

log = logging.getLogger(__name__)

USER_AGENT = "Coherence-Network-GatheringsImporter/1.0 (+https://coherencycoin.com)"
FETCH_TIMEOUT = 8.0


class EventbriteSource:
    """Plugin: ``eventbrite.com/e/<event>`` or ``/o/<organizer>``."""

    name = "eventbrite"

    def matches(self, url: str) -> bool:
        if not url:
            return False
        p = urlparse(url)
        host = (p.netloc or "").lower()
        path = (p.path or "").lower()
        if not host:
            return False
        if "eventbrite." not in host:
            return False
        return path.startswith("/e/") or path.startswith("/o/")

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
            log.debug("eventbrite fetch failed for %s: %s", url, exc)
            return []
