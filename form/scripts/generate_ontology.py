#!/usr/bin/env python3
"""Generate Form ontology .fk artifacts from form-stdlib/form-ontology.json.

The JSON file is the canonical data grammar. Two .fk artifacts are emitted:

  form-stdlib/form-ontology.fk        — kernel ontology tables
                                        (FORM-CATEGORY-TABLE,
                                         FORM-PRIMITIVE-TABLE)
  form-stdlib/dialect-categories.fk   — per-dialect BMF/AST category
                                        constants, one (let ...) per
                                        dialect category

Usage:
  python3 scripts/generate_ontology.py            # write both .fk files
  python3 scripts/generate_ontology.py --check    # exit 1 if either differs

Stdlib only, no external deps. Idempotent: running it twice produces
identical output.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
FORM_ROOT = SCRIPT_DIR.parent
ONTOLOGY_JSON = FORM_ROOT / "form-stdlib" / "form-ontology.json"
ONTOLOGY_FK = FORM_ROOT / "form-stdlib" / "form-ontology.fk"
DIALECTS_FK = FORM_ROOT / "form-stdlib" / "dialect-categories.fk"

GENERATED_HEADER = """; form-ontology.fk — Form-side ontology, pure data.
;
; ┌──────────────────────────────────────────────────────────────────────┐
; │  GENERATED FILE — DO NOT EDIT BY HAND.                               │
; │  Source of truth: form-stdlib/form-ontology.json                     │
; │  Regenerate with: python3 scripts/generate_ontology.py               │
; │  Drift check    : python3 scripts/generate_ontology.py --check       │
; └──────────────────────────────────────────────────────────────────────┘
;
; This file holds DATA only — no helpers, no scanners, no emit logic.
; The kernel parser (form-kernel-{go,rust,ts}) carries the canonical
; (name → category) dispatch table for primitive special forms and
; composite shapes; this file mirrors that table on the Form side so
; emitters can look up by name instead of inlining (make_nodeid 1 2
; X Y) at every call site.
;
; Two tables — each row: (list name type-id inst).
;
;   FORM-CATEGORY-TABLE    — composite Recipe shapes the kernel
;                            interns for block / cond / fndef /
;                            fncall / ident.
;   FORM-PRIMITIVE-TABLE   — parser special-form primitives the
;                            kernel lifts to typed math / compare /
;                            logic categories before falling through
;                            to FNCALL.
;
; Source of truth (kernel side):
;   form/form-kernel-go/main.go constants ~73-95
;     RBasicMath=12, RBasicCompare=13, RBasicLogic=14, RBasicCond=11,
;     RBasicBlock=9, RBasicFnDef=31, RBasicFnCall=32, RBasicIdent=33.
;   form/form-kernel-go/main.go parseSexp ~1956-2014
;     case "add" → catMath(RMathPlus), case "gt" → catCompare(RCompareGt), etc.
;
; A new primitive added to the kernel must add a row to form-ontology.json
; (and re-run the generator). The lookup helpers and emit code live in
; form-stdlib/source-compiler.fk — load this file before source-compiler.fk
; so the bindings are in scope when the helpers reference them.
"""


def _fmt_row(name: str, ty: int, inst: int, name_width: int,
             close_parens: int = 0, note: str = "") -> str:
    """Render one `(list "name" type inst)` row.

    `close_parens` adds extra trailing `)` for the final row of a table
    (closing both the (list ...) and the enclosing (let ... (list ...))).
    `note` is rendered as a trailing `;; ...` comment AFTER all closing
    parens, so the comment never swallows them.
    """
    quoted = f'"{name}"'
    body = f'    (list {quoted:<{name_width}} {ty:>2} {inst})' + (")" * close_parens)
    if note:
        body = f"{body}   ;; {note}"
    return body


def render(data: dict) -> str:
    categories = data["categories"]
    primitives = data["primitives"]

    # Compute aligned width for quoted names so the columns line up.
    cat_name_width = max(len(f'"{r["name"]}"') for r in categories)
    prim_name_width = max(len(f'"{r["name"]}"') for r in primitives)

    lines: List[str] = [GENERATED_HEADER.rstrip(), ""]

    lines.append("(let FORM-CATEGORY-TABLE (list")
    lines.append("    ;; (name        type  inst)")
    for idx, r in enumerate(categories):
        is_last = idx == len(categories) - 1
        lines.append(_fmt_row(
            r["name"], r["type"], r["inst"], cat_name_width,
            close_parens=2 if is_last else 0,
            note=r.get("note", ""),
        ))
    lines.append("")

    lines.append("(let FORM-PRIMITIVE-TABLE (list")
    lines.append("    ;; (name  type  inst)")

    # Group by family with header comments.
    family_order = ["math", "compare", "logic"]
    family_header = {
        "math":    "    ;; math (type 12)",
        "compare": "    ;; compare (type 13)",
        "logic":   "    ;; logic (type 14)",
    }
    grouped: Dict[str, List[dict]] = {f: [] for f in family_order}
    extras: List[dict] = []
    for r in primitives:
        fam = r.get("family")
        if fam in grouped:
            grouped[fam].append(r)
        else:
            extras.append(r)

    # Flatten in family order, tagging each row with whether it's the last
    # overall (so we can attach the closing parens to its end).
    flat: List[tuple] = []
    for fam in family_order:
        rows = grouped[fam]
        if not rows:
            continue
        flat.append(("header", family_header[fam]))
        for r in rows:
            flat.append(("row", r))
    for r in extras:
        flat.append(("row", r))

    # Find index of last row entry so we can close on it.
    last_row_idx = max(i for i, (kind, _) in enumerate(flat) if kind == "row")
    for i, (kind, payload) in enumerate(flat):
        if kind == "header":
            lines.append(payload)
        else:
            lines.append(_fmt_row(
                payload["name"], payload["type"], payload["inst"], prim_name_width,
                close_parens=2 if i == last_row_idx else 0,
                note=payload.get("note", ""),
            ))

    lines.append("")
    lines.append("0")
    lines.append("")  # trailing newline

    return "\n".join(lines)


DIALECTS_HEADER = """; dialect-categories.fk — per-dialect BMF/AST category constants.
;
; ┌──────────────────────────────────────────────────────────────────────┐
; │  GENERATED FILE — DO NOT EDIT BY HAND.                               │
; │  Source of truth: form-stdlib/form-ontology.json (dialects: section) │
; │  Regenerate with: python3 scripts/generate_ontology.py               │
; │  Drift check    : python3 scripts/generate_ontology.py --check       │
; └──────────────────────────────────────────────────────────────────────┘
;
; This file holds DATA only — one `(let <PREFIX>-<NAME> (make_nodeid 1
; 2 <type> <inst>))` binding per dialect category. The per-dialect
; grammar files in form-stdlib/grammars/ (python-bmf.fk, bml.fk,
; go-bmf.fk, typescript-bmf.fk, rust-bmf.fk) reference these names as
; free identifiers from their emit/source helpers; load this file as a
; prelude before any of those grammar files.
;
; The (type, inst) numbers are load-bearing: they intern the Recipe
; shapes the grammar code constructs. Moving a constant changes its
; structural identity in the substrate.
"""


def render_dialects(data: dict) -> str:
    dialects = data.get("dialects") or {}
    if not dialects:
        return DIALECTS_HEADER.rstrip() + "\n\n0\n"

    lines: List[str] = [DIALECTS_HEADER.rstrip(), ""]

    # Stable order: as declared in JSON (Python preserves insertion order).
    for dialect_name, dialect in dialects.items():
        prefix = dialect["name_prefix"]
        type_id = dialect["category_type"]
        categories = dialect["categories"]
        grammar_file = dialect.get("grammar_file", "")

        header = f";; --- {dialect_name} (type {type_id}, prefix {prefix})"
        if grammar_file:
            header = f"{header} — {grammar_file}"
        header = f"{header} ---"
        lines.append(header)

        # Compute name-column width so the make_nodeid columns line up
        # per-dialect (Python's PY-BMF-* names vary in length).
        name_width = max(len(f"{prefix}-{r['name']}") for r in categories)

        for r in categories:
            full_name = f"{prefix}-{r['name']}"
            inst = r["inst"]
            note = r.get("note", "")
            row = (f"(let {full_name:<{name_width}} "
                   f"(make_nodeid 1 2 {type_id} {inst}))")
            if note:
                row = f"{row}   ;; {note}"
            lines.append(row)
        lines.append("")

    lines.append("0")
    lines.append("")  # trailing newline
    return "\n".join(lines)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if either file on disk differs from regenerated output")
    args = parser.parse_args(argv)

    if not ONTOLOGY_JSON.exists():
        print(f"error: source data not found: {ONTOLOGY_JSON}", file=sys.stderr)
        return 2

    data = json.loads(ONTOLOGY_JSON.read_text())
    rendered_ontology = render(data)
    rendered_dialects = render_dialects(data)

    artifacts = [
        (ONTOLOGY_FK, rendered_ontology),
        (DIALECTS_FK, rendered_dialects),
    ]

    if args.check:
        drift = 0
        for path, rendered in artifacts:
            if not path.exists():
                print(f"✗ {path} does not exist — run generate_ontology.py")
                drift += 1
                continue
            on_disk = path.read_text()
            if on_disk != rendered:
                print(f"✗ {path} is out of date with {ONTOLOGY_JSON}")
                print("  run: python3 scripts/generate_ontology.py")
                drift += 1
            else:
                print(f"✓ {path.name} matches {ONTOLOGY_JSON.name}")
        return 1 if drift else 0

    for path, rendered in artifacts:
        path.write_text(rendered)
        print(f"✓ wrote {path} from {ONTOLOGY_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
