"""Bandcamp creation source.

Bandcamp artist pages embed their discography as JSON-LD
``MusicAlbum`` records. The artist root often redirects to a
featured album (a single-work landing); the real artist page
lives at ``/music``. We look at JSON-LD first because it's the
most reliable signal, then fall back to the artist-grid HTML on
``/music`` when JSON-LD isn't present.

Each match becomes an ``ImportedCreation`` with ``kind="album"``.
"""
from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

from .base import ImportedCreation
from ._http import safe_get


SOURCE_ITEM_CAP = 50


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.json_ld_chunks: list[str] = []
        self._capture_jsonld = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            a = {k.lower(): (v or "") for k, v in attrs}
            if a.get("type", "").lower() == "application/ld+json":
                self._capture_jsonld = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._capture_jsonld:
            self._capture_jsonld = False

    def handle_data(self, data: str) -> None:
        if self._capture_jsonld:
            self.json_ld_chunks.append(data)


def _walk(node: Any):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _extract_jsonld_albums(html: str, base_url: str) -> list[ImportedCreation]:
    parser = _Parser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 — malformed HTML is the norm
        return []
    found: list[ImportedCreation] = []
    seen: set[tuple[str, str]] = set()
    for chunk in parser.json_ld_chunks:
        text = (chunk or "").strip()
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        for item in _walk(data):
            if not isinstance(item, dict):
                continue
            raw_type = item.get("@type") or ""
            if isinstance(raw_type, list):
                raw_type = next((t for t in raw_type if isinstance(t, str)), "")
            if str(raw_type).lower() not in ("musicalbum", "musicrelease"):
                continue
            name = unescape((item.get("name") or item.get("headline") or "")).strip()
            if not name:
                continue
            url = item.get("url") or item.get("@id")
            if isinstance(url, dict):
                url = url.get("@id")
            if isinstance(url, str) and url:
                url = urljoin(base_url, url)
            else:
                url = None
            image = item.get("image")
            if isinstance(image, dict):
                image = image.get("url")
            if isinstance(image, list):
                image = image[0] if image else None
            image_url = image if isinstance(image, str) else None
            when = item.get("datePublished") or item.get("releaseDate")
            if not isinstance(when, str):
                when = None
            key = ("album", (url or name).lower())
            if key in seen:
                continue
            seen.add(key)
            found.append(ImportedCreation(
                name=name[:200],
                kind="album",
                url=url,
                image_url=image_url,
                when=when,
            ))
            if len(found) >= SOURCE_ITEM_CAP:
                return found
    return found


# Artist-grid fallback for `/music` pages where Bandcamp doesn't ship
# JSON-LD. Each `<li class="music-grid-item">` carries title + href +
# cover image (data-original or src).
_GRID_ITEM = re.compile(
    r'<li[^>]*class="[^"]*music-grid-item[^"]*"[^>]*>(.*?)</li>',
    re.IGNORECASE | re.DOTALL,
)
_ITEM_HREF = re.compile(r'<a[^>]*href="(/album/[^"]+)"', re.IGNORECASE)
_ITEM_IMG_DATA = re.compile(r'data-original="([^"]+)"', re.IGNORECASE)
_ITEM_IMG_SRC = re.compile(r'<img[^>]*src="([^"]+)"', re.IGNORECASE)
_ITEM_TITLE = re.compile(
    r'<p[^>]*class="[^"]*title[^"]*"[^>]*>\s*([^<]+?)\s*(?:<br|</p)',
    re.IGNORECASE | re.DOTALL,
)


def _extract_grid_albums(html: str, base_url: str) -> list[ImportedCreation]:
    found: list[ImportedCreation] = []
    for block in _GRID_ITEM.findall(html):
        href_m = _ITEM_HREF.search(block)
        title_m = _ITEM_TITLE.search(block)
        if not href_m or not title_m:
            continue
        title = unescape(re.sub(r"\s+", " ", title_m.group(1))).strip()
        if not title:
            continue
        data_m = _ITEM_IMG_DATA.search(block)
        src_m = _ITEM_IMG_SRC.search(block)
        image = (data_m and data_m.group(1)) or (src_m and src_m.group(1)) or None
        url = urljoin(base_url, href_m.group(1))
        image_url = urljoin(base_url, image) if image else None
        found.append(ImportedCreation(
            name=title[:200],
            kind="album",
            url=url,
            image_url=image_url,
        ))
        if len(found) >= SOURCE_ITEM_CAP:
            break
    return found


class BandcampSource:
    """Discography importer for `*.bandcamp.com` URLs."""

    name = "bandcamp"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return host.endswith(".bandcamp.com") or host == "bandcamp.com"

    def fetch(self, url: str) -> list[ImportedCreation]:
        if not self.matches(url):
            return []
        # Pivot to /music when the URL points at the subdomain root or
        # an album/track landing — that's where the full discography
        # surfaces. Same logic as the inspired-by resolver.
        target = url
        host = urlparse(url).netloc.lower()
        path = urlparse(url).path or "/"
        if host.endswith(".bandcamp.com") and (
            path in ("", "/")
            or path.startswith("/album/")
            or path.startswith("/track/")
        ):
            parts = urlparse(url)
            target = f"{parts.scheme or 'https'}://{parts.netloc}/music"
        fetched = safe_get(target)
        if not fetched:
            return []
        final_url, html = fetched
        items = _extract_jsonld_albums(html, final_url)
        if not items:
            items = _extract_grid_albums(html, final_url)
        return items[:SOURCE_ITEM_CAP]
