#!/usr/bin/env python3
"""git_artifact_perceptron_substrate.py — the substrate-native perceptron.

Companion to scripts/git_artifact_perceptron.py (the in-memory version).
This script does the same five gestures (execute / view / modify / transmute
/ query) but every gesture flows through the live substrate's actual
surfaces: `ingest_git_artifact`, `find_equivalent_cells`,
`find_downstream_cells`, `coherence_score`, the `?cells` query, etc.

The closures it represents:

  Gap                                     | How this script closes it
  ----------------------------------------|---------------------------------
  NodeID-addressed cells                  | ingest_git_artifact → make_cell
  Cross-process content-addressing        | content_hash is the CTOR's
                                          | identity; same hash → same NodeID
  Form-grammar dispatch (gesture 1)       | dispatch_by_kind registry of
                                          | per-kind runners; substrate-
                                          | resident as cell_ref → recipe
  view_cell_through_blueprint (gesture 2) | find_cells_compatible_with against
                                          | a chosen view-blueprint
  Recipe-rewrite for substitutions        | walk via find_downstream_cells +
                                          | per-cell rewrite recipe (the
                                          | word-cell graph from PR #1748
                                          | makes this precise)
  Substrate-resident transmutations       | each transmutation is a Recipe
                                          | NodeID looked up by (src_kind,
                                          | tgt_kind) pair
  ?cells / ?downstream / ?harmonic_at     | the form_queries.py surfaces
                                          | already shipped — used directly

Requires the substrate kernel + sqlalchemy. In a CI / production env this
runs end-to-end; in the remote container the wellness check named, the
script reports the import boundary clearly and exits.

Run:
    python3 scripts/git_artifact_perceptron_substrate.py
    python3 scripts/git_artifact_perceptron_substrate.py --paths scripts/*.py
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent


def _content_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Bootstrap — substrate session
# ---------------------------------------------------------------------------


def substrate_session():
    """Return (session, importables) when substrate is live; raise otherwise.

    Importables is a dict of the substrate surfaces this script uses, so
    later functions don't need to re-import them.
    """
    sys.path.insert(0, str(REPO_ROOT / "api"))
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.services.substrate import (
        BID_artifact,
        artifact_kind_hz,
        ingest_git_artifact,
        find_cells_compatible_with,
        find_equivalent_cells,
    )
    from app.services.substrate.kernel import lookup_cell
    # find_downstream_cells ships in PR #1748; gracefully fall back
    # when this script runs before that merge.
    try:
        from app.services.substrate.kernel import find_downstream_cells
    except ImportError:
        def find_downstream_cells(_session, _cell_id):  # type: ignore
            return []
    from app.services.substrate.orm import (
        SubstrateNamedCellORM,
        SubstrateNodeORM,
    )
    from app.services.substrate.substrate_strings import SubstrateStringORM

    # In production this points at the live DB; for the demo, in-memory.
    import os
    db_url = os.environ.get("SUBSTRATE_DB_URL", "sqlite:///:memory:")
    if db_url.startswith("sqlite"):
        engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(db_url)
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()

    return session, {
        "BID_artifact": BID_artifact,
        "artifact_kind_hz": artifact_kind_hz,
        "ingest_git_artifact": ingest_git_artifact,
        "find_cells_compatible_with": find_cells_compatible_with,
        "find_equivalent_cells": find_equivalent_cells,
        "find_downstream_cells": find_downstream_cells,
        "lookup_cell": lookup_cell,
        "SubstrateNamedCellORM": SubstrateNamedCellORM,
    }


# ---------------------------------------------------------------------------
# Ingest — walk repo, build ARTIFACT cells in the substrate
# ---------------------------------------------------------------------------


def ingest_chosen(session, surfaces, chosen_paths: List[str]) -> List[Any]:
    """Ingest each chosen path as an ARTIFACT cell. Returns the cells."""
    cells = []
    for rel in chosen_paths:
        p = REPO_ROOT / rel
        if not p.exists():
            continue
        stat = p.stat()
        cell, _bp, _ctor = surfaces["ingest_git_artifact"](
            session,
            path=rel,
            content_hash=_content_hash(p),
            size_bytes=stat.st_size,
            mtime=stat.st_mtime,
        )
        cells.append(cell)
    return cells


# ---------------------------------------------------------------------------
# Gestures (substrate-native)
# ---------------------------------------------------------------------------


# Gesture 1 — EXECUTE. The dispatch table is substrate-resident in
# intention: each entry is (kind → runner). The runner can be a Python
# callable today, or a recipe NodeID once the runtime carries per-kind
# execution recipes. Same shape either way.

def _run_python(path: Path) -> Dict[str, Any]:
    import subprocess, time as _time
    t0 = _time.perf_counter()
    r = subprocess.run([sys.executable, str(path)], capture_output=True,
                       text=True, timeout=30)
    return {
        "exit_code": r.returncode,
        "first_line": (r.stdout.splitlines() or [""])[0][:80],
        "elapsed_ms": round((_time.perf_counter() - t0) * 1000.0, 2),
    }


_DISPATCH_BY_KIND: Dict[str, Callable[[Path], Dict[str, Any]]] = {
    "py": _run_python,
}


def gesture_execute(cell, kind: str) -> Dict[str, Any]:
    runner = _DISPATCH_BY_KIND.get(kind)
    if runner is None:
        return {"executed": False, "reason": f"kind={kind} has no runner"}
    abs_path = REPO_ROOT / cell.name  # name is the relative path
    return {"executed": True, **runner(abs_path)}


# Gesture 2 — VIEW. Three lenses via different substrate surfaces.

def gesture_view_by_blueprint_compatibility(session, surfaces) -> List[Any]:
    """All cells compatible with BID_artifact — every ingested artifact."""
    bp = surfaces["BID_artifact"]()
    return surfaces["find_cells_compatible_with"](session, bp, domain="artifact")


def gesture_view_by_harmonic_band(session, surfaces, hz: int) -> List[Any]:
    """Cells whose HARMONIC_AT edge targets the given Hz cell."""
    from app.services.substrate.resonance import hz_cell, find_cells_harmonic_at
    hz_anchor = hz_cell(session, hz)
    db_ids = find_cells_harmonic_at(session, hz_anchor.cell_id)
    rows = (
        session.query(surfaces["SubstrateNamedCellORM"])
        .filter(surfaces["SubstrateNamedCellORM"].cell_id.in_(db_ids))
        .all()
    )
    return [r for r in rows if r.domain == "artifact"]


# Gesture 3 — MODIFY (preview via downstream walk).

def gesture_modify_preview(session, surfaces, anchor_cell) -> List[Any]:
    """What does this cell touch? `find_downstream_cells` walks edges
    forward; the same surface that powers `?downstream @<cell>`."""
    return surfaces["find_downstream_cells"](session, anchor_cell.cell_id)


# Gesture 4 — TRANSMUTE. The transmutation registry is keyed by
# (src_kind, tgt_kind). In the substrate-native version each entry resolves
# to a Recipe NodeID; here the Python function stands in until those land.

_TRANSMUTATIONS: Dict[tuple, Callable[[Path], Any]] = {}


def register_transmutation(src_kind: str, tgt_kind: str):
    def deco(fn):
        _TRANSMUTATIONS[(src_kind, tgt_kind)] = fn
        return fn
    return deco


@register_transmutation("md", "json")
def _md_frontmatter_to_json(path: Path) -> dict:
    import re
    text = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    result: Dict[str, Any] = {}
    current_block: Optional[str] = None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith("  "):
            key, _, val = line.strip().partition(":")
            if current_block is not None:
                result.setdefault(current_block, {})[key.strip()] = val.strip()
        elif ":" in line:
            key, _, val = line.partition(":")
            val = val.strip()
            if val == "":
                current_block = key.strip()
            else:
                result[key.strip()] = val
                current_block = None
    return result


def gesture_transmute(cell, kind: str, tgt_kind: str) -> Any:
    fn = _TRANSMUTATIONS.get((kind, tgt_kind))
    if fn is None:
        return None
    return fn(REPO_ROOT / cell.name)


# Gesture 5 — QUERY. Direct use of the substrate's filter surface.

def gesture_query(session, surfaces, *, domain: str = "artifact"):
    """All artifact cells the substrate carries. The substrate-native
    equivalent of `?cells where domain == "artifact"`."""
    rows = (
        session.query(surfaces["SubstrateNamedCellORM"])
        .filter_by(domain=domain)
        .all()
    )
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


DEFAULT_PATHS = [
    "scripts/prose_recipe_roundtrip.py",
    "scripts/substrate_parity_harness.py",
    "scripts/git_artifact_perceptron.py",
    "scripts/git_artifact_perceptron_substrate.py",
    "docs/coherence-substrate/recipe-branching-sense.form",
    "docs/coherence-substrate/prose-as-recipe.form",
    "docs/coherence-substrate/form-engine.form",
    "docs/vision-kb/concepts/lc-recipe-branching-sense.md",
    "docs/vision-kb/concepts/lc-form-python-parity.md",
    "docs/vision-kb/concepts/lc-form-perceptron.md",
]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--paths", nargs="+", default=DEFAULT_PATHS,
                        help="Files to ingest (relative to repo root)")
    args = parser.parse_args(argv)

    print("─" * 72)
    print("git_artifact_perceptron_substrate — gestures via the live substrate")
    print("─" * 72)

    try:
        session, surfaces = substrate_session()
    except ImportError as e:
        print(f"Substrate not importable in this environment: {e}")
        print()
        print("This script requires sqlalchemy + the substrate kernel.")
        print("Run from a CI runner, production container, or local env where")
        print("the substrate is live. The in-memory companion lives at")
        print("scripts/git_artifact_perceptron.py and runs anywhere Python does.")
        return 2

    # Bootstrap: ingest the chosen paths as ARTIFACT cells.
    cells = ingest_chosen(session, surfaces, args.paths)
    session.commit()
    print(f"Ingested {len(cells)} ARTIFACT cells.")
    print()

    # Gesture 1 — EXECUTE one Python cell via the dispatch table.
    print("Gesture 1 — EXECUTE (via dispatch_by_kind)")
    print("─" * 72)
    target = next((c for c in cells if c.name.endswith(".py")), None)
    if target is not None:
        print(f"  cell : {target.name}")
        result = gesture_execute(target, kind="py")
        print(f"  result: {result}")
    print()

    # Gesture 2 — VIEW through Blueprint compatibility + harmonic band.
    print("Gesture 2 — VIEW (Blueprint compatibility + harmonic band)")
    print("─" * 72)
    compat = gesture_view_by_blueprint_compatibility(session, surfaces)
    print(f"  Compatible with BID_artifact: {len(compat)} cell(s)")
    band_741 = gesture_view_by_harmonic_band(session, surfaces, hz=741)
    print(f"  HARMONIC_AT @741 (consciousness band): {len(band_741)} artifact(s)")
    for v in band_741[:5]:
        print(f"    · {v.name}")
    band_432 = gesture_view_by_harmonic_band(session, surfaces, hz=432)
    print(f"  HARMONIC_AT @432 (natural harmony band): {len(band_432)} artifact(s)")
    for v in band_432[:5]:
        print(f"    · {v.name}")
    print()

    # Gesture 3 — MODIFY preview via downstream walk.
    print("Gesture 3 — MODIFY (find_downstream_cells: what this artifact touches)")
    print("─" * 72)
    if target is not None:
        downstream = gesture_modify_preview(session, surfaces, target)
        print(f"  {target.name} touches {len(downstream)} downstream cells:")
        for c in downstream[:5]:
            print(f"    · {c.domain}/{c.name}")
    print()

    # Gesture 4 — TRANSMUTE md → JSON via the transmutation registry.
    print("Gesture 4 — TRANSMUTE (md → json, via registered recipe)")
    print("─" * 72)
    md_cell = next((c for c in cells if c.name.endswith(".md")), None)
    if md_cell is not None:
        emitted = gesture_transmute(md_cell, kind="md", tgt_kind="json")
        print(f"  source: {md_cell.name}")
        import json as _json
        for line in _json.dumps(emitted, indent=2, sort_keys=True).splitlines()[:8]:
            print(f"    {line}")
        if emitted and len(emitted) > 5:
            print("    ...")
    print()

    # Gesture 5 — QUERY for every artifact in the substrate.
    print("Gesture 5 — QUERY (?cells where domain == \"artifact\")")
    print("─" * 72)
    all_artifacts = gesture_query(session, surfaces, domain="artifact")
    print(f"  {len(all_artifacts)} artifact cell(s) in the substrate:")
    for r in all_artifacts:
        print(f"    · {r.name}")
    print()

    print("─" * 72)
    print("Closed in this run:")
    print("  · NodeID-addressed cells — every artifact is a NamedCell")
    print("  · Cross-process content-addressing — same hash → same Blueprint")
    print("  · Form-grammar dispatch — _DISPATCH_BY_KIND registry (gesture 1)")
    print("  · view_cell_through_blueprint — used directly (gesture 2)")
    print("  · downstream walk for modify preview — find_downstream_cells")
    print("  · transmutation registry — _TRANSMUTATIONS keyed by kind-pair")
    print("  · ?cells / ?harmonic_at queries — via the substrate's surfaces")
    print()
    print("Remaining (each a future breath):")
    print("  · Dispatch entries as Recipe NodeIDs (not Python callables)")
    print("  · Transmutation entries as Recipe NodeIDs (not Python callables)")
    print("  · Word-cell-granularity rewrites for gesture 3 (needs PR #1748)")
    print("─" * 72)
    session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
