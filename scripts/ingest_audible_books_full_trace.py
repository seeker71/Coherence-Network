#!/usr/bin/env python3
"""Lay every Audible book as a first-class asset with full source trace.

The earlier `ingest_audible_history.py` aggregates inspired-by edges
by author hours but doesn't surface each book — the trace
dead-ends at the author. The visitor sees "604h · 30 books" but
can't click through to any of the 30 actual works or follow them
to their Audible product pages.

This script closes that gap. For each book in the listener's
Audible library:

  1. Resolve the canonical author identity (name-dedupe — the
     resolver previously created some authors named after their
     book-series websites; this run renames them to the actual
     author name).
  2. Create the book as an `asset` node with full metadata:
     `canonical_url` = Audible product page,
     `image_url` = cover thumbnail,
     `runtime_length_min` = duration,
     `asin`, `creation_kind="book"`.
  3. Lay author → book as `contributes-to` (creator side).
  4. Lay listener → book as `inspired-by` with per-book hours
     (consumer side, more granular than the per-author edge).

After this, the trace reads end-to-end: a visitor encountering a
"Terry Mancour 604h · 30 books" chip in the unified body-of-evidence
view → clicks → lands on Mancour's page → sees his 30 books as
emitted creations → clicks any one → lands on its asset page →
follows `canonical_url` to the public Audible page.

Usage:
    python3 scripts/ingest_audible_books_full_trace.py \\
        --library ~/CoherenceFieldAnalysis/input/audible/playwright/audible-library.json \\
        --durations docs/field/urs/trace/audible_duration_metadata.json \\
        --listener contributor:seeker71 \\
        --api https://api.coherencycoin.com
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


def _req(api: str, method: str, path: str, body: dict | None = None,
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


def _slugify(s: str) -> str:
    n = unicodedata.normalize("NFKD", s or "")
    n = "".join(c for c in n if not unicodedata.combining(c))
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", n.lower())).strip("-")


def _strength(hours: float) -> float:
    return min(1.0, math.log1p(max(0.0, hours)) / math.log1p(1000))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--library", type=Path, required=True)
    p.add_argument("--durations", type=Path, required=True)
    p.add_argument("--listener", required=True,
                   help="Listener contributor id (e.g. contributor:seeker71)")
    p.add_argument("--api", default="https://api.coherencycoin.com")
    p.add_argument("--sleep", type=float, default=0.05)
    p.add_argument("--source-tag", default="audible_listening_history",
                   help="Match existing inspired-by edges by this source value")
    args = p.parse_args(argv)

    library = json.loads(args.library.read_text())
    durations = json.loads(args.durations.read_text()).get("products", {})

    print(f"=== Step 1: rename existing audible-author contributors to canonical names ===")
    existing_edges = _req(
        args.api, "GET",
        f"/api/edges?from_id={urllib.parse.quote(args.listener)}&type=inspired-by&limit=300",
    ).get("items", [])
    audible_edges = [
        e for e in existing_edges
        if (e.get("properties") or {}).get("source") == args.source_tag
    ]

    # Aggregate by author for canonical-name mapping
    by_author: dict[str, dict] = defaultdict(
        lambda: {"hours": 0.0, "books": [], "name": None}
    )
    for entry in library:
        asin = entry.get("asin")
        if not asin:
            continue
        meta = durations.get(asin)
        if not meta:
            continue
        rt = meta.get("runtime_length_min") or 0
        if not isinstance(rt, (int, float)) or rt <= 0:
            continue
        authors = meta.get("authors") or [entry.get("author") or "Unknown"]
        if isinstance(authors, str):
            authors = [authors]
        for raw in authors:
            name = (raw or "").strip()
            if not name:
                continue
            norm = re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", name.lower())).strip()
            agg = by_author[norm]
            agg["hours"] += rt / 60.0
            agg["books"].append({"entry": entry, "meta": meta, "minutes": rt})
            if not agg["name"] or len(name) < len(agg["name"]):
                agg["name"] = name

    # Match existing edges to author clusters by hours-closest, rename if off
    authors_by_id: dict[str, str] = {}
    fixed = 0
    for e in audible_edges:
        edge_hours = (e.get("properties") or {}).get("audible_hours") or 0
        cur_id = e.get("to_id")
        if not cur_id or not edge_hours:
            continue
        best = None
        best_diff = 999.0
        for norm, agg in by_author.items():
            d = abs(agg["hours"] - edge_hours)
            if d < best_diff:
                best_diff = d
                best = (norm, agg)
        if best and best_diff < 1.0:
            _, agg = best
            authors_by_id[cur_id] = agg["name"]
            cur_name = (e.get("to_node") or {}).get("name", "")
            if cur_name != agg["name"]:
                slug = _slugify(agg["name"])
                r = _req(args.api, "PATCH",
                    f"/api/graph/nodes/{urllib.parse.quote(cur_id)}",
                    {"name": agg["name"], "properties": {
                        "slug": slug, "imported_from": "audible_author_rename"}})
                if "_err" not in r:
                    fixed += 1
                    print(f"  ✓ {cur_id[:30]} '{cur_name[:30]}' → '{agg['name']}'")
    print(f"  renamed {fixed} authors to canonical names\n")

    print(f"=== Step 2: create book assets with canonical_url to Audible ===")
    created = existing_books = edges_landed = 0
    for norm, agg in by_author.items():
        author_name = agg["name"]
        author_id = next(
            (cid for cid, nm in authors_by_id.items() if nm == author_name),
            None,
        )
        if not author_id:
            # Tier-2 author below the inspired-by significance threshold;
            # skip per-book ingest since the chip wouldn't be reachable.
            continue
        for book in agg["books"]:
            entry = book["entry"]
            meta = book["meta"]
            asin = meta.get("asin") or entry.get("asin")
            title = entry.get("title") or meta.get("title") or asin
            if not asin or not title:
                continue
            book_id = f"asset:audible-{asin}"
            ex = _req(args.api, "GET",
                f"/api/graph/nodes/{urllib.parse.quote(book_id)}")
            if ex and not ex.get("_err"):
                existing_books += 1
            else:
                clean_title = re.sub(r"\s*By\s*:\s*.*$", "", title).strip()
                r = _req(args.api, "POST", "/api/graph/nodes", {
                    "id": book_id, "type": "asset",
                    "name": clean_title,
                    "description": (
                        f"Audible audiobook by {author_name}. Runtime "
                        f"{book['minutes']//60}h {book['minutes']%60}m."
                    ),
                    "properties": {
                        "creation_kind": "book",
                        "asset_type": "CONTENT",
                        # Library entries carry `url`; listen-history
                        # carries `product_url`. Try both so either
                        # source path lands the trace.
                        "canonical_url": entry.get("url") or entry.get("product_url") or "",
                        "image_url": entry.get("cover") or "",
                        "runtime_length_min": book["minutes"],
                        "asin": asin,
                        "imported_from": "audible_book_ingest",
                        "claimable": False,
                        "slug": f"audible-{_slugify(clean_title)[:60]}",
                    },
                })
                if r.get("_err"):
                    print(f"  ✗ {book_id}: {r}")
                    continue
                created += 1

            # Author --contributes-to--> book
            r = _req(args.api, "POST", "/api/edges", {
                "from_id": author_id, "to_id": book_id,
                "type": "contributes-to",
                "properties": {"kind": "book", "role": "primary"},
                "strength": 1.0, "created_by": "audible_book_ingest",
            })
            if r.get("_err") in (None, 409):
                edges_landed += 1

            # Listener --inspired-by--> book (per-book granularity)
            h = book["minutes"] / 60.0
            _req(args.api, "POST", "/api/edges", {
                "from_id": args.listener, "to_id": book_id,
                "type": "inspired-by",
                "properties": {
                    "audible_hours": round(h, 1),
                    "audible_book_minutes": book["minutes"],
                    "source": "audible_book_listening",
                },
                "strength": _strength(h),
                "created_by": "audible_book_ingest",
            })
            if args.sleep:
                time.sleep(args.sleep)

    print(f"  created: {created} book assets")
    print(f"  existed: {existing_books}")
    print(f"  edges landed/refreshed: {edges_landed}")
    print(f"\ntrace now complete: chip → author → books → Audible URL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
