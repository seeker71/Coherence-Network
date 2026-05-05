"""Generic RSS / Atom creation source.

Tries the URL itself first. If that doesn't look like a feed
(no `<rss>`, `<feed>`, or `<channel>` root), tries
``<root>/feed`` and ``<root>/rss`` in order. Each item becomes
an ``ImportedCreation``.

Default kind is ``article``. When the feed has
``<itunes:duration>`` on its items it's a podcast feed and the
kind switches to ``episode``.
"""
from __future__ import annotations

import re
from html import unescape
from typing import Iterable
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

from .base import ImportedCreation
from ._http import safe_get


SOURCE_ITEM_CAP = 50


_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def _strip_html(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _looks_like_feed(body: str) -> bool:
    head = body[:500].lower()
    return (
        "<rss" in head
        or "<feed" in head
        or "<channel" in head
        or "<atom" in head
    )


def _parse_feed(body: str) -> list[ImportedCreation]:
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []

    items: list[ImportedCreation] = []
    is_atom = root.tag.endswith("}feed") or root.tag == "feed"

    if is_atom:
        entries = root.findall("atom:entry", _NAMESPACES) or root.findall("entry")
        for e in entries:
            title_el = e.find("atom:title", _NAMESPACES) or e.find("title")
            link_el = e.find("atom:link", _NAMESPACES) or e.find("link")
            summary_el = e.find("atom:summary", _NAMESPACES) or e.find("summary")
            pub_el = e.find("atom:published", _NAMESPACES) or e.find("published")

            title = _strip_html(title_el.text if title_el is not None else None)
            url: str | None = None
            if link_el is not None:
                url = link_el.get("href") or link_el.text
                if url:
                    url = url.strip() or None
            description = _strip_html(summary_el.text if summary_el is not None else None)
            when = (pub_el.text or "").strip() if pub_el is not None else None
            if not title:
                continue
            duration = e.find("itunes:duration", _NAMESPACES)
            kind = "episode" if duration is not None else "article"
            items.append(ImportedCreation(
                name=title[:200],
                kind=kind,
                url=url,
                description=description,
                when=when or None,
            ))
            if len(items) >= SOURCE_ITEM_CAP:
                break
        return items

    # RSS 2.0 — items live at channel/item.
    channel = root.find("channel") if root.tag.lower() == "rss" else root
    if channel is None:
        return []
    for it in channel.findall("item"):
        title_el = it.find("title")
        link_el = it.find("link")
        desc_el = it.find("description")
        pub_el = it.find("pubDate")

        title = _strip_html(title_el.text if title_el is not None else None)
        url = (link_el.text or "").strip() if link_el is not None else None
        description = _strip_html(desc_el.text if desc_el is not None else None)
        when = (pub_el.text or "").strip() if pub_el is not None else None
        if not title:
            continue
        # Image enrichment from media:thumbnail / itunes:image / enclosure.
        image_url: str | None = None
        media_thumb = it.find("media:thumbnail", _NAMESPACES)
        if media_thumb is not None:
            image_url = media_thumb.get("url")
        if not image_url:
            itunes_img = it.find("itunes:image", _NAMESPACES)
            if itunes_img is not None:
                image_url = itunes_img.get("href")
        if not image_url:
            enclosure = it.find("enclosure")
            if enclosure is not None:
                t = (enclosure.get("type") or "").lower()
                if t.startswith("image/"):
                    image_url = enclosure.get("url")
        # Podcast detection — itunes:duration on the item flips kind.
        duration = it.find("itunes:duration", _NAMESPACES)
        kind = "episode" if duration is not None else "article"
        items.append(ImportedCreation(
            name=title[:200],
            kind=kind,
            url=url,
            image_url=image_url,
            description=description,
            when=when or None,
        ))
        if len(items) >= SOURCE_ITEM_CAP:
            break
    return items


def _candidate_urls(url: str) -> Iterable[str]:
    """Yield the URL itself, then `<root>/feed`, then `<root>/rss`.

    The feed may live at the URL the caller hands us, or one of two
    well-known suffixes off the root. We try in that order so a
    direct feed URL always wins."""
    yield url
    p = urlparse(url)
    if not (p.scheme and p.netloc):
        return
    root = f"{p.scheme}://{p.netloc}"
    yield urljoin(root + "/", "feed")
    yield urljoin(root + "/", "rss")


class RSSSource:
    """Generic RSS / Atom feed importer.

    Acts as the fallback for any URL that exposes a feed. Specific
    sources (Substack) layer on top because they want their own kind
    label, but they can delegate the feed parse to this module.
    """

    name = "rss"

    def matches(self, url: str) -> bool:
        try:
            p = urlparse(url)
        except ValueError:
            return False
        return bool(p.scheme and p.netloc)

    def fetch(self, url: str) -> list[ImportedCreation]:
        for candidate in _candidate_urls(url):
            fetched = safe_get(candidate, accept="application/rss+xml,application/atom+xml,application/xml,text/xml,*/*;q=0.5")
            if not fetched:
                continue
            _, body = fetched
            if not _looks_like_feed(body):
                continue
            items = _parse_feed(body)
            if items:
                return items[:SOURCE_ITEM_CAP]
        return []


def parse_feed_xml(body: str) -> list[ImportedCreation]:
    """Public helper for sources that want feed parsing without the
    URL-discovery step (e.g. Substack, which always knows its own
    `/feed` path)."""
    return _parse_feed(body)
