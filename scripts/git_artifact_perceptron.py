#!/usr/bin/env python3
"""git_artifact_perceptron.py — the smallest real version of the form perceptron.

Honest start: the lc-form-perceptron concept named a direction; this script
embodies one small breath of it. Walks a chosen set of real repo files,
builds gas-cells for them in-memory (since the substrate isn't importable
in this remote container), then demonstrates each of the five gestures
the concept names — execute, view, modify, transmute, query — on actual
files in actual paths.

This is not the full perceptron. It is what the perceptron looks like at
the scale of one breath, with the substrate primitives swapped for Python
in-memory structures that share the same shape. The substrate-native
version replaces:

    GasCell dataclass  →  NamedCell in BDomain.<KIND>
    in-memory list     →  substrate_nodes / substrate_named_cells tables
    content_hash       →  SubstrateString instance for the file body
    kind tag           →  BDomain enum entry (per file type)

Companion to docs/vision-kb/concepts/lc-form-perceptron.md.

Run:
    python3 scripts/git_artifact_perceptron.py
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# The gas-cell — minimum participation for any git artifact
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GasCell:
    """A file's gas-form in the substrate. Path + content-hash + kind + size.

    Two cells with the same content_hash are the same content, regardless of
    path or kind. This is the in-memory stand-in for what a NamedCell in
    `BDomain.SOURCE` (or .DOC, .CONFIG, .DATA) would carry once the
    substrate-native version lands.
    """

    path: str           # relative to REPO_ROOT
    kind: str           # "py" | "md" | "form" | "yaml" | "json" | "other"
    content_hash: str   # sha256 hex digest, 16 chars
    size_bytes: int
    mtime: float

    @property
    def blueprint(self) -> tuple:
        """Structural fingerprint — two cells with the same blueprint are
        structurally identical (same kind + same content)."""
        return ("gas", self.kind, self.content_hash)


def _content_hash(path: Path) -> str:
    """sha256 hex digest of the file's bytes, truncated to 16 chars."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _kind_of(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "py"
    if suffix == ".md":
        return "md"
    if suffix == ".form":
        return "form"
    if suffix in (".yaml", ".yml"):
        return "yaml"
    if suffix == ".json":
        return "json"
    if suffix in (".ts", ".tsx", ".js", ".jsx"):
        return "ts"
    return "other"


def ingest_gas(path: Path) -> GasCell:
    """Build a gas-cell for one file."""
    rel = str(path.relative_to(REPO_ROOT))
    stat = path.stat()
    return GasCell(
        path=rel,
        kind=_kind_of(path),
        content_hash=_content_hash(path),
        size_bytes=stat.st_size,
        mtime=stat.st_mtime,
    )


def ingest_chosen() -> List[GasCell]:
    """Walk a small chosen set of real files — the perceptron's
    demonstration surface. Real files, real paths, real content."""
    chosen = [
        "scripts/prose_recipe_roundtrip.py",
        "scripts/substrate_parity_harness.py",
        "scripts/git_artifact_perceptron.py",
        "docs/coherence-substrate/recipe-branching-sense.form",
        "docs/coherence-substrate/prose-as-recipe.form",
        "docs/coherence-substrate/form-engine.form",
        "docs/vision-kb/concepts/lc-recipe-branching-sense.md",
        "docs/vision-kb/concepts/lc-form-python-parity.md",
        "docs/vision-kb/concepts/lc-form-perceptron.md",
        "docs/vision-kb/concepts/lc-assemblage-point.md",
    ]
    cells: List[GasCell] = []
    for relpath in chosen:
        p = REPO_ROOT / relpath
        if p.exists():
            cells.append(ingest_gas(p))
    return cells


_WALKABLE_SUFFIXES = {".py", ".md", ".form", ".yaml", ".yml",
                      ".json", ".ts", ".tsx", ".js", ".jsx", ".sh", ".toml"}
_SKIP_DIRS = {"node_modules", ".git", ".next", "__pycache__", ".claude",
              ".pytest_cache", ".venv", "venv", "dist", "build"}


def ingest_all() -> List[GasCell]:
    """Walk every git-trackable artifact under REPO_ROOT. Production-scale
    demonstration that the gas-cell shape composes across thousands of
    files without architectural change."""
    cells: List[GasCell] = []
    for p in REPO_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in _WALKABLE_SUFFIXES:
            continue
        try:
            cells.append(ingest_gas(p))
        except OSError:
            continue
    return cells


# ---------------------------------------------------------------------------
# Gesture 1 — EXECUTE
# ---------------------------------------------------------------------------


def gesture_execute(cell: GasCell) -> Dict[str, Any]:
    """Run a cell whose content carries executable semantics.

    For .py cells, dispatch through `python3 <path>` and capture exit code
    + first line of output. The substrate-native version dispatches
    through a recipe attached to the cell; here, the kind tag is the
    dispatch key.
    """
    if cell.kind != "py":
        return {"executed": False, "reason": f"kind={cell.kind} not executable"}
    abs_path = REPO_ROOT / cell.path
    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(abs_path)],
        capture_output=True, text=True, timeout=30,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    first_line = (result.stdout.splitlines() or [""])[0]
    return {
        "executed": True,
        "exit_code": result.returncode,
        "first_line": first_line[:80],
        "elapsed_ms": round(elapsed_ms, 2),
    }


# ---------------------------------------------------------------------------
# Gesture 2 — VIEW (render through different lenses)
# ---------------------------------------------------------------------------


def view_by_size(cells: List[GasCell]) -> List[str]:
    """Lens: cells sorted by size descending. The body's largest content."""
    return [f"{c.size_bytes:>7}  {c.path}" for c in sorted(cells, key=lambda c: -c.size_bytes)]


def view_by_kind(cells: List[GasCell]) -> Dict[str, List[str]]:
    """Lens: cells grouped by file kind. Each kind a domain in the substrate."""
    by_kind: Dict[str, List[str]] = {}
    for c in cells:
        by_kind.setdefault(c.kind, []).append(c.path)
    return by_kind


def view_by_content_neighborhood(cells: List[GasCell]) -> List[str]:
    """Lens: cells grouped by their content_hash prefix (4 chars).

    Two cells in the same neighborhood share a hash prefix — they don't share
    content (sha256 collisions on 4-char prefix are random), but the lens
    demonstrates how Blueprint-based grouping works regardless of file kind.
    """
    by_prefix: Dict[str, List[str]] = {}
    for c in cells:
        by_prefix.setdefault(c.content_hash[:2], []).append(f"{c.content_hash}  {c.path}")
    return [f"  prefix={k}: {v}" for k, v in sorted(by_prefix.items())]


# ---------------------------------------------------------------------------
# Gesture 3 — MODIFY (structural edit through Form's grammar)
# ---------------------------------------------------------------------------


def would_modify(cells: List[GasCell], find: str, replace: str) -> Dict[str, int]:
    """Show what a structural substitution would touch — without writing.

    For each cell, count occurrences of `find` in the file's bytes. The
    substrate-native version walks word-cells and substitutes one for
    another via recipe rewrite. Here: byte-level count as a preview.
    """
    counts: Dict[str, int] = {}
    for c in cells:
        try:
            text = (REPO_ROOT / c.path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError):
            continue
        n = text.count(find)
        if n > 0:
            counts[c.path] = n
    return counts


# ---------------------------------------------------------------------------
# Gesture 4 — TRANSMUTE (one shape to another, content-preserving)
# ---------------------------------------------------------------------------


def transmute_md_frontmatter_to_json(cell: GasCell) -> Optional[Dict[str, Any]]:
    """Convert a markdown cell's YAML frontmatter into a JSON dict.

    The cell stays the same (same content_hash); the lens changes. Two
    different views of the same content. This is what transmutation means
    in the substrate: same source cell, different emit shape.
    """
    if cell.kind != "md":
        return None
    text = (REPO_ROOT / cell.path).read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    # Tiny YAML-ish parser — enough for our frontmatter shape.
    result: Dict[str, Any] = {}
    current_block: Optional[str] = None
    for line in m.group(1).splitlines():
        if not line.strip():
            continue
        if line.startswith("  "):
            # nested under current_block
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


# ---------------------------------------------------------------------------
# Gesture 5 — QUERY (the substrate query surface, in-memory edition)
# ---------------------------------------------------------------------------


def query_cells(
    cells: List[GasCell],
    *,
    kind: Optional[str] = None,
    name_matches: Optional[str] = None,
    size_gt: Optional[int] = None,
) -> List[GasCell]:
    """In-memory equivalent of `?cells where kind == "form" and size > 1000`.

    The substrate-native version dispatches through `form_queries.py`'s
    `?cells` handler with the same filter shapes. This is the same gesture
    operating on the in-memory gas-cell list.
    """
    result = cells
    if kind is not None:
        result = [c for c in result if c.kind == kind]
    if name_matches is not None:
        pat = re.compile(name_matches.replace("*", ".*"))
        result = [c for c in result if pat.search(c.path)]
    if size_gt is not None:
        result = [c for c in result if c.size_bytes > size_gt]
    return result


# ---------------------------------------------------------------------------
# Main — demonstrate each gesture on the chosen set
# ---------------------------------------------------------------------------


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true",
                        help="Ingest every walkable artifact under repo root")
    args = parser.parse_args()

    print("─" * 72)
    print("git_artifact_perceptron — the smallest real version of the form perceptron")
    print("─" * 72)

    if args.all:
        import time as _time
        t0 = _time.perf_counter()
        cells = ingest_all()
        elapsed = _time.perf_counter() - t0
        print(f"Ingested {len(cells)} gas-cells from full repo walk in {elapsed:.2f}s")
    else:
        cells = ingest_chosen()
        print(f"Ingested {len(cells)} gas-cells across {len({c.kind for c in cells})} kinds.")
    print()

    # ─── Gesture 1: EXECUTE ──────────────────────────────────────────────
    print("Gesture 1 — EXECUTE")
    print("─" * 72)
    target = next((c for c in cells if c.path == "scripts/prose_recipe_roundtrip.py"), None)
    if target is not None:
        result = gesture_execute(target)
        print(f"  cell: {target.path}")
        print(f"  result: exit={result['exit_code']}  first_line={result['first_line']!r}")
        print(f"  elapsed: {result['elapsed_ms']} ms")
    print()

    # ─── Gesture 2: VIEW ─────────────────────────────────────────────────
    print("Gesture 2 — VIEW (three lenses on the same cells)")
    print("─" * 72)
    print("  Lens: by size (top 5)")
    for line in view_by_size(cells)[:5]:
        print(f"    {line}")
    print()
    print("  Lens: by kind")
    by_kind = view_by_kind(cells)
    for k, paths in sorted(by_kind.items()):
        print(f"    {k:>5}: {len(paths)} cell(s)")
    print()
    print("  Lens: by content-hash neighborhood (prefix 2 chars)")
    nbh_lines = view_by_content_neighborhood(cells)
    for line in nbh_lines[:5]:
        print(line)
    if len(nbh_lines) > 5:
        print(f"    ... and {len(nbh_lines) - 5} more")
    print()

    # ─── Gesture 3: MODIFY ───────────────────────────────────────────────
    print("Gesture 3 — MODIFY (preview: what would 'rename choice → option' touch?)")
    print("─" * 72)
    counts = would_modify(cells, find="choice", replace="option")
    if counts:
        for path, n in sorted(counts.items(), key=lambda kv: -kv[1])[:5]:
            print(f"    {n:>4} occurrences in {path}")
        total = sum(counts.values())
        print(f"    total: {total} occurrences in {len(counts)} cells")
    else:
        print("    (no matches)")
    print()

    # ─── Gesture 4: TRANSMUTE ────────────────────────────────────────────
    print("Gesture 4 — TRANSMUTE (md frontmatter → JSON, same cell, different lens)")
    print("─" * 72)
    target = next((c for c in cells if c.path == "docs/vision-kb/concepts/lc-form-perceptron.md"), None)
    if target is not None:
        emitted = transmute_md_frontmatter_to_json(target)
        if emitted is not None:
            print(f"  source cell: {target.path}")
            print(f"  source content_hash (preserved): {target.content_hash}")
            print(f"  emitted JSON:")
            json_str = json.dumps(emitted, indent=2, sort_keys=True)
            for line in json_str.splitlines()[:14]:
                print(f"    {line}")
            print("    ...")
    print()

    # ─── Gesture 5: QUERY ────────────────────────────────────────────────
    print("Gesture 5 — QUERY (?cells where kind == 'form')")
    print("─" * 72)
    forms = query_cells(cells, kind="form")
    for c in forms:
        print(f"    {c.path}  ({c.size_bytes} bytes)")
    print()
    print("Gesture 5 — QUERY (?cells where name matches 'lc-form-*')")
    print("─" * 72)
    lc_forms = query_cells(cells, name_matches="lc-form-")
    for c in lc_forms:
        print(f"    {c.path}  (kind={c.kind})")
    print()

    # ─── Honest naming of what's not yet here ────────────────────────────
    print("─" * 72)
    print("What's real in this run:")
    print(f"  · {len(cells)} gas-cells built from actual files on disk")
    print(f"  · One actual subprocess execution (gesture 1)")
    print(f"  · Three actual lens-renderings of the same cell-set (gesture 2)")
    print(f"  · Real byte-count modify-preview across the cells (gesture 3)")
    print(f"  · Real frontmatter parse + JSON emit (gesture 4)")
    print(f"  · Real in-memory filter queries (gesture 5)")
    print()
    print("All seven gaps the substrate-native version names are now CLOSED:")
    print(f"  · NodeID-addressed cells       → BDomain.ARTIFACT + ingest_git_artifact")
    print(f"  · Cross-process content-address → make_cell content-addressing")
    print(f"  · Form-grammar dispatch (g1)   → _DISPATCH_BY_KIND registry")
    print(f"  · find_cells_compatible_with (g2) → already in kernel.py, used directly")
    print(f"  · Downstream walk for rewrite (g3) → find_downstream_cells (PR #1748)")
    print(f"  · Transmutation registry (g4)  → _TRANSMUTATIONS keyed by kind-pair")
    print(f"  · ?cells / ?harmonic_at (g5)   → form_queries.py surfaces (PR #1748)")
    print()
    print("The substrate-native version lives at")
    print("    scripts/git_artifact_perceptron_substrate.py")
    print("and runs end-to-end when sqlalchemy + the substrate kernel are")
    print("importable. This in-memory version remains valuable as the")
    print("standalone-runnable shape — anywhere Python runs, this runs.")
    print("─" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
