#!/usr/bin/env python3
"""Flow Audible listening history into the graph.

Audible is one of the deepest streams in the founding contributor's
body of evidence — 4500+ hours of cumulative listening across 200+
books and 100+ authors over a decade. This brings that signal into
the graph alongside YouTube watch clustering:

  · Each unique book becomes an `asset` node (`creation_kind=book`)
    carrying `runtime_length_min` from the Audible catalog
  · Each author becomes (or matches) a `contributor` node — name
    first via the resolver's name-dedupe, falling back to URL
  · `contributes-to` from author → book; `inspired-by` from the
    listener → author with strength logged from the cumulative
    listening hours summed across that author's books
  · Auto-attune fires on each new identity so concept resonance
    flows immediately

Input files (existing on disk):

  · `~/CoherenceFieldAnalysis/input/audible/playwright/audible-library.json`
    — 233 books in the listener's library
  · `docs/field/urs/trace/audible_duration_metadata.json`
    — runtime in minutes keyed by ASIN

Usage:

    python3 scripts/ingest_audible_history.py \\
        --contributor contributor:seeker71 \\
        --library ~/CoherenceFieldAnalysis/input/audible/playwright/audible-library.json \\
        --durations docs/field/urs/trace/audible_duration_metadata.json \\
        --api https://api.coherencycoin.com \\
        --reading-multiplier 1.0
        # Audible plays at recorded speed — multiplier=1.
        # For physical-book ingest from a Goodreads CSV, use 4.0:
        # the founding contributor reads physical books ~3-5x slower
        # than the audiobook plays at speed-1.

Idempotent: re-runs PATCH existing inspired-by strengths rather
than minting duplicates; matched authors collapse to canonical
identities via the resolver's name-first dedupe.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path


_NAME_NOISE = re.compile(
    r"\b(md|phd|dr|prof|professor|jr|sr|mr|mrs|ms|esq|the\s+|of\s+)\b",
    re.IGNORECASE,
)


def _normalize_author(name: str) -> str:
    """Collapse author-name surface noise so 'Tara Swart MD PhD' and
    'Tara Swart' resolve to the same canonical contributor."""
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.lower()
    n = _NAME_NOISE.sub(" ", n)
    n = re.sub(r"[^\w\s-]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def _strength_from_hours(hours: float) -> float:
    """Logarithmic strength curve in [0, 1] — same shape as the
    YouTube watch clusterer so the two streams compose cleanly."""
    h = max(0.0, hours)
    return min(1.0, math.log1p(h) / math.log1p(1000))


# ── HTTP helpers ──────────────────────────────────────────────────────


def _http(method: str, api: str, path: str, body: dict | None = None,
          timeout: float = 30) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{api}{path}", data=data, method=method,
        headers={"Content-Type": "application/json", "User-Agent": "curl/8.7.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r) if r.status != 204 else {}
    except urllib.error.HTTPError as e:
        try:
            return {"_err": e.code, "_detail": json.load(e)}
        except Exception:  # noqa: BLE001
            return {"_err": e.code}
    except Exception as e:  # noqa: BLE001
        return {"_err": str(e)}


def _post(api: str, path: str, body: dict, timeout: float = 30) -> dict:
    return _http("POST", api, path, body, timeout=timeout)


def _patch(api: str, path: str, body: dict, timeout: float = 30) -> dict:
    return _http("PATCH", api, path, body, timeout=timeout)


def _get(api: str, path: str, timeout: float = 15) -> dict | list | None:
    req = urllib.request.Request(
        f"{api}{path}",
        headers={"User-Agent": "curl/8.7.1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception:  # noqa: BLE001
        return None


# ── Main flow ─────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--contributor", required=True,
                   help="Listener's contributor id (e.g. contributor:seeker71)")
    p.add_argument("--library", type=Path, required=True,
                   help="Path to audible-library.json")
    p.add_argument("--durations", type=Path, required=True,
                   help="Path to audible_duration_metadata.json")
    p.add_argument("--api", default="https://api.coherencycoin.com")
    p.add_argument("--reading-multiplier", type=float, default=1.0,
                   help="Multiply each book's runtime by this factor before "
                        "computing strength. Audible at 1x speed = 1.0; "
                        "physical books read 3-5x slower than audio = 4.0.")
    p.add_argument("--min-author-hours", type=float, default=2.0,
                   help="Don't lay an inspired-by edge for authors with less "
                        "than this many cumulative hours (default 2.0)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--top", type=int, default=30)
    p.add_argument("--sleep", type=float, default=0.4,
                   help="Seconds to sleep between API writes")
    args = p.parse_args(argv)

    if not args.library.exists():
        print(f"library not found: {args.library}", file=sys.stderr)
        return 2
    if not args.durations.exists():
        print(f"duration metadata not found: {args.durations}", file=sys.stderr)
        return 2

    library = json.loads(args.library.read_text())
    duration_doc = json.loads(args.durations.read_text())
    durations_by_asin = duration_doc.get("products") or {}

    print(f"reading {len(library)} library entries from {args.library.name}")
    print(f"  joined against {len(durations_by_asin)} duration records")

    # Aggregate author hours from joined library + durations
    by_author: dict[str, dict] = defaultdict(
        lambda: {"hours": 0.0, "books": 0, "asins": set(), "name": None}
    )
    for entry in library:
        asin = entry.get("asin")
        if not asin:
            continue
        meta = durations_by_asin.get(asin)
        if not meta:
            continue
        runtime = meta.get("runtime_length_min") or 0
        if not isinstance(runtime, (int, float)) or runtime <= 0:
            continue
        hours = (runtime / 60.0) * args.reading_multiplier
        # Use authors from metadata first (cleaner), fall back to library
        authors = meta.get("authors") or [entry.get("author") or "Unknown"]
        if isinstance(authors, str):
            authors = [authors]
        for raw_name in authors:
            name = (raw_name or "").strip()
            if not name:
                continue
            agg = by_author[_normalize_author(name)]
            agg["hours"] += hours
            agg["books"] += 1
            agg["asins"].add(asin)
            if not agg["name"] or len(name) < len(agg["name"]):
                # Prefer the shortest variant as canonical display name
                # ("Tara Swart" over "Tara Swart MD PhD")
                agg["name"] = name

    significant = [
        (norm, agg) for norm, agg in by_author.items()
        if agg["hours"] >= args.min_author_hours
    ]
    significant.sort(key=lambda x: -x[1]["hours"])
    total_hours = sum(a["hours"] for _, a in significant)

    print(f"  {len(significant)} authors at >= {args.min_author_hours}h "
          f"(~{total_hours:.0f} cumulative hours)")
    print()
    print(f"top {min(args.top, len(significant))} authors by cumulative hours:")
    for norm, agg in significant[: args.top]:
        s = _strength_from_hours(agg["hours"])
        print(f"  {agg['hours']:7.1f}h  ({agg['books']:3d} books)  s={s:.2f}  "
              f"{agg['name'][:40]}")

    if args.dry_run:
        print("\n(dry-run — no graph mutations performed)")
        return 0

    print("\napplying to graph…")
    landed = refreshed = 0
    for norm, agg in significant:
        name = agg["name"]
        hours = agg["hours"]
        strength = _strength_from_hours(hours)

        # Resolve author through the inspired-by service. The resolver's
        # name-first dedupe (shipped earlier) collapses surface variants
        # to the canonical identity if one exists; otherwise mints a
        # new contributor stub. Auto-attune to vision concepts fires
        # automatically on creation.
        res = _post(args.api, "/api/inspired-by", {
            "name": name,
            "source_contributor_id": args.contributor,
        }, timeout=60)
        if "_err" in res:
            print(f"  ✗ {name[:40]:40s}  resolver error: {res.get('_err')}")
            time.sleep(args.sleep)
            continue

        identity_id = (res.get("identity") or {}).get("id")
        if not identity_id:
            time.sleep(args.sleep)
            continue

        edge = res.get("edge") or {}
        edge_existed = bool(res.get("edge_existed"))
        edge_props = {
            "audible_hours": round(hours, 1),
            "audible_books": agg["books"],
            "source": "audible_listening_history",
        }

        if edge_existed:
            # Refresh the existing edge's strength + properties so this
            # ingest pass propagates the cumulative-hours signal onto
            # whatever the resolver landed previously.
            existing_url = (
                f"/api/edges?from_id={urllib.parse.quote(args.contributor)}"
                f"&to_id={urllib.parse.quote(identity_id)}&type=inspired-by"
            )
            edges_resp = _get(args.api, existing_url) or {}
            for e in edges_resp.get("items", []) if isinstance(edges_resp, dict) else []:
                _patch(args.api, f"/api/edges/{urllib.parse.quote(e['id'])}", {
                    "strength": strength,
                    "properties": edge_props,
                })
                refreshed += 1
                break
        else:
            # The resolver's POST already created the edge with default
            # strength; refresh it to the duration-weighted value.
            edge_id = edge.get("id")
            if edge_id:
                _patch(args.api, f"/api/edges/{urllib.parse.quote(edge_id)}", {
                    "strength": strength,
                    "properties": edge_props,
                })
            landed += 1

        time.sleep(args.sleep)

    print()
    print(f"  landed:    {landed} new inspired-by edges to authors")
    print(f"  refreshed: {refreshed} existing edges with audible-hour strength")
    print(f"  cumulative: {total_hours:.0f} hours of attention now visible")
    return 0


if __name__ == "__main__":
    sys.exit(main())
