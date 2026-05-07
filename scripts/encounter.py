#!/usr/bin/env python3
"""Encounter — flow external influences into the graph.

A contributor brings the body of evidence they carry — books read,
talks watched, songs listened to, gatherings attended — into the
graph by naming each one. Each becomes an asset or contributor
node; an `inspired-by` edge from the encountering contributor
holds the weave; auto-resonance computes which vision concepts
share frequency with the influence.

Two paths:

    # Single encounter from the command line
    python3 scripts/encounter.py \\
        --contributor contributor:seeker71 \\
        --url https://example.com/book-page

    # Bulk encounter from a file (one URL or name per line)
    python3 scripts/encounter.py \\
        --contributor contributor:seeker71 \\
        --file ~/encounters.txt

Each line in the file is treated as input to the resolver — a URL,
a name, or a paste. Empty lines and lines starting with ``#`` are
ignored so the file can be human-edited.

Lines beginning with a `>` are treated as encounter notes attached
to the *next* URL/name line — letting you record what was happening
in your field when you encountered it. The note lands as edge
metadata on the inspired-by edge.

Output prints one line per encounter: status + identity + concept
resonances landed. Idempotent — re-running on the same input doesn't
duplicate edges.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _ensure_app_path() -> None:
    here = Path(__file__).resolve().parent
    api_dir = here.parent / "api"
    if api_dir.exists():
        sys_path = str(api_dir)
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)


def _encounter_one(input_text: str, contributor_id: str, *, note: str | None = None) -> dict:
    from app.services import inspired_by_service as service
    from app.services import graph_service

    resolved = service.resolve(input_text)
    if resolved is None:
        return {"input": input_text, "ok": False, "reason": "resolver couldn't make sense of input"}

    result = service.import_inspired_by(contributor_id, resolved)

    # Surface concept resonance the auto-attune produced for this
    # newly-resolved identity. Reading the edges back lets the caller
    # see what frequencies the influence met.
    identity_id = result["identity"]["id"]
    try:
        concept_edges = graph_service.list_edges(
            from_id=identity_id, edge_type="resonates-with", limit=20,
        ).get("items", [])
        concepts = sorted(
            (e for e in concept_edges if (e.get("to_id") or "").startswith("lc-")),
            key=lambda e: -(e.get("strength") or 0),
        )
    except Exception:  # noqa: BLE001
        concepts = []

    # Tag the edge with the encounter note when one was supplied.
    if note and result.get("edge"):
        edge_id = result["edge"].get("id")
        if edge_id:
            try:
                graph_service.update_edge(
                    edge_id, properties={"encounter_note": note},
                )
            except Exception:  # noqa: BLE001 — fall back gracefully
                pass

    return {
        "input": input_text,
        "ok": True,
        "identity_id": identity_id,
        "name": result["resolved"]["name"],
        "node_type": result["resolved"]["node_type"],
        "edge_existed": result.get("edge_existed", False),
        "weight": result.get("weight"),
        "concepts": [
            {"id": e["to_id"], "score": e.get("strength")} for e in concepts[:5]
        ],
    }


def _encounters_from_file(path: Path) -> list[tuple[str, str | None]]:
    """Read encounters from a text file.

    Returns a list of (input, note) tuples. A line starting with `>`
    is held as the next encounter's note.
    """
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


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--contributor", required=True, help="Contributor id of the encountering presence (e.g. contributor:seeker71)")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--url", help="A single URL or name to encounter")
    src.add_argument("--file", type=Path, help="Path to a file with one URL or name per line")
    p.add_argument("--note", help="Optional encounter note (only with --url)")
    p.add_argument("--limit", type=int, default=0, help="Stop after N encounters (0 = no limit)")
    args = p.parse_args()

    _ensure_app_path()

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

    landed = 0
    for i, (text, note) in enumerate(encounters, 1):
        result = _encounter_one(text, args.contributor, note=note)
        if not result["ok"]:
            print(f"  [{i:3d}] ✗ {text[:60]:60s}  {result['reason']}")
            continue
        concepts = ", ".join(
            f"{c['id'].replace('lc-', '')}({c['score']:.2f})" if c.get("score") else c["id"]
            for c in result["concepts"]
        )
        marker = "↺" if result["edge_existed"] else "✓"
        print(
            f"  [{i:3d}] {marker} {result['name'][:38]:38s}  → {concepts or '(no concept resonance)'}"
        )
        landed += 1
    print()
    print(f"landed: {landed}/{len(encounters)} encounters")
    return 0 if landed > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
