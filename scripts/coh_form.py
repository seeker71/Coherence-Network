#!/usr/bin/env python3
"""coh form — evaluate Form expressions against the coherence-substrate.

Usage:
    python3 scripts/coh_form.py "?equivalent @memory(arrival_relational_ground)"
    python3 scripts/coh_form.py "@memory(claude) |> @presence"
    python3 scripts/coh_form.py "?cells where domain == \"presence\""
    python3 scripts/coh_form.py "?cells |> ~Memory"

See docs/coherence-substrate/form-language.md for the full grammar.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.services.substrate import (  # noqa: E402
    NodeID,
    NamedCell,
    form_evaluate_text,
    form_serialize_cell,
    form_serialize_node_id,
)
from app.services.substrate.kernel import CellView  # noqa: E402
from app.services.unified_db import session as session_scope  # noqa: E402


def _format_value(value, as_json: bool = False) -> str:
    if as_json:
        return json.dumps(_to_json(value), indent=2)
    return _format_human(value)


def _to_json(v):
    if isinstance(v, NodeID):
        return {
            "package": v.package, "level": v.level,
            "type": v.type_, "instance": v.instance,
            "form": form_serialize_node_id(v),
        }
    if isinstance(v, NamedCell):
        return {
            "domain": v.domain, "name": v.name,
            "blueprint": _to_json(v.blueprint) if v.blueprint else None,
            "source_path": v.source_path,
            "form": form_serialize_cell(v),
        }
    if isinstance(v, CellView):
        return {
            "cell": _to_json(v.cell),
            "view_blueprint": _to_json(v.view_blueprint),
            "compatible": v.compatible,
            "reason": v.reason,
        }
    if isinstance(v, list):
        return [_to_json(x) for x in v]
    return repr(v)


def _format_human(v) -> str:
    if isinstance(v, NodeID):
        return form_serialize_node_id(v)
    if isinstance(v, NamedCell):
        return f"{form_serialize_cell(v)}  blueprint={form_serialize_node_id(v.blueprint) if v.blueprint else '?'}"
    if isinstance(v, CellView):
        bp = form_serialize_node_id(v.view_blueprint) if v.view_blueprint else "?"
        cell = form_serialize_cell(v.cell)
        if v.compatible:
            return f"{cell} |> {bp}  ✓ compatible"
        return f"{cell} |> {bp}  ✗ incompatible: {v.reason}"
    if isinstance(v, list):
        if not v:
            return "(empty)"
        lines = [f"  {_format_human(x)}" for x in v[:50]]
        out = f"({len(v)} results)\n" + "\n".join(lines)
        if len(v) > 50:
            out += f"\n  ... and {len(v) - 50} more"
        return out
    return repr(v)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expression", help="Form expression to evaluate")
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON (machine-readable)",
    )
    args = parser.parse_args(argv)

    try:
        with session_scope() as session:
            result = form_evaluate_text(session, args.expression)
    except (SyntaxError, NameError, LookupError, TypeError) as exc:
        print(f"Form: {exc}", file=sys.stderr)
        return 1

    print(_format_value(result.value, as_json=args.json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
