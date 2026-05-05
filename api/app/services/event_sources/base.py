"""Plugin shape — every event source returns the same envelope.

An :class:`ImportedEvent` is the smallest thing the gatherings importer
needs to decide whether an event already exists in the graph and, if
not, what to write into it. Anything richer (lineup, tags, ticket
links) is dropped on purpose — the graph stores presence-and-context,
not the source's full record. Visitors who want the full detail click
through via the event ``url``.

Each :class:`EventSource` is a small Protocol — duck-typed plugins
that the registry instantiates once. Two methods carry the contract:

* ``matches(url)`` — cheap predicate. Hostname check, suffix check,
  path-segment check. No HTTP. Allowed to be conservative; the
  importer asks every source.
* ``fetch(url)`` — does the network work. Returns whatever events it
  found, or an empty list on any soft failure (timeout, 4xx, malformed
  payload). Hard failures raise; the importer logs them per-URL and
  keeps walking.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ImportedEvent:
    """One gathering, normalized for the graph.

    ``when`` is ISO 8601 when the source provides a structured date
    (most do — iCal DTSTART, JSON-LD startDate). When the source only
    has free text ("Spring 2026", "Every Friday"), we keep it as-is —
    the event still threads into the graph and the visitor reads what
    was published.

    ``where`` is the venue or city as the source presents it. The
    graph doesn't try to geocode here; the user-facing page renders
    whatever string comes through.

    ``url`` is the canonical event link — usually back to the source
    (Bandsintown event page, Eventbrite ticket page, ICS UID URL). The
    presence page surfaces this so a visitor can click straight to the
    place that owns the listing.
    """
    name: str
    when: str
    where: str | None = None
    url: str | None = None
    description: str | None = None


@runtime_checkable
class EventSource(Protocol):
    """A source surface — iCal, Bandsintown, Eventbrite, generic HTML."""

    name: str

    def matches(self, url: str) -> bool:
        """Cheap predicate — does this plugin know how to read this URL?"""
        ...

    def fetch(self, url: str) -> list[ImportedEvent]:
        """Pull events from the URL. Returns [] on soft failure."""
        ...
