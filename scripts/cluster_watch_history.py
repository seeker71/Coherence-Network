#!/usr/bin/env python3
"""Cluster a YouTube/podcast watch-history into main influences.

We don't need to track every video the user has ever watched — that
shape introduces noise and bias. What we do need is the cluster of
where they returned: the channels they watched repeatedly, the
voices that shaped them. Each surviving cluster becomes one
inspired-by edge from the user to the channel's contributor node,
weighted by how often they returned.

For channels that match an existing contributor in the graph (by
channel URL or normalized name), the edge attaches to that
canonical identity — Urs watching Lex Fridman lands as
``contributor:seeker71 --inspired-by-> contributor:lex-fridman``,
not as a thousand individual video edges.

For channels that don't yet match but cleared the significance
threshold, a stub contributor is created so the influence is
visible — and so anyone in the network whose body of work shares
frequency with the cluster can be discovered later.

Input: a Google Takeout watch-history.json file. Same shape used
by both YouTube and YouTube Music Takeout exports — each entry has
``title``, ``titleUrl``, ``subtitles`` (the channel), ``time``.

Usage:

    # Plan-only — see what would land without writing
    python3 scripts/cluster_watch_history.py \\
        --contributor contributor:seeker71 \\
        --file ~/Takeout/YouTube\\ and\\ YouTube\\ Music/history/watch-history.json \\
        --min-watches 5 \\
        --dry-run

    # Apply — create the inspired-by edges
    python3 scripts/cluster_watch_history.py \\
        --contributor contributor:seeker71 \\
        --file ~/.../watch-history.json \\
        --min-watches 5

By default only clusters with >= --min-watches entries qualify as
"main influences"; one-off random watches don't enter the graph.
The threshold protects against noise — recommendation-feed accidents
shouldn't show up as your influences.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse


def _ensure_app_path() -> None:
    here = Path(__file__).resolve().parent
    api_dir = here.parent / "api"
    if api_dir.exists():
        p = str(api_dir)
        if p not in sys.path:
            sys.path.insert(0, p)


# ── Format readers ────────────────────────────────────────────────────


def _read_takeout(path: Path) -> list[dict]:
    """Read a Google Takeout watch-history file in either format.

    Google Takeout exports YouTube history as JSON or HTML depending
    on the user's selection. Both carry the same shape — title, video
    URL, channel name, channel URL, watch time. This reader detects
    the format and returns a uniform list of entry dicts.
    """
    if path.suffix.lower() in (".json",):
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError(f"expected a JSON array, got {type(data).__name__}")
        return data
    if path.suffix.lower() in (".html", ".htm"):
        return _parse_takeout_html(path.read_text(encoding="utf-8"))
    # Best-effort: try JSON first, then HTML
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return _parse_takeout_html(raw)


# Each entry in the HTML export wraps in
# <div class="outer-cell..."> ... <div class="content-cell...body-1">
# Watched <a href="VIDEO_URL">VIDEO_TITLE</a><br>
# <a href="CHANNEL_URL">CHANNEL_NAME</a><br>
# DATE_STRING<br>
# </div> ...
_ENTRY_RE = re.compile(
    r'<div class="content-cell[^"]*body-1[^"]*">'
    r'(?:Watched|Watched\s+at\s+)?'
    r'\s*<a href="([^"]+)"[^>]*>(.*?)</a>'  # video URL + title
    r'(?:<br\s*/?>)?\s*'
    r'(?:<a href="([^"]*)"[^>]*>(.*?)</a>)?'  # optional channel URL + name
    r'(?:<br\s*/?>)?\s*([^<]*?)<br',  # date text
    re.DOTALL,
)


def _strip_html(text: str) -> str:
    """Drop any nested tags + decode HTML entities."""
    text = re.sub(r"<[^>]+>", "", text)
    text = (text.replace("&amp;", "&").replace("&quot;", '"')
                .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&nbsp;", " "))
    return text.strip()


def _parse_takeout_html(html: str) -> list[dict]:
    """Convert Takeout HTML → uniform entry dicts.

    Each surviving match contributes one entry shaped like the JSON
    export. Removed/private/ad entries that don't expose a watch URL
    are skipped here so the rest of the pipeline (clustering,
    matching) doesn't carry noise.
    """
    out: list[dict] = []
    for m in _ENTRY_RE.finditer(html):
        v_url, v_title, c_url, c_name, when = m.groups()
        if not v_url or "youtube.com" not in v_url:
            continue
        entry = {
            "title": _strip_html(v_title),
            "titleUrl": v_url,
            "time": (when or "").strip(),
            "subtitles": [],
        }
        if c_url and c_name:
            entry["subtitles"] = [{
                "name": _strip_html(c_name),
                "url": c_url,
            }]
        out.append(entry)
    return out


# ── Channel normalization & matching ──────────────────────────────────


_NAME_NOISE = re.compile(
    r"\b(official|vevo|topic|channel|youtube|music|podcast|show|tv|"
    r"the\s+show|live)\b",
    re.IGNORECASE,
)


def _normalize_name(name: str) -> str:
    """Lowercase, strip diacritics, drop platform-noise tokens, collapse.

    "Lex Fridman Podcast - Official" and "Lex Fridman" both
    normalize to "lex fridman" so a single match resolves them.
    """
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.lower()
    n = _NAME_NOISE.sub(" ", n)
    # Drop punctuation, then collapse whitespace.
    n = re.sub(r"[^\w\s-]", " ", n)
    n = re.sub(r"-+", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _channel_id_from_url(url: str | None) -> str | None:
    """Extract a stable channel handle / id from a YouTube channel URL."""
    if not url:
        return None
    try:
        p = urlparse(url)
    except ValueError:
        return None
    if not (p.netloc or "").lower().endswith("youtube.com"):
        return None
    parts = (p.path or "/").lstrip("/").split("/")
    if not parts:
        return None
    first = parts[0]
    if first.startswith("@"):
        return first.lower()
    if first in ("channel", "c", "user") and len(parts) > 1:
        return f"{first}/{parts[1].lower()}"
    return None


# ── Cluster building ──────────────────────────────────────────────────


def _build_clusters(entries: list[dict]) -> dict[str, dict]:
    """Group watch-history entries by channel.

    Keyed by channel URL when present (most stable). Falls back to
    channel name when the URL is missing — older Takeout exports
    sometimes lose URLs for removed channels.
    """
    clusters: dict[str, dict] = defaultdict(
        lambda: {"name": None, "channel_url": None, "watches": []}
    )
    for entry in entries:
        subs = entry.get("subtitles") or []
        if not subs:
            continue
        first = subs[0]
        if not isinstance(first, dict):
            continue
        cname = (first.get("name") or "").strip()
        curl = first.get("url")
        if not cname and not curl:
            continue
        key = curl or f"name:{_normalize_name(cname)}"
        c = clusters[key]
        if not c["name"]:
            c["name"] = cname
            c["channel_url"] = curl
        c["watches"].append({
            "title": entry.get("title"),
            "url": entry.get("titleUrl"),
            "time": entry.get("time"),
        })
    return dict(clusters)


# ── Graph matching ────────────────────────────────────────────────────


def _load_existing_contributors(api_base: str) -> tuple[dict[str, str], dict[str, str]]:
    """Return (by_normalized_name, by_channel_handle) → contributor_id.

    by_normalized_name maps "lex fridman" → "contributor:lex-fridman".
    by_channel_handle maps "@lexfridman" → "contributor:lex-fridman" when
    the contributor's presences[] carries a matching YouTube URL.
    """
    import urllib.request
    req = urllib.request.Request(
        f"{api_base}/api/graph/nodes?type=contributor&limit=500",
        headers={"User-Agent": "curl/8.7.1"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    by_name: dict[str, str] = {}
    by_handle: dict[str, str] = {}
    for n in data.get("items", []):
        cid = n.get("id")
        name = n.get("name") or ""
        norm = _normalize_name(name)
        if norm and norm not in by_name:
            by_name[norm] = cid
        for p in n.get("presences", []) or []:
            handle = _channel_id_from_url(p.get("url"))
            if handle and handle not in by_handle:
                by_handle[handle] = cid
    return by_name, by_handle


def _match_cluster(
    cluster: dict,
    by_name: dict[str, str],
    by_handle: dict[str, str],
) -> str | None:
    handle = _channel_id_from_url(cluster.get("channel_url"))
    if handle and handle in by_handle:
        return by_handle[handle]
    norm = _normalize_name(cluster.get("name") or "")
    if norm and norm in by_name:
        return by_name[norm]
    return None


# ── Duration estimation ───────────────────────────────────────────────


# Watch entries carry a timestamp but no duration. The cleanest proxy
# we have is the gap between consecutive watches: when one entry is
# at 10:00 and the next at 10:45, ~45 minutes of attention sat with
# the first. Capped at MAX_SESSION_GAP because gaps longer than that
# are someone walking away — the body wasn't watching, the tab was.
MAX_SESSION_GAP_SECONDS = 90 * 60  # 1.5 hours
# Minimum recognized engagement when we can't estimate (last entry
# in a session, parse failure). A small floor so a watch still
# counts as engagement even when its duration can't be measured.
MIN_WATCH_SECONDS = 60


# Takeout time strings look like:
#   "May 7, 2026, 12:55:36 AM WITA"
#   "Apr 23, 2024, 9:14:08 PM PDT"
# The trailing timezone is a non-standard label; strip it and parse
# the rest as wall time. We don't need exact UTC — only deltas.
_TIME_RE = re.compile(
    r"(?P<month>\w+)\s+(?P<day>\d+),\s+(?P<year>\d+),\s+"
    r"(?P<hour>\d+):(?P<minute>\d+):(?P<second>\d+)\s+"
    r"(?P<ampm>AM|PM)\b"
)
_MONTHS = {m: i for i, m in enumerate(
    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"], 1
)}


def _parse_takeout_time(text: str) -> int | None:
    """Parse a Takeout time string to a Unix-ish epoch (timezone-agnostic).

    We don't need true UTC — we use deltas only, and Takeout entries
    in a single export come from a consistent local timezone, so wall-
    time deltas are accurate within a session.
    """
    if not text:
        return None
    m = _TIME_RE.search(text)
    if not m:
        return None
    try:
        month = _MONTHS.get(m.group("month")[:3])
        if not month:
            return None
        hour = int(m.group("hour")) % 12
        if m.group("ampm").upper() == "PM":
            hour += 12
        from datetime import datetime
        dt = datetime(
            int(m.group("year")), month, int(m.group("day")),
            hour, int(m.group("minute")), int(m.group("second")),
        )
        return int(dt.timestamp())
    except (ValueError, OverflowError):
        return None


def _estimate_durations(entries: list[dict]) -> None:
    """Add `duration_seconds` to each watch entry by reading the gap
    between this entry and the next (in chronological order). Mutates
    the entries list in place.

    Takeout exports newest-first, so the *previous* entry in the file
    is actually the *next* in time. Sort by parsed time ascending and
    compute forward deltas.
    """
    timed = [(e, _parse_takeout_time(e.get("time", ""))) for e in entries]
    timed.sort(key=lambda t: t[1] if t[1] is not None else 0)
    for i, (entry, t) in enumerate(timed):
        nxt = timed[i + 1][1] if i + 1 < len(timed) else None
        if t is None or nxt is None:
            entry["duration_seconds"] = MIN_WATCH_SECONDS
            continue
        gap = nxt - t
        if gap <= 0:
            entry["duration_seconds"] = MIN_WATCH_SECONDS
        else:
            entry["duration_seconds"] = min(gap, MAX_SESSION_GAP_SECONDS)


def _cluster_duration_seconds(cluster: dict) -> int:
    """Sum the duration proxy across every watch in the cluster."""
    return sum(int(w.get("duration_seconds") or MIN_WATCH_SECONDS)
               for w in cluster["watches"])


# ── Strength curve ────────────────────────────────────────────────────


def _strength_from_duration(seconds: int) -> float:
    """Map cumulative listening duration → strength in [0, 1].

    Logarithmic so a 100-hour podcast catalog doesn't dominate the
    visual against a 5-hour deeply-attended teacher. Calibration:
      ·    1 hour  → 0.18
      ·    5 hours → 0.36
      ·   20 hours → 0.51
      ·  100 hours → 0.69
      ·  500 hours → 0.86
      · 1000 hours → 0.93
    """
    hours = max(0.0, seconds / 3600.0)
    return min(1.0, math.log1p(hours) / math.log1p(1000))


def _strength(count: int) -> float:
    """Legacy count-based strength — retained for tests that reference
    it directly. New runs use duration via _strength_from_duration.

    Logarithmic so a viewer who watched 200 episodes doesn't strangle
    the visual against one who watched 10. 5 watches → 0.27;
    20 → 0.43; 100 → 0.66; 500 → 0.85.
    """
    if count <= 0:
        return 0.0
    return min(1.0, math.log1p(count) / math.log1p(500))


# ── Main flow ─────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--contributor", required=True,
                   help="Contributor id of the watcher (e.g. contributor:seeker71)")
    p.add_argument("--file", type=Path, required=True,
                   help="Path to watch-history.json from Google Takeout")
    p.add_argument("--min-minutes", type=int, default=15,
                   help="Minimum cumulative attention (minutes) to qualify as a "
                        "main influence (default 15). Duration is estimated from "
                        "the gap between consecutive watches, capped at 1.5h "
                        "per entry to handle session breaks.")
    p.add_argument("--create-stub-min-minutes", type=int, default=180,
                   help="Minimum cumulative attention (minutes) to create a stub "
                        "for unmatched channels (default 180 = 3 hours)")
    # Legacy count-based flags accepted for backwards compatibility but
    # mapped to rough minute equivalents (assuming ~3 minutes per watch
    # on average — the count→duration mapping isn't precise but the
    # discipline still produces a sensible filter).
    p.add_argument("--min-watches", type=int, default=None,
                   help=argparse.SUPPRESS)
    p.add_argument("--create-stub-min", type=int, default=None,
                   help=argparse.SUPPRESS)
    p.add_argument("--api", default="http://localhost:8000",
                   help="API base URL (default http://localhost:8000)")
    p.add_argument("--dry-run", action="store_true",
                   help="Plan only — show what would land without writing the graph")
    p.add_argument("--top", type=int, default=50,
                   help="Show details for the top N clusters in the report (default 50)")
    args = p.parse_args(argv)

    # Map the legacy count-based flags into duration approximations
    # so older invocations keep working while we transition.
    if args.min_watches is not None:
        args.min_minutes = max(args.min_minutes, args.min_watches * 3)
    if args.create_stub_min is not None:
        args.create_stub_min_minutes = max(args.create_stub_min_minutes, args.create_stub_min * 3)

    if not args.file.exists():
        print(f"file not found: {args.file}", file=sys.stderr)
        return 2

    try:
        entries = _read_takeout(args.file)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"could not parse {args.file}: {exc}", file=sys.stderr)
        return 2

    print(f"reading {len(entries)} watch entries from {args.file.name}")
    # Estimate per-watch duration from the gap between consecutive
    # entries. Duration carries more signal than count — a 3-hour
    # podcast and a 30-second clip aren't equivalent attentions.
    _estimate_durations(entries)

    clusters = _build_clusters(entries)
    print(f"clustered into {len(clusters)} unique channels")

    # Significance is now duration-based: a cluster qualifies as a
    # main influence when cumulative listening crosses the threshold,
    # not just because the user clicked on it many times.
    min_seconds = args.min_minutes * 60
    significant = {
        k: c for k, c in clusters.items()
        if _cluster_duration_seconds(c) >= min_seconds
    }
    total_hours = sum(_cluster_duration_seconds(c) for c in significant.values()) / 3600
    print(f"  {len(significant)} clusters at >= {args.min_minutes} minutes total "
          f"(~{total_hours:.0f} cumulative hours of attention)")

    print("loading existing contributors from the graph…")
    by_name, by_handle = _load_existing_contributors(args.api)
    print(f"  {len(by_name)} contributors known by name, "
          f"{len(by_handle)} known by youtube channel")

    # Sort by cumulative duration desc and process
    ordered = sorted(
        significant.values(),
        key=lambda c: -_cluster_duration_seconds(c),
    )

    stub_min_seconds = args.create_stub_min_minutes * 60
    matched = unmatched = stubbed = 0
    plan: list[dict] = []
    for cluster in ordered:
        seconds = _cluster_duration_seconds(cluster)
        count = len(cluster["watches"])
        target_id = _match_cluster(cluster, by_name, by_handle)
        action: str
        if target_id:
            action = "match"
            matched += 1
        elif seconds >= stub_min_seconds:
            action = "stub"
            stubbed += 1
        else:
            action = "skip"
            unmatched += 1
        plan.append({
            "name": cluster.get("name"),
            "url": cluster.get("channel_url"),
            "count": count,
            "seconds": seconds,
            "action": action,
            "target_id": target_id,
            "strength": _strength_from_duration(seconds),
        })

    # Report
    print()
    print(f"  matched:   {matched:4d}  (existing contributors)")
    print(f"  stubbed:   {stubbed:4d}  (new contributor created — duration >= {args.create_stub_min_minutes} min)")
    print(f"  skipped:   {unmatched:4d}  (below stub threshold; not your main influence)")
    print()
    print(f"top {min(args.top, len(plan))} clusters by cumulative attention:")
    for row in plan[: args.top]:
        marker = {"match": "✓", "stub": "+", "skip": "·"}[row["action"]]
        target = row["target_id"] or "—"
        hours = row["seconds"] / 3600
        print(f"  {marker} {hours:6.1f}h  ({row['count']:4d}×)  s={row['strength']:.2f}  "
              f"{(row['name'] or '?')[:32]:32s}  → {target}")

    if args.dry_run:
        print("\n(dry-run — no graph mutations performed)")
        return 0

    # Apply via HTTP API so the same script works against any
    # environment from any machine — no DB credentials needed.
    import urllib.error

    def _get_edges(api: str, from_id: str, to_id: str) -> list[str]:
        url = (f"{api}/api/edges?from_id={urllib.parse.quote(from_id)}"
               f"&to_id={urllib.parse.quote(to_id)}&type=inspired-by&limit=10")
        try:
            with urllib.request.urlopen(
                urllib.request.Request(url, headers={"User-Agent": "curl/8.7.1"}),
                timeout=10,
            ) as r:
                return [e.get("id") for e in json.load(r).get("items", []) if e.get("id")]
        except Exception:  # noqa: BLE001
            return []

    def _post(path: str, body: dict) -> dict:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            f"{args.api}{path}", data=data, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "curl/8.7.1"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            return {"_err": e.code}
        except Exception as e:  # noqa: BLE001
            return {"_err": str(e)}

    landed = 0
    for row in plan:
        if row["action"] == "skip":
            continue
        target_id = row["target_id"]
        if row["action"] == "stub":
            handle = _channel_id_from_url(row.get("url"))
            slug = (handle or _normalize_name(row["name"] or "")).strip("@/").replace("/", "-")
            slug = re.sub(r"[^a-z0-9-]", "-", slug.lower()).strip("-") or "watched-channel"
            target_id = f"contributor:{slug}"
            # Check if it already exists; create if not
            check = urllib.request.Request(
                f"{args.api}/api/graph/nodes/{urllib.parse.quote(target_id)}",
                headers={"User-Agent": "curl/8.7.1"},
            )
            try:
                urllib.request.urlopen(check, timeout=10)
                existing = True
            except Exception:  # noqa: BLE001
                existing = False
            if not existing:
                _post("/api/graph/nodes", {
                    "id": target_id,
                    "type": "contributor",
                    "name": row["name"] or slug,
                    "description": row["name"] or slug,
                    "properties": {
                        "claimed": False,
                        "contributor_type": "HUMAN",
                        "presences": [{"provider": "youtube", "url": row["url"]}] if row.get("url") else [],
                        "imported_from": "watch_history_clustering",
                        "slug": slug,
                    },
                })
                # Auto-attune against vision concepts
                _post(f"/api/presences/{urllib.parse.quote(target_id)}/resonances/attune", {})

        # Create or refresh the inspired-by edge — strength carries
        # the duration signal, properties keep both signals visible
        # for debugging and richer downstream analysis.
        edge_props = {
            "watch_count": row["count"],
            "watch_seconds": row["seconds"],
            "watch_hours": round(row["seconds"] / 3600, 1),
            "source": "youtube_watch_history_cluster",
        }
        edge = _post("/api/edges", {
            "from_id": args.contributor,
            "to_id": target_id,
            "type": "inspired-by",
            "properties": edge_props,
            "strength": row["strength"],
            "created_by": "watch_history_clusterer",
        })
        if "_err" not in edge:
            landed += 1
        elif edge.get("_err") == 409:
            # Edge already exists — refresh its strength + properties
            # so re-runs propagate the duration discipline onto edges
            # that were created earlier with count-based strengths.
            existing_edges = _get_edges(args.api, args.contributor, target_id)
            for eid in existing_edges:
                req = urllib.request.Request(
                    f"{args.api}/api/edges/{urllib.parse.quote(eid)}",
                    data=json.dumps({
                        "strength": row["strength"],
                        "properties": edge_props,
                    }).encode(),
                    method="PATCH",
                    headers={"Content-Type": "application/json", "User-Agent": "curl/8.7.1"},
                )
                try:
                    urllib.request.urlopen(req, timeout=15).read()
                except Exception:  # noqa: BLE001
                    pass
            landed += 1

    print(f"\nlanded {landed} inspired-by edges to your main influences")
    return 0


if __name__ == "__main__":
    sys.exit(main())
