#!/usr/bin/env python3
"""Augment every spec's done_when with Form predicates derived from its
source: and test: fields, then evaluate and (optionally) update status.

Idempotent — only adds Form predicates not already in done_when. Existing
prose items are preserved. The substrate's content-addressing means
running this twice has no effect.

For each spec:
  1. Parse frontmatter (tolerant of legacy markdown-link `specs:` shape)
  2. Auto-generate file_exists + symbol_in_file predicates from source:
  3. If `test:` is a pytest invocation, add pytest_passes(target) predicate
  4. Insert the new items at the end of the existing done_when: block
  5. After all rewrites, ingest into the substrate
  6. Evaluate Form predicates against the live body
  7. Update status: draft → active when all source files materialize

Usage:
    python3 scripts/upgrade_specs_to_form_predicates.py [--dry-run]
        [--limit N] [--no-status-update]
"""
from __future__ import annotations

import argparse
import re
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPECS_DIR = ROOT / "specs"
sys.path.insert(0, str(ROOT / "api"))


def parse_frontmatter(text: str):
    """Return (frontmatter_dict, body_text). Tolerant of legacy
    markdown-link `specs:` items that break strict YAML."""
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return None, text
    fm_text = m.group(1)
    try:
        fm = yaml.safe_load(fm_text) or {}
        if not isinstance(fm, dict):
            fm = {}
    except yaml.YAMLError:
        fm = _tolerant_parse(fm_text)
    return fm, text[m.end():]


def _tolerant_parse(fm_text: str) -> dict:
    """Fallback: key-per-line parser. Used when strict YAML fails (typically
    the markdown-link `specs:` shape)."""
    out: dict = {}
    cur_key = None
    cur_list: list | None = None
    for line in fm_text.splitlines():
        if not line.strip():
            continue
        if line.startswith("  - "):
            if cur_list is not None:
                cur_list.append(line[4:].strip().strip('"').strip("'"))
            continue
        if re.match(r"^[a-zA-Z_][\w-]*:\s*$", line):
            cur_key = line.split(":", 1)[0]
            cur_list = []
            out[cur_key] = cur_list
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"').strip("'")
            cur_list = None
    return out


def derive_form_predicates(fm: dict) -> list[str]:
    """Return Form predicate strings derivable from source:/test: fields."""
    preds: list[str] = []

    # source: list of {file, symbols: [...]} dicts
    source = fm.get("source")
    if isinstance(source, list):
        for entry in source:
            if not isinstance(entry, dict):
                continue
            fpath = entry.get("file")
            if not isinstance(fpath, str) or not fpath.strip():
                continue
            fpath = fpath.strip()
            preds.append(f'file_exists("{fpath}")')
            syms = entry.get("symbols", [])
            if isinstance(syms, list):
                for sym in syms:
                    if not isinstance(sym, str):
                        continue
                    # Strip parens / parameters from declarator-style symbols
                    bare = re.split(r"[\s(]", sym.strip(), maxsplit=1)[0]
                    # Only emit predicates for syntactically-valid identifiers
                    if re.match(r"^[A-Za-z_][\w-]*$", bare):
                        preds.append(f'symbol_in_file("{fpath}", "{bare}")')

    # test: pytest invocation — extract test targets
    test = fm.get("test")
    if isinstance(test, str) and "pytest" in test:
        # Find tests/<path>.py or tests/<path>.py::test_name patterns
        for tgt in re.findall(r"\b(tests/\S+\.py(?:::[A-Za-z_]\w*)?)", test):
            full = f"api/{tgt}"
            preds.append(f'pytest_passes("{full}")')

    return preds


def existing_done_when_items(text: str) -> list[str]:
    """Extract the literal item strings currently in the done_when: block."""
    m = re.search(r"^done_when:\n((?:  - .*\n)*)", text, re.MULTILINE)
    if not m:
        return []
    items: list[str] = []
    for line in m.group(1).splitlines():
        if line.startswith("  - "):
            raw = line[4:].strip()
            # Strip surrounding quotes (single or double) for comparison
            if (raw.startswith("'") and raw.endswith("'")) or (
                raw.startswith('"') and raw.endswith('"')
            ):
                raw = raw[1:-1]
            items.append(raw)
    return items


def insert_into_done_when(text: str, new_preds: list[str]) -> tuple[str, int]:
    """Append items to existing done_when: block. If absent, create it
    before the closing frontmatter ---. Returns (new_text, count_added)."""
    if not new_preds:
        return text, 0
    new_lines = "".join(f"  - '{p}'\n" for p in new_preds)

    m = re.search(r"^(done_when:\n(?:  - .*\n)*)", text, re.MULTILINE)
    if m:
        end = m.end()
        return text[:end] + new_lines + text[end:], len(new_preds)

    # No done_when block — insert before closing ---
    m = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if m:
        fm_text = m.group(1)
        # Insert before the second ---
        fm_end = m.start() + 4 + len(fm_text)  # after "---\n" + body of fm
        new_block = "done_when:\n" + new_lines
        return text[:fm_end] + "\n" + new_block + text[fm_end:], len(new_preds)
    return text, 0


def update_status(text: str, new_status: str) -> tuple[str, str | None]:
    """Replace the `status: <X>` line if present. Returns (new_text, old_status_or_None)."""
    m = re.search(r"^(status:\s*)(\S+)", text, re.MULTILINE)
    if not m:
        return text, None
    old = m.group(2)
    if old == new_status:
        return text, old
    return text[:m.start()] + m.group(1) + new_status + text[m.end():], old


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would change without writing.")
    ap.add_argument("--limit", type=int, default=0,
                    help="Process only first N specs.")
    ap.add_argument("--no-status-update", action="store_true",
                    help="Skip the status update pass after evaluation.")
    args = ap.parse_args()

    spec_paths = sorted([
        p for p in SPECS_DIR.glob("*.md")
        if p.name not in ("INDEX.md", "TEMPLATE.md")
    ])
    if args.limit:
        spec_paths = spec_paths[: args.limit]

    print(f"Processing {len(spec_paths)} specs...")
    print()

    added_total = 0
    touched_specs: list[Path] = []
    no_change: list[Path] = []

    for path in spec_paths:
        text = path.read_text()
        fm, _ = parse_frontmatter(text)
        if fm is None:
            continue

        derived = derive_form_predicates(fm)
        if not derived:
            no_change.append(path)
            continue

        existing = set(existing_done_when_items(text))
        new_items = [p for p in derived if p not in existing]
        if not new_items:
            no_change.append(path)
            continue

        new_text, added = insert_into_done_when(text, new_items)
        if added == 0:
            no_change.append(path)
            continue

        print(f"  {path.name}: +{added} Form predicate(s)")
        if not args.dry_run:
            path.write_text(new_text)
            touched_specs.append(path)
        added_total += added

    print()
    print(f"Touched {len(touched_specs)} specs, +{added_total} Form predicate(s) total.")
    print(f"No-change: {len(no_change)}")

    if args.dry_run or not touched_specs:
        return 0

    if args.no_status_update:
        return 0

    # ── Status update pass ───────────────────────────────────────────────
    # Re-ingest the touched specs, evaluate file_exists predicates, decide
    # status changes. Skip pytest_passes here — it's impure/subprocess; the
    # caller can run `coh substrate execute <slug>` to evaluate live.
    print()
    print("Re-ingesting touched specs into the substrate...")

    from app.services.substrate import ingest_spec_file
    from app.services.unified_db import session as session_scope
    from app.services.substrate.kernel import lookup_cell
    from app.services.substrate.form_runtime import (
        _resolve_access, _node_children, _trivial_value,
    )
    from app.services.substrate.category import RBasic, RType

    # Local helper — walk the CTOR for a key (cell.source is a built-in,
    # so we can't use _resolve_access for "source" frontmatter; same trick
    # for done_when which is a list, not a string).
    def ctor_walk(session, ctor_nid, field):
        if ctor_nid is None:
            return None
        from app.services.substrate.form_runtime import (
            _node_category as _cat,
        )
        for let_nid in _node_children(session, ctor_nid):
            let_cat = _cat(session, let_nid)
            if let_cat.type_ != RBasic.BLOCK.value or let_cat.instance != 3:
                continue
            kids = _node_children(session, let_nid)
            if len(kids) != 2:
                continue
            try:
                key = _trivial_value(session, kids[0])
            except (ValueError, AttributeError):
                continue
            if key == field:
                return kids[1]
        return None

    realized: list[Path] = []
    partial: list[Path] = []
    aspirational: list[Path] = []

    with session_scope() as session:
        for path in touched_specs:
            try:
                ingest_spec_file(session, path, structured=True)
            except Exception as exc:
                print(f"  WARN: failed to ingest {path.name}: {exc!r}")
                continue

        session.flush()

        # Evaluate each spec's file_exists predicates by walking the spec
        # body source: list (cheap — no Form interpretation; just check
        # paths). Status decision: all files present = realized; partial =
        # partial; none = aspirational.
        for path in touched_specs:
            slug = path.stem
            spec = lookup_cell(session, "spec", slug)
            if spec is None:
                continue
            text = path.read_text()
            fm, _ = parse_frontmatter(text)
            source = fm.get("source", []) if fm else []
            if not isinstance(source, list) or not source:
                continue
            n_files = 0
            n_present = 0
            for entry in source:
                if not isinstance(entry, dict):
                    continue
                fpath = entry.get("file")
                if not isinstance(fpath, str) or not fpath.strip():
                    continue
                n_files += 1
                if (ROOT / fpath.strip()).exists():
                    n_present += 1
            if n_files == 0:
                continue
            if n_present == n_files:
                realized.append(path)
            elif n_present > 0:
                partial.append(path)
            else:
                aspirational.append(path)

    print()
    print(f"Realization survey (touched specs, by file presence):")
    print(f"  REALIZED    : {len(realized)}   — all source files present")
    print(f"  PARTIAL     : {len(partial)}    — some source files present")
    print(f"  ASPIRATIONAL: {len(aspirational)} — no source files yet")

    # Update status: draft → active when all source files materialize.
    # Conservative: don't auto-promote active → done; that wants pytest_passes
    # evaluation which is impure/slow; let `coh substrate execute` do it.
    promoted = 0
    for path in realized:
        text = path.read_text()
        new_text, old = update_status(text, "active")
        if old == "draft" and new_text != text:
            path.write_text(new_text)
            promoted += 1
            print(f"  status: draft → active : {path.name}")

    print()
    print(f"Promoted {promoted} spec(s) from draft → active.")
    print(f"Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
