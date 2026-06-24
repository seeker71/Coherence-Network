#!/usr/bin/env python3
"""gen_flt_ops_from_manifest.py — emit flt-ops from native-op-manifest.fk.

Manifest is authoritative; flt-ops in form-flatten.fk is generated output.
Default --check fails when drifted; --write refreshes the slice.

Spec: specs/fkwu-only-kernel-collapse.md (Phase 1)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FORM = Path(__file__).resolve().parents[1]
FLATTEN = FORM / "form-stdlib" / "form-flatten.fk"
MANIFEST = FORM / "form-stdlib" / "native-op-manifest.fk"
GEN_MARKER = "; GENERATED: flt-ops body from native-op-manifest.fk — do not hand-edit"


def parse_manifest(text: str) -> list[tuple[str, int, int]]:
    m = re.search(r"\(defn nom-ops \(\)\s*\n\s*\(list", text)
    if not m:
        raise ValueError("nom-ops not found")
    start = m.end()
    depth, i = 1, start
    while i < len(text) and depth:
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
        i += 1
    body = text[start : i - 1]
    return [
        (name, int(arity), int(tag))
        for name, arity, tag, _cls in re.findall(
            r'\(nom-row "([^"]+)" (\d+) (\d+) "([^"]+)"\)', body
        )
    ]


def format_flt_ops(rows: list[tuple[str, int, int]]) -> str:
    entries = [f'(list "{name}" {arity} {tag})' for name, arity, tag in rows]
    lines = ["(defn flt-ops ()", f"    {GEN_MARKER}"]
    line = "    (list "
    for idx, entry in enumerate(entries):
        sep = "" if not line.endswith("(list ") else ""
        candidate = line + sep + entry
        if idx > 0 and len(candidate) > 96:
            lines.append(line.rstrip())
            line = "          " + entry
        else:
            line = candidate + " "
    lines.append(line.rstrip() + "))")
    return "\n".join(lines)


def replace_flt_ops(text: str, new_block: str) -> str:
    m = re.search(r"\(defn flt-ops \(\)", text)
    if not m:
        raise ValueError("flt-ops not found in form-flatten.fk")
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
    return text[:start] + new_block + "\n\n" + text[i:].lstrip("\n")


def extract_flt_ops_block(text: str) -> str:
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
    return text[start:i].rstrip()


def normalize_block(block: str) -> str:
    block = re.sub(r"; GENERATED:.*", "", block)
    return re.sub(r"\s+", " ", block.strip())


def parse_flt_ops_entries(block: str) -> list[tuple[str, int, int]]:
    return [
        (name, int(arity), int(tag))
        for name, arity, tag in re.findall(r'\(list "([^"]+)" (\d+) (\d+)\)', block)
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="rewrite flt-ops in form-flatten.fk")
    args = ap.parse_args()

    rows = parse_manifest(MANIFEST.read_text(encoding="utf-8"))
    generated = format_flt_ops(rows)
    current = extract_flt_ops_block(FLATTEN.read_text(encoding="utf-8"))

    gen_rows = parse_flt_ops_entries(generated)
    cur_rows = parse_flt_ops_entries(current)
    if gen_rows != cur_rows:
        if args.write:
            FLATTEN.write_text(
                replace_flt_ops(FLATTEN.read_text(encoding="utf-8"), generated),
                encoding="utf-8",
            )
            print(f"gen_flt_ops_from_manifest: wrote {len(rows)} rows to {FLATTEN}")
            return 0
        print(
            "error: flt-ops drifted from native-op-manifest.fk "
            "(run gen_flt_ops_from_manifest.py --write)",
            file=sys.stderr,
        )
        return 1

    print(f"gen_flt_ops_from_manifest: OK ({len(rows)} rows aligned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
