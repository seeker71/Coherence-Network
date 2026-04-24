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

# When the initial page-scrape returns fewer than this many cross-
# platform presences, the resolver automatically does a name-search
# enrichment pass to discover the rest of the constellation. Bandcamp
# artist pages and Facebook profiles often only surface 0–1 outbound
# presences; a search for the artist's name reliably finds Spotify,
# SoundCloud, YouTube, Instagram, etc. Saves the user from having to
# prompt us for every platform.
SPARSE_PRESENCE_THRESHOLD = 3


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
        """Deterministic id from the canonical URL alone.

        The id used to include the name slug: `contributor:{slug}-{hash}`.
        That was the source of a class of duplicates — the same URL
        re-resolved at different times could parse to slightly
        different names (trailing space, case change, OG vs
        json-ld disagreement) and each variant produced a new id.
        Now the URL hash is the whole suffix, so the same URL → the
        same id forever, regardless of what name the page happens to
        parse as this time."""
        digest = canonical_url_hash(self.canonical_url)
        return f"{self.node_type}:{digest}"


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


# Query parameters we preserve during canonicalization — everything
# else (tracking, sharing, session) is dropped because it changes the
# URL without changing the identity. Kept tight on purpose: YouTube's
# `v=` is the video id, Spotify's embed link uses it too. Extend only
# when a new provider demonstrably needs a param to address content.
_CANONICAL_PRESERVE_QUERY_PARAMS = {
    "v",          # youtube.com/watch?v=ID
    "list",       # youtube.com playlists
    "id",         # a few SaaS platforms use this as the entity id
}

# Query parameters that are always noise — strip aggressively. This is
# a denylist of known tracking and share-tool params so we don't miss
# one even if _CANONICAL_PRESERVE_QUERY_PARAMS is widened later.
_TRACKING_QUERY_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "mc_cid", "mc_eid", "_hsenc", "_hsmi", "yclid",
    "ref", "ref_src", "ref_url", "share", "sharing", "shared", "source",
    "from", "src",
})


def canonicalize_url(url: str) -> str:
    """Return the single canonical form of a URL.

    The resolver used to keep the query string and host case, which
    meant `?utm_source=1471` and `www.example.com` produced a
    different 'canonical_url' than `example.com` — and every one of
    those variants minted a new graph node. This is the single
    function every write path now uses to key nodes by URL. Same
    content on the same host → same string, every time.

    Transformations:
      · Scheme lowercased, defaults to `https` when missing
      · Host lowercased, leading `www.` stripped (site and its www
        alias are one identity)
      · Path with trailing slashes collapsed to a single non-trailing
        form
      · Fragment dropped (same page)
      · Query string rebuilt: tracking/share params dropped, the
        remaining params sorted, only allowlisted params kept when
        the host uses them to address content (YouTube's `v=`,
        etc.). Most sites have no meaningful query — one canonical
        form wins.
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    p = urlparse(raw if "://" in raw else f"https://{raw}")
    # Force https for canonical identity. http and https pointing to
    # the same host + path are the same thing — a resource is defined
    # by where it lives, not by how this particular link to it was
    # typed. Allows an old `http://` link in someone's email to
    # resolve to the same identity as the current `https://` variant.
    scheme = "https"
    host = (p.netloc or "").lower()
    # Strip leading www. — the identity is the site, not the subdomain
    # alias. Keep any other subdomain (music.example.com stays).
    if host.startswith("www."):
        host = host[4:]
    # Collapse //segments and trailing slashes on the path.
    path = re.sub(r"/{2,}", "/", p.path or "")
    path = path.rstrip("/") or ""
    # Query canonicalization: keep only allowlisted params (and only
    # when they carry a value); drop the rest.
    query = ""
    if p.query:
        from urllib.parse import parse_qsl, urlencode
        kept = [
            (k, v) for k, v in parse_qsl(p.query, keep_blank_values=False)
            if k.lower() in _CANONICAL_PRESERVE_QUERY_PARAMS
            and k.lower() not in _TRACKING_QUERY_PARAMS
        ]
        # Deterministic order so two callers who send the same params
        # in different orders still produce the same canonical.
        kept.sort()
        query = urlencode(kept) if kept else ""
    return urlunparse((scheme, host, path, "", query, ""))


# Backwards-compatible alias — callers still import _normalize_url.
# Every write path now flows through the strict canonicalizer.
def _normalize_url(url: str) -> str:
    return canonicalize_url(url)


def canonical_url_hash(url: str) -> str:
    """Stable 16-char hash of a URL's canonical form. Used as the
    deterministic id suffix so the same identity always lands on the
    same node, no matter which code path creates it."""
    return hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()[:16]


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


def _ddg_search_urls(query: str, limit: int = 20) -> list[str]:
    """Return the top DDG result URLs for a query.

    DuckDuckGo's HTML endpoint wraps each result's real URL inside a
    redirector — we unpack the ``uddg`` param back to the canonical
    target. Used both for the first-result lookup (resolving a bare
    name) and for the sparse-resolution enrichment pass (harvesting
    an entity's cross-platform constellation).
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
                return []
            html = r.text
    except httpx.HTTPError:
        return []

    from urllib.parse import parse_qs, urlparse as _u

    urls: list[str] = []
    for m in re.finditer(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"',
        html,
    ):
        href = m.group(1)
        if "uddg=" in href:
            q = parse_qs(_u(href).query)
            if "uddg" in q:
                href = q["uddg"][0]
        urls.append(href)
        if len(urls) >= limit:
            break
    return urls


def _ddg_first_result(query: str) -> str | None:
    results = _ddg_search_urls(query, limit=1)
    return results[0] if results else None


def _name_slug(name: str) -> str:
    """A lowercased, alphanumeric-only slug for fuzzy URL matching."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _url_verified_against_name(url: str, name: str) -> bool:
    """Cheap verification for opaque-ID platform URLs (Spotify
    /artist/{hash}, YouTube /channel/{id}): fetch the page and check
    if og:title / twitter:title contains the entity name. One HTTP
    call per candidate — the enrichment runs once per presence and
    caches into the graph, so this cost is amortized forever."""
    fetched = _fetch(url)
    if not fetched:
        return False
    _, html = fetched
    parsed = _parse_html(html)
    name_slug = _name_slug(name)
    if not name_slug:
        return False
    for key in ("og:title", "twitter:title", "og:site_name"):
        val = parsed.og.get(key) or ""
        if name_slug in _name_slug(val):
            return True
    if parsed.title and name_slug in _name_slug(parsed.title):
        return True
    return False


def _search_platform_presences(
    name: str,
    own_provider: str,
    already_have: list[Presence],
) -> list[Presence]:
    """Harvest the entity's cross-platform constellation from a name
    search. For each known platform (Spotify, SoundCloud, YouTube,
    Instagram…) the resolver takes the first-ranked DDG result on
    that platform's host and either:

      · accepts it when the entity's name slug appears in the host
        or path (profile URLs like soundcloud.com/liquidbloom,
        liquidbloom.bandcamp.com, instagram.com/liquidbloom), OR
      · fetches the page and accepts when og:title echoes the name
        (opaque-ID URLs like spotify.com/artist/{hash})

    Same-provider dupes are filtered by keeping the first match per
    provider. Runs when the initial page-scrape is sparse. The user
    shouldn't have to ask for each platform — search + verify pulls
    the whole constellation once.
    """
    if not name or len(name) < 3:
        return []
    slug = _name_slug(name)
    if not slug:
        return []
    have_norm = {_normalize_url(p.url) for p in already_have}
    have_providers = {p.provider for p in already_have}

    results = _ddg_search_urls(name, limit=40)
    found: dict[str, Presence] = {}
    for raw in results:
        try:
            absolute = raw if "://" in raw else f"https://{raw}"
            host = urlparse(absolute).netloc.lower()
            path = urlparse(absolute).path.lower()
        except ValueError:
            continue
        provider = _match_presence_provider(absolute)
        if not provider:
            continue
        if provider == own_provider:
            continue
        if provider in have_providers or any(
            p.provider == provider for p in found.values()
        ):
            continue
        normalized = _normalize_url(absolute)
        if normalized in have_norm or normalized in found:
            continue
        host_slug = _name_slug(host)
        path_slug = _name_slug(path)
        # Fast path: slug shows up in host or path
        if slug in host_slug or slug in path_slug:
            found[normalized] = Presence(provider=provider, url=normalized)
            continue
        # Opaque-ID path: verify via fetch + og:title match
        if _url_verified_against_name(absolute, name):
            found[normalized] = Presence(provider=provider, url=normalized)
    return list(found.values())


# ── Presences + creations extraction ──────────────────────────────────


# Social-share URLs aren't an entity's own presence — they're
# "share this page" buttons that happen to live on the platform's
# host. Filter them out so Pyramids of Chi doesn't claim
# facebook.com/sharer/sharer.php as its Facebook account.
_SHARE_PATH_MARKERS = ("/sharer/", "/share?", "/intent/", "/shareArticle")


def _is_share_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    query = urlparse(url).query.lower()
    lowered = f"{path}?{query}"
    return any(marker in lowered for marker in _SHARE_PATH_MARKERS)


def _extract_presences(
    parsed: _PageParser,
    canonical_url: str,
    own_provider: str,
) -> list[Presence]:
    """Collect outbound links to known-provider platforms.

    One URL per provider — most sites link to their main artist page
    plus a handful of specific videos/tracks/posts on the same
    platform. The main profile is what a visitor wants as a chip;
    the rest is noise on a presence row. Same-provider-as-identity
    links (e.g. bandcamp → bandcamp nav chrome) are filtered out
    entirely, and "share this page" URLs are skipped because they
    aren't an account — they're social-share buttons that happen to
    point at the platform's sharer endpoint.
    """
    seen_providers: set[str] = set()
    seen_urls: set[str] = set()
    presences: list[Presence] = []
    for raw_href in parsed.hrefs:
        absolute = urljoin(canonical_url, raw_href)
        provider = _match_presence_provider(absolute)
        if not provider:
            continue
        if provider == own_provider:
            continue
        if _is_share_url(absolute):
            continue
        if provider in seen_providers:
            continue
        normalized = _normalize_url(absolute)
        if normalized in seen_urls:
            continue
        seen_providers.add(provider)
        seen_urls.add(normalized)
        presences.append(Presence(provider=provider, url=normalized))
        if len(presences) >= MAX_PRESENCES:
            break
    return presences


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

    from html import unescape as _html_unescape
    for item in _iter_jsonld_items(parsed.json_ld_chunks):
        if not isinstance(item, dict):
            continue
        raw_type = item.get("@type") or ""
        if isinstance(raw_type, list):
            raw_type = next((t for t in raw_type if isinstance(t, str)), "")
        kind = _JSON_LD_CREATION_TYPES.get(str(raw_type).lower())
        if not kind:
            continue
        # WordPress sites (and others) emit titles with HTML entities
        # ("Hatha Flow &#038; Sound"). Decode once at the boundary so they
        # never reach the graph as literal "&#038;".
        name = _html_unescape((item.get("name") or item.get("headline") or "")).strip()
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
        from html import unescape as _html_unescape
        og_type = parsed.og.get("og:type", "").lower()
        og_title = _html_unescape(parsed.og.get("og:title", "")).strip()
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
    # Many sites set og:title to "domain.com – real name – tagline" or
    # "real name | domain". Strip a leading `domain.com –` / `.com -` /
    # trailing ` | Site` so the name is the entity itself. This helps
    # both the visual hero and the name-search enrichment (which uses
    # the name as the search query).
    from html import unescape as _unescape
    name = _unescape(name)
    # Strip a leading domain-like prefix ending in `.com|.org|.net|.earth` etc.
    name = re.sub(
        r"^[a-z0-9][a-z0-9\-\.]*\.(?:com|org|net|earth|io|world|tv|app|one)\s*[\-–—|]\s*",
        "",
        name,
        flags=re.IGNORECASE,
    )
    # Strip a trailing ` — tagline` or ` | Site` — keep just the name
    # on the left of the first separator, but only if that left side
    # is reasonably specific (≥ 3 chars, not just "The").
    m = re.match(r"^(.{3,})\s*[\-–—|·]\s", name)
    if m:
        left = m.group(1).strip()
        if len(left) >= 3 and left.lower() not in {"the", "an", "a"}:
            name = left
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

    # Auto-enrich when the initial scrape didn't find the full
    # constellation. Bandcamp artist pages link to one or two socials
    # at most; Facebook profiles hide outlinks behind auth; many
    # personal sites bury them in JS-rendered footers. A name search
    # reliably surfaces the rest of the presences, and the slug-match
    # / fetch-verify check keeps random strangers out of the graph.
    # Threshold is on unique providers (not total URLs), so an artist
    # with 4 YouTube links still triggers discovery of Spotify etc.
    unique_providers = {p.provider for p in presences}
    if len(unique_providers) < SPARSE_PRESENCE_THRESHOLD and name:
        discovered = _search_platform_presences(name, provider, presences)
        for p in discovered:
            if len(presences) >= MAX_PRESENCES:
                break
            presences.append(p)

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
    """Look up an already-imported identity by its canonical URL.

    The previous implementation only scanned three node types
    (contributor, community, network-org). The moment a presence was
    retyped to `scene` (a venue), `asset` (a work), `event`,
    `practice`, or `skill`, the next resolve of the same URL missed
    the existing node and minted a fresh one. Scanning every
    presence type closes that gap: once a URL has a home, every
    future resolve finds it regardless of what type the graph has
    sorted it into.

    The comparison is tolerant: it matches the caller's canonical
    against both the stored `canonical_url` property and the
    re-canonicalized form of whatever's stored. That way pre-fix
    nodes whose stored URL still has `?utm_source=...` still get
    found when a caller sends the clean form.
    """
    canonical = canonicalize_url(canonical_url)
    if not canonical:
        return None
    # Also compute the id under the deterministic scheme — if the
    # create ever landed one, get_node is O(1) versus a type-by-type
    # scan. Try all presence types so retype doesn't orphan lookups.
    target_hash = canonical_url_hash(canonical)
    for node_type in CROSS_REF_NODE_TYPES:
        direct = graph_service.get_node(f"{node_type}:{target_hash}")
        if direct:
            return direct
    # Slow path: the node pre-dates the deterministic id scheme.
    # Walk each presence type and match on the stored canonical_url
    # (re-canonicalized on the fly so legacy nodes with tracking
    # params still resolve).
    for node_type in CROSS_REF_NODE_TYPES:
        result = graph_service.list_nodes(type=node_type, limit=500)
        for node in result.get("items", []):
            stored = node.get("canonical_url")
            if not stored:
                continue
            if canonicalize_url(stored) == canonical:
                return node
    return None


def _creation_node_id(creation: Creation, identity_id: str) -> str:
    """Deterministic id for an asset node — URL-derived when we have
    one, name+owner-derived as a fallback.

    Same URL → same asset id, same name-under-same-owner → same id.
    Historically the id carried a name slug too, which meant the
    same URL (re)resolving to a slightly-different name spawned
    fresh asset nodes every time. Now the suffix is pure hash: one
    URL, one asset."""
    if creation.url:
        return f"asset:{canonical_url_hash(creation.url)}"
    # No URL — fall back to owner+name so the same album listed
    # under the same artist collapses even without a link.
    seed = f"{identity_id}|{(creation.name or '').strip().lower()}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"asset:{digest}"


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


# ── Cross-reference mining ────────────────────────────────────────────
#
# When a new identity enters the graph, its name may already appear in
# other nodes' descriptions — every page a visitor has landed on that
# mentions the name leaves an implicit thread that's worth surfacing.
# This scan walks existing nodes and writes a ``referenced-by`` edge
# for each mention (direction: referenced → referencer, so reading a
# node's outgoing ``referenced-by`` edges shows "everyone who mentions
# me"). method="mention-scan" marks the edge so later passes can
# refine or re-score.

# Node types worth scanning — skip concept/idea/spec etc which are
# text-dense and would match common nouns. These types carry real
# presence signal where a mention is meaningful.
CROSS_REF_NODE_TYPES = frozenset({
    "contributor", "community", "network-org", "event", "asset",
    "scene", "practice", "skill",
})

# Short names would match too broadly ("Anne" mentioned in unrelated
# contexts). Require at least two words OR a name long enough to be
# unambiguous.
def _name_is_scannable(name: str) -> bool:
    n = (name or "").strip()
    if len(n) < 4:
        return False
    if " " in n:  # multi-word names are inherently more specific
        return True
    return len(n) >= 6


def _scan_cross_references(identity: dict[str, Any]) -> list[dict[str, Any]]:
    """Find nodes whose description mentions this identity's name and
    lay a ``referenced-by`` edge from identity → referencer. Runs once
    when a new identity is minted, and can be re-run idempotently.
    """
    name = (identity.get("name") or "").strip()
    if not _name_is_scannable(name):
        return []
    identity_id = identity["id"]
    # Also try alternate names if present
    alt = (identity.get("author_display_name") or "").strip()
    known_as = (identity.get("also_known_as") or "").strip()
    needles: list[str] = [name]
    if alt and alt != name and _name_is_scannable(alt):
        needles.append(alt)
    if known_as and known_as != name and _name_is_scannable(known_as):
        needles.append(known_as)
    # Compile regexes with word boundaries so we don't match substrings.
    patterns = [re.compile(r"\b" + re.escape(n) + r"\b", re.IGNORECASE) for n in needles]

    # Cheap first-pass: if the graph doesn't carry many presences
    # yet, the scan will find nothing — skip the 8-type walk and its
    # DB cost entirely. Shows up in test flows where each identity
    # creation would otherwise trip 8 list_nodes queries for nothing.
    # Threshold 5 is conservative — by the time there are 5+
    # presences, the chance of a real mention is meaningful.
    any_existing = graph_service.list_nodes(type="contributor", limit=6)
    if len(any_existing.get("items", [])) < 2:
        return []

    written: list[dict[str, Any]] = []
    for ntype in CROSS_REF_NODE_TYPES:
        result = graph_service.list_nodes(type=ntype, limit=500)
        for node in result.get("items", []):
            if node["id"] == identity_id:
                continue
            haystack = " ".join([
                str(node.get("description") or ""),
                str(node.get("tagline") or ""),
                str(node.get("note") or ""),
            ])
            if not haystack:
                continue
            if not any(p.search(haystack) for p in patterns):
                continue
            # Skip if the edge already exists
            existing = graph_service.list_edges(
                from_id=identity_id, to_id=node["id"],
                edge_type="referenced-by", limit=1,
            ).get("items", [])
            if existing:
                continue
            r = graph_service.create_edge_strict(
                from_id=identity_id, to_id=node["id"],
                type="referenced-by",
                properties={"method": "mention-scan"},
                strength=0.3,
                created_by="cross_reference_scan",
            )
            if r.get("id"):
                written.append({
                    "referencer_id": node["id"],
                    "referencer_name": node.get("name") or node["id"],
                    "edge_id": r["id"],
                })
    return written


def ensure_identity(resolved: ResolvedIdentity) -> tuple[dict[str, Any], bool, list[dict[str, Any]]]:
    """Create (or find) the identity subgraph for a resolved input.

    Separate from :func:`import_inspired_by` because not every resolve
    is a "someone inspired me" gesture. Adding a co-leader to a
    gathering, linking a collaborator on an album, crediting a teacher
    on an essay — these all need the resolver's identity-minting
    behaviour without forging an inspired-by edge the visitor didn't
    actually mean.

    Returns ``(identity_node, created, creations_out)``.
    """
    existing = find_existing_identity(resolved.canonical_url)
    if existing:
        identity_node = existing
        identity_id = existing["id"]
        identity_created = False
    else:
        identity_id = resolved.node_id()
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
    # Mention scan — the moment this identity enters the graph, look
    # for existing nodes whose text carries its name, and lay
    # ``referenced-by`` edges for each. The graph discovers its own
    # latent connections rather than waiting for a human to draw them.
    # Only runs on fresh identities so re-adding an existing presence
    # doesn't re-scan.
    if identity_created:
        try:
            _scan_cross_references(identity_node)
        except Exception:  # noqa: BLE001 — don't let a scan failure block resolve
            log.debug("mention scan non-fatal error", exc_info=True)
    return identity_node, identity_created, creations_out


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

    identity_node, identity_created, creations_out = ensure_identity(resolved)
    identity_id = identity_node["id"]

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
