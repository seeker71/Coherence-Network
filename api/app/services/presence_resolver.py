"""Presence resolver — backfill image_url + tagline on existing graph nodes.

Every ``identity`` / ``contributor`` / ``community`` / ``network-org`` /
``interested-person`` node carries an ``image_url`` and a description
(tagline). The inspired-by resolver populates these once when a node
is first minted. Everything that landed before the resolver matured —
or whose canonical page was bare on the day of first capture — sits
in the graph with empty hero art and no tagline. This worker walks
the field, fetches every URL associated with each node (canonical_url
plus everything in ``presences[]``), reads og:image and og:description,
picks the strongest signal, and writes it back.

It's a re-runnable companion to the inspired-by resolver, not a
replacement: minting still happens through that path. This one tends
the body that already exists, and it tends every kind of presence —
musicians, teachers, communities, retreat centres, ceremonies — under
one shape.

Reuse over re-implement: the OG/JSON-LD parsing already lives in
``inspired_by_service._PageParser``. This module imports it so the
two resolvers stay in agreement on what an og:image is.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.services import graph_service, inspired_by_service

log = logging.getLogger(__name__)


USER_AGENT = "Coherence-Network-Resolver/1.0 (+https://coherencycoin.com)"
FETCH_TIMEOUT = 8.0
MAX_URLS_PER_NODE = 8
SAME_HOST_DELAY_S = 1.0


# Hosts that block server-side scraping. Their og tags are useless to
# us — fetching just burns a request and a citizenship hit. The data
# we want lives on the canonical page or the other platform URLs.
NO_SCRAPE_HOSTS: frozenset[str] = frozenset({
    "instagram.com",
    "www.instagram.com",
    "facebook.com",
    "www.facebook.com",
    "m.facebook.com",
    "tiktok.com",
    "www.tiktok.com",
})


# Node types this worker tends. The spec lists the four buckets that
# carry public-facing image_url + description; ``identity`` is the
# umbrella name in conversation, but the actual graph types are below.
RESOLVABLE_NODE_TYPES: frozenset[str] = frozenset({
    "contributor",
    "community",
    "network-org",
    "interested-person",
    # Sanctuaries, retreat centres, venues — already retyped to `scene`
    # by `graph_service`, so the resolver should walk them too. Without
    # this, places like Pyramids of Chi never get their og:image
    # picked up.
    "scene",
})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_no_scrape(url: str) -> bool:
    if not url:
        return False
    try:
        host = (urlparse(url).netloc or "").lower()
    except ValueError:
        return False
    if not host:
        return False
    if host in NO_SCRAPE_HOSTS:
        return True
    # Match subdomains too (e.g. someone.facebook.com)
    return any(
        host == bad or host.endswith("." + bad)
        for bad in NO_SCRAPE_HOSTS
    )


def _has_image(node: dict[str, Any]) -> bool:
    val = node.get("image_url")
    return isinstance(val, str) and val.strip() != ""


def _has_tagline(node: dict[str, Any]) -> bool:
    # Description is a first-class column; tagline can also live in
    # properties (the inspired-by resolver writes ``tagline`` there).
    # Either non-empty counts as "we already have something to show".
    desc = node.get("description")
    if isinstance(desc, str) and desc.strip() != "":
        return True
    tag = node.get("tagline")
    return isinstance(tag, str) and tag.strip() != ""


def _candidate_urls(node: dict[str, Any]) -> list[str]:
    """Build the ordered list of URLs to probe for og data.

    Canonical first (the entity's home), then every presence URL.
    Capped at MAX_URLS_PER_NODE so a single node with 20 platform
    presences doesn't burn a full minute of HTTP. Same URL is only
    fetched once.
    """
    urls: list[str] = []
    seen: set[str] = set()
    canonical = node.get("canonical_url")
    if isinstance(canonical, str) and canonical.strip():
        urls.append(canonical.strip())
        seen.add(canonical.strip())
    presences = node.get("presences") or []
    if isinstance(presences, list):
        for p in presences:
            if not isinstance(p, dict):
                continue
            u = p.get("url")
            if not isinstance(u, str):
                continue
            u = u.strip()
            if not u or u in seen:
                continue
            urls.append(u)
            seen.add(u)
            if len(urls) >= MAX_URLS_PER_NODE:
                break
    return urls[:MAX_URLS_PER_NODE]


def _fetch_html(url: str, client: httpx.Client) -> tuple[str, str] | None:
    """Return (final_url, html) or None on any failure. Never raises."""
    try:
        # SSRF guard — only hit public targets. Reuses the inspired-by
        # service's helper so the two resolvers refuse the same hosts.
        if not inspired_by_service._is_public_target(url):
            return None
        r = client.get(url)
        if r.status_code >= 400:
            return None
        if not inspired_by_service._is_public_target(str(r.url)):
            return None
        return str(r.url), r.text
    except (httpx.HTTPError, ValueError):
        return None
    except Exception:  # noqa: BLE001 — keep walking the graph
        log.debug("presence_resolver fetch error for %s", url, exc_info=True)
        return None


def _parse_og(url: str, client: httpx.Client) -> tuple[str | None, str | None]:
    """Fetch ``url`` and return (og_image, og_description).

    Either may be None when the page didn't carry the tag, the host
    was opaque (Instagram/Facebook/TikTok), or fetch failed.
    """
    if _is_no_scrape(url):
        return None, None
    fetched = _fetch_html(url, client)
    if not fetched:
        return None, None
    _, html = fetched
    parser = inspired_by_service._parse_html(html)
    image = parser.og.get("og:image") or parser.og.get("twitter:image")
    description = (
        parser.og.get("og:description")
        or parser.og.get("twitter:description")
        or parser.description
    )
    if isinstance(image, str):
        image = image.strip() or None
    else:
        image = None
    if isinstance(description, str):
        description = description.strip() or None
    else:
        description = None
    return image, description


def _pick_best(
    candidates: list[tuple[str, str | None, str | None]],
) -> tuple[str | None, str | None, str | None, str | None]:
    """From a list of (source_url, og_image, og_description), pick
    the first non-empty image AND the first non-empty cleaned tagline.
    Returns (image, image_source, tagline, tagline_source).

    Both picks are first-wins, not longest-wins: the spec calls
    canonical_url first, so the entity's own home page anchors both
    fields. A verbose YouTube About blurb shouldn't outrank the artist
    site's tight bio just because it has more characters.
    """
    image: str | None = None
    image_source: str | None = None
    tagline: str | None = None
    tagline_source: str | None = None
    for src, img, desc in candidates:
        if image is None and isinstance(img, str) and img.strip():
            image = img.strip()
            image_source = src
        if tagline is None and isinstance(desc, str) and desc.strip():
            cleaned = inspired_by_service._clean_tagline(desc)
            if cleaned:
                tagline = cleaned
                tagline_source = src
    return image, image_source, tagline, tagline_source


def resolve_one(
    node_id: str,
    *,
    force: bool = False,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Resolve one node's image_url + tagline. Returns a result dict.

    Schema:
      {
        "node_id": str,
        "image_resolved": bool,        # True if we wrote a new image_url
        "image_source": str | None,    # URL the image came from
        "tagline_resolved": bool,      # True if we wrote a new description
        "tagline_source": str | None,  # URL the description came from
        "skipped_reason": str | None,  # set when nothing was done
        "errors": list[str]            # per-URL fetch errors (debug aid)
      }

    Returns a ``skipped_reason`` (and writes nothing) when:
      · ``not_found`` — no node at that id
      · ``unsupported_type`` — node type isn't in RESOLVABLE_NODE_TYPES
      · ``already-resolved`` — both fields are populated and force=False
      · ``no_candidate_urls`` — no canonical_url and empty presences
      · ``no_signal`` — every URL came back empty
    """
    result: dict[str, Any] = {
        "node_id": node_id,
        "image_resolved": False,
        "image_source": None,
        "tagline_resolved": False,
        "tagline_source": None,
        "skipped_reason": None,
        "errors": [],
    }

    node = graph_service.get_node(node_id)
    if not node:
        result["skipped_reason"] = "not_found"
        return result

    node_type = node.get("type")
    if node_type not in RESOLVABLE_NODE_TYPES:
        result["skipped_reason"] = "unsupported_type"
        return result

    if not force and _has_image(node) and _has_tagline(node):
        result["skipped_reason"] = "already-resolved"
        return result

    urls = _candidate_urls(node)
    if not urls:
        result["skipped_reason"] = "no_candidate_urls"
        return result

    # Fetch each URL, throttling per-host so we behave on shared
    # platforms. Skip already-known no-scrape hosts so we don't even
    # try (and don't count it as an error).
    own_client = False
    if client is None:
        client = httpx.Client(
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
        )
        own_client = True

    candidates: list[tuple[str, str | None, str | None]] = []
    last_seen_at: dict[str, float] = {}
    try:
        for url in urls:
            if _is_no_scrape(url):
                continue
            host = (urlparse(url).netloc or "").lower()
            if host:
                last = last_seen_at.get(host)
                if last is not None:
                    elapsed = time.monotonic() - last
                    if elapsed < SAME_HOST_DELAY_S:
                        time.sleep(SAME_HOST_DELAY_S - elapsed)
            # Stamp the host clock BEFORE the fetch so a fetch that
            # raises still leaves the throttle armed. Earlier the
            # stamp was set only after a successful fetch — meaning
            # if the first URL on a host errored, the next URL on the
            # same host fetched immediately, which silently disabled
            # the 1s discipline for the rest of the run.
            if host:
                last_seen_at[host] = time.monotonic()
            try:
                image, description = _parse_og(url, client)
            except Exception as exc:  # noqa: BLE001 — never raise
                result["errors"].append(f"{url}: {exc.__class__.__name__}")
                continue
            if image is None and description is None:
                result["errors"].append(f"{url}: empty")
                continue
            candidates.append((url, image, description))
    finally:
        if own_client:
            client.close()

    if not candidates:
        result["skipped_reason"] = "no_signal"
        return result

    image, image_source, tagline, tagline_source = _pick_best(candidates)

    # What we'll actually write. Only fill in the missing piece(s)
    # unless force is set, so a re-resolve doesn't clobber a
    # human-curated tagline with a fresh og:description.
    updates_props: dict[str, Any] = {"last_resolved_at": _now_iso()}
    description_update: str | None = None

    if image and (force or not _has_image(node)):
        updates_props["image_url"] = image
        result["image_resolved"] = True
        result["image_source"] = image_source

    if tagline and (force or not _has_tagline(node)):
        # Description is a first-class column; tagline mirrors it in
        # properties so consumers reading either spot still see it.
        description_update = tagline
        updates_props["tagline"] = tagline
        result["tagline_resolved"] = True
        result["tagline_source"] = tagline_source

    # Even if we found nothing usable, stamp last_resolved_at so the
    # next walk knows we tried — but only when we touched the graph
    # for some reason. If we didn't actually find image or tagline,
    # don't write a timestamp-only update; let the next pass try.
    if not result["image_resolved"] and not result["tagline_resolved"]:
        result["skipped_reason"] = "no_signal"
        return result

    update_kwargs: dict[str, Any] = {"properties": updates_props}
    if description_update is not None:
        update_kwargs["description"] = description_update
    graph_service.update_node(node_id, **update_kwargs)

    return result


def resolve_all(
    *,
    limit: int | None = None,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Walk every node missing image_url or description and resolve it.

    When ``force=True``, also re-resolves nodes that already have both
    fields. ``limit`` caps the scan size — useful for partial backfills
    or one-pass sanity checks before committing to a full sweep.

    Returns a list of result dicts in walk order.
    """
    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    # Reuse a single httpx client across the walk so connection
    # keep-alive and DNS caching kick in. One worker, one socket pool.
    with httpx.Client(
        timeout=FETCH_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
    ) as client:
        for node_type in RESOLVABLE_NODE_TYPES:
            page_offset = 0
            page_size = 200
            while True:
                page = graph_service.list_nodes(
                    type=node_type, limit=page_size, offset=page_offset,
                )
                items = page.get("items", [])
                if not items:
                    break
                for node in items:
                    nid = node.get("id")
                    if not nid or nid in seen_ids:
                        continue
                    seen_ids.add(nid)
                    needs_image = not _has_image(node)
                    needs_tagline = not _has_tagline(node)
                    if not force and not needs_image and not needs_tagline:
                        continue
                    if limit is not None and len(results) >= limit:
                        return results
                    results.append(
                        resolve_one(nid, force=force, client=client),
                    )
                if len(items) < page_size:
                    break
                page_offset += page_size

    return results


def summarize(results: list[dict[str, Any]]) -> dict[str, int]:
    """Aggregate stats from a batch of resolve results."""
    scanned = len(results)
    resolved_image = sum(1 for r in results if r.get("image_resolved"))
    resolved_tagline = sum(1 for r in results if r.get("tagline_resolved"))
    skipped = sum(1 for r in results if r.get("skipped_reason"))
    return {
        "scanned": scanned,
        "resolved_image": resolved_image,
        "resolved_tagline": resolved_tagline,
        "skipped": skipped,
    }
