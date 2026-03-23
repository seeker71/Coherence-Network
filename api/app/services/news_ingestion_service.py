"""News ingestion service: fetches RSS feeds and caches results."""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FEED_SOURCES: list[dict[str, str]] = [
    {"name": "Hacker News", "url": "https://news.ycombinator.com/rss"},
    {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
    {"name": "The Guardian Tech", "url": "https://www.theguardian.com/technology/rss"},
    {"name": "Reddit r/programming", "url": "https://www.reddit.com/r/programming/.rss"},
]

CACHE_TTL_SECONDS = 900  # 15 minutes


@dataclass
class NewsItem:
    title: str
    description: str
    url: str
    published_at: Optional[str]  # ISO 8601 string or None
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------
_cached_items: list[NewsItem] = []
_cache_timestamp: float = 0.0


def _parse_rss(xml_text: str, source_name: str) -> list[NewsItem]:
    """Parse RSS/Atom XML and return NewsItem list."""
    items: list[NewsItem] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse XML from %s", source_name)
        return items

    # RSS 2.0: channel/item
    for item_el in root.iter("item"):
        title = (item_el.findtext("title") or "").strip()
        desc = (item_el.findtext("description") or "").strip()
        link = (item_el.findtext("link") or "").strip()
        pub_date_raw = (item_el.findtext("pubDate") or "").strip()

        pub_iso: Optional[str] = None
        if pub_date_raw:
            try:
                dt = parsedate_to_datetime(pub_date_raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                pub_iso = dt.isoformat()
            except Exception:
                pub_iso = None

        if title or link:
            items.append(NewsItem(
                title=title,
                description=desc[:500] if desc else "",
                url=link,
                published_at=pub_iso,
                source=source_name,
            ))

    # Atom: entry (for Reddit RSS which uses Atom)
    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title = (entry.findtext("atom:title", namespaces=ns)
                     or entry.findtext("{http://www.w3.org/2005/Atom}title")
                     or "").strip()
            link_el = entry.find("{http://www.w3.org/2005/Atom}link[@href]")
            link = link_el.get("href", "") if link_el is not None else ""
            content_el = entry.find("{http://www.w3.org/2005/Atom}content")
            desc = (content_el.text or "").strip()[:500] if content_el is not None else ""
            updated = (entry.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()

            pub_iso = updated if updated else None

            if title or link:
                items.append(NewsItem(
                    title=title,
                    description=desc,
                    url=link,
                    published_at=pub_iso,
                    source=source_name,
                ))

    return items


async def fetch_feeds(force_refresh: bool = False) -> list[NewsItem]:
    """Fetch all RSS feeds, using cache if fresh."""
    global _cached_items, _cache_timestamp

    now = time.time()
    if not force_refresh and _cached_items and (now - _cache_timestamp) < CACHE_TTL_SECONDS:
        return list(_cached_items)

    all_items: list[NewsItem] = []
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for source in FEED_SOURCES:
            try:
                resp = await client.get(source["url"], headers={"User-Agent": "CoherenceNetwork/1.0"})
                resp.raise_for_status()
                parsed = _parse_rss(resp.text, source["name"])
                all_items.extend(parsed)
                logger.info("Fetched %d items from %s", len(parsed), source["name"])
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", source["name"], exc)

    # Sort by published_at descending (items without dates go last)
    all_items.sort(
        key=lambda x: x.published_at or "0000-00-00",
        reverse=True,
    )

    _cached_items = all_items
    _cache_timestamp = now
    return list(_cached_items)


def get_cached_items() -> list[NewsItem]:
    """Return currently cached items without fetching."""
    return list(_cached_items)


def extract_trending_keywords(items: list[NewsItem], top_n: int = 20) -> list[dict]:
    """Extract trending keywords from news items by frequency."""
    from app.services.news_resonance_service import extract_keywords

    freq: dict[str, int] = {}
    for item in items:
        kws = extract_keywords(f"{item.title} {item.description}")
        for kw in kws:
            freq[kw] = freq.get(kw, 0) + 1

    sorted_kws = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [{"keyword": kw, "count": count} for kw, count in sorted_kws[:top_n]]
