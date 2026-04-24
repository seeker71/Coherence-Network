"""News ingestion service: fetches RSS feeds and caches results.

Sources are loaded from the configured JSON source list and are editable via
the API. If the source file is missing or unreadable, the service returns an
empty source list rather than carrying hidden feed data in code.
"""

from __future__ import annotations

import json
import logging
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import httpx

from app.config_loader import get_float, get_int, get_str

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Source configuration — loaded from config file, editable via API
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "config" / "news-sources.json"


def _config_path() -> Path:
    configured = get_str("news", "sources_path", default=str(_DEFAULT_CONFIG_PATH)).strip()
    path = Path(configured or str(_DEFAULT_CONFIG_PATH))
    return path if path.is_absolute() else _REPO_ROOT / path


def _load_sources() -> list[dict]:
    """Load news sources from config file."""
    cfg = _config_path()
    if cfg.exists():
        try:
            sources = json.loads(cfg.read_text())
            active = [s for s in sources if s.get("is_active", True)]
            logger.info("Loaded %d news sources (%d active) from %s", len(sources), len(active), cfg)
            return sources
        except Exception as e:
            logger.warning("Failed to load %s: %s — using empty source list", cfg, e)
    else:
        logger.info("News source config %s not found — using empty source list", cfg)
    return []


def _save_sources(sources: list[dict]) -> None:
    """Persist news sources to config file."""
    cfg = _config_path()
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(sources, indent=2))
    logger.info("Saved %d news sources to %s", len(sources), cfg)


# Module-level source list — reloaded on mutation
_sources: list[dict] = _load_sources()

CACHE_TTL_SECONDS = get_int("news", "cache_ttl_seconds", default=900)


# ---------------------------------------------------------------------------
# Source CRUD — used by the API router
# ---------------------------------------------------------------------------

def list_sources(active_only: bool = False) -> list[dict]:
    """Return all configured news sources."""
    if active_only:
        return [s for s in _sources if s.get("is_active", True)]
    return list(_sources)


def get_source(source_id: str) -> dict | None:
    """Get a single source by ID."""
    for s in _sources:
        if s.get("id") == source_id:
            return dict(s)
    return None


def add_source(source: dict) -> dict:
    """Add a new news source. Returns the created source."""
    global _sources
    # Validate required fields
    if not source.get("id") or not source.get("url"):
        raise ValueError("Source must have 'id' and 'url'")
    if any(s["id"] == source["id"] for s in _sources):
        raise ValueError(f"Source '{source['id']}' already exists")
    # Set defaults
    source.setdefault("name", source["id"])
    source.setdefault("type", "rss")
    source.setdefault("categories", [])
    source.setdefault("ontology_levels", [])
    source.setdefault("is_active", True)
    source.setdefault("update_interval_minutes", 60)
    source.setdefault("priority", 50)
    _sources.append(source)
    _save_sources(_sources)
    return source


def update_source(source_id: str, updates: dict) -> dict | None:
    """Update a news source. Returns the updated source."""
    global _sources
    for i, s in enumerate(_sources):
        if s.get("id") == source_id:
            s.update(updates)
            s["id"] = source_id  # prevent ID change
            _sources[i] = s
            _save_sources(_sources)
            return dict(s)
    return None


def remove_source(source_id: str) -> bool:
    """Remove a news source. Returns True if found and removed."""
    global _sources
    before = len(_sources)
    _sources = [s for s in _sources if s.get("id") != source_id]
    if len(_sources) < before:
        _save_sources(_sources)
        return True
    return False


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
    """Fetch all active RSS feeds, using cache if fresh."""
    global _cached_items, _cache_timestamp

    now = time.time()
    if not force_refresh and _cached_items and (now - _cache_timestamp) < CACHE_TTL_SECONDS:
        return list(_cached_items)

    active_sources = [s for s in _sources if s.get("is_active", True) and s.get("type") == "rss"]
    all_items: list[NewsItem] = []
    timeout = get_float("news", "fetch_timeout_seconds", default=15.0)
    user_agent = get_str("news", "user_agent", default="CoherenceNetwork/1.0")
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        for source in active_sources:
            try:
                resp = await client.get(source["url"], headers={"User-Agent": user_agent})
                resp.raise_for_status()
                parsed = _parse_rss(resp.text, source.get("name", source["id"]))
                all_items.extend(parsed)
                logger.info("Fetched %d items from %s", len(parsed), source.get("name", source["id"]))
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", source.get("name", source["id"]), exc)

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
