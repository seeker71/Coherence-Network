#!/usr/bin/env python3
"""Detect drift between form-stdlib/form-ontology.json and the kernel parser
dispatch tables in Go / Rust / TypeScript.

The Form-side ontology (categories + primitives in form-stdlib/form-ontology.json)
is the data grammar. At Form runtime, form-stdlib/form-ontology-loader.fk reads
the JSON via form-stdlib/json.fk's parse-json and exposes the rows as
top-level bindings (water). This script reads the JSON — the canonical
source — and verifies each row against each kernel's buildVerb dispatch.

Each kernel has cases like

    case "add": return k.intern(catMath(RMathPlus), args)

If a primitive is added to the kernel without updating form-ontology.json
(or vice-versa) tests still pass but the body has silently drifted.
This script catches that drift.

Runs read-only; standard library only.

Exits 0 on a clean match, 1 on drift.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ----------------------------------------------------------------------------
# Paths — script lives at form/scripts/validate_form_ontology.py
# ----------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
FORM_ROOT = SCRIPT_DIR.parent  # .../form

ONTOLOGY_JSON = FORM_ROOT / "form-stdlib" / "form-ontology.json"
GO_MAIN = FORM_ROOT / "form-kernel-go" / "main.go"
RUST_MAIN = FORM_ROOT / "form-kernel-rust" / "src" / "main.rs"
TS_READER = FORM_ROOT / "form-kernel-ts" / "src" / "reader.ts"

# ----------------------------------------------------------------------------
# Category-table name → set of acceptable kernel verb-case names. Some
# category-table entries (fncall, ident) never appear as parser cases —
# they are the default / identifier-wrap branch. We accept their absence.
# ----------------------------------------------------------------------------
CATEGORY_NAME_ALIASES: Dict[str, Set[str]] = {
    "do": {"do"},
    "sequence": {"seq", "params"},
    "let": {"let"},
    "if-then": {"if"},
    "if": {"if"},
    "match": {"match"},
    "fndef": {"defn"},
    "fncall": set(),  # default branch in each kernel — no explicit case
    "ident": set(),   # identifier-wrap path — no explicit case
}

# Primitive-table type → kernel "category" tag and the matching catX call
# used in the dispatch sources. Each kernel uses slightly different
# spelling; we recognize all three.
PRIM_TYPE_TO_CAT_LABELS: Dict[int, Tuple[str, Set[str]]] = {
    12: ("math",    {"catMath",    "cat_math",    "RBasic.MATH"}),
    13: ("compare", {"catCompare", "cat_compare", "RBasic.COMPARE"}),
    14: ("logic",   {"catLogic",   "cat_logic",   "RBasic.LOGIC"}),
}

# Primitive inst values are 1-based offsets per category. For human
# error messages we want symbolic names too.
PRIM_INST_LABELS: Dict[Tuple[int, int], str] = {
    (12, 1): "add", (12, 2): "sub", (12, 3): "mul", (12, 4): "div", (12, 5): "mod",
    (13, 1): "eq",  (13, 2): "ne",  (13, 3): "lt",  (13, 4): "le",  (13, 5): "gt",  (13, 6): "ge",
    (14, 1): "and", (14, 2): "or",  (14, 3): "not",
}


# ----------------------------------------------------------------------------
# Parse form-ontology.json
# ----------------------------------------------------------------------------

def parse_ontology(path: Path) -> Tuple[List[Tuple[str, int, int]], List[Tuple[str, int, int]]]:
    """Return (category_rows, primitive_rows). Each row: (name, type, inst).

    Reads the canonical JSON data grammar. The .fk file is a generated
    artifact — we go to the source.
    """
    data = json.loads(path.read_text())
    cat_rows = [(r["name"], int(r["type"]), int(r["inst"])) for r in data.get("categories", [])]
    prim_rows = [(r["name"], int(r["type"]), int(r["inst"])) for r in data.get("primitives", [])]
    return cat_rows, prim_rows


# ----------------------------------------------------------------------------
# Parse each kernel's dispatch table into a uniform shape.
#
# For each kernel we produce: dict[verb_name -> KernelEntry], where a
# KernelEntry is (category_label, inst_int_or_None). Category label is one
# of "math", "compare", "logic", "block", "cond", "match", "fndef", "fncall", "ident",
# "list", or "shape" for fixed-shape cases (let, defn, etc) we don't
# decode further.
# ----------------------------------------------------------------------------

KernelEntry = Tuple[str, Optional[int]]  # (category_label, inst)


def _parse_int_consts(text: str, line_pattern: re.Pattern) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for m in line_pattern.finditer(text):
        out[m.group(1)] = int(m.group(2))
    return out


def parse_go(path: Path) -> Dict[str, KernelEntry]:
    text = path.read_text()
    # Constants: `RMathPlus uint32 = 1`
    const_re = re.compile(r'\b(R\w+)\s+uint32\s*=\s*(\d+)')
    consts = _parse_int_consts(text, const_re)
    return _parse_dispatch(
        text=text,
        # case "name":
        case_re=re.compile(r'case\s+"([^"]+)"\s*:'),
        # next non-empty content should reference the cat constructor + instance.
        cat_call_re=re.compile(r'\b(catMath|catCompare|catLogic|catBlock|catCond|catMatch|catFnDef|catFnCall|catIdent)\s*\(\s*(R\w+)?\s*\)'),
        cat_to_label={
            "catMath":    "math",
            "catCompare": "compare",
            "catLogic":   "logic",
            "catBlock":   "block",
            "catCond":    "cond",
            "catMatch":   "match",
            "catFnDef":   "fndef",
            "catFnCall":  "fncall",
            "catIdent":   "ident",
        },
        consts=consts,
        end_marker_re=re.compile(r'^\s*default\s*:|\bfunc\b'),
    )


def parse_rust(path: Path) -> Dict[str, KernelEntry]:
    text = path.read_text()
    # Constants: `const RMATH_PLUS: u32 = 1;`
    const_re = re.compile(r'\bconst\s+(R\w+)\s*:\s*u32\s*=\s*(\d+)\s*;')
    consts = _parse_int_consts(text, const_re)
    return _parse_dispatch(
        text=text,
        # "name" =>
        case_re=re.compile(r'"([^"]+)"\s*=>'),
        cat_call_re=re.compile(r'\b(cat_math|cat_compare|cat_logic|cat_block|cat_cond|cat_match|cat_fndef|cat_fncall|cat_ident)\s*\(\s*(R\w+)?\s*\)'),
        cat_to_label={
            "cat_math":    "math",
            "cat_compare": "compare",
            "cat_logic":   "logic",
            "cat_block":   "block",
            "cat_cond":    "cond",
            "cat_match":   "match",
            "cat_fndef":   "fndef",
            "cat_fncall":  "fncall",
            "cat_ident":   "ident",
        },
        consts=consts,
        end_marker_re=re.compile(r'^\s*_\s*=>|\bfn\b'),
    )


def parse_ts(path: Path) -> Dict[str, KernelEntry]:
    text = path.read_text()
    # TS uses object-literal RBasic.MATH / RMath.PLUS — not constants but
    # enum members. Resolve them ourselves by scanning enums.
    enums = _parse_ts_enums(text)
    # We treat RBasic.MATH → label "math" etc., and look up inst from RMath.PLUS.
    rbasic_to_label = {
        "MATH":    "math",
        "COMPARE": "compare",
        "LOGIC":   "logic",
        "MATCH":   "match",
        "BLOCK":   "block",
        "COND":    "cond",
        "FNDEF":   "fndef",
        "FNCALL":  "fncall",
        "IDENT":   "ident",
        "LIST":    "list",
    }

    out: Dict[str, KernelEntry] = {}
    # Locate buildVerb body.
    bv = re.search(r'function\s+buildVerb\s*\([^)]*\)\s*:\s*NodeID\s*\{', text)
    if not bv:
        raise ValueError("buildVerb not found in TS reader.ts")
    body_start = bv.end()
    body_end = _find_matching_brace(text, body_start - 1)
    body = text[body_start:body_end]

    # case "name":  ...  RBasic.MATH ... RMath.PLUS ...
    case_re = re.compile(r'case\s+"([^"]+)"\s*:')
    # Gather positions of every case and parse forward.
    positions = [(m.start(), m.group(1)) for m in case_re.finditer(body)]
    positions.append((len(body), None))  # sentinel

    pending_names: List[str] = []
    for idx in range(len(positions) - 1):
        pos, name = positions[idx]
        next_pos = positions[idx + 1][0]
        chunk = body[pos:next_pos]
        # Find first RBasic.X reference in this chunk.
        rb = re.search(r'RBasic\.(\w+)', chunk)
        if not rb:
            # Fall-through case (no body before next case): defer to next.
            pending_names.append(name)
            continue
        label = rbasic_to_label.get(rb.group(1))
        if label is None:
            pending_names = []
            continue
        # Find inst — RMath.PLUS, RCmp.EQ, RLogic.AND, RBlock.DO, RCond.IF_THEN.
        # Some entries (alias, list, fncall, ident) don't have a sub-inst.
        inst: Optional[int] = None
        sub = re.search(r'inst\s*:\s*(R\w+)\.(\w+)', chunk)
        if sub:
            enum_name, member = sub.group(1), sub.group(2)
            inst = enums.get(enum_name, {}).get(member)
        else:
            lit = re.search(r'inst\s*:\s*(\d+)', chunk)
            if lit:
                inst = int(lit.group(1))
        # Skip multi-width math (mathInst(RMathWidth.F64, RMath.PLUS)) — these
        # are addf/subf/mulf/divf/addq/subq/mulq, not Form-side primitives.
        if re.search(r'mathInst\s*\(', chunk):
            pending_names = []
            continue
        for nm in pending_names + [name]:
            out[nm] = (label, inst)
        pending_names = []
    return out


def _parse_ts_enums(text: str) -> Dict[str, Dict[str, int]]:
    """Parse `export enum Name { K = N, K2 = N2 }` and similar."""
    enums: Dict[str, Dict[str, int]] = {}
    enum_re = re.compile(r'\benum\s+(\w+)\s*\{([^}]*)\}', re.DOTALL)
    member_re = re.compile(r'(\w+)\s*=\s*(\d+)')
    for em in enum_re.finditer(text):
        name = em.group(1)
        members = {m.group(1): int(m.group(2)) for m in member_re.finditer(em.group(2))}
        enums[name] = members
    return enums


def _find_matching_brace(text: str, open_pos: int) -> int:
    """Given a position of `{`, return the index of the matching `}`."""
    assert text[open_pos] == '{'
    depth = 0
    i = open_pos
    while i < len(text):
        c = text[i]
        if c == '"' or c == "'" or c == '`':
            quote = c
            j = i + 1
            while j < len(text) and text[j] != quote:
                if text[j] == '\\':
                    j += 2
                else:
                    j += 1
            i = j + 1
            continue
        if c == '/' and i + 1 < len(text) and text[i + 1] == '/':
            nl = text.find('\n', i)
            i = len(text) if nl == -1 else nl + 1
            continue
        if c == '/' and i + 1 < len(text) and text[i + 1] == '*':
            end = text.find('*/', i + 2)
            i = len(text) if end == -1 else end + 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("unmatched brace")


def _parse_dispatch(
    text: str,
    case_re: re.Pattern,
    cat_call_re: re.Pattern,
    cat_to_label: Dict[str, str],
    consts: Dict[str, int],
    end_marker_re: re.Pattern,
) -> Dict[str, KernelEntry]:
    """Common dispatch parser for Go/Rust style.

    Walks every `case "name":` (Go) or `"name" =>` (Rust) inside the
    buildVerb function and resolves the next catX(...) call.
    """
    # Locate the dispatch region. For Go: `func (k *Kernel) buildVerb`.
    # For Rust: `fn build_verb`.
    fn_re = re.compile(
        r'(?:func\s+\([^)]*\)\s+buildVerb|fn\s+build_verb)\s*\([^)]*\)[^{]*\{'
    )
    m = fn_re.search(text)
    if not m:
        raise ValueError("buildVerb/build_verb function not found")
    body_start = m.end() - 1  # position of `{`
    body_end = _find_matching_brace(text, body_start)
    body = text[body_start:body_end]

    out: Dict[str, KernelEntry] = {}

    # Walk case positions in order; for each, look ahead until the next case
    # or end. Find the first catX(...) call in that slice.
    positions = [(mm.start(), mm.group(1)) for mm in case_re.finditer(body)]
    positions.append((len(body), None))

    pending_names: List[str] = []
    for idx in range(len(positions) - 1):
        pos, name = positions[idx]
        next_pos = positions[idx + 1][0]
        chunk = body[pos:next_pos]
        cc = cat_call_re.search(chunk)
        if not cc:
            # Fall-through (Go: empty case body; Rust: doesn't really happen).
            pending_names.append(name)
            continue
        cat_fn = cc.group(1)
        const_name = cc.group(2)
        label = cat_to_label.get(cat_fn)
        if label is None:
            pending_names = []
            continue
        inst: Optional[int] = None
        if const_name and const_name in consts:
            inst = consts[const_name]
        for nm in pending_names + [name]:
            out[nm] = (label, inst)
        pending_names = []
    return out


# ----------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------

PRIM_TYPE_TO_LABEL = {12: "math", 13: "compare", 14: "logic"}


def validate_primitives(
    prim_rows: List[Tuple[str, int, int]],
    kernels: Dict[str, Dict[str, KernelEntry]],
    verbose: bool,
) -> List[str]:
    drifts: List[str] = []
    ontology_prim_names: Set[str] = set()
    for name, ty, inst in prim_rows:
        ontology_prim_names.add(name)
        want_label = PRIM_TYPE_TO_LABEL.get(ty)
        if want_label is None:
            drifts.append(
                f"FORM-PRIMITIVE-TABLE row ({name!r} {ty} {inst}) has unknown type {ty}"
            )
            continue
        for kname, kmap in kernels.items():
            entry = kmap.get(name)
            if entry is None:
                drifts.append(
                    f"primitive {name!r} (type={ty} inst={inst}) in ontology "
                    f"but no `case \"{name}\"` in {kname}"
                )
                continue
            got_label, got_inst = entry
            if got_label != want_label:
                drifts.append(
                    f"primitive {name!r} in ontology says category={want_label} "
                    f"but {kname} dispatches to category={got_label}"
                )
            if got_inst is not None and got_inst != inst:
                drifts.append(
                    f"primitive {name!r} in ontology has inst={inst} "
                    f"but {kname} dispatches with inst={got_inst}"
                )
            if verbose:
                print(f"  ✓ {kname}: {name} → {got_label}/{got_inst}")
        if verbose:
            print(f"checked primitive {name!r} (type={ty} inst={inst})")

    # Reverse check: every math/compare/logic case in each kernel must be in
    # FORM-PRIMITIVE-TABLE — except for operator-symbol aliases (+, -, ==, etc).
    # The Form ontology lists named verbs; operator-symbol aliases that
    # fall through to the same intern call are surface conveniences, not
    # new primitives.
    is_word = re.compile(r'^[A-Za-z_][A-Za-z0-9_-]*$')
    for kname, kmap in kernels.items():
        for case_name, (label, _inst) in kmap.items():
            if label not in {"math", "compare", "logic"}:
                continue
            if case_name in ontology_prim_names:
                continue
            if not is_word.match(case_name):
                continue  # operator-symbol alias (+, -, ==, <=, etc.)
            drifts.append(
                f"{kname} has `case \"{case_name}\"` → {label} but "
                f"FORM-PRIMITIVE-TABLE has no row for it"
            )
    return drifts


def validate_categories(
    cat_rows: List[Tuple[str, int, int]],
    kernels: Dict[str, Dict[str, KernelEntry]],
    kernel_source_text: Dict[str, str],
    verbose: bool,
) -> List[str]:
    """For each shape name in FORM-CATEGORY-TABLE, verify at least one
    acceptable verb-string appears as a special-cased handler in each
    kernel source. We search the full file text rather than just buildVerb
    because some kernels (TS) handle `let`/`if`/`defn` in parseSexp above
    the buildVerb dispatch table.
    """
    drifts: List[str] = []
    for name, ty, inst in cat_rows:
        accept = CATEGORY_NAME_ALIASES.get(name)
        if accept is None:
            drifts.append(
                f"FORM-CATEGORY-TABLE row ({name!r} {ty} {inst}) has no "
                f"alias mapping in validate_form_ontology.py — extend "
                f"CATEGORY_NAME_ALIASES if this is a new shape"
            )
            continue
        if not accept:
            if verbose:
                print(f"  · category {name!r} has no explicit kernel case (default/wrap path) — OK")
            continue
        for kname, src in kernel_source_text.items():
            found = None
            for candidate in accept:
                # Match `case "X"`, `"X" =>`, or `verb === "X"`.
                pat = (
                    r'(?:case\s+"' + re.escape(candidate) + r'"\s*[:=]|'
                    r'"' + re.escape(candidate) + r'"\s*=>|'
                    r'verb\s*===\s*"' + re.escape(candidate) + r'")'
                )
                if re.search(pat, src):
                    found = candidate
                    break
            if found is None:
                drifts.append(
                    f"category {name!r} (type={ty} inst={inst}) in ontology "
                    f"expects one of {sorted(accept)} as a verb handler in {kname} but none found"
                )
            elif verbose:
                print(f"  ✓ {kname}: category {name!r} satisfied by {found!r}")
    return drifts


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="print every checked row")
    args = parser.parse_args(argv)

    for p in (ONTOLOGY_JSON, GO_MAIN, RUST_MAIN, TS_READER):
        if not p.exists():
            print(f"error: required file not found: {p}", file=sys.stderr)
            return 2

    cat_rows, prim_rows = parse_ontology(ONTOLOGY_JSON)
    if args.verbose:
        print(f"FORM-CATEGORY-TABLE: {len(cat_rows)} rows")
        print(f"FORM-PRIMITIVE-TABLE: {len(prim_rows)} rows")

    kernels = {
        "form-kernel-go":   parse_go(GO_MAIN),
        "form-kernel-rust": parse_rust(RUST_MAIN),
        "form-kernel-ts":   parse_ts(TS_READER),
    }
    kernel_source_text = {
        "form-kernel-go":   GO_MAIN.read_text(),
        "form-kernel-rust": RUST_MAIN.read_text(),
        "form-kernel-ts":   TS_READER.read_text(),
    }
    if args.verbose:
        for kname, kmap in kernels.items():
            relevant = {n: v for n, v in kmap.items()
                        if v[0] in {"math", "compare", "logic"}}
            print(f"{kname} primitive cases: {len(relevant)}")

    drifts: List[str] = []
    drifts += validate_primitives(prim_rows, kernels, args.verbose)
    drifts += validate_categories(cat_rows, kernels, kernel_source_text, args.verbose)

    if drifts:
        print("✗ form ontology drift detected:")
        for d in drifts:
            print(f"  - {d}")
        return 1

    print("✓ form ontology matches kernel parsers (Go/Rust/TS)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
