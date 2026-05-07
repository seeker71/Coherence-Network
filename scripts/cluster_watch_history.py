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


# ── Strength curve ────────────────────────────────────────────────────


def _strength(count: int) -> float:
    """Map watch count → inspired-by edge strength in [0, 1].

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
    p.add_argument("--min-watches", type=int, default=5,
                   help="Minimum watches to qualify as a main influence (default 5)")
    p.add_argument("--create-stub-min", type=int, default=15,
                   help="Minimum watches to create a stub for unmatched channels (default 15)")
    p.add_argument("--api", default="http://localhost:8000",
                   help="API base URL (default http://localhost:8000)")
    p.add_argument("--dry-run", action="store_true",
                   help="Plan only — show what would land without writing the graph")
    p.add_argument("--top", type=int, default=50,
                   help="Show details for the top N clusters in the report (default 50)")
    args = p.parse_args(argv)

    if not args.file.exists():
        print(f"file not found: {args.file}", file=sys.stderr)
        return 2

    try:
        entries = _read_takeout(args.file)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"could not parse {args.file}: {exc}", file=sys.stderr)
        return 2

    print(f"reading {len(entries)} watch entries from {args.file.name}")
    clusters = _build_clusters(entries)
    print(f"clustered into {len(clusters)} unique channels")

    significant = {
        k: c for k, c in clusters.items()
        if len(c["watches"]) >= args.min_watches
    }
    print(f"  {len(significant)} clusters at >= {args.min_watches} watches "
          f"({sum(len(c['watches']) for c in significant.values())} watches total)")

    print("loading existing contributors from the graph…")
    by_name, by_handle = _load_existing_contributors(args.api)
    print(f"  {len(by_name)} contributors known by name, "
          f"{len(by_handle)} known by youtube channel")

    # Sort by watch count desc and process
    ordered = sorted(
        significant.values(), key=lambda c: -len(c["watches"]),
    )

    matched = unmatched = stubbed = 0
    plan: list[dict] = []
    for cluster in ordered:
        count = len(cluster["watches"])
        target_id = _match_cluster(cluster, by_name, by_handle)
        action: str
        if target_id:
            action = "match"
            matched += 1
        elif count >= args.create_stub_min:
            action = "stub"
            stubbed += 1
        else:
            action = "skip"
            unmatched += 1
        plan.append({
            "name": cluster.get("name"),
            "url": cluster.get("channel_url"),
            "count": count,
            "action": action,
            "target_id": target_id,
            "strength": _strength(count),
        })

    # Report
    print()
    print(f"  matched:   {matched:4d}  (existing contributors)")
    print(f"  stubbed:   {stubbed:4d}  (new contributor created — count >= {args.create_stub_min})")
    print(f"  skipped:   {unmatched:4d}  (below stub threshold; not your main influence)")
    print()
    print(f"top {min(args.top, len(plan))} clusters:")
    for row in plan[: args.top]:
        marker = {"match": "✓", "stub": "+", "skip": "·"}[row["action"]]
        target = row["target_id"] or "—"
        print(f"  {marker} {row['count']:5d} watches  s={row['strength']:.2f}  "
              f"{(row['name'] or '?')[:32]:32s}  → {target}")

    if args.dry_run:
        print("\n(dry-run — no graph mutations performed)")
        return 0

    # Apply via HTTP API so the same script works against any
    # environment from any machine — no DB credentials needed.
    import urllib.error

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

        # Create inspired-by edge
        edge = _post("/api/edges", {
            "from_id": args.contributor,
            "to_id": target_id,
            "type": "inspired-by",
            "properties": {
                "watch_count": row["count"],
                "source": "youtube_watch_history_cluster",
            },
            "strength": row["strength"],
            "created_by": "watch_history_clusterer",
        })
        # 201/200 mean landed; 409 (conflict) means already exists
        if "_err" not in edge or edge.get("_err") == 409:
            landed += 1

    print(f"\nlanded {landed} inspired-by edges to your main influences")
    return 0


if __name__ == "__main__":
    sys.exit(main())
