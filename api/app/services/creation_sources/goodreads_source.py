"""Goodreads author creation source.

Goodreads author pages (``goodreads.com/author/show/<id>``) list
the author's books with Schema.org ``Book`` JSON-LD records. Each
match becomes an ``ImportedCreation`` with ``kind="book"``.

When JSON-LD is missing (older author pages) we fall back to the
``<a class="bookTitle">`` anchor pattern with ``<span itemprop="name">``
inside, plus the cover image from the same row's ``<img class="..." src="…" />``.
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


def _extract_jsonld_books(html: str, base_url: str) -> list[ImportedCreation]:
    parser = _Parser()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001
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
            if str(raw_type).lower() != "book":
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
            description = item.get("description")
            description = description.strip()[:500] if isinstance(description, str) else None
            when = item.get("datePublished")
            if not isinstance(when, str):
                when = None
            key = ("book", (url or name).lower())
            if key in seen:
                continue
            seen.add(key)
            found.append(ImportedCreation(
                name=name[:200],
                kind="book",
                url=url,
                image_url=image_url,
                description=description,
                when=when,
            ))
            if len(found) >= SOURCE_ITEM_CAP:
                return found
    return found


# Fallback HTML pattern: `<a class="bookTitle" href="/book/show/…"><span
# itemprop="name" role="heading" aria-level="4">Title</span></a>`. Cover
# image lives in the same `<tr>` as `<img alt="…" class="bookCover"
# src="…" />`. We scan a limited portion of the rendered list.
_BOOK_TITLE = re.compile(
    r'<a[^>]*class="[^"]*bookTitle[^"]*"[^>]*href="(/book/show/[^"]+)"[^>]*>\s*'
    r'<span[^>]*itemprop="name"[^>]*>\s*([^<]+?)\s*</span>',
    re.IGNORECASE | re.DOTALL,
)


def _extract_html_books(html: str, base_url: str) -> list[ImportedCreation]:
    found: list[ImportedCreation] = []
    for m in _BOOK_TITLE.finditer(html):
        href = m.group(1)
        title = unescape(re.sub(r"\s+", " ", m.group(2))).strip()
        if not title:
            continue
        url = urljoin(base_url, href)
        found.append(ImportedCreation(
            name=title[:200],
            kind="book",
            url=url,
        ))
        if len(found) >= SOURCE_ITEM_CAP:
            break
    return found


class GoodreadsSource:
    """Books listed on a Goodreads author page."""

    name = "goodreads"

    def matches(self, url: str) -> bool:
        try:
            p = urlparse(url)
        except ValueError:
            return False
        host = (p.netloc or "").lower()
        path = (p.path or "/").lower()
        return host.endswith("goodreads.com") and path.startswith("/author/show/")

    def fetch(self, url: str) -> list[ImportedCreation]:
        if not self.matches(url):
            return []
        fetched = safe_get(url)
        if not fetched:
            return []
        final_url, html = fetched
        items = _extract_jsonld_books(html, final_url)
        if not items:
            items = _extract_html_books(html, final_url)
        return items[:SOURCE_ITEM_CAP]
