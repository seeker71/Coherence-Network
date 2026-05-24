#!/usr/bin/env python3
"""intern_modality_blueprints.py — CLI wrapper for the cross-modal interner.

The canonical-shape source-of-truth lives in
`api/app/services/substrate/modality_shapes` so both this CLI and
`api/app/routers/substrate.py` (the read endpoints backing the MCP
cross-modal tools) share one list. This script is the I/O wrapper that
opens a database session and calls `intern_all_canonical_shapes`.

Re-exports `CANONICAL_SHAPES`, `DOMAIN_RECIPE_SHAPE`, `intern_canonical_shape`,
`shape_signature_blueprint`, and `intern_all` (alias for
`intern_all_canonical_shapes`) so callers that imported from this script
historically — including `api/tests/test_modality_blueprints.py` and
`mcp-server/tests/test_cross_modal_tools.py` — keep working.

Run:
    python3 scripts/intern_modality_blueprints.py

Idempotent: re-running interns the same cells (NamedCell upsert via
make_cell). Reports per-shape NodeIDs and family sizes.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.services.substrate.kernel import find_equivalent_cells  # noqa: E402
from app.services.substrate.modality_shapes import (  # noqa: E402
    CANONICAL_SHAPES,
    DOMAIN_RECIPE_SHAPE,
    canonical_shape_names,
    intern_all_canonical_shapes,
    intern_canonical_shape,
    shape_signature_blueprint,
)
from app.services.unified_db import session as session_scope  # noqa: E402


# Backward-compatible alias — historical callers (tests, hooks) import
# `intern_all` from this script. The substrate module exports the same
# function under its longer, self-describing name.
intern_all = intern_all_canonical_shapes


def main() -> int:
    print("─" * 70)
    print("intern_modality_blueprints — landing the cross-modal proofs in the lattice")
    print("─" * 70)
    with session_scope() as session:
        report = intern_all_canonical_shapes(session)
        # Flush + verify each shape's equivalent set
        session.flush()

        for canonical_name, bp, names in report:
            equivalents = find_equivalent_cells(session, bp)
            eq_names = sorted({c.name for c in equivalents})
            print()
            print(f"{canonical_name}")
            print(f"  blueprint NodeID:  @{bp}")
            print(f"  interned cells:    {len(names)} ({', '.join(names)})")
            print(f"  ?equivalent set:   {len(eq_names)} cells")
            for n in eq_names:
                print(f"    - @recipe-shape({n})")

        session.commit()

    print()
    print("─" * 70)
    print("Done. The cross-modal claims now live in the real substrate.")
    print("Query examples:")
    print('  coh substrate form \'?equivalent @recipe-shape("R_Recovery")\'')
    print('  coh substrate form \'?equivalent @recipe-shape("R_Measurement-Collapse")\'')
    print('  coh substrate form \'?equivalent @recipe-shape("R_Tunnel")\'')
    print('  coh substrate form \'?equivalent @recipe-shape("R_FieldHoldingPresence")\'')
    print('  coh substrate form \'?equivalent @recipe-shape("R_Hold-Multiple")\'')
    print('  coh substrate form \'?equivalent @recipe-shape("R_Witness")\'')
    print("─" * 70)
    return 0


__all__ = [
    "CANONICAL_SHAPES",
    "DOMAIN_RECIPE_SHAPE",
    "canonical_shape_names",
    "intern_all",
    "intern_all_canonical_shapes",
    "intern_canonical_shape",
    "shape_signature_blueprint",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
