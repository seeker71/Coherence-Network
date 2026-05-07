#!/usr/bin/env python3
"""Encounter — flow external influences into the graph.

A contributor brings the body of evidence they carry — books read,
talks watched, songs listened to, gatherings attended — into the
graph by naming each one. Each becomes an asset or contributor
node; an `inspired-by` edge from the encountering contributor
holds the weave; auto-resonance computes which vision concepts
share frequency with the influence; and (when --with-creations is
on) the influence's public works auto-import so their emitted
spectrum joins the field.

Two paths:

    # Single encounter from the command line
    python3 scripts/encounter.py \\
        --contributor contributor:seeker71 \\
        --url https://example.com/book-page

    # Bulk encounter from a file (one URL or name per line)
    python3 scripts/encounter.py \\
        --contributor contributor:seeker71 \\
        --file ~/encounters.txt \\
        --with-creations

Each line in the file is treated as input to the resolver — a URL,
a name, or a paste. Empty lines and lines starting with ``#`` are
ignored so the file can be human-edited.

Lines beginning with a `>` are treated as encounter notes attached
to the *next* URL/name line — letting you record what was happening
in your field when you encountered it. The note lands as edge
metadata on the inspired-by edge.

Runs against any API URL via --api so the same script populates a
local dev DB or production. HTTP, not in-process, so no DB
credentials needed.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


# ── HTTP helpers ──────────────────────────────────────────────────────


def _post(api: str, path: str, body: dict, *, timeout: float = 30) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{api}{path}",
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "encounter-cli/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            return {"_http_error": e.code, "_detail": json.load(e)}
        except Exception:  # noqa: BLE001
            return {"_http_error": e.code, "_detail": str(e)}


def _patch(api: str, path: str, body: dict, *, timeout: float = 15) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{api}{path}",
        data=data,
        method="PATCH",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "encounter-cli/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        return {"_http_error": e.code}


def _get(api: str, path: str, *, timeout: float = 15) -> dict | list | None:
    req = urllib.request.Request(
        f"{api}{path}",
        headers={"User-Agent": "encounter-cli/1.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)
    except Exception:  # noqa: BLE001
        return None


# ── One encounter ─────────────────────────────────────────────────────


def _encounter_one(
    api: str,
    input_text: str,
    contributor_id: str,
    *,
    note: str | None = None,
    with_creations: bool = False,
) -> dict:
    res = _post(
        api, "/api/inspired-by",
        {"name": input_text, "source_contributor_id": contributor_id},
        timeout=60,
    )
    if "_http_error" in res:
        return {
            "input": input_text,
            "ok": False,
            "reason": f"http {res['_http_error']}: {str(res.get('_detail'))[:80]}",
        }

    identity_id = (res.get("identity") or {}).get("id")
    if not identity_id:
        return {"input": input_text, "ok": False, "reason": "no identity returned"}

    name = (res.get("resolved") or {}).get("name") or identity_id
    edge = res.get("edge") or {}
    edge_existed = bool(res.get("edge_existed"))

    # Optional encounter note on the edge
    if note and edge.get("id"):
        _patch(api, f"/api/edges/{edge['id']}", {"properties": {"encounter_note": note}})

    creations_imported = 0
    if with_creations:
        # Fill the influence's public works so their emitted spectrum
        # joins the field. Best-effort — sources may return 0 for
        # presences on uncovered platforms; that's recorded in the
        # coverage map on the node.
        cre = _post(
            api, f"/api/presences/{urllib.parse.quote(identity_id)}/creations/import",
            {}, timeout=120,
        )
        if "_http_error" not in cre:
            creations_imported = int(cre.get("creations_imported") or 0)

    # Read back the influence's concept resonances for the report
    concepts: list[dict] = []
    edges_resp = _get(
        api,
        f"/api/graph/nodes/{urllib.parse.quote(identity_id)}/edges?type=resonates-with&direction=outgoing",
    )
    if isinstance(edges_resp, list):
        concepts = [
            {"id": e.get("to_id"), "score": e.get("strength")}
            for e in edges_resp
            if (e.get("to_id") or "").startswith("lc-")
        ]
        concepts.sort(key=lambda c: -(c.get("score") or 0))

    return {
        "input": input_text,
        "ok": True,
        "identity_id": identity_id,
        "name": name,
        "edge_existed": edge_existed,
        "creations_imported": creations_imported,
        "concepts": concepts[:5],
    }


# ── File parsing ──────────────────────────────────────────────────────


def _encounters_from_file(path: Path) -> list[tuple[str, str | None]]:
    pending_note: str | None = None
    out: list[tuple[str, str | None]] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(">"):
            pending_note = line[1:].strip() or None
            continue
        out.append((line, pending_note))
        pending_note = None
    return out


# ── Main ──────────────────────────────────────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--contributor", required=True,
                   help="Contributor id of the encountering presence")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="A single URL or name to encounter")
    src.add_argument("--file", type=Path, help="Path to a file with one URL or name per line")
    p.add_argument("--note", help="Optional encounter note (only with --url)")
    p.add_argument("--limit", type=int, default=0, help="Stop after N encounters (0 = no limit)")
    p.add_argument("--api", default="http://localhost:8000",
                   help="API base URL (default http://localhost:8000)")
    p.add_argument("--with-creations", action="store_true",
                   help="After resolving each influence, also import their public creations "
                        "(YouTube/RSS/Substack/Goodreads/Bandcamp). Slower but fills the spectrum.")
    p.add_argument("--sleep", type=float, default=0.5,
                   help="Seconds to sleep between encounters (default 0.5)")
    args = p.parse_args()

    encounters: list[tuple[str, str | None]]
    if args.url:
        encounters = [(args.url, args.note)]
    else:
        if not args.file.exists():
            print(f"file not found: {args.file}", file=sys.stderr)
            return 2
        encounters = _encounters_from_file(args.file)

    if args.limit > 0:
        encounters = encounters[: args.limit]

    print(f"encountering {len(encounters)} input(s) → {args.contributor}  api={args.api}")
    if args.with_creations:
        print(f"  with-creations: ON (will fetch public works per influence)")

    landed = total_creations = 0
    for i, (text, note) in enumerate(encounters, 1):
        result = _encounter_one(
            args.api, text, args.contributor,
            note=note, with_creations=args.with_creations,
        )
        if not result["ok"]:
            print(f"  [{i:3d}] ✗ {text[:60]:60s}  {result['reason']}")
            continue
        concepts = ", ".join(
            f"{c['id'].replace('lc-', '')}({c['score']:.2f})"
            if c.get("score") else c["id"]
            for c in result["concepts"]
        )
        marker = "↺" if result["edge_existed"] else "✓"
        cre = f" +{result['creations_imported']}cre" if result.get("creations_imported") else ""
        print(
            f"  [{i:3d}] {marker} {result['name'][:38]:38s}{cre:8s}  → "
            f"{concepts or '(no concept resonance)'}"
        )
        landed += 1
        total_creations += result.get("creations_imported", 0)
        if args.sleep and i < len(encounters):
            time.sleep(args.sleep)
    print()
    print(f"landed: {landed}/{len(encounters)} encounters")
    if args.with_creations:
        print(f"creations imported across all influences: {total_creations}")
    return 0 if landed > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
