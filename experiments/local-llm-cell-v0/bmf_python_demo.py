"""bmf_python_demo.py — verify BMF rules produce ast.parse-equivalent Form objects.

The honest answer to Urs's "why BMF tomorrow, what are we waiting for?":
nothing. This demo runs Python import statements through the real BMF
rules in bmf.py — no ast.parse delegation in the path — and verifies
the Form objects match what the ast.parse-based path produces for the
same inputs.

The carrier is still Python (Urs's second observation: "still seeing
python executions, interesting" — that's the move to route through
TS/Rust kernel, named in this PR's follow-ups). But the *parser* is
honest BMF: Choice/Capture/Sequence/Star primitives, FAIL-unwind on
non-match, semantic actions firing on match. ast.parse is in the
parity check, not in the BMF path.

Run: python3 bmf_python_demo.py
Exit 0 on every case matching; non-zero with a printed reason otherwise.
"""

from __future__ import annotations

import ast
import sys

from bmf import parse_python_imports


# Test cases — every `import` variation the body's Python code uses.
# Each entry is (source, expected_categories) where expected_categories
# names the Form-object categories the BMF rules should produce.

CASES = [
    # (source, [expected category for each top-level statement])
    ("import os",                                ["py_Import"]),
    ("import os.path",                           ["py_Import"]),
    ("import os as oss",                         ["py_Import"]),
    ("import os, sys, json",                     ["py_Import"]),
    ("import os.path, sys.argv as args",         ["py_Import"]),

    ("from os import path",                      ["py_ImportFrom"]),
    ("from os.path import join",                 ["py_ImportFrom"]),
    ("from os import path as p",                 ["py_ImportFrom"]),
    ("from os import path, sep",                 ["py_ImportFrom"]),
    ("from os import path as p, sep as s",       ["py_ImportFrom"]),

    ("from . import x",                          ["py_ImportFrom"]),
    ("from .. import x",                         ["py_ImportFrom"]),
    ("from .package import x",                   ["py_ImportFrom"]),
]


def _ast_imports_to_form(source: str) -> list[dict]:
    """Reference path: parse via ast, convert to the same Form shape
    bmf.py's actions produce. We compare against THIS, not against
    raw ast nodes, because the Form shape is the contract."""
    tree = ast.parse(source)
    out: list[dict] = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            out.append({
                "category": "py_Import",
                "names": [
                    {"name": a.name, "asname": a.asname}
                    for a in node.names
                ],
            })
        elif isinstance(node, ast.ImportFrom):
            out.append({
                "category": "py_ImportFrom",
                "module":   node.module,
                "level":    node.level,
                "names": [
                    {"name": a.name, "asname": a.asname}
                    for a in node.names
                ],
            })
        else:
            out.append({"category": f"py_{type(node).__name__}"})
    return out


def _strip_source_attribution(obj):
    """For comparison: ignore source_attribution (BMF stamps it from
    its own tokenizer; ast.parse doesn't carry the same coords). The
    parity check is over the semantic shape, not the coords; both
    paths carry coords from their own carriers honestly."""
    if isinstance(obj, dict):
        return {k: _strip_source_attribution(v)
                for k, v in obj.items() if k != "source_attribution"}
    if isinstance(obj, list):
        return [_strip_source_attribution(v) for v in obj]
    return obj


def _fail(reason: str) -> int:
    print(f"FAIL: {reason}")
    return 1


def main() -> int:
    print("bmf_python_demo — real BMF rules vs ast.parse reference")
    print("=" * 64)
    passed = 0
    for source, expected_cats in CASES:
        # BMF path — no ast.parse in the call chain
        try:
            bmf_objs = parse_python_imports(source)
        except SyntaxError as e:
            return _fail(f"BMF could not parse {source!r}: {e}")

        # Reference: same Form shape via ast.parse
        ast_objs = _ast_imports_to_form(source)

        # Category sanity check
        bmf_cats = [o["category"] for o in bmf_objs]
        if bmf_cats != expected_cats:
            return _fail(
                f"category mismatch for {source!r}: "
                f"BMF emitted {bmf_cats}, expected {expected_cats}"
            )

        # Semantic equivalence (ignoring source_attribution)
        bmf_stripped = _strip_source_attribution(bmf_objs)
        if bmf_stripped != ast_objs:
            return _fail(
                f"semantic divergence for {source!r}:\n"
                f"  BMF:      {bmf_stripped}\n"
                f"  ast.parse: {ast_objs}"
            )

        # Source attribution honestly present on BMF output
        first = bmf_objs[0]
        attr = first.get("source_attribution")
        if not attr or "start_line" not in attr:
            return _fail(f"BMF missed source_attribution on {source!r}")

        print(f"  ✓ {source:<42} → {bmf_cats[0]}  (line {attr['start_line']}, "
              f"col {attr['start_col']})")
        passed += 1

    print()
    print(f"{passed}/{len(CASES)} import variations parity-checked")
    print("BMF rules running in BMF semantics (Choice/Capture/Sequence/Star")
    print("with FAIL-unwind); ast.parse only in the reference path.")
    print()
    print("Source attribution stamped natively by BMF (token line/col),")
    print("not borrowed from ast.parse. Per lc-the-recipe-remembers-its-source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
