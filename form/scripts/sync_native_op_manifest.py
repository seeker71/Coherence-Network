#!/usr/bin/env python3
"""sync_native_op_manifest.py — Phase 1 drift gate: manifest must match flt-ops.

Compares form/form-stdlib/native-op-manifest.fk rows to form-flatten.fk flt-ops.
Spec: specs/fkwu-only-kernel-collapse.md (Phase 1)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

FORM = Path(__file__).resolve().parents[1]
FLATTEN = FORM / "form-stdlib" / "form-flatten.fk"
MANIFEST = FORM / "form-stdlib" / "native-op-manifest.fk"


def parse_ops_list(text: str, defn: str) -> list[tuple[str, int, int]]:
    if defn == "flt-ops":
        m = re.search(r"\(defn flt-ops \(\)", text)
        if not m:
            raise ValueError("flt-ops not found")
        start = m.start()
        depth, i = 0, start
        while i < len(text):
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
                if depth == 0:
                    i += 1
                    break
            i += 1
        block = text[start:i]
        return [
            (name, int(arity), int(tag))
            for name, arity, tag in re.findall(r'\(list "([^"]+)" (\d+) (\d+)\)', block)
        ]
    m = re.search(rf"\(defn {defn} \(\)\s*\n\s*\(list", text)
    if not m:
        raise ValueError(f"{defn} not found")
    start = m.end()
    depth, i = 1, start
    while i < len(text) and depth:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
        i += 1
    body = text[start : i - 1]
    if defn == "nom-ops":
        return [
            (name, int(arity), int(tag))
            for name, arity, tag, _cls in re.findall(
                r'\(nom-row "([^"]+)" (\d+) (\d+) "([^"]+)"\)', body
            )
        ]
    return [(name, int(arity), int(tag)) for name, arity, tag in re.findall(
        r'\(list "([^"]+)" (\d+) (\d+)\)', body
    )]


def main() -> int:
    flatten_rows = parse_ops_list(FLATTEN.read_text(encoding="utf-8"), "flt-ops")
    manifest_rows = parse_ops_list(MANIFEST.read_text(encoding="utf-8"), "nom-ops")

    flt_set = {(n, a, t) for n, a, t in flatten_rows}
    nom_set = {(n, a, t) for n, a, t in manifest_rows}

    errors: list[str] = []
    only_flt = sorted(flt_set - nom_set)
    only_nom = sorted(nom_set - flt_set)
    if only_flt:
        errors.append(f"in flt-ops but not manifest ({len(only_flt)}): {only_flt[:5]}...")
    if only_nom:
        errors.append(f"in manifest but not flt-ops ({len(only_nom)}): {only_nom[:5]}...")

    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        print("sync_native_op_manifest: FAIL", file=sys.stderr)
        return 1

    print(
        f"sync_native_op_manifest: OK ({len(flatten_rows)} rows aligned; "
        "edit manifest first, then regenerate flt-ops — not the reverse)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
