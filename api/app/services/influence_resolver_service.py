"""Influence resolver — turn a paste (URL or bare name) into a graph node.

The gesture: someone names an influence — a teacher, an artist, a
festival, a dance floor — and the system makes a place for them. Their
node is claimable by the real person or collective; until they show
up, the node simply waits with the canonical link attached.

Resolution flow
---------------
1. ``resolve(input)`` accepts any string.
2. If the input parses as a URL, fetch it directly. Otherwise, search
   the open web for the best match and recurse on the top hit.
3. Parse OpenGraph + JSON-LD + ``<meta>`` to extract: name,
   description, image, canonical_url. Infer node_type from hostname.
4. ``import_influence(source_id, resolved)`` writes a node (idempotent
   on canonical_url) and an ``inspired-by`` edge from the source.

Provider awareness is kept thin on purpose: hostname → node_type +
provider name. Richer per-provider scrapes (Spotify discography,
YouTube uploads) can layer in later as plugins; nothing here blocks
that.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx

from app.services import graph_service

log = logging.getLogger(__name__)

USER_AGENT = (
    "CoherenceNetwork-InfluenceResolver/1.0 "
    "(+https://coherencycoin.com)"
)
FETCH_TIMEOUT = 8.0
SEARCH_TIMEOUT = 6.0

# Hostname → (node_type, provider) inference. The keys are matched as
# suffixes of the hostname, so "music.youtube.com" matches "youtube.com".
HOST_HINTS: list[tuple[str, str, str]] = [
    # (hostname suffix, node_type, provider)
    ("youtube.com", "contributor", "youtube"),
    ("youtu.be", "contributor", "youtube"),
    ("bandcamp.com", "contributor", "bandcamp"),
    ("spotify.com", "contributor", "spotify"),
    ("soundcloud.com", "contributor", "soundcloud"),
    ("apple.com", "contributor", "apple-music"),
    ("music.apple.com", "contributor", "apple-music"),
    ("substack.com", "contributor", "substack"),
    ("patreon.com", "contributor", "patreon"),
    ("instagram.com", "contributor", "instagram"),
    ("twitter.com", "contributor", "twitter"),
    ("x.com", "contributor", "twitter"),
    ("eventbrite.com", "community", "eventbrite"),
    ("eventbrite.co.uk", "community", "eventbrite"),
    ("songkick.com", "community", "songkick"),
    ("meetup.com", "community", "meetup"),
    ("facebook.com/events", "community", "facebook"),
]

DEFAULT_NODE_TYPE = "contributor"


@dataclass
class ResolvedInfluence:
    """The structured result of resolving a free-text input."""
    input: str
    name: str
    description: str
    canonical_url: str
    provider: str
    provider_id: str
    node_type: str
    image_url: str | None = None
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def node_id(self) -> str:
        """Stable, slugged node id derived from canonical_url."""
        digest = hashlib.sha256(self.canonical_url.encode("utf-8")).hexdigest()[:12]
        slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")[:40] or "influence"
        return f"{self.node_type}:{slug}-{digest}"


class _OpenGraphParser(HTMLParser):
    """Extract OpenGraph, Twitter card, JSON-LD, and basic meta tags."""

    def __init__(self) -> None:
        super().__init__()
        self.og: dict[str, str] = {}
        self.title: str | None = None
        self.description: str | None = None
        self.canonical: str | None = None
        self.json_ld_chunks: list[str] = []
        self._capture_title: bool = False
        self._capture_jsonld: bool = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            prop = a.get("property") or a.get("name")
            content = a.get("content")
            if not prop or content is None:
                return
            prop = prop.lower()
            if prop.startswith("og:") or prop.startswith("twitter:"):
                self.og[prop] = content
            elif prop == "description":
                self.description = self.description or content
        elif tag == "link" and a.get("rel", "").lower() == "canonical":
            self.canonical = a.get("href")
        elif tag == "title":
            self._capture_title = True
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._capture_jsonld = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._capture_title = False
        elif tag == "script" and self._capture_jsonld:
            self._capture_jsonld = False

    def handle_data(self, data: str) -> None:
        if self._capture_title and not self.title:
            t = data.strip()
            if t:
                self.title = t
        elif self._capture_jsonld:
            self.json_ld_chunks.append(data)


def _is_url(s: str) -> bool:
    s = s.strip()
    if " " in s or "\n" in s:
        return False
    parsed = urlparse(s if "://" in s else f"https://{s}")
    return bool(parsed.netloc) and "." in parsed.netloc


def _normalize_url(url: str) -> str:
    """Drop fragments and trailing slashes; keep query."""
    p = urlparse(url if "://" in url else f"https://{url}")
    path = p.path.rstrip("/")
    return urlunparse((p.scheme or "https", p.netloc.lower(), path, "", p.query, ""))


def _infer_type_and_provider(url: str) -> tuple[str, str]:
    p = urlparse(url)
    host = (p.netloc or "").lower()
    path = p.path.lower()
    for suffix, node_type, provider in HOST_HINTS:
        # Allow path-aware hints like "facebook.com/events"
        if "/" in suffix:
            host_part, path_part = suffix.split("/", 1)
            if host.endswith(host_part) and path.startswith(f"/{path_part}"):
                return node_type, provider
        elif host.endswith(suffix):
            return node_type, provider
    return DEFAULT_NODE_TYPE, host or "web"


def _extract_provider_id(url: str, provider: str) -> str:
    """Best-effort extraction of a stable id from the URL path."""
    p = urlparse(url)
    path = p.path.strip("/")
    if not path:
        return p.netloc.lower()
    parts = path.split("/")
    # YouTube channel/handle, Bandcamp subdomain, Spotify track id, etc.
    if provider == "youtube" and parts[0] in ("channel", "user", "c"):
        return parts[1] if len(parts) > 1 else parts[0]
    if provider == "youtube" and parts[0].startswith("@"):
        return parts[0]
    if provider == "spotify" and len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}"
    if provider == "bandcamp":
        return p.netloc.lower().split(".")[0]
    return parts[-1] or path


def _fetch(url: str) -> tuple[str, str] | None:
    """Fetch a URL and return (final_url, html). None on failure."""
    try:
        with httpx.Client(
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
        ) as client:
            r = client.get(url)
            if r.status_code >= 400:
                log.info("influence_resolver fetch %s -> %s", url, r.status_code)
                return None
            return str(r.url), r.text
    except httpx.HTTPError as exc:
        log.info("influence_resolver fetch %s failed: %s", url, exc)
        return None


def _parse_html(html: str) -> _OpenGraphParser:
    parser = _OpenGraphParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 — malformed HTML is the norm
        log.debug("influence_resolver html parse non-fatal error", exc_info=True)
    return parser


def _ddg_first_result(query: str) -> str | None:
    """Use DuckDuckGo's HTML endpoint to find the most relevant URL.

    No API key required. We parse the HTML and pick the first ``a.result__a``
    href, then strip DDG's redirect wrapper if present.
    """
    try:
        with httpx.Client(
            timeout=SEARCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            r = client.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
            )
            if r.status_code >= 400:
                return None
            html = r.text
    except httpx.HTTPError:
        return None

    # Pick the first result anchor. DDG wraps URLs in /l/?uddg=<encoded>.
    m = re.search(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"',
        html,
    )
    if not m:
        return None
    href = m.group(1)
    if "uddg=" in href:
        from urllib.parse import parse_qs, urlparse as _u
        q = parse_qs(_u(href).query)
        if "uddg" in q:
            return q["uddg"][0]
    return href


def resolve(input_text: str) -> ResolvedInfluence | None:
    """Resolve any free-text input to a ResolvedInfluence.

    Returns None if the resolver cannot find a usable canonical URL or
    extract a name. Callers should treat None as a soft failure
    (worth surfacing to the visitor; not an exception).
    """
    text = (input_text or "").strip()
    if not text:
        return None

    # 1. Find the URL we'll trust as canonical.
    if _is_url(text):
        target = text if "://" in text else f"https://{text}"
    else:
        target = _ddg_first_result(text)
        if not target:
            return None

    fetched = _fetch(target)
    if not fetched:
        return None
    final_url, html = fetched
    parsed = _parse_html(html)

    canonical = parsed.canonical or parsed.og.get("og:url") or final_url
    canonical = _normalize_url(canonical)
    name = (
        parsed.og.get("og:site_name")
        or parsed.og.get("og:title")
        or parsed.og.get("twitter:title")
        or parsed.title
        or text
    ).strip()
    description = (
        parsed.og.get("og:description")
        or parsed.og.get("twitter:description")
        or parsed.description
        or ""
    ).strip()
    image = (
        parsed.og.get("og:image")
        or parsed.og.get("twitter:image")
    )
    node_type, provider = _infer_type_and_provider(canonical)
    provider_id = _extract_provider_id(canonical, provider)

    raw = {"og": parsed.og, "title": parsed.title}
    return ResolvedInfluence(
        input=text,
        name=name[:200],
        description=description[:500],
        canonical_url=canonical,
        provider=provider,
        provider_id=provider_id,
        node_type=node_type,
        image_url=image,
        raw_metadata=raw,
    )


def find_existing_node(canonical_url: str) -> dict[str, Any] | None:
    """Look up an already-imported influence by its canonical URL.

    We scan candidate node types because the same canonical_url should
    only ever map to one node, regardless of inferred type.
    """
    for node_type in ("contributor", "community", "network-org", "asset"):
        result = graph_service.list_nodes(type=node_type, limit=500)
        for node in result.get("items", []):
            if node.get("canonical_url") == canonical_url:
                return node
    return None


def _normalize_contributor_id(contributor_id: str) -> str:
    """Accept either the bare slug (`alice-abc12`) or the full node id
    (`contributor:alice-abc12`); always return the full node id."""
    cid = contributor_id.strip()
    return cid if cid.startswith("contributor:") else f"contributor:{cid}"


def import_influence(
    source_contributor_id: str,
    resolved: ResolvedInfluence,
) -> dict[str, Any]:
    """Create (or find) the influence node and the inspired-by edge.

    Idempotent: re-importing the same canonical_url returns the existing
    node and creates the edge only if missing.
    """
    source_contributor_id = _normalize_contributor_id(source_contributor_id)
    existing = find_existing_node(resolved.canonical_url)
    if existing:
        node_id = existing["id"]
        node = existing
        node_created = False
    else:
        node_id = resolved.node_id()
        properties = {
            "tagline": resolved.description,
            "canonical_url": resolved.canonical_url,
            "provider": resolved.provider,
            "provider_id": resolved.provider_id,
            "image_url": resolved.image_url,
            "claimable": True,
            "imported_by": source_contributor_id,
            "import_input": resolved.input,
        }
        # Contributor nodes need a placeholder email so the typed
        # /api/contributors endpoint can render them without coercion.
        if resolved.node_type == "contributor":
            properties.update({
                "contributor_type": "HUMAN",
                "email": f"{resolved.provider_id}@unclaimed.coherence.network",
                "author_display_name": resolved.name,
            })
        node = graph_service.create_node(
            id=node_id,
            type=resolved.node_type,
            name=resolved.name,
            description=resolved.description,
            properties=properties,
        )
        node_created = True

    # Edge: source --inspired-by--> node
    edge_result = graph_service.create_edge_strict(
        from_id=source_contributor_id,
        to_id=node_id,
        type="inspired-by",
        properties={"input": resolved.input},
        strength=1.0,
        created_by="influence_resolver",
    )
    edge_existed = edge_result.get("error") == "edge_exists"

    return {
        "node": node,
        "node_created": node_created,
        "edge": edge_result if not edge_existed else None,
        "edge_existed": edge_existed,
        "resolved": {
            "input": resolved.input,
            "name": resolved.name,
            "description": resolved.description,
            "canonical_url": resolved.canonical_url,
            "provider": resolved.provider,
            "provider_id": resolved.provider_id,
            "node_type": resolved.node_type,
            "image_url": resolved.image_url,
        },
    }


def list_influences(source_contributor_id: str) -> list[dict[str, Any]]:
    """Return all nodes the source contributor is inspired-by, with edge ids."""
    source_contributor_id = _normalize_contributor_id(source_contributor_id)
    edges = graph_service.list_edges(
        from_id=source_contributor_id,
        edge_type="inspired-by",
        limit=500,
    )
    items: list[dict[str, Any]] = []
    for edge in edges.get("items", []):
        node = graph_service.get_node(edge["to_id"])
        if not node:
            continue
        items.append({
            "edge_id": edge["id"],
            "node": node,
            "created_at": edge.get("created_at"),
        })
    return items


def remove_influence_edge(edge_id: str) -> bool:
    """Remove an inspired-by edge. Node is intentionally left in place
    so it stays available for the real person to claim."""
    return graph_service.delete_edge(edge_id)
