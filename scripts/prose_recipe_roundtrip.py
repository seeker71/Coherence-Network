#!/usr/bin/env python3
"""prose_recipe_roundtrip.py — the bidirectional test, walking.

The smallest runnable demonstration of Urs's claim from 2026-05-20:

    a sequence of words is a recipe of cells with blueprints

If the claim holds, the body should be able to parse a sentence into
a Recipe whose children are word-cells, emit the same Recipe back to
the same sentence, and intern two structurally-identical sentences
to the same Blueprint NodeID.

This script is a *stand-in* for the substrate-backed version. The
substrate itself carries cells via SQLAlchemy + Postgres; in this
remote container that path is not importable, so the lattice is held
in-memory as a Python dict. The shapes are identical to what the
substrate would intern; only the persistence layer differs.

The companion .form file at
    docs/coherence-substrate/prose-as-recipe.form
holds the substrate-native version with `# GAP:` markers for the
work that lands the same shape into the lattice itself.

Run:
    python3 scripts/prose_recipe_roundtrip.py

Exit code 0 if every assertion holds; nonzero if any breaks.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Part 1 — word-cells (stand-in for the substrate's WORD domain)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WordCell:
    """One word as a cell. The Blueprint NodeID is content-addressed
    from the four fields: identical (lemma, pos, hz, field) → identical
    Blueprint, regardless of how many times the word is interned.
    """

    lemma: str
    pos: str             # NOUN, VERB, ADJ, DET, ADV, ...
    hz: int              # Solfeggio band the word fires in
    semantic_field: str  # consciousness, vitality, transmutation, neutral, ...

    @property
    def blueprint(self) -> tuple:
        """The four axes that determine structural identity."""
        return ("word", self.lemma, self.pos, self.hz, self.semantic_field)


@dataclass(frozen=True)
class PunctToken:
    """A trailing punctuation token. Joins to the prior word on emit."""

    value: str

    @property
    def blueprint(self) -> tuple:
        return ("punct", self.value)


# The in-memory lattice. In the substrate this is `substrate_nodes`.
# Content-addressed: same blueprint tuple → same canonical cell.
_WORD_LATTICE: dict[tuple, WordCell] = {}


def intern_word_cell(
    lemma: str, pos: str, hz: int, semantic_field: str
) -> WordCell:
    """Idempotent: looking up the same word twice returns the same cell."""
    key = ("word", lemma, pos, hz, semantic_field)
    if key not in _WORD_LATTICE:
        _WORD_LATTICE[key] = WordCell(lemma, pos, hz, semantic_field)
    return _WORD_LATTICE[key]


# ---------------------------------------------------------------------------
# Part 2 — the lexicon (a stand-in for the cross-locale tokenizer)
# ---------------------------------------------------------------------------
#
# The substrate-native version uses a locale-aware tokenizer with
# lemma + POS extraction (spaCy, or registered token patterns). Here
# the lexicon is hand-tuned for the test sentence, which is honest:
# the round-trip test depends on these five words having known
# Blueprints, and naming them by hand makes the structural claim
# explicit rather than hidden behind a black-box tokenizer.

LEXICON: dict[str, dict[str, Any]] = {
    "the":     {"lemma": "the",     "pos": "DET",  "hz": 432, "field": "neutral"},
    "choice":  {"lemma": "choice",  "pos": "NOUN", "hz": 741, "field": "consciousness"},
    "point":   {"lemma": "point",   "pos": "NOUN", "hz": 741, "field": "consciousness"},
    "becomes": {"lemma": "become",  "pos": "VERB", "hz": 417, "field": "transmutation"},
    "visible": {"lemma": "visible", "pos": "ADJ",  "hz": 741, "field": "consciousness"},
}


def tokenize_words(text: str) -> list[Any]:
    """Surface tokenizer: split on whitespace, peel trailing punctuation.

    Returns a list whose elements are either dict (word) or PunctToken.
    """
    tokens: list[Any] = []
    raw_tokens = re.findall(r"[A-Za-z]+|[\.\?,!;:]", text)
    for raw in raw_tokens:
        if re.match(r"[A-Za-z]+$", raw):
            key = raw.lower()
            if key not in LEXICON:
                # Unknown word: default to 432 Hz neutral. The substrate
                # version would lazy-create the cell on first encounter.
                tokens.append({"surface": raw, "lemma": key, "pos": "UNK",
                              "hz": 432, "field": "neutral"})
            else:
                entry = LEXICON[key]
                tokens.append({"surface": raw, **entry})
        else:
            tokens.append(PunctToken(raw))
    return tokens


# ---------------------------------------------------------------------------
# Part 3 — the sentence-recipe
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SentenceRecipe:
    """R_Block.SEQUENCE [word_cells..., punct?].

    Content-addressed Blueprint: identical word-sequence → identical
    Blueprint regardless of when/where the recipe was built.
    """

    children: tuple = field(default_factory=tuple)

    @property
    def blueprint(self) -> tuple:
        """Compose the Blueprint from children's blueprints. This IS
        the substrate's content-addressing primitive — children's
        NodeIDs compose the parent's NodeID.
        """
        return ("R_Block.SEQUENCE",) + tuple(c.blueprint for c in self.children)


# ---------------------------------------------------------------------------
# Part 4 — parse: prose → recipe (forward)
# ---------------------------------------------------------------------------


def parse_prose(text: str) -> SentenceRecipe:
    children: list[Any] = []
    for tok in tokenize_words(text):
        if isinstance(tok, PunctToken):
            children.append(tok)
        else:
            children.append(intern_word_cell(
                lemma=tok["lemma"],
                pos=tok["pos"],
                hz=tok["hz"],
                semantic_field=tok["field"],
            ))
    return SentenceRecipe(children=tuple(children))


# ---------------------------------------------------------------------------
# Part 5 — emit: recipe → prose (backward)
# ---------------------------------------------------------------------------


def emit_prose(recipe: SentenceRecipe, surface_map: dict[tuple, str]) -> str:
    """Walk the SEQUENCE, render each child. Punctuation collapses
    onto the prior word.

    surface_map carries the original-form spelling for each word's
    blueprint — so "becomes" round-trips to "becomes", not "become"
    (the lemma). In the substrate version this map lives on the
    word-cell itself as an `inflections` axis; here it's passed in.
    """
    parts: list[str] = []
    for child in recipe.children:
        if isinstance(child, WordCell):
            surface = surface_map.get(child.blueprint, child.lemma)
            # Capitalize the first word of the sentence
            if not parts:
                surface = surface[0].upper() + surface[1:]
            parts.append(surface)
        elif isinstance(child, PunctToken):
            if parts:
                parts[-1] = parts[-1] + child.value
            else:
                parts.append(child.value)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Part 6 — the round-trip on a real sentence
# ---------------------------------------------------------------------------


def main() -> int:
    # The sentence is taken from lc-recipe-branching-sense's opening:
    # "...the choice point becomes visible..."
    original = "The choice point becomes visible."

    # Build the surface_map from the lexicon so inflections survive
    # the round-trip ("becomes" → "become" → "becomes").
    surface_map: dict[tuple, str] = {}
    for tok in tokenize_words(original):
        if isinstance(tok, dict):
            bp = ("word", tok["lemma"], tok["pos"], tok["hz"], tok["field"])
            surface_map[bp] = tok["surface"]

    # Forward: prose → recipe
    recipe = parse_prose(original)

    print("─" * 70)
    print(f"Original  : {original}")
    print("─" * 70)
    print("Word cells (lemma.POS @ hz / field):")
    for child in recipe.children:
        if isinstance(child, WordCell):
            print(f"  · {child.lemma}.{child.pos:<5} @ {child.hz} Hz "
                  f"/ {child.semantic_field}")
        else:
            print(f"  · «{child.value}»  (punct)")
    print("─" * 70)
    print(f"Recipe Blueprint:")
    print(f"  {recipe.blueprint}")
    print("─" * 70)

    # Backward: recipe → prose
    emitted = emit_prose(recipe, surface_map)
    print(f"Emitted   : {emitted}")
    print("─" * 70)

    # Assertion 1 — surface stability.
    assert emitted == original, (
        f"surface drift: {original!r} → {emitted!r}"
    )

    # Assertion 2 — Blueprint stability across re-parse.
    recipe2 = parse_prose(emitted)
    assert recipe.blueprint == recipe2.blueprint, (
        f"blueprint drift: {recipe.blueprint} ≠ {recipe2.blueprint}"
    )

    # Assertion 3 — content-addressing. A fresh process parsing the
    # same sentence resolves to the same word-cell objects (identity,
    # not just equality — `intern_word_cell` is idempotent).
    fresh = parse_prose(original)
    for a, b in zip(recipe.children, fresh.children):
        if isinstance(a, WordCell):
            assert a is b, f"word-cell identity drift: {a} is not {b}"

    # Assertion 4 — paraphrase resolves to a DIFFERENT Blueprint
    # (different surface form), but the word-cells overlap. This is
    # the seed of continuous coherence_distance: shared cells →
    # measurable proximity, not hard equivalence.
    paraphrase = "Visibility arrives at the point of choice."
    # Extend the lexicon briefly so the paraphrase can parse.
    LEXICON.update({
        "visibility": {"lemma": "visibility", "pos": "NOUN", "hz": 741,
                       "field": "consciousness"},
        "arrives":    {"lemma": "arrive",     "pos": "VERB", "hz": 528,
                       "field": "vitality"},
        "at":         {"lemma": "at",         "pos": "ADP",  "hz": 432,
                       "field": "neutral"},
        "of":         {"lemma": "of",         "pos": "ADP",  "hz": 432,
                       "field": "neutral"},
    })
    para_recipe = parse_prose(paraphrase)
    assert para_recipe.blueprint != recipe.blueprint, (
        "paraphrase should differ structurally"
    )

    # Compute a tiny coherence_distance — count overlapping word-cells.
    original_cells = {c.blueprint for c in recipe.children
                      if isinstance(c, WordCell)}
    para_cells = {c.blueprint for c in para_recipe.children
                  if isinstance(c, WordCell)}
    overlap = original_cells & para_cells
    print(f"Paraphrase: {paraphrase}")
    print(f"Overlapping word-cells with original: "
          f"{[bp[1] for bp in overlap]}")
    print(f"  → coherence_distance hint: {len(overlap)} cells shared")
    print("─" * 70)

    print()
    print("All four assertions hold:")
    print("  1. Surface stability — emit ∘ parse is identity on the original")
    print("  2. Blueprint stability — re-parse intern's to the same NodeID")
    print("  3. Content-addressing — fresh parse returns identical cell objects")
    print("  4. Paraphrase differentiation — different surface → different Blueprint,")
    print("     with measurable overlap via shared word-cells")
    print()
    print("The claim holds at this scale:")
    print("  a sequence of words IS a recipe of cells with blueprints.")
    print("─" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
