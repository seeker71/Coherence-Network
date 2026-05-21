#!/usr/bin/env python3
"""view_recipe_library.py — read a .recipelib bundle and render any tongue.

Implements the viewer half of lc-recipes-as-binary-library. Loads a
content-addressed recipe library, picks a tongue (form / python /
typescript / …), and emits source text for every recipe in that
tongue.

Two modes:
  - --list                  : print library meta + per-recipe summary
  - --tongue form|python|…  : emit each recipe's source in that tongue
  - --recipe <name>         : show one recipe across all tongues

The library is the artifact; the viewer is one of many readers.
Different tongues see different source text; the recipe's NodeID-hint
and structural identity stay the same across views.

Usage:
    python3 scripts/view_recipe_library.py --list
    python3 scripts/view_recipe_library.py --tongue form
    python3 scripts/view_recipe_library.py --tongue python
    python3 scripts/view_recipe_library.py --tongue typescript
    python3 scripts/view_recipe_library.py --recipe cosine
    python3 scripts/view_recipe_library.py --library <path> --tongue form
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY = (
    REPO_ROOT / "docs" / "coherence-substrate" / "libraries"
    / "cell-numerics.recipelib.json"
)


def load_library(path: Path) -> dict:
    if not path.exists():
        print(f"library not found: {path}", file=sys.stderr)
        sys.exit(2)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def print_list(library: dict) -> None:
    meta = library.get("library_meta", {})
    print(f"library: {meta.get('name')}  v{meta.get('version')}")
    print(f"  generated: {meta.get('generated_at')}")
    print(f"  generator: {meta.get('generator_tongue')}")
    print(f"  package_hint: {meta.get('package_hint')}")
    print(f"  language_cells: {', '.join(library.get('language_cells', []))}")
    deps = library.get("dependencies", [])
    print(f"  dependencies: {', '.join(deps) if deps else '(none)'}")
    print()
    print(f"recipes ({len(library.get('recipes', []))}):")
    name_w = max((len(r.get("name", "")) for r in library.get("recipes", [])),
                 default=8)
    for r in library.get("recipes", []):
        bp = r.get("blueprint", {})
        in_types = ", ".join(bp.get("input_types", []))
        out_type = bp.get("output_type", "")
        sig = f"({in_types}) → {out_type}"
        tongues = list((r.get("tongue_caches") or {}).keys())
        print(f"  {r['name']:<{name_w}}  {sig:<48}  views: {', '.join(tongues)}")
        prov = r.get("source_provenance", {})
        if prov:
            print(f"  {'':<{name_w}}  ↑ authored in {prov.get('tongue')} "
                  f"at {prov.get('source_path')}")


def emit_tongue(library: dict, tongue: str) -> None:
    available = library.get("language_cells", [])
    if tongue not in available:
        print(f"tongue '{tongue}' not in library "
              f"(available: {', '.join(available)})", file=sys.stderr)
        sys.exit(2)

    meta = library.get("library_meta", {})
    sep = "─" * 70
    header_comment = _comment_for(tongue)
    print(header_comment.format(
        sep=sep,
        name=meta.get("name", "?"),
        version=meta.get("version", "?"),
        tongue=tongue,
        count=len(library.get("recipes", [])),
    ))

    for r in library.get("recipes", []):
        caches = r.get("tongue_caches") or {}
        text = caches.get(tongue)
        if text is None:
            # No cache for this tongue — the viewer would normally
            # render via the Language cell's emit template. The cache-
            # less rendering path stays open as a future capability;
            # today we mark the absence honestly.
            print(f"\n# {r['name']} — no {tongue} cache; tree-render path "
                  f"would compose the Language cell's emit template.\n")
            continue
        bp = r.get("blueprint", {})
        sig = f"{', '.join(bp.get('input_types', []))} → " \
              f"{bp.get('output_type', '')}"
        node_hint = r.get("node_id_hint", "?")
        print()
        print(_recipe_header(tongue, r["name"], sig, node_hint))
        print(text)


def show_recipe(library: dict, recipe_name: str) -> None:
    target = None
    for r in library.get("recipes", []):
        if r.get("name") == recipe_name:
            target = r
            break
    if target is None:
        names = [r.get("name") for r in library.get("recipes", [])]
        print(f"recipe '{recipe_name}' not in library "
              f"(available: {', '.join(names)})", file=sys.stderr)
        sys.exit(2)

    bp = target.get("blueprint", {})
    sig = (", ".join(bp.get("input_types", []))) + " → " + bp.get("output_type", "")
    print(f"recipe: {target['name']}")
    print(f"  node_id_hint: {target.get('node_id_hint')}")
    print(f"  signature: ({sig})")
    prov = target.get("source_provenance", {})
    print(f"  authored in {prov.get('tongue')} at {prov.get('source_path')}")
    print()
    print("  tree (structural identity — shared across all tongues):")
    tree = target.get("tree", {})
    print(json.dumps(tree, indent=4))
    print()
    print("  views:")
    for tongue, text in (target.get("tongue_caches") or {}).items():
        sep = "─" * 60
        print(f"\n  {tongue}")
        print(f"  {sep}")
        for line in text.splitlines():
            print(f"    {line}")


def _comment_for(tongue: str) -> str:
    if tongue == "form":
        return (
            "# {sep}\n"
            "# {name} v{version} — viewed through tongue: {tongue}\n"
            "# {count} recipe(s). Library is the artifact; this view is\n"
            "# one of many sibling renderings.\n"
            "# {sep}"
        )
    if tongue == "python":
        return (
            "# {sep}\n"
            "# {name} v{version} — viewed through tongue: {tongue}\n"
            "# {count} recipe(s). Same content-addressed identity as the\n"
            "# form/typescript views; the source text below is one carrier.\n"
            "# {sep}\n"
            "import math"
        )
    if tongue == "typescript":
        return (
            "// {sep}\n"
            "// {name} v{version} — viewed through tongue: {tongue}\n"
            "// {count} recipe(s). Same content-addressed identity as the\n"
            "// form/python views; the source text below is one carrier.\n"
            "// {sep}"
        )
    return (
        "// {sep}\n"
        "// {name} v{version} — viewed through tongue: {tongue}\n"
        "// {count} recipe(s)\n"
        "// {sep}"
    )


def _recipe_header(tongue: str, name: str, sig: str, node_hint: str) -> str:
    if tongue == "form":
        return f"# ─── {name} :: {sig} ── @recipe({node_hint}) ───"
    if tongue == "python":
        return f"# ─── {name} :: {sig} ── @recipe({node_hint}) ───"
    return f"// ─── {name} :: {sig} ── @recipe({node_hint}) ───"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY,
                        help="path to the .recipelib JSON file")
    parser.add_argument("--list", action="store_true",
                        help="print library meta + per-recipe summary")
    parser.add_argument("--tongue", type=str,
                        help="emit every recipe in this tongue")
    parser.add_argument("--recipe", type=str,
                        help="show one recipe across all tongues")
    args = parser.parse_args()

    library = load_library(args.library)

    if args.list:
        print_list(library)
        return 0
    if args.recipe:
        show_recipe(library, args.recipe)
        return 0
    if args.tongue:
        emit_tongue(library, args.tongue)
        return 0

    # default: list
    print_list(library)
    return 0


if __name__ == "__main__":
    sys.exit(main())
