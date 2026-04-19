"""Inspired-by resolver — turn a name (or URL) into a small subgraph.

This is how someone highlights the people, communities, and places
that made them — the lineage of who and what they're inspired by.
From one string, three things come back:

  · **identity**   — a graph node keyed to a canonical URL
  · **presences**  — every platform the identity shows up on
                     (YouTube, Bandcamp, Spotify, IG, personal site…)
                     collected from external links on the canonical
                     page. Stored on the identity node as a list.
  · **creations**  — albums, tracks, videos, events parsed from
                     JSON-LD / OpenGraph. Each becomes an asset node
                     with a ``contributes-to`` edge from the identity.

The ``inspired-by`` edge from the source contributor to the identity
carries a weight that emerges from what was found: richer discovery,
stronger edge. Nothing here is set by fiat — the number comes from
the signals.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from app.services import graph_service

log = logging.getLogger(__name__)

USER_AGENT = (
    "CoherenceNetwork-InspiredBy/1.0 (+https://coherencycoin.com)"
)
FETCH_TIMEOUT = 8.0
SEARCH_TIMEOUT = 6.0

# Hostname → (node_type, provider) inference. Keys match as suffixes.
HOST_HINTS: list[tuple[str, str, str]] = [
    ("facebook.com/events", "community", "facebook"),
    ("youtube.com", "contributor", "youtube"),
    ("youtu.be", "contributor", "youtube"),
    ("bandcamp.com", "contributor", "bandcamp"),
    ("spotify.com", "contributor", "spotify"),
    ("soundcloud.com", "contributor", "soundcloud"),
    ("music.apple.com", "contributor", "apple-music"),
    ("substack.com", "contributor", "substack"),
    ("patreon.com", "contributor", "patreon"),
    ("instagram.com", "contributor", "instagram"),
    ("tiktok.com", "contributor", "tiktok"),
    ("twitter.com", "contributor", "x"),
    ("x.com", "contributor", "x"),
    ("eventbrite.com", "community", "eventbrite"),
    ("eventbrite.co.uk", "community", "eventbrite"),
    ("songkick.com", "community", "songkick"),
    ("meetup.com", "community", "meetup"),
    ("wikipedia.org", "contributor", "wikipedia"),
]

# Providers recognized as "presences" when linked from a canonical page.
# Ordered — earlier entries are stronger signals.
PRESENCE_PROVIDERS: list[tuple[str, str]] = [
    ("bandcamp.com", "bandcamp"),
    ("spotify.com", "spotify"),
    ("music.apple.com", "apple-music"),
    ("soundcloud.com", "soundcloud"),
    ("youtube.com", "youtube"),
    ("youtu.be", "youtube"),
    ("substack.com", "substack"),
    ("patreon.com", "patreon"),
    ("instagram.com", "instagram"),
    ("tiktok.com", "tiktok"),
    ("twitter.com", "x"),
    ("x.com", "x"),
    ("facebook.com", "facebook"),
    ("linktr.ee", "linktree"),
    ("wikipedia.org", "wikipedia"),
]

DEFAULT_NODE_TYPE = "contributor"
MAX_PRESENCES = 10
MAX_CREATIONS = 8


@dataclass
class Presence:
    provider: str
    url: str


@dataclass
class Creation:
    kind: str  # "album" | "track" | "video" | "event" | "book" | "work"
    name: str
    url: str | None = None
    image_url: str | None = None


@dataclass
class ResolvedIdentity:
    """The subgraph a single input resolves into."""
    input: str
    name: str
    description: str
    canonical_url: str
    provider: str
    provider_id: str
    node_type: str
    image_url: str | None = None
    presences: list[Presence] = field(default_factory=list)
    creations: list[Creation] = field(default_factory=list)

    def node_id(self) -> str:
        digest = hashlib.sha256(self.canonical_url.encode("utf-8")).hexdigest()[:12]
        slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")[:40] or "inspiration"
        return f"{self.node_type}:{slug}-{digest}"


# ── HTML parsing ──────────────────────────────────────────────────────


class _PageParser(HTMLParser):
    """Collect OpenGraph, canonical, title, outbound hrefs, JSON-LD."""

    def __init__(self) -> None:
        super().__init__()
        self.og: dict[str, str] = {}
        self.title: str | None = None
        self.description: str | None = None
        self.canonical: str | None = None
        self.json_ld_chunks: list[str] = []
        self.hrefs: list[str] = []
        self._capture_title: bool = False
        self._capture_jsonld: bool = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "meta":
            prop = (a.get("property") or a.get("name") or "").lower()
            content = a.get("content")
            if not prop or content is None:
                return
            if prop.startswith("og:") or prop.startswith("twitter:"):
                self.og[prop] = content
            elif prop == "description":
                self.description = self.description or content
        elif tag == "link" and a.get("rel", "").lower() == "canonical":
            self.canonical = a.get("href")
        elif tag == "a":
            href = a.get("href")
            if href:
                self.hrefs.append(href)
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


# ── Utilities ─────────────────────────────────────────────────────────


def _is_url(s: str) -> bool:
    s = s.strip()
    if not s or " " in s or "\n" in s:
        return False
    parsed = urlparse(s if "://" in s else f"https://{s}")
    return bool(parsed.netloc) and "." in parsed.netloc


def _normalize_url(url: str) -> str:
    """Drop fragments and trailing slashes; keep query."""
    p = urlparse(url if "://" in url else f"https://{url}")
    path = p.path.rstrip("/")
    return urlunparse((p.scheme or "https", p.netloc.lower(), path, "", p.query, ""))


def _host_match(host: str, path: str, suffix: str) -> bool:
    if "/" in suffix:
        host_part, path_part = suffix.split("/", 1)
        return host.endswith(host_part) and path.startswith(f"/{path_part}")
    return host.endswith(suffix)


def _infer_type_and_provider(url: str) -> tuple[str, str]:
    p = urlparse(url)
    host = (p.netloc or "").lower()
    path = p.path.lower()
    for suffix, node_type, provider in HOST_HINTS:
        if _host_match(host, path, suffix):
            return node_type, provider
    return DEFAULT_NODE_TYPE, host or "web"


def _match_presence_provider(url: str) -> str | None:
    p = urlparse(url)
    host = (p.netloc or "").lower()
    if not host:
        return None
    for suffix, provider in PRESENCE_PROVIDERS:
        if host.endswith(suffix):
            return provider
    return None


def _extract_provider_id(url: str, provider: str) -> str:
    p = urlparse(url)
    path = p.path.strip("/")
    if not path:
        return (p.netloc or "").lower()
    parts = path.split("/")
    if provider == "youtube" and parts[0] in ("channel", "user", "c"):
        return parts[1] if len(parts) > 1 else parts[0]
    if provider == "youtube" and parts[0].startswith("@"):
        return parts[0]
    if provider == "spotify" and len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}"
    if provider == "bandcamp":
        return (p.netloc or "").lower().split(".")[0]
    return parts[-1] or path


# ── Fetch + search ────────────────────────────────────────────────────


def _is_public_target(url: str) -> bool:
    """Refuse anything that resolves to a loopback, private, link-local,
    or otherwise internal address. The resolver is meant to reach the
    open web; a user posting ``http://127.0.0.1/admin`` or
    ``http://169.254.169.254/`` (cloud metadata) would be SSRF, not
    gratitude. Returns False on any such host or on resolution failure.
    """
    p = urlparse(url)
    host = (p.hostname or "").strip()
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return False
    for info in infos:
        sockaddr = info[4]
        raw_ip = sockaddr[0] if sockaddr else ""
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def _fetch(url: str) -> tuple[str, str] | None:
    if not _is_public_target(url):
        log.info("inspired_by refusing non-public target: %s", url)
        return None
    try:
        with httpx.Client(
            timeout=FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.8"},
        ) as client:
            r = client.get(url)
            if r.status_code >= 400:
                return None
            # Re-check the final URL after redirects — a public host can
            # redirect to an internal one.
            if not _is_public_target(str(r.url)):
                log.info("inspired_by refusing redirect to non-public: %s", r.url)
                return None
            return str(r.url), r.text
    except httpx.HTTPError:
        return None


def _parse_html(html: str) -> _PageParser:
    parser = _PageParser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 — malformed HTML is the norm
        log.debug("inspired_by html parse non-fatal error", exc_info=True)
    return parser


def _ddg_first_result(query: str) -> str | None:
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


# ── Presences + creations extraction ──────────────────────────────────


def _extract_presences(
    parsed: _PageParser,
    canonical_url: str,
    own_provider: str,
) -> list[Presence]:
    """Collect outbound links to known-provider platforms.

    Same-provider links (e.g. Bandcamp's own /settings, /cart, or another
    artist's subdomain) are filtered out — they're navigation chrome or
    unrelated accounts, not this identity's presences. Cross-platform
    links are the signal we want.
    """
    seen: dict[str, Presence] = {}
    for raw_href in parsed.hrefs:
        absolute = urljoin(canonical_url, raw_href)
        provider = _match_presence_provider(absolute)
        if not provider:
            continue
        if provider == own_provider:
            continue
        normalized = _normalize_url(absolute)
        if normalized in seen:
            continue
        seen[normalized] = Presence(provider=provider, url=normalized)
        if len(seen) >= MAX_PRESENCES:
            break
    return list(seen.values())


_JSON_LD_CREATION_TYPES = {
    "musicalbum": "album",
    "musicrecording": "track",
    "song": "track",
    "videoobject": "video",
    "event": "event",
    "musicevent": "event",
    "book": "book",
    "creativework": "work",
}


def _walk_jsonld(node: Any):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk_jsonld(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_jsonld(v)


def _iter_jsonld_items(chunks: list[str]):
    for chunk in chunks:
        text = (chunk or "").strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        for item in _walk_jsonld(data):
            yield item


def _extract_creations(
    parsed: _PageParser,
    canonical_url: str,
) -> list[Creation]:
    """Pull creations from JSON-LD first (most reliable), then fall back
    to OpenGraph if the page itself is a single work."""
    found: list[Creation] = []
    seen_keys: set[tuple[str, str]] = set()

    for item in _iter_jsonld_items(parsed.json_ld_chunks):
        if not isinstance(item, dict):
            continue
        raw_type = item.get("@type") or ""
        if isinstance(raw_type, list):
            raw_type = next((t for t in raw_type if isinstance(t, str)), "")
        kind = _JSON_LD_CREATION_TYPES.get(str(raw_type).lower())
        if not kind:
            continue
        name = (item.get("name") or item.get("headline") or "").strip()
        if not name:
            continue
        url = item.get("url") or item.get("@id")
        if isinstance(url, dict):
            url = url.get("@id")
        if isinstance(url, str) and url:
            url = _normalize_url(urljoin(canonical_url, url))
        else:
            url = None
        image = item.get("image")
        if isinstance(image, dict):
            image = image.get("url")
        if isinstance(image, list):
            image = image[0] if image else None
        image_url = image if isinstance(image, str) else None
        key = (kind, (url or name).lower())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        found.append(Creation(kind=kind, name=name[:200], url=url, image_url=image_url))
        if len(found) >= MAX_CREATIONS:
            return found

    if not found:
        og_type = parsed.og.get("og:type", "").lower()
        og_title = parsed.og.get("og:title", "").strip()
        og_kind: str | None = None
        if og_title:
            if "music.album" in og_type:
                og_kind = "album"
            elif "music.song" in og_type or "music.track" in og_type:
                og_kind = "track"
            elif "video" in og_type:
                og_kind = "video"
            elif og_type in ("event", "article.event"):
                og_kind = "event"
            elif "book" in og_type:
                og_kind = "book"
        if og_kind:
            found.append(Creation(
                kind=og_kind,
                name=og_title[:200],
                url=canonical_url,
                image_url=parsed.og.get("og:image"),
            ))

    return found


# ── Bandcamp artist-page specifics ────────────────────────────────────
#
# Bandcamp redirects an artist subdomain root (`artist.bandcamp.com/`)
# to whatever album they're currently featuring. That's a single-work
# page with a generic "N track album" OG description — not a presence.
# The artist's actual front is `/music`: real bio, portrait, album grid.
# When the resolver lands on an album/track under a `*.bandcamp.com`
# subdomain, pivot to `/music` once so the identity is the artist, not
# the album. The album itself still shows up below as a creation.


# Match a complete `<li class="music-grid-item">…</li>` block so we can
# pick the best image attribute (data-original > src) without depending
# on attribute order.
_BANDCAMP_GRID_ITEM = re.compile(
    r'<li[^>]*class="[^"]*music-grid-item[^"]*"[^>]*>(.*?)</li>',
    re.IGNORECASE | re.DOTALL,
)
_BANDCAMP_ITEM_HREF = re.compile(r'<a[^>]*href="(/album/[^"]+)"', re.IGNORECASE)
_BANDCAMP_ITEM_IMG_DATA = re.compile(r'data-original="([^"]+)"', re.IGNORECASE)
_BANDCAMP_ITEM_IMG_SRC = re.compile(r'<img[^>]*src="([^"]+)"', re.IGNORECASE)
_BANDCAMP_ITEM_TITLE = re.compile(
    r'<p[^>]*class="[^"]*title[^"]*"[^>]*>\s*([^<]+?)\s*(?:<br|</p)',
    re.IGNORECASE | re.DOTALL,
)


def _is_bandcamp_subdomain(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host.endswith(".bandcamp.com") and host != "bandcamp.com"


def _needs_bandcamp_pivot(url: str) -> bool:
    """True when we landed on an album/track page under a *.bandcamp.com
    subdomain and the artist root would carry more identity signal."""
    if not _is_bandcamp_subdomain(url):
        return False
    path = urlparse(url).path or "/"
    return (
        path.startswith("/album/")
        or path.startswith("/track/")
        or path in ("", "/")
    )


def _bandcamp_music_url(url: str) -> str:
    p = urlparse(url)
    return urlunparse((p.scheme or "https", p.netloc, "/music", "", "", ""))


_TAGLINE_ADMIN_PREFIX = re.compile(
    r"^\s*(bookings?|contact|management|press|inquiries|email|booking\s+inquiries?)"
    r"\s*[:\-–—]\s*\S+.*?(?:\n\s*\n|\. )",
    re.IGNORECASE | re.DOTALL,
)


def _clean_tagline(raw: str) -> str:
    """Tighten an og:description into something a reader actually wants.

    Many artist pages open with booking/contact boilerplate
    ("Bookings: setesh@…") before the real bio. That's admin noise in
    tagline position. Strip leading admin lines, decode entities,
    collapse whitespace, then keep the first sentence — a tagline is
    one held breath, not a press release.
    """
    from html import unescape

    text = unescape(raw or "").strip()
    if not text:
        return ""
    text = _TAGLINE_ADMIN_PREFIX.sub("", text, count=1).strip()
    text = re.sub(r"\s+", " ", text)
    # Keep the first sentence (up to . ! ?) if that fits under the
    # tagline budget. Otherwise fall back to a char-clamp on a word
    # boundary. 180 is a bit beyond the spec's 140 because the
    # presence-page italic body absorbs one more line gracefully, and
    # some bios start with a proper opening clause we don't want to cut
    # mid-word.
    first = re.match(r"[^.!?]{10,180}[.!?]", text)
    if first:
        return first.group(0).strip()
    if len(text) <= 180:
        return text
    return text[:180].rsplit(" ", 1)[0].rstrip(",;:-—") + "…"


def _upscale_bandcamp_image(url: str | None) -> str | None:
    """Rewrite `…_2.jpg` (small thumb) to `…_10.jpg` (1200px). The CDN
    serves whatever size you ask for — the artist grid page hands us
    thumbs by default so the list stays light."""
    if not url or "bcbits.com/img/" not in url:
        return url
    return re.sub(r"_(2|3|4|7|11|12|13|23|42)\.(jpg|png|gif)$", r"_10.\2", url)


def _extract_bandcamp_albums(html: str, canonical_url: str) -> list[Creation]:
    """Parse the album grid on a Bandcamp artist `/music` page.

    Bandcamp ships no JSON-LD for the discography; the grid lives as
    static `<li class="music-grid-item">` anchors. Each has a title,
    a link, and a cover image we upscale to 1200px. Items below the
    fold lazy-load — their real image URL sits in `data-original` while
    `src` points at a 1×1 transparent gif.
    """
    from html import unescape

    found: list[Creation] = []
    for block in _BANDCAMP_GRID_ITEM.findall(html):
        href_m = _BANDCAMP_ITEM_HREF.search(block)
        title_m = _BANDCAMP_ITEM_TITLE.search(block)
        if not href_m or not title_m:
            continue
        title = unescape(re.sub(r"\s+", " ", title_m.group(1))).strip()
        if not title:
            continue
        data_m = _BANDCAMP_ITEM_IMG_DATA.search(block)
        src_m = _BANDCAMP_ITEM_IMG_SRC.search(block)
        image = (data_m and data_m.group(1)) or (src_m and src_m.group(1)) or None
        url = _normalize_url(urljoin(canonical_url, href_m.group(1)))
        image_url = _upscale_bandcamp_image(urljoin(canonical_url, image)) if image else None
        found.append(Creation(kind="album", name=title[:200], url=url, image_url=image_url))
        if len(found) >= MAX_CREATIONS:
            break
    return found


# ── Public API ────────────────────────────────────────────────────────


def resolve(input_text: str) -> ResolvedIdentity | None:
    """Resolve any free-text input to a ResolvedIdentity subgraph."""
    text = (input_text or "").strip()
    if not text:
        return None

    target = text if _is_url(text) else _ddg_first_result(text)
    if not target:
        return None
    if "://" not in target:
        target = f"https://{target}"

    fetched = _fetch(target)
    if not fetched:
        return None
    final_url, html = fetched

    # Pivot Bandcamp album/track landings up to the artist `/music` page.
    # That's where the bio, the portrait, and the full discography live;
    # the redirected album page only knows about itself.
    if _needs_bandcamp_pivot(final_url):
        artist_root = _bandcamp_music_url(final_url)
        pivoted = _fetch(artist_root)
        if pivoted:
            final_url, html = pivoted

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
    description = _clean_tagline(
        parsed.og.get("og:description")
        or parsed.og.get("twitter:description")
        or parsed.description
        or ""
    )
    image = parsed.og.get("og:image") or parsed.og.get("twitter:image")
    if _is_bandcamp_subdomain(canonical):
        image = _upscale_bandcamp_image(image)
    node_type, provider = _infer_type_and_provider(canonical)
    provider_id = _extract_provider_id(canonical, provider)
    presences = _extract_presences(parsed, canonical, provider)
    creations = _extract_creations(parsed, canonical)
    if not creations and _is_bandcamp_subdomain(canonical):
        creations = _extract_bandcamp_albums(html, canonical)

    return ResolvedIdentity(
        input=text,
        name=name[:200],
        description=description[:500],
        canonical_url=canonical,
        provider=provider,
        provider_id=provider_id,
        node_type=node_type,
        image_url=image,
        presences=presences,
        creations=creations,
    )


# ── Weight (emerges from what was found) ──────────────────────────────


CANONICAL_HOSTS = frozenset({
    "bandcamp.com", "spotify.com", "music.apple.com", "soundcloud.com",
    "youtube.com", "wikipedia.org", "eventbrite.com", "songkick.com",
})


def compute_weight(resolved: ResolvedIdentity) -> float:
    """Derive the inspired-by edge weight from discovery signals.

    Base 0.4 — we found *something*. Each cross-platform presence adds
    0.05 (capped +0.25) because presence across platforms suggests a
    real public identity. Each creation adds 0.05 (capped +0.25)
    because named works are a strong signal. +0.1 bonus when the
    canonical host is a well-known primary (Bandcamp, Wikipedia, etc.).
    Capped at 1.0.
    """
    weight = 0.4
    weight += min(len(resolved.presences), 5) * 0.05
    weight += min(len(resolved.creations), 5) * 0.05
    host = urlparse(resolved.canonical_url).netloc.lower()
    if any(host.endswith(h) for h in CANONICAL_HOSTS):
        weight += 0.1
    return round(min(weight, 1.0), 3)


# ── Persistence ───────────────────────────────────────────────────────


def _normalize_contributor_id(contributor_id: str) -> str:
    cid = (contributor_id or "").strip()
    return cid if cid.startswith("contributor:") else f"contributor:{cid}"


def find_existing_identity(canonical_url: str) -> dict[str, Any] | None:
    """Look up an already-imported identity by its canonical URL."""
    for node_type in ("contributor", "community", "network-org"):
        result = graph_service.list_nodes(type=node_type, limit=500)
        for node in result.get("items", []):
            if node.get("canonical_url") == canonical_url:
                return node
    return None


def _creation_node_id(creation: Creation, identity_id: str) -> str:
    seed = (creation.url or f"{identity_id}:{creation.name}").lower()
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^a-z0-9]+", "-", creation.name.lower()).strip("-")[:40] or "work"
    return f"asset:{slug}-{digest}"


def _ensure_creation_nodes(
    identity_id: str,
    creations: list[Creation],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for creation in creations:
        node_id = _creation_node_id(creation, identity_id)
        existing = graph_service.get_node(node_id)
        if existing:
            node = existing
        else:
            node = graph_service.create_node(
                id=node_id,
                type="asset",
                name=creation.name,
                description=creation.name,
                properties={
                    "asset_type": "CONTENT",
                    "creation_kind": creation.kind,
                    "canonical_url": creation.url,
                    "image_url": creation.image_url,
                    "total_cost": "0",
                    "claimable": True,
                },
                phase="ice",
            )
        edge_result = graph_service.create_edge_strict(
            from_id=identity_id,
            to_id=node_id,
            type="contributes-to",
            properties={"kind": creation.kind},
            strength=1.0,
            created_by="inspired_by_resolver",
        )
        out.append({
            "node": node,
            "edge": edge_result if edge_result.get("error") != "edge_exists" else None,
            "edge_existed": edge_result.get("error") == "edge_exists",
        })
    return out


def import_inspired_by(
    source_contributor_id: str,
    resolved: ResolvedIdentity,
) -> dict[str, Any]:
    """Create (or find) the identity subgraph and the inspired-by edge.

    Idempotent on canonical URL for the identity; creation nodes are
    keyed by creation URL (or name if URL is missing). Weight on the
    inspired-by edge is computed from discovery signals.
    """
    source_contributor_id = _normalize_contributor_id(source_contributor_id)
    weight = compute_weight(resolved)

    existing = find_existing_identity(resolved.canonical_url)
    if existing:
        identity_node = existing
        identity_id = existing["id"]
        identity_created = False
    else:
        identity_id = resolved.node_id()
        # The tagline slot stays open. The resolver seeds what it can
        # verify — name, canonical URL, cross-platform presences, album
        # art — but the voice belongs to the person. Scraping
        # og:description from a platform like Bandcamp leaves a
        # third-party blurb in the hero ("led by Amani Friend of
        # Desert Dwellers" when that's no longer true), which reads as
        # the platform's voice, not the artist's. An empty tagline is
        # an honest held breath; the first person who knows the truth
        # types it in. ``claimed`` flips to true when that person is
        # the identity itself.
        properties: dict[str, Any] = {
            "tagline": "",
            "canonical_url": resolved.canonical_url,
            "provider": resolved.provider,
            "provider_id": resolved.provider_id,
            "image_url": resolved.image_url,
            "presences": [
                {"provider": p.provider, "url": p.url} for p in resolved.presences
            ],
            "claimed": False,
        }
        # Only contributors that *actually* represent a human carry the
        # HUMAN contributor_type + placeholder email. A festival or a
        # network-org isn't a person; forcing HUMAN onto their node
        # pollutes the contributors directory and breaks the claim story.
        if resolved.node_type == "contributor":
            properties.update({
                "contributor_type": "HUMAN",
                "email": f"{resolved.provider_id}@unclaimed.coherence.network",
                "author_display_name": resolved.name,
            })
        identity_node = graph_service.create_node(
            id=identity_id,
            type=resolved.node_type,
            name=resolved.name,
            description=resolved.description,
            properties=properties,
        )
        identity_created = True

    creations_out = _ensure_creation_nodes(identity_id, resolved.creations)

    edge_result = graph_service.create_edge_strict(
        from_id=source_contributor_id,
        to_id=identity_id,
        type="inspired-by",
        properties={"input": resolved.input},
        strength=weight,
        created_by="inspired_by_resolver",
    )
    edge_existed = edge_result.get("error") == "edge_exists"

    return {
        "identity": identity_node,
        "identity_created": identity_created,
        "edge": edge_result if not edge_existed else None,
        "edge_existed": edge_existed,
        "weight": weight,
        "presences": [
            {"provider": p.provider, "url": p.url} for p in resolved.presences
        ],
        "creations": creations_out,
        "resolved": {
            "input": resolved.input,
            "name": resolved.name,
            "description": resolved.description,
            "canonical_url": resolved.canonical_url,
            "provider": resolved.provider,
            "node_type": resolved.node_type,
            "image_url": resolved.image_url,
        },
    }


def list_inspired_by(
    source_contributor_id: str,
    viewer_contributor_id: str | None = None,
) -> list[dict[str, Any]]:
    """Return every identity the source is inspired-by, with weight.

    When a ``viewer_contributor_id`` is supplied and differs from the
    source, each item is annotated with ``shared_with_viewer`` — True
    when the viewer is also inspired-by that identity. This is what
    lights the small thread of kinship on a public person page.
    """
    source_contributor_id = _normalize_contributor_id(source_contributor_id)
    edges = graph_service.list_edges(
        from_id=source_contributor_id,
        edge_type="inspired-by",
        limit=500,
    )

    viewer_node_ids: set[str] = set()
    if viewer_contributor_id:
        viewer_id = _normalize_contributor_id(viewer_contributor_id)
        if viewer_id != source_contributor_id:
            viewer_edges = graph_service.list_edges(
                from_id=viewer_id,
                edge_type="inspired-by",
                limit=500,
            )
            viewer_node_ids = {
                e["to_id"] for e in viewer_edges.get("items", []) if e.get("to_id")
            }

    items: list[dict[str, Any]] = []
    for edge in edges.get("items", []):
        node = graph_service.get_node(edge["to_id"])
        if not node:
            continue
        item: dict[str, Any] = {
            "edge_id": edge["id"],
            "weight": edge.get("strength", 1.0),
            "node": node,
            "created_at": edge.get("created_at"),
        }
        if viewer_node_ids:
            item["shared_with_viewer"] = edge["to_id"] in viewer_node_ids
        items.append(item)
    return items


def remove_inspired_by_edge(edge_id: str) -> bool:
    """Drop the inspired-by edge. The identity node stays — it's still
    claimable and still linked to its creations."""
    return graph_service.delete_edge(edge_id)
