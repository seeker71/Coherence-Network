"""YouTube channel creation source.

YouTube channel pages embed an enormous JSON blob in
``var ytInitialData = …`` that holds every recent upload's
title, video id, and thumbnail. We extract video items from that
blob — no API key, no rate-limited official endpoint, just the
public page the same as any browser would.

Each match becomes an ``ImportedCreation`` with ``kind="video"``.
Capped at 24 most recent (a presence page renders a band of recent
videos, not a 600-video catalog).
"""
from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urlparse

from .base import ImportedCreation
from ._http import safe_get


YOUTUBE_VIDEO_CAP = 24

# Match `var ytInitialData = {…};` — content stops at the closing
# `};` on its own line. Greedy match between the assignment and
# the `</script>` close so we always capture the whole JSON payload.
_INITIAL_DATA = re.compile(
    r"var\s+ytInitialData\s*=\s*({.*?})\s*;\s*</script>",
    re.DOTALL,
)


def _walk(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk(v)


def _extract_videos(html: str) -> list[ImportedCreation]:
    m = _INITIAL_DATA.search(html)
    if not m:
        return []
    raw = m.group(1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    found: list[ImportedCreation] = []
    seen_ids: set[str] = set()
    for node in _walk(data):
        if not isinstance(node, dict):
            continue
        # videoRenderer / gridVideoRenderer / playlistVideoRenderer all
        # share the same minimal shape: videoId, title.runs/simpleText,
        # thumbnail.thumbnails[].url.
        vid = node.get("videoId")
        if not isinstance(vid, str) or not vid:
            continue
        if vid in seen_ids:
            continue
        title_node = node.get("title")
        title: str | None = None
        if isinstance(title_node, dict):
            runs = title_node.get("runs")
            if isinstance(runs, list) and runs:
                first = runs[0]
                if isinstance(first, dict):
                    t = first.get("text")
                    if isinstance(t, str):
                        title = t.strip()
            if not title:
                t = title_node.get("simpleText")
                if isinstance(t, str):
                    title = t.strip()
            if not title:
                t = title_node.get("accessibility")
                if isinstance(t, dict):
                    accdata = t.get("accessibilityData") or {}
                    label = accdata.get("label") if isinstance(accdata, dict) else None
                    if isinstance(label, str):
                        title = label.strip()
        if not title:
            continue
        thumbs = node.get("thumbnail")
        image: str | None = None
        if isinstance(thumbs, dict):
            arr = thumbs.get("thumbnails")
            if isinstance(arr, list) and arr:
                # Last entry is usually the largest size.
                last = arr[-1]
                if isinstance(last, dict):
                    u = last.get("url")
                    if isinstance(u, str):
                        image = u
        published_text = None
        pt = node.get("publishedTimeText")
        if isinstance(pt, dict):
            t = pt.get("simpleText")
            if isinstance(t, str):
                published_text = t.strip()
        seen_ids.add(vid)
        found.append(ImportedCreation(
            name=unescape(title)[:200],
            kind="video",
            url=f"https://www.youtube.com/watch?v={vid}",
            image_url=image,
            when=published_text,
        ))
        if len(found) >= YOUTUBE_VIDEO_CAP:
            break
    return found


class YouTubeSource:
    """Recent-video importer for ``youtube.com/@<handle>`` and
    ``youtube.com/channel/<id>`` pages."""

    name = "youtube"

    def matches(self, url: str) -> bool:
        try:
            p = urlparse(url)
        except ValueError:
            return False
        host = (p.netloc or "").lower()
        if not (host.endswith("youtube.com") or host == "youtu.be"):
            return False
        path = (p.path or "/").lstrip("/")
        if not path:
            return False
        first = path.split("/", 1)[0]
        return first.startswith("@") or first in ("channel", "c", "user")

    def fetch(self, url: str) -> list[ImportedCreation]:
        if not self.matches(url):
            return []
        # Append `/videos` to land on the recent-uploads tab when the
        # caller hands us a bare channel URL. The blob we're parsing
        # exists on the channel root too, but the videos tab gives us
        # a longer list reliably.
        target = url
        if "/videos" not in target:
            target = target.rstrip("/") + "/videos"
        fetched = safe_get(target)
        if not fetched:
            return []
        _, html = fetched
        return _extract_videos(html)
