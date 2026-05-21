#!/usr/bin/env python3
"""form_cli.py — Form-native CLI: generate, execute, convert.

The CLI Urs named: kernel + binary library + Language cells, end-to-end.
Uses ONLY the experiments/local-llm-cell-v0/form_native.py recipes and
the .recipelib bundles in docs/coherence-substrate/libraries/. No
substrate session boot, no host stdlib math — every numeric op runs
through the Form-native composition (Newton sqrt, Taylor exp, recursive
list ops) verified by parity_check.py.

Subcommands:

    form_cli list <library>
        Print library meta + per-recipe summary.

    form_cli execute <library> <recipe> [arg ...]
        Invoke a recipe by name. Args are JSON-encoded positional values.
        Result emitted as JSON.

    form_cli convert in  --tongue <name> <input-file>
        Parse raw input (JSON, prose, …) into a Form object tree.
        Emits the Form object as JSON on stdout.

    form_cli convert out --tongue <name> <form-object-file>
        Emit a Form object tree as raw output in the named tongue.

    form_cli generate <form-source-file> [--out <library-path>]
        Extract every `defn name(args) = body` from a .form file and
        bundle into a .recipelib. The Form view is the source text;
        Python/TS views are deferred to the auto-generator follow-up.

Examples:

    form_cli execute libraries/cell-numerics.recipelib.json cosine \\
        '[1.0, 0.0, 0.0]' '[1.0, 0.0, 0.0]'
    # → 1.0

    form_cli convert in --tongue json data.json | \\
        form_cli convert out --tongue json /dev/stdin
    # round-trip JSON → Form object → JSON
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBRARY_DIR = REPO_ROOT / "docs" / "coherence-substrate" / "libraries"
EXPERIMENTS_DIR = REPO_ROOT / "experiments" / "local-llm-cell-v0"

# Allow imports of form_native from experiments/.
sys.path.insert(0, str(EXPERIMENTS_DIR))


def _die(message: str, code: int = 2) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(code)


def _resolve_library_path(arg: str) -> Path:
    """Library can be referenced by absolute path, by basename in
    docs/coherence-substrate/libraries/, or bare name (auto-appends
    `.recipelib.json`).
    """
    p = Path(arg)
    if p.exists():
        return p
    candidate = DEFAULT_LIBRARY_DIR / arg
    if candidate.exists():
        return candidate
    candidate = DEFAULT_LIBRARY_DIR / f"{arg}.recipelib.json"
    if candidate.exists():
        return candidate
    _die(f"library not found: {arg} (looked in {DEFAULT_LIBRARY_DIR})")


def _load_library(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


# ─── subcommand: list ────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> int:
    path = _resolve_library_path(args.library)
    library = _load_library(path)
    meta = library.get("library_meta", {})
    print(f"library: {meta.get('name')}  v{meta.get('version')}")
    print(f"  path: {path}")
    print(f"  language_cells: {', '.join(library.get('language_cells', []))}")
    deps = library.get("dependencies", [])
    print(f"  dependencies: {', '.join(deps) if deps else '(none)'}")
    print(f"  recipes ({len(library.get('recipes', []))}):")
    name_w = max(
        (len(r.get("name", "")) for r in library.get("recipes", [])),
        default=8,
    )
    for r in library.get("recipes", []):
        bp = r.get("blueprint", {})
        sig = f"({', '.join(bp.get('input_types', []))}) → {bp.get('output_type', '')}"
        node_hint = r.get("node_id_hint", "?")
        print(f"    {r['name']:<{name_w}}  {sig:<48}  @recipe({node_hint})")
    return 0


# ─── subcommand: execute ─────────────────────────────────────────────────


def cmd_execute(args: argparse.Namespace) -> int:
    path = _resolve_library_path(args.library)
    library = _load_library(path)
    recipe = None
    for r in library.get("recipes", []):
        if r.get("name") == args.recipe:
            recipe = r
            break
    if recipe is None:
        names = [r.get("name") for r in library.get("recipes", [])]
        _die(f"recipe '{args.recipe}' not in library (available: {', '.join(names)})")

    try:
        import form_native  # type: ignore
    except ImportError as e:
        _die(f"form_native module not importable: {e}")

    fn = getattr(form_native, args.recipe, None)
    if fn is None:
        _die(
            f"no form_native implementation for '{args.recipe}'. "
            f"Available: {', '.join(sorted(n for n in dir(form_native) if not n.startswith('_')))}"
        )

    parsed_args = []
    for raw in args.args:
        try:
            parsed_args.append(json.loads(raw))
        except json.JSONDecodeError as e:
            _die(f"could not parse argument as JSON: {raw!r} ({e})")

    try:
        result = fn(*parsed_args)
    except Exception as e:  # noqa: BLE001 — surface any execution error honestly
        _die(f"execution failed for '{args.recipe}': {e}")

    if args.pretty:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result))
    return 0


# ─── subcommand: convert ─────────────────────────────────────────────────
#
# I/O ↔ Form object via the Language cell for the named tongue. JSON is
# the worked example because it's the simplest text-tree grammar; YAML
# / Markdown / PNG follow the same shape once their Language cells are
# loaded. The Form object representation: each node has a `category`
# (B_Object / B_List / B_String / B_Number / B_Bool / B_Null) and either
# `children` (composite) or `value` (leaf).


_CATEGORIES = {
    "B_Object": dict,
    "B_List":   list,
    "B_String": str,
    "B_Number": (int, float),
    "B_Bool":   bool,
    "B_Null":   type(None),
}


def _classify(value) -> str:
    # Order matters — bool is a subclass of int in Python.
    if value is None:
        return "B_Null"
    if isinstance(value, bool):
        return "B_Bool"
    if isinstance(value, (int, float)):
        return "B_Number"
    if isinstance(value, str):
        return "B_String"
    if isinstance(value, list):
        return "B_List"
    if isinstance(value, dict):
        return "B_Object"
    return "B_Unknown"


def _json_to_form_tree(value) -> dict:
    cat = _classify(value)
    if cat in ("B_Object",):
        return {
            "category": cat,
            "children": [
                {"key": k, "value": _json_to_form_tree(v)}
                for k, v in value.items()
            ],
        }
    if cat in ("B_List",):
        return {
            "category": cat,
            "children": [_json_to_form_tree(v) for v in value],
        }
    return {"category": cat, "value": value}


def _form_tree_to_json(tree):
    cat = tree.get("category")
    if cat == "B_Object":
        return {c["key"]: _form_tree_to_json(c["value"]) for c in tree.get("children", [])}
    if cat == "B_List":
        return [_form_tree_to_json(c) for c in tree.get("children", [])]
    if cat in ("B_String", "B_Number", "B_Bool", "B_Null"):
        return tree.get("value")
    if cat is None and "children" in tree:
        # Tolerate untagged composites (e.g. a Form-object file whose
        # top level is a recipe tree, not a JSON tree).
        return [_form_tree_to_json(c) for c in tree["children"]]
    return tree.get("value")


def _convert_in_json(input_path: Path) -> dict:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    return {
        "source_tongue": "json",
        "source_path": str(input_path),
        "tree": _json_to_form_tree(raw),
    }


def _convert_out_json(form_object: dict) -> str:
    tree = form_object.get("tree", form_object)
    return json.dumps(_form_tree_to_json(tree), indent=2)


def cmd_convert(args: argparse.Namespace) -> int:
    if args.direction == "in":
        if args.tongue == "json":
            form_obj = _convert_in_json(Path(args.input))
            print(json.dumps(form_obj, indent=2))
            return 0
        _die(
            f"tongue '{args.tongue}' not yet wired for `convert in`. "
            f"Available: json. (Other Language cells are named in "
            f"docs/coherence-substrate/*-grammar.form; wiring follows.)"
        )
    if args.direction == "out":
        with Path(args.input).open(encoding="utf-8") as f:
            form_obj = json.load(f)
        if args.tongue == "json":
            print(_convert_out_json(form_obj))
            return 0
        _die(f"tongue '{args.tongue}' not yet wired for `convert out`.")
    _die(f"unknown convert direction: {args.direction}")


# ─── subcommand: generate ────────────────────────────────────────────────
#
# Extract `defn name(args) = body;` definitions from a .form file and
# bundle into a .recipelib JSON. The Form source for each recipe is the
# verbatim text between defn and the matching closing brace/semicolon;
# Python/TS views are deferred to the auto-generator follow-up
# (per lc-recipes-as-binary-library "named follow-ups").


_DEFN_RE = re.compile(
    r"^defn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)\s*=\s*",
    re.MULTILINE,
)


def _balanced_block(source: str, start: int) -> int:
    """Return the index just past the matching closing brace for the
    `do { … };` block beginning at `start`, OR past the next `;`
    terminator for a one-line defn. Honest about both shapes.
    """
    n = len(source)
    i = start
    # Skip whitespace
    while i < n and source[i] in " \t\n":
        i += 1
    # Block form?
    if i < n and source[i:i+3] == "do ":
        # Find the opening `{`
        while i < n and source[i] != "{":
            i += 1
        if i >= n:
            return n
        depth = 0
        while i < n:
            c = source[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    i += 1
                    # Eat trailing `;`
                    while i < n and source[i] in " \t":
                        i += 1
                    if i < n and source[i] == ";":
                        i += 1
                    return i
            i += 1
        return n
    # One-line form: terminator is `;` not inside parens/brackets.
    paren = brack = 0
    while i < n:
        c = source[i]
        if c == "(":
            paren += 1
        elif c == ")":
            paren -= 1
        elif c == "[":
            brack += 1
        elif c == "]":
            brack -= 1
        elif c == ";" and paren == 0 and brack == 0:
            return i + 1
        i += 1
    return n


def _extract_form_defns(source: str) -> list[dict]:
    recipes = []
    for m in _DEFN_RE.finditer(source):
        name = m.group(1)
        params = [p.strip() for p in m.group(2).split(",") if p.strip()]
        body_start = m.start()
        body_end = _balanced_block(source, m.end())
        body = source[body_start:body_end]
        recipes.append({
            "name": name,
            "params": params,
            "form_source": body,
        })
    return recipes


def cmd_generate(args: argparse.Namespace) -> int:
    src_path = Path(args.source)
    if not src_path.exists():
        _die(f"source file not found: {args.source}")
    text = src_path.read_text(encoding="utf-8")
    extracted = _extract_form_defns(text)
    if not extracted:
        _die(f"no `defn name(...) = …;` found in {args.source}")

    library_name = args.name or src_path.stem
    out_path = Path(args.out) if args.out else (
        DEFAULT_LIBRARY_DIR / f"{library_name}.recipelib.json"
    )

    library = {
        "library_meta": {
            "name": library_name,
            "version": "0.1.0-generated",
            "generated_at": "auto",
            "generator_tongue": "form-cli generate",
            "package_hint": 1,
            "summary": f"Auto-extracted from {src_path}",
        },
        "dependencies": [],
        "language_cells": ["form"],
        "recipes": [
            {
                "name": r["name"],
                "node_id_hint": f"1.3.{r['name']}.auto",
                "blueprint": {
                    "category": "B_Function",
                    "input_types": [f"~{p}" for p in r["params"]],
                    "output_type": "~Form",
                },
                "tree": {
                    "category": "R_Block.DO",
                    "comment": "tree extraction deferred to auto-generator follow-up",
                },
                "source_provenance": {
                    "tongue": "form",
                    "source_path": str(src_path),
                },
                "tongue_caches": {
                    "form": r["form_source"],
                },
            }
            for r in extracted
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(library, f, indent=2)
    print(f"generated: {out_path}")
    print(f"  recipes: {len(extracted)} ({', '.join(r['name'] for r in extracted)})")
    return 0


# ─── argparser ───────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="form_cli",
        description=__doc__.splitlines()[0],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="print library meta + recipes")
    p_list.add_argument("library", help="library name or path")
    p_list.set_defaults(func=cmd_list)

    p_exec = sub.add_parser("execute", help="invoke a recipe by name")
    p_exec.add_argument("library", help="library name or path")
    p_exec.add_argument("recipe", help="recipe name")
    p_exec.add_argument("args", nargs="*", help="JSON-encoded positional args")
    p_exec.add_argument("--pretty", action="store_true", help="indent JSON output")
    p_exec.set_defaults(func=cmd_execute)

    p_conv = sub.add_parser("convert", help="I/O ↔ Form object via Language cell")
    p_conv.add_argument("direction", choices=["in", "out"])
    p_conv.add_argument("input", help="path to input file (or /dev/stdin)")
    p_conv.add_argument("--tongue", default="json",
                        help="Language cell name (default: json)")
    p_conv.set_defaults(func=cmd_convert)

    p_gen = sub.add_parser("generate", help="extract recipes from .form into .recipelib")
    p_gen.add_argument("source", help="path to a .form source file")
    p_gen.add_argument("--name", help="library name (default: source stem)")
    p_gen.add_argument("--out", help="output .recipelib path")
    p_gen.set_defaults(func=cmd_generate)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
