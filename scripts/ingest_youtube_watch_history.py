#!/usr/bin/env python3
"""Ingest a YouTube watch-history file from Google Takeout.

Google Takeout exports YouTube watch history as
``Takeout/YouTube and YouTube Music/history/watch-history.json`` —
a JSON array of every video the user watched, with title, URL,
channel, and timestamp. Each entry becomes:

  · An ``asset`` node for the video (deduped by canonical URL)
  · A low-confidence ``contributor`` node for the channel (when not
    yet in the graph) so the video has a creator
  · A ``contributes-to`` edge from channel → video
  · An ``inspired-by`` edge from the watcher → video, carrying the
    watch timestamp on the edge as ``encountered_at``
  · Auto-resonance edges from the video to vision concepts the
    title or channel name shares frequency with

Usage:

    python3 scripts/ingest_youtube_watch_history.py \\
        --contributor contributor:seeker71 \\
        --file ~/Takeout/YouTube\\ and\\ YouTube\\ Music/history/watch-history.json

By default the script ingests every entry in the file. Use ``--limit``
when iterating; the script is idempotent so a re-run with a higher
limit just adds the next slice.

Watch history can be tens of thousands of entries for long-time
users. The script reports progress every 50 entries and skips
ad-impression / removed / restricted videos that have no real URL.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlparse


def _ensure_app_path() -> None:
    here = Path(__file__).resolve().parent
    api_dir = here.parent / "api"
    if api_dir.exists():
        p = str(api_dir)
        if p not in sys.path:
            sys.path.insert(0, p)


def _is_real_video_url(url: str | None) -> bool:
    """A real watch-history entry points at a watch URL with a real
    video id. Ad impressions and removed videos either lack
    ``titleUrl`` or point at ``youtube.com`` without a video id."""
    if not url:
        return False
    try:
        p = urlparse(url)
    except ValueError:
        return False
    host = (p.netloc or "").lower()
    if not (host.endswith("youtube.com") or host == "youtu.be"):
        return False
    if host.endswith("youtube.com"):
        # Real watches have ``?v=...`` on the watch URL.
        return "v=" in (p.query or "")
    # youtu.be/<id>
    return bool((p.path or "").lstrip("/"))


def _ingest_one(entry: dict, contributor_id: str) -> dict:
    """Resolve one watch-history entry into the graph."""
    from app.services import inspired_by_service as service
    from app.services import graph_service

    url = entry.get("titleUrl")
    if not _is_real_video_url(url):
        return {"skipped": True, "reason": "no_real_url"}

    resolved = service.resolve(url)
    if resolved is None:
        return {"skipped": True, "reason": "resolver_miss", "url": url}

    result = service.import_inspired_by(contributor_id, resolved)

    # Tag the inspired-by edge with the watch timestamp.
    when = entry.get("time")
    if when and result.get("edge"):
        edge_id = result["edge"].get("id")
        if edge_id:
            try:
                graph_service.update_edge(
                    edge_id, properties={"encountered_at": when, "source": "youtube_watch_history"},
                )
            except Exception:  # noqa: BLE001 — encounter metadata isn't load-bearing
                pass
    return {
        "ok": True,
        "name": result["resolved"]["name"],
        "node_id": result["identity"]["id"],
        "edge_existed": result.get("edge_existed", False),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--contributor", required=True,
                   help="Contributor id of the watcher (e.g. contributor:seeker71)")
    p.add_argument("--file", type=Path, required=True,
                   help="Path to watch-history.json from Google Takeout")
    p.add_argument("--limit", type=int, default=0,
                   help="Stop after N entries (0 = no limit). Idempotent — re-runs continue.")
    p.add_argument("--start", type=int, default=0,
                   help="Skip the first N entries (resume from offset)")
    args = p.parse_args(argv)

    if not args.file.exists():
        print(f"file not found: {args.file}", file=sys.stderr)
        return 2

    _ensure_app_path()

    raw = args.file.read_text(encoding="utf-8")
    try:
        entries = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"could not parse {args.file} as JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(entries, list):
        print(f"expected a JSON array, got {type(entries).__name__}", file=sys.stderr)
        return 2

    if args.start:
        entries = entries[args.start:]
    if args.limit > 0:
        entries = entries[: args.limit]

    print(f"ingesting {len(entries)} watch-history entries → {args.contributor}")
    landed = skipped = errored = duped = 0
    for i, entry in enumerate(entries, 1):
        try:
            r = _ingest_one(entry, args.contributor)
        except Exception as exc:  # noqa: BLE001
            errored += 1
            print(f"  [{i:5d}] ✗ {exc}")
            continue
        if r.get("skipped"):
            skipped += 1
            continue
        if r.get("edge_existed"):
            duped += 1
        else:
            landed += 1
        if i % 50 == 0:
            print(f"  [{i:5d}] landed={landed} duped={duped} skipped={skipped} errored={errored}")

    print()
    print(f"  landed:  {landed}")
    print(f"  duped:   {duped}  (already in graph)")
    print(f"  skipped: {skipped}  (ads / removed / no real URL)")
    print(f"  errored: {errored}")
    return 0 if (landed + duped) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
