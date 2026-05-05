"""Substack creation source.

Substack publications expose a public RSS feed at ``<root>/feed``.
We hit that, parse the items, and label every one as ``essay``
(Substack's identity is long-form personal writing — the renderer
displays essays distinctly from generic articles).
"""
from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from .base import ImportedCreation
from ._http import safe_get
from .rss_source import parse_feed_xml


SOURCE_ITEM_CAP = 50


class SubstackSource:
    """Essays from any ``*.substack.com`` publication."""

    name = "substack"

    def matches(self, url: str) -> bool:
        host = urlparse(url).netloc.lower()
        return host.endswith(".substack.com") or host == "substack.com"

    def fetch(self, url: str) -> list[ImportedCreation]:
        if not self.matches(url):
            return []
        p = urlparse(url)
        feed_url = urlunparse((p.scheme or "https", p.netloc, "/feed", "", "", ""))
        fetched = safe_get(
            feed_url,
            accept="application/rss+xml,application/atom+xml,application/xml,text/xml,*/*;q=0.5",
        )
        if not fetched:
            return []
        _, body = fetched
        items = parse_feed_xml(body)
        # Override kind — Substack's voice is essay, not generic article.
        relabeled = [
            ImportedCreation(
                name=item.name,
                kind="essay",
                url=item.url,
                image_url=item.image_url,
                description=item.description,
                when=item.when,
            )
            for item in items
        ]
        return relabeled[:SOURCE_ITEM_CAP]
