#!/usr/bin/env python3
"""validate_fkwu_native_surface.py — Phase 0 gate for fkwu native tag surface.

Ensures flt-ops tags are unique, within fkc-arm-slots, and covered by fkc-flat
handlers (unary/tri/nullary cannot fall through to the binary fallback).

Spec: specs/fkwu-only-kernel-collapse.md (Phase 0)
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

FORM = Path(__file__).resolve().parents[1]
FLATTEN = FORM / "form-stdlib" / "form-flatten.fk"
EMIT = FORM / "form-stdlib" / "fkc-table-serialize.fk"
FS_EMIT = FORM / "form-stdlib" / "host-io-fs-fkwu-emit.fk"


def _read(path: Path) -> str:
    if not path.is_file():
        print(f"validate_fkwu_native_surface: missing {path}", file=sys.stderr)
        sys.exit(2)
    return path.read_text(encoding="utf-8")


def parse_flt_ops(text: str) -> list[tuple[str, int, int]]:
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
    block = text[start:i]
    return [
        (name, int(arity), int(tag))
        for name, arity, tag in re.findall(r'\(list "([^"]+)" (\d+) (\d+)\)', block)
    ]


def parse_arm_slots(text: str) -> int:
    m = re.search(r"\(defn fkc-arm-slots \(\)\s+(\d+)\)", text)
    if not m:
        raise ValueError("fkc-arm-slots not found")
    return int(m.group(1))


def parse_fkc_flat_block(text: str) -> str:
    parts = text.split("(defn fkc-flat")
    if len(parts) < 2:
        raise ValueError("fkc-flat not found")
    return parts[1].split("(defn fkc-call2")[0]


def explicit_flat_tags(flat: str) -> set[int]:
    return {int(x) for x in re.findall(r"\(eq \(fk-tag n\) (\d+)\)", flat)}


def dynamic_unary_tags(flat: str) -> set[int]:
    """Tags handled via (fkc-un2 (fk-tag n) ...) in or-groups."""
    tags: set[int] = set()
    for block in re.finditer(
        r"\(if \(or[^)]*(?:\([^)]*\)[^)]*)*\)\s+\(fkc-un2 \(fk-tag n\)",
        flat,
        re.S,
    ):
        tags.update(int(x) for x in re.findall(r"\(eq \(fk-tag n\) (\d+)\)", block.group(0)))
    return tags


def dynamic_binary_tags(flat: str) -> set[int]:
    tags: set[int] = set()
    for block in re.finditer(
        r"\(if \(or[^)]*(?:\([^)]*\)[^)]*)*\)\s+\(fkc-bin2 \(fk-tag n\)",
        flat,
        re.S,
    ):
        tags.update(int(x) for x in re.findall(r"\(eq \(fk-tag n\) (\d+)\)", block.group(0)))
    return tags


def tri_tags(flat: str) -> set[int]:
    tags = set()
    for m in re.finditer(r"\(if \(eq \(fk-tag n\) (\d+)\) \(fkc-tri2 \1", flat):
        tags.add(int(m.group(1)))
    for m in re.finditer(r"\(if \(eq \(fk-tag n\) (\d+)\) \(fkc-tri2", flat):
        tags.add(int(m.group(1)))
    return tags


def c_walker_tags(*paths: Path) -> set[int]:
    tags: set[int] = set()
    for path in paths:
        if path.is_file():
            tags.update(int(x) for x in re.findall(r"if \(t == (\d+)\)", path.read_text(encoding="utf-8")))
    return tags


def main() -> int:
    flatten = _read(FLATTEN)
    emit = _read(EMIT)
    ops = parse_flt_ops(flatten)
    arm_slots = parse_arm_slots(emit)
    flat = parse_fkc_flat_block(emit)
    explicit = explicit_flat_tags(flat)
    dyn_unary = dynamic_unary_tags(flat)
    dyn_bin = dynamic_binary_tags(flat)
    tri = tri_tags(flat)
    c_tags = c_walker_tags(EMIT, FS_EMIT)

    errors: list[str] = []
    warnings: list[str] = []

    by_tag: dict[int, list[tuple[str, int]]] = defaultdict(list)
    for name, arity, tag in ops:
        by_tag[tag].append((name, arity))
    for tag, entries in sorted(by_tag.items()):
        if len(entries) <= 1:
            continue
        arities = {a for _, a in entries}
        names = [n for n, _ in entries]
        if len(arities) > 1:
            errors.append(
                f"conflicting flt-ops tag {tag} (mixed arity {sorted(arities)}): {names}"
            )
        else:
            warnings.append(f"alias flt-ops tag {tag}: {names}")

    max_tag = max((t for _, _, t in ops), default=0)
    if max_tag >= arm_slots:
        errors.append(f"max flt-ops tag {max_tag} >= fkc-arm-slots {arm_slots}")

    for name, arity, tag in ops:
        if tag >= arm_slots:
            errors.append(f"{name}: tag {tag} out of arm slots range 0..{arm_slots - 1}")
        if arity == 0:
            if tag not in explicit:
                errors.append(f"{name}: nullary tag {tag} missing explicit fkc-flat row")
        elif arity == 1:
            if tag not in explicit and tag not in dyn_unary:
                errors.append(
                    f"{name}: unary tag {tag} not in fkc-flat "
                    "(would hit binary fallback — flatten crash or wrong arity)"
                )
        elif arity == 2:
            if tag not in explicit and tag not in dyn_bin:
                # binary fallback at end of fkc-flat handles unknown bin ops
                pass
        elif arity == 3:
            if tag not in tri and tag not in explicit:
                errors.append(f"{name}: ternary tag {tag} missing fkc-tri2 / explicit fkc-flat")
        elif arity == 4:
            if tag not in explicit:
                warnings.append(f"{name}: quad tag {tag} — verify fkc-quad4 coverage manually")
        else:
            errors.append(f"{name}: unsupported arity {arity}")

        # Host-io / high tags: explicit C arms or dynamic or-group dispatch.
        if (
            tag >= 55
            and tag not in c_tags
            and tag not in dyn_unary
            and tag not in dyn_bin
            and tag not in {80, 106}  # node_eq/value_eq and _get use shared arms
        ):
            warnings.append(f"{name}: tag {tag} not found in C walker if (t == N) strings")

    if warnings:
        for w in warnings:
            print(f"warn: {w}", file=sys.stderr)

    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        print(
            f"validate_fkwu_native_surface: FAIL ({len(errors)} error(s), "
            f"{len(ops)} flt-ops rows, arm_slots={arm_slots})",
            file=sys.stderr,
        )
        return 1

    print(
        f"validate_fkwu_native_surface: OK ({len(ops)} flt-ops rows, "
        f"max_tag={max_tag}, arm_slots={arm_slots}, "
        f"{len(warnings)} warning(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
