"""HTML scraper — fallback for any page with Schema.org Event JSON-LD.

Many independent teachers and venues run their own sites with an
``/events``, ``/calendar``, or ``/gatherings`` page. The good ones
publish Schema.org ``Event`` markup so search engines can read them;
this plugin reads the same markup.

Match predicate: URL path contains ``/events``, ``/calendar``, or
``/gatherings`` (case-insensitive). Pages without structured data
return an empty list silently — we don't try to scrape free-form
prose into events.
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

_EVENT_PATH_HINTS = ("/events", "/calendar", "/gatherings")


class HtmlScraperSource:
    """Plugin: any URL whose path looks like an events page."""

    name = "html"

    def matches(self, url: str) -> bool:
        if not url:
            return False
        path = (urlparse(url).path or "").lower()
        return any(hint in path for hint in _EVENT_PATH_HINTS)

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
            log.debug("html_scraper fetch failed for %s: %s", url, exc)
            return []
