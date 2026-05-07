"""YouTube channel creation source.

YouTube channel pages embed an enormous JSON blob in
``var ytInitialData = …`` that holds every recent upload's
title, video id, thumbnail, view count, and published time text.
We extract video items from that blob — no API key, no
rate-limited official endpoint, just the public page the same as
any browser would.

Each match becomes an ``ImportedCreation`` with ``kind="video"``.
View counts ride along as a property so the rendering layer can
weight a presence's emitted spectrum by which works actually
broadcast loudest into the field.

The cap is set generously so the importer's stratified-sampling
discipline has material to spread across rather than just truncating
to first-N. The body of work a YouTuber emits is never truly the
last 24 uploads.
"""
from __future__ import annotations

import json
import re
from html import unescape
from urllib.parse import urlparse

from .base import ImportedCreation
from ._http import safe_get


YOUTUBE_VIDEO_CAP = 60

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
        view_count = _parse_view_count(node)
        seen_ids.add(vid)
        found.append(ImportedCreation(
            name=unescape(title)[:200],
            kind="video",
            url=f"https://www.youtube.com/watch?v={vid}",
            image_url=image,
            when=published_text,
            view_count=view_count,
        ))
        if len(found) >= YOUTUBE_VIDEO_CAP:
            break
    return found


_VIEW_COUNT_NUM = re.compile(r"([0-9][0-9.,]*)\s*([KMB]?)\s*views?", re.IGNORECASE)


def _parse_view_count(node: dict) -> int | None:
    """Extract the integer view count from a YouTube videoRenderer.

    The renderer carries view counts in two places — `viewCountText`
    (visible label, e.g. "1.2M views") and `shortViewCountText`
    (compact label). We try the visible one first and parse the
    "K/M/B" suffix when present. Returns None when no count is
    readable; that's normal for newly-published videos and shorts.
    """
    for key in ("viewCountText", "shortViewCountText"):
        slot = node.get(key)
        if not isinstance(slot, dict):
            continue
        text: str | None = None
        if isinstance(slot.get("simpleText"), str):
            text = slot["simpleText"]
        else:
            runs = slot.get("runs")
            if isinstance(runs, list) and runs:
                first = runs[0]
                if isinstance(first, dict) and isinstance(first.get("text"), str):
                    text = first["text"]
        if not text:
            continue
        m = _VIEW_COUNT_NUM.search(text)
        if not m:
            continue
        raw, suffix = m.group(1), (m.group(2) or "").upper()
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        multiplier = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(suffix, 1)
        return int(value * multiplier)
    return None


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
