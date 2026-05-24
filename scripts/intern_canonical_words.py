#!/usr/bin/env python3
"""intern_canonical_words.py — CLI wrapper for the canonical lexicon interner.

The canonical-lexicon source-of-truth lives in
`api/app/services/substrate/canonical_lexicon` so both this CLI and any
future router/MCP surface that needs to enumerate the body's canonical
word-cells share one list. This script is the I/O wrapper that opens a
database session and calls `intern_all_canonical_words`.

Re-exports `canonical_word_entries`, `intern_canonical_word`, and
`intern_all` (alias for `intern_all_canonical_words`) so callers that
imported from this script keep working — same pattern as
`scripts/intern_modality_blueprints.py`.

Run:
    python3 scripts/intern_canonical_words.py

Idempotent: re-running interns the same cells (NamedCell upsert via
`make_cell` + content-addressing on the four-axis Blueprint). Reports
per-pool counts and verifies one query through the lattice.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "api"))

from app.services.substrate.canonical_lexicon import (  # noqa: E402
    ANCHOR_TERMS,
    DOMAIN_WORD,
    canonical_word_entries,
    intern_all_canonical_words,
    intern_canonical_word,
)
from app.services.substrate.kernel import (  # noqa: E402
    find_equivalent_cells,
    lookup_cell,
)
from app.services.substrate.markdown_frontend import (  # noqa: E402
    _WORD_LEXICON_DEFAULTS,
)
from app.services.substrate.modality_shapes import CANONICAL_SHAPES  # noqa: E402
from app.services.unified_db import session as session_scope  # noqa: E402


# Backward-compatible alias — historical callers (tests, hooks) import
# `intern_all` from this script. The substrate module exports the same
# function under its longer, self-describing name.
intern_all = intern_all_canonical_words


def main() -> int:
    print("─" * 70)
    print("intern_canonical_words — landing the body's lexicon in the substrate")
    print("─" * 70)

    entries = canonical_word_entries()
    body_lexicon_count = len({
        (e["lemma"].lower(), e["pos"].upper())
        for e in _WORD_LEXICON_DEFAULTS.values()
    })
    recipe_shape_count = len(CANONICAL_SHAPES)
    anchor_count = len(ANCHOR_TERMS)

    print()
    print(f"  Pool 1 — body lexicon            : {body_lexicon_count:>4} unique (lemma, POS)")
    print(f"  Pool 2 — canonical recipe-shapes : {recipe_shape_count:>4} entries")
    print(f"  Pool 3 — anchor terms            : {anchor_count:>4} entries")
    print(f"  ─────────────────────────────────────────────────")
    print(f"  Total after dedupe               : {len(entries):>4} canonical words")
    print()

    with session_scope() as session:
        report = intern_all_canonical_words(session)
        session.flush()

        # Verify one cell from each pool round-trips.
        verifications = [
            "choice.NOUN",          # Pool 1 — round-trip sentence word
            "recovery.NOUN",        # Pool 2 — canonical recipe-shape word
            "wholeness.NOUN",       # Pool 3 — anchor term
        ]
        print("Verification — lookup_cell + ?equivalent on canonical samples:")
        for name in verifications:
            cell = lookup_cell(session, DOMAIN_WORD, name)
            if cell is None:
                print(f"  ✗ {name:<24} MISSING — canonical interner did not land")
                continue
            equivalents = find_equivalent_cells(session, cell.blueprint)
            eq_count = len({c.name for c in equivalents})
            print(
                f"  ✓ {name:<24} @{cell.blueprint}  "
                f"?equivalent → {eq_count} cell(s)"
            )

        # Surface the consciousness-field family — every 741-Hz/consciousness
        # word now shares a HARMONIC_AT @741 resonance edge through the
        # word-cell's geometry signature.
        consciousness_count = sum(
            1 for (_l, _p, hz, field) in entries
            if field == "consciousness"
        )
        print()
        print(
            f"  Consciousness-field words  : {consciousness_count} "
            f"(all share HARMONIC_AT @741)"
        )

        session.commit()

    print()
    print("─" * 70)
    print("Done. The body's lexicon now lives in the real substrate.")
    print("Query examples:")
    print("  coh substrate form '?equivalent @word(choice.NOUN)'")
    print("  coh substrate form '?equivalent @word(recovery.NOUN)'")
    print("  coh substrate form '?equivalent @word(wholeness.NOUN)'")
    print(
        "  coh substrate form "
        "'?equivalent @word(choice.NOUN) where harmonic_at == @spectrum(\"Hz-741\")'"
    )
    print("─" * 70)
    return 0


__all__ = [
    "canonical_word_entries",
    "intern_all",
    "intern_all_canonical_words",
    "intern_canonical_word",
    "main",
]


if __name__ == "__main__":
    sys.exit(main())
