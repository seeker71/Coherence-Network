"""Event-source plugin registry — adapters for the world's event surfaces.

A presence carries gatherings on whatever surface its keeper already
tends — an iCal feed, a Bandsintown tour page, an Eventbrite organizer
profile, a generic /events page with Schema.org markup. Each surface
has its own grammar; each plugin in this package speaks one grammar
and returns the same shape: a list of :class:`ImportedEvent`.

The :func:`get_sources` helper returns every registered source. The
gatherings importer iterates them, asking each whether a URL matches,
and collecting events from every match. New surfaces (Songkick, Meetup,
Luma) become a new file in this package — no other code changes.
"""
from __future__ import annotations

from .base import EventSource, ImportedEvent
from .ical_source import IcalSource
from .bandsintown_source import BandsintownSource
from .eventbrite_source import EventbriteSource
from .html_scraper_source import HtmlScraperSource


def get_sources() -> list[EventSource]:
    """Return every registered event source in match-priority order.

    The HTML scraper is last because its match predicate is the
    broadest — it would otherwise eat URLs the more specific plugins
    handle better (Bandsintown JSON-LD has a richer shape than a raw
    `<script>` tag find).
    """
    return [
        IcalSource(),
        BandsintownSource(),
        EventbriteSource(),
        HtmlScraperSource(),
    ]


__all__ = [
    "EventSource",
    "ImportedEvent",
    "IcalSource",
    "BandsintownSource",
    "EventbriteSource",
    "HtmlScraperSource",
    "get_sources",
]
