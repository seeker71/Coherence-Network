"""Auto-import creations from a presence's known URLs.

A presence node — contributor, community, scene — carries a
``canonical_url`` and a ``presences`` list of cross-platform
URLs. This worker walks those URLs against every registered
:class:`CreationSource` and turns the matches into ``asset`` nodes
with ``contributes-to`` edges from the presence.

It mirrors the inspired-by resolver's persistence shape: same
node type (``asset``), same edge type (``contributes-to``), same
``creation_kind`` property. The renderer doesn't care whether a
creation came from inspired-by ingest, an explicit POST, or this
auto-importer.

Idempotent. Re-running on the same presence skips creations that
already exist (dedupe by name+kind+canonical URL).
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any
from urllib.parse import urlparse

from app.services import graph_service
from app.services.creation_sources import (
    CREATION_KINDS,
    CreationSource,
    ImportedCreation,
    SOURCES,
    is_valid_kind,
)
from app.services.inspired_by_service import (
    canonical_url_hash,
    canonicalize_url,
)


log = logging.getLogger(__name__)


# Presence types this worker walks. Other types (concept, idea, spec,
# etc.) don't carry creations and would only generate noise.
_PRESENCE_TYPES = ("contributor", "community", "scene", "network-org")

# Sampling discipline. The body of public work a presence has emitted
# is much larger than any single feed surfaces. Recency-biased feeds
# return latest-N; without discipline a presence's "spectrum" becomes
# whatever they happened to publish last week, not what they have
# emitted across their career.
#
# The discipline:
# - Per-source cap (`_PER_SOURCE_TARGET`) keeps any one platform from
#   dominating the presence's emitted spectrum.
# - When a source returns more than the cap, we stratify across the
#   returned ordering — oldest, newest, plus an evenly-spaced middle
#   sample — rather than truncating to first-N.
# - Coverage gaps are recorded on the contributor node so the body
#   knows where its sampling is thin and where the spectrum we're
#   drawing is partial.
_PER_SOURCE_TARGET = 30


def _stratify(items: list[Any], target: int) -> list[Any]:
    """Stratified sample across an ordered list.

    When ``items`` has at most ``target`` entries the whole list is
    returned. Otherwise the sample weaves four bands together:

    - Newest (head of the list, since most feeds are newest-first)
    - Oldest (tail of the list)
    - Evenly-spaced middle (career-spanning coverage)
    - Highest-loudness — top items by ``view_count`` when present

    The view-count band makes "general signal" — what a presence
    actually broadcast loudest into the field — visible in the
    sample even when those works fall outside the temporal bands.
    Items without a view count are skipped from that band only;
    they still participate in the temporal bands.

    Returns items in source order so dedupe keys stay stable.
    """
    n = len(items)
    if n <= target or target <= 0:
        return list(items)
    # Quarter-reserves so each band has weight without crowding out
    # the others. With target=30: 8 newest + 8 oldest + 8 by-views +
    # 6 evenly-spaced middle = 30.
    quarter = max(1, target // 4)
    newest = set(range(0, quarter))
    oldest = set(range(n - quarter, n))

    # Loudness band — sort indexes by view_count desc, take the top
    # `quarter` that aren't already in newest/oldest. When no view
    # counts are present this band collapses gracefully.
    def _vc(idx: int) -> int:
        item = items[idx]
        v = getattr(item, "view_count", None) if hasattr(item, "view_count") else (
            (item.get("view_count") if isinstance(item, dict) else None)
        )
        return v if isinstance(v, (int, float)) else -1
    by_loudness_sorted = sorted(range(n), key=lambda i: -_vc(i))
    loudest: set[int] = set()
    for idx in by_loudness_sorted:
        if _vc(idx) <= 0:
            break
        if idx in newest or idx in oldest:
            continue
        loudest.add(idx)
        if len(loudest) >= quarter:
            break

    middle_count = target - len(newest) - len(oldest) - len(loudest)
    middle: set[int] = set()
    if middle_count > 0:
        lo = quarter
        hi = n - quarter - 1
        if hi > lo:
            step = (hi - lo) / (middle_count + 1)
            for i in range(middle_count):
                idx = int(lo + step * (i + 1))
                if idx not in newest and idx not in oldest and idx not in loudest:
                    middle.add(idx)

    chosen = sorted(newest | oldest | loudest | middle)
    return [items[i] for i in chosen]


def _gather_source_urls(presence: dict[str, Any]) -> list[str]:
    """Read every URL on the presence node that a creation source
    might claim — canonical URL plus every entry in the presences
    list. De-duplicated, in original order."""
    urls: list[str] = []
    seen: set[str] = set()

    def _add(u: Any) -> None:
        if isinstance(u, str) and u.strip():
            cleaned = u.strip()
            if cleaned not in seen:
                seen.add(cleaned)
                urls.append(cleaned)

    _add(presence.get("canonical_url"))
    presences = presence.get("presences")
    if isinstance(presences, list):
        for entry in presences:
            if isinstance(entry, dict):
                _add(entry.get("url"))
            elif isinstance(entry, str):
                _add(entry)
    return urls


def _creation_node_id(creation: ImportedCreation, identity_id: str) -> str:
    """Deterministic id matching the inspired-by resolver's scheme:
    URL-hash when we have a URL, name-under-owner otherwise. Same
    URL → same asset, every time."""
    if creation.url:
        return f"asset:{canonical_url_hash(creation.url)}"
    seed = f"{identity_id}|{(creation.name or '').strip().lower()}|{creation.kind}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"asset:{digest}"


def _dedupe_key(creation: ImportedCreation) -> tuple[str, str, str]:
    """Triple used to recognise the same creation across runs.

    Name + kind + canonical URL. URL is canonicalized when present
    so utm/www variants collapse; falls back to empty string when
    a creation has no URL."""
    name = (creation.name or "").strip().lower()
    kind = (creation.kind or "").strip().lower()
    url = canonicalize_url(creation.url) if creation.url else ""
    return (name, kind, url)


def _existing_creation_keys(identity_id: str) -> set[tuple[str, str, str]]:
    """Return the dedupe keys for every creation already attached
    to ``identity_id`` via a ``contributes-to`` edge."""
    keys: set[tuple[str, str, str]] = set()
    edges = graph_service.list_edges(
        from_id=identity_id,
        edge_type="contributes-to",
        limit=500,
    )
    for edge in edges.get("items", []):
        to_id = edge.get("to_id")
        if not to_id:
            continue
        node = graph_service.get_node(to_id)
        if not node or node.get("type") != "asset":
            continue
        kind = node.get("creation_kind") or (
            edge.get("properties", {}).get("kind") if isinstance(edge.get("properties"), dict) else None
        )
        if not kind:
            continue
        url = node.get("canonical_url") or ""
        canonical = canonicalize_url(url) if url else ""
        keys.add(((node.get("name") or "").strip().lower(), str(kind).strip().lower(), canonical))
    return keys


def _ensure_creation(
    identity_id: str,
    creation: ImportedCreation,
    *,
    source_name: str,
) -> dict[str, Any]:
    """Persist one creation as an ``asset`` node + ``contributes-to``
    edge. Returns the node + edge dicts plus a flag for whether the
    edge pre-existed (so the importer can count skips correctly)."""
    node_id = _creation_node_id(creation, identity_id)
    existing = graph_service.get_node(node_id)
    if existing:
        node = existing
        node_created = False
    else:
        properties: dict[str, Any] = {
            "asset_type": "CONTENT",
            "creation_kind": creation.kind,
            "canonical_url": creation.url,
            "image_url": creation.image_url,
            "when": creation.when,
            "imported_from": source_name,
            "total_cost": "0",
            "claimable": True,
        }
        # View count carries the loudness this work broadcasts into
        # the field — used downstream to weight a presence's emitted
        # spectrum so a high-viewed TEDx talk emits more strongly
        # than a low-viewed behind-the-scenes clip. None when the
        # source can't read it (early-life videos, no-API platforms).
        if getattr(creation, "view_count", None) is not None:
            properties["view_count"] = creation.view_count
        node = graph_service.create_node(
            id=node_id,
            type="asset",
            name=creation.name,
            description=creation.description or creation.name,
            properties=properties,
            phase="ice",
        )
        node_created = True
    edge_result = graph_service.create_edge_strict(
        from_id=identity_id,
        to_id=node_id,
        type="contributes-to",
        properties={"kind": creation.kind, "role": "primary"},
        strength=1.0,
        created_by="creations_importer",
    )
    edge_existed = edge_result.get("error") == "edge_exists"

    # A presence's emitted frequency lives in its creations. Each
    # asset carries its own keyword spectrum (title, description),
    # so attune the new asset against vision concepts the moment it
    # enters the graph. The contributor's concept resonance then
    # composes from the union of their works rather than from the
    # contributor node's text alone — which for external presences
    # is often a shallow scaffold.
    if node_created:
        try:
            from app.services import resonance_service
            resonance_service.attune(node_id)
        except Exception:  # noqa: BLE001 — attune failure doesn't block import
            log.debug("auto-attune on creation import non-fatal", exc_info=True)

    return {
        "node": node,
        "node_created": node_created,
        "edge": edge_result if not edge_existed else None,
        "edge_existed": edge_existed,
        "source": source_name,
    }


def _matching_sources(url: str, *, only: str | None = None) -> list[CreationSource]:
    """Return the source plugins that claim this URL.

    The first matcher wins because :data:`SOURCES` is ordered from
    specific to generic — a Substack URL goes through the substack
    source, not the RSS fallback. ``only`` constrains the search to
    a named source for CLI invocations like ``--source bandcamp``.
    """
    for source in SOURCES:
        if only and source.name != only:
            continue
        if source.matches(url):
            return [source]
    return []


def import_for_presence(
    node_id: str,
    *,
    only_source: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Walk a presence's URLs, run matching sources, persist the
    creations.

    Returns a dict with the node id, the URLs that were inspected,
    counts of imported and skipped creations, and any per-URL errors.
    Idempotent: a second run with no new content imports zero.
    """
    presence = graph_service.get_node(node_id)
    if not presence:
        return {
            "node_id": node_id,
            "source_urls": [],
            "creations_imported": 0,
            "creations_skipped_dedupe": 0,
            "creations_skipped_invalid_kind": 0,
            "errors": [{"reason": "presence_not_found"}],
        }

    if presence.get("type") not in _PRESENCE_TYPES:
        return {
            "node_id": node_id,
            "source_urls": [],
            "creations_imported": 0,
            "creations_skipped_dedupe": 0,
            "creations_skipped_invalid_kind": 0,
            "errors": [{"reason": "unsupported_node_type", "type": presence.get("type")}],
        }

    source_urls = _gather_source_urls(presence)
    existing_keys = _existing_creation_keys(node_id) if not dry_run else set()
    seen_keys: set[tuple[str, str, str]] = set(existing_keys)

    imported: list[dict[str, Any]] = []
    dedupe_count = 0
    invalid_kind_count = 0
    errors: list[dict[str, Any]] = []

    coverage: dict[str, dict[str, Any]] = {}
    for url in source_urls:
        sources = _matching_sources(url, only=only_source)
        if not sources:
            continue
        for source in sources:
            try:
                creations = source.fetch(url)
            except Exception as exc:  # noqa: BLE001
                log.warning("creation source %s failed on %s: %s", source.name, url, exc)
                errors.append({"url": url, "source": source.name, "reason": "fetch_error"})
                continue
            # Sampling discipline — stratify across the full returned
            # ordering when the source surfaced more than the per-source
            # target. Records what we saw vs what we kept so the body
            # can sense its own coverage gaps later.
            returned_total = len(creations)
            creations = _stratify(creations, _PER_SOURCE_TARGET)
            entry = coverage.setdefault(
                source.name,
                {"returned": 0, "sampled": 0, "urls": []},
            )
            entry["returned"] += returned_total
            entry["sampled"] += len(creations)
            entry["urls"].append(url)
            for creation in creations:
                # Normalize kind at the import boundary. `is_valid_kind`
                # accepts case-insensitive input, but downstream the
                # renderer matches against the lowercase vocabulary
                # only — so a source returning "Book" would write a
                # node with creation_kind="Book" that the page silently
                # skips. Lowercase here, validate after, store after.
                if isinstance(creation.kind, str):
                    creation.kind = creation.kind.strip().lower()
                if not is_valid_kind(creation.kind):
                    invalid_kind_count += 1
                    log.info(
                        "creations_importer skipping invalid kind=%r from %s",
                        creation.kind, source.name,
                    )
                    continue
                key = _dedupe_key(creation)
                if key in seen_keys:
                    dedupe_count += 1
                    continue
                seen_keys.add(key)
                if dry_run:
                    imported.append({
                        "node": {
                            "id": _creation_node_id(creation, node_id),
                            "name": creation.name,
                            "creation_kind": creation.kind,
                            "canonical_url": creation.url,
                            "image_url": creation.image_url,
                        },
                        "node_created": True,
                        "edge_existed": False,
                        "source": source.name,
                        "dry_run": True,
                    })
                else:
                    result = _ensure_creation(
                        node_id, creation, source_name=source.name,
                    )
                    if result["edge_existed"]:
                        dedupe_count += 1
                    else:
                        imported.append(result)

    # Record the coverage map on the presence so the next run, the
    # rendering layer, and any humans looking at the data can sense
    # what's been sampled vs what each source returned. Keeps gaps
    # visible rather than silent.
    if not dry_run and coverage:
        from datetime import datetime, timezone
        try:
            graph_service.update_node(
                node_id,
                properties={
                    "creations_coverage": {
                        "by_source": coverage,
                        "total_returned": sum(c["returned"] for c in coverage.values()),
                        "total_sampled": sum(c["sampled"] for c in coverage.values()),
                        "per_source_target": _PER_SOURCE_TARGET,
                        "sampled_at": datetime.now(timezone.utc).isoformat(),
                    },
                },
            )
        except Exception:  # noqa: BLE001 — coverage record isn't load-bearing
            log.debug("coverage record write non-fatal", exc_info=True)

    return {
        "node_id": node_id,
        "source_urls": source_urls,
        "creations_imported": len(imported),
        "creations_skipped_dedupe": dedupe_count,
        "creations_skipped_invalid_kind": invalid_kind_count,
        "creations_coverage": coverage,
        "errors": errors,
        "imported": imported,
        "dry_run": dry_run,
    }


def import_all(
    *,
    only_source: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Walk every presence node in the graph and run
    :func:`import_for_presence` against each.

    ``limit`` caps the number of presences per type so callers can
    smoke-test on a small population. ``only_source`` restricts the
    plugin pool to one named source.
    """
    results: list[dict[str, Any]] = []
    for presence_type in _PRESENCE_TYPES:
        per_type_limit = 500 if limit is None else limit
        page = graph_service.list_nodes(type=presence_type, limit=per_type_limit)
        for presence in page.get("items", []):
            node_id = presence.get("id")
            if not node_id:
                continue
            results.append(
                import_for_presence(
                    node_id,
                    only_source=only_source,
                    dry_run=dry_run,
                )
            )
            if limit is not None and len(results) >= limit:
                return results
    return results
