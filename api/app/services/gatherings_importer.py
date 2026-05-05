"""Gatherings importer — scan presences for event listings, plant the missing ones.

Today, an event reaches the graph only when a contributor manually POSTs
``/api/presences/{id}/gatherings``. But many presences carry their event
listings on Bandsintown, Eventbrite, an iCal feed, or a generic
``/events`` page. Those listings never flow into the graph, so a
presence page reads "no upcoming gatherings" while its keeper runs a
retreat every weekend.

This worker closes the gap. For each presence node, it walks every URL
the node carries (``canonical_url`` plus everything in ``presences``),
asks the registered :mod:`event_sources` plugins which one can read
each URL, fetches the events the source publishes, and creates the
events that aren't already in the graph. Every imported event picks up
a ``contributes-to`` edge from the presence with ``role="primary"`` —
the same edge shape the manual gathering endpoint uses, so visitor
pages render imported gatherings exactly the same as hand-added ones.

The dedupe key is ``(name, when, where)`` against existing event nodes,
case-insensitive with whitespace collapsed. So an event added by hand
yesterday and the same event resurfaced from the source feed today
collapse onto one node — the graph stays one record per gathering, no
duplicates.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse

from app.services import graph_service
from app.services.event_sources import (
    EventSource,
    ImportedEvent,
    get_sources,
)

log = logging.getLogger(__name__)


# Hosts the importer skips silently because they need authenticated
# access. A presence page might link to a Facebook events tab; without
# a token that endpoint returns a login wall, not events. Marking
# these as known-skipped lets the visitor see *why* they didn't import
# rather than wondering if the worker just missed them.
_AUTH_REQUIRED_HOSTS = {"facebook.com", "m.facebook.com", "fb.com"}

# Per-host pacing — at least this many seconds between two requests
# to the same hostname. Most public sources are fine with one
# request per second; this keeps the importer a polite citizen even
# when a presence has many same-host URLs.
_HOST_INTERVAL_SECONDS = 1.0

# Max number of URLs we'll process per presence. Most presence nodes
# carry 5–10 URLs; this cap prevents a pathological page that listed
# dozens of platforms from spending the worker's whole budget.
_MAX_URLS_PER_PRESENCE = 32


def _normalize(s: str | None) -> str:
    """Lowercase + collapse whitespace — the dedupe key shape."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", s.strip().lower())


def _slugify(s: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]
    return slug or "gathering"


def _imported_event_id(name: str, when: str, where: str | None) -> str:
    """Stable id for an imported gathering, content-addressed.

    Two imports of the same event from the same or different sources
    collapse onto one node. Independent of who imported and when —
    only the gathering's identity matters."""
    seed = f"{_normalize(name)}|{_normalize(when)}|{_normalize(where)}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    return f"event:{_slugify(name)}-{digest}"


def _is_auth_required(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    if host.startswith("www."):
        host = host[4:]
    return any(host == bad or host.endswith("." + bad) for bad in _AUTH_REQUIRED_HOSTS)


def _gather_urls(node: dict[str, Any]) -> list[str]:
    """Every URL this presence carries — canonical + presences[].

    Ordered: canonical first (most authoritative), then platform
    presences in the order the resolver stored them. De-duplicated
    while preserving order.
    """
    urls: list[str] = []
    seen: set[str] = set()

    canonical = node.get("canonical_url")
    if isinstance(canonical, str) and canonical.strip():
        u = canonical.strip()
        urls.append(u)
        seen.add(u)

    presences = node.get("presences") or []
    if isinstance(presences, list):
        for p in presences:
            if isinstance(p, dict):
                u = p.get("url")
            elif isinstance(p, str):
                u = p
            else:
                u = None
            if isinstance(u, str) and u.strip() and u not in seen:
                urls.append(u.strip())
                seen.add(u)
            if len(urls) >= _MAX_URLS_PER_PRESENCE:
                break
    return urls


def _existing_event_for_key(
    name: str,
    when: str,
    where: str | None,
) -> dict[str, Any] | None:
    """Look for an event already in the graph that matches our dedupe key.

    Two paths: first the deterministic id (fastest — every imported
    event lands at the same id). Second, scan event nodes by the same
    normalized key tuple, so events created via the manual endpoint
    (which uses a different id scheme that includes the adder) still
    collapse onto the imported ones.
    """
    target_id = _imported_event_id(name, when, where)
    direct = graph_service.get_node(target_id)
    if direct:
        return direct

    target_key = (_normalize(name), _normalize(when), _normalize(where))
    page = graph_service.list_nodes(type="event", limit=500)
    for ev in page.get("items", []):
        ev_name = ev.get("name") or ""
        ev_when = ev.get("when") or ""
        ev_where = ev.get("where")
        if (_normalize(ev_name), _normalize(ev_when), _normalize(ev_where)) == target_key:
            return ev
    return None


def _link_primary(event_id: str, presence_id: str, created_by: str) -> None:
    """Lay the contributes-to edge from presence to event with role=primary.

    Same shape the manual gathering endpoint uses, so any UI that
    renders gatherings reads imported events identically to hand-added
    ones. Idempotent: ``create_edge_strict`` returns a duplicate marker
    instead of stacking edges on re-import.
    """
    graph_service.create_edge_strict(
        from_id=presence_id,
        to_id=event_id,
        type="contributes-to",
        properties={"kind": "event", "role": "primary"},
        strength=1.0,
        created_by=created_by,
    )


def _create_event_node(
    event: ImportedEvent,
    presence_id: str,
    source_name: str,
) -> dict[str, Any]:
    """Mint a new event node from an :class:`ImportedEvent`."""
    event_id = _imported_event_id(event.name, event.when, event.where)
    properties: dict[str, Any] = {
        "when": event.when or None,
        "where": event.where or None,
        "url": event.url or None,
        "note": event.description or None,
        "added_by": "gatherings_importer",
        "added_by_name": f"imported from {source_name}",
        "added_at": datetime.now(timezone.utc).isoformat(),
        "import_source": source_name,
        "import_origin_presence": presence_id,
    }
    properties = {k: v for k, v in properties.items() if v}
    return graph_service.create_node(
        id=event_id,
        type="event",
        name=event.name,
        description=event.description or event.name,
        properties=properties,
    )


def _select_source(url: str, sources: list[EventSource]) -> EventSource | None:
    for src in sources:
        try:
            if src.matches(url):
                return src
        except Exception:  # noqa: BLE001 — a misbehaving plugin can't kill the worker
            log.debug("source %s.matches raised on %s", src.name, url, exc_info=True)
    return None


def import_for_presence(
    node_id: str,
    *,
    sources: list[EventSource] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Walk every URL on a presence node, import every gathering we find.

    Returns a structured report with everything a caller (CLI, API
    endpoint, monitoring view) needs to understand what happened —
    which URLs matched, which sources fired, how many events were
    new vs deduped, and any errors.
    """
    node = graph_service.get_node(node_id)
    if not node:
        return {
            "node_id": node_id,
            "source_urls": [],
            "events_imported": 0,
            "events_skipped_dedupe": 0,
            "errors": [{"reason": "presence-not-found"}],
            "events": [],
            "skipped": [],
        }

    sources = sources or get_sources()
    urls = _gather_urls(node)

    events_imported = 0
    events_skipped_dedupe = 0
    matched_urls: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    imported_events: list[dict[str, Any]] = []

    last_request_at: dict[str, float] = defaultdict(lambda: 0.0)

    for url in urls:
        if _is_auth_required(url):
            skipped.append({"url": url, "reason": "facebook-needs-auth"})
            continue

        src = _select_source(url, sources)
        if src is None:
            continue

        # Per-host pacing — sleep until at least _HOST_INTERVAL_SECONDS
        # after the previous request to the same host.
        host = (urlparse(url).hostname or "").lower()
        now = time.monotonic()
        wait = _HOST_INTERVAL_SECONDS - (now - last_request_at[host])
        if wait > 0 and last_request_at[host] > 0:
            time.sleep(wait)

        try:
            fetched_events = src.fetch(url)
        except Exception as exc:  # noqa: BLE001 — record and continue
            errors.append({"url": url, "source": src.name, "reason": str(exc)})
            last_request_at[host] = time.monotonic()
            continue

        last_request_at[host] = time.monotonic()
        matched_urls.append({"url": url, "source": src.name, "fetched": len(fetched_events)})

        for ev in fetched_events:
            existing = _existing_event_for_key(ev.name, ev.when, ev.where)
            if existing:
                events_skipped_dedupe += 1
                if not dry_run:
                    _link_primary(existing["id"], node_id, created_by="gatherings_importer")
                continue
            if dry_run:
                events_imported += 1
                imported_events.append({
                    "id": _imported_event_id(ev.name, ev.when, ev.where),
                    "name": ev.name,
                    "when": ev.when,
                    "where": ev.where,
                    "source": src.name,
                    "dry_run": True,
                })
                continue
            event_node = _create_event_node(ev, node_id, src.name)
            _link_primary(event_node["id"], node_id, created_by="gatherings_importer")
            events_imported += 1
            imported_events.append({
                "id": event_node["id"],
                "name": event_node.get("name"),
                "when": event_node.get("when") or ev.when,
                "where": event_node.get("where") or ev.where,
                "source": src.name,
            })

    return {
        "node_id": node_id,
        "source_urls": matched_urls,
        "events_imported": events_imported,
        "events_skipped_dedupe": events_skipped_dedupe,
        "errors": errors,
        "skipped": skipped,
        "events": imported_events,
    }


def _presence_node_iter(limit: int | None) -> Iterable[dict[str, Any]]:
    """Yield presence-bucket nodes that carry at least one URL.

    A presence-bucket node is contributor / community / scene / event /
    asset — everything the gathering endpoint considers a presence. We
    skip nodes with no URLs at all because the importer would have
    nothing to read.
    """
    types = ("contributor", "community", "scene")
    yielded = 0
    for node_type in types:
        offset = 0
        page_size = 100
        while True:
            page = graph_service.list_nodes(type=node_type, limit=page_size, offset=offset)
            items = page.get("items") or []
            if not items:
                break
            for n in items:
                if not (n.get("canonical_url") or n.get("presences")):
                    continue
                yield n
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            if len(items) < page_size:
                break
            offset += page_size


def import_all(
    *,
    limit: int | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Run the importer over every presence node that carries any URL."""
    sources = get_sources()
    reports: list[dict[str, Any]] = []
    for node in _presence_node_iter(limit):
        report = import_for_presence(
            node["id"],
            sources=sources,
            dry_run=dry_run,
        )
        reports.append(report)
    return reports
