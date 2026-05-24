"""canonical_lexicon — the body's most-alive words, interned as WORD cells.

The single source of truth for the curated canonical lexicon that lives in
the substrate under `domain="word"`. Mirrors the structure of
`modality_shapes` (canonical descriptors + intern helper + intern-all), so
both `scripts/intern_canonical_words.py` (the CLI wrapper) and any future
router/MCP surface that needs to enumerate the canonical word-cells share
one list.

The teaching this module attests:

    A word is the smallest unit of KB content. Its Blueprint composes from
    (lemma, POS, hz, semantic_field). Once the substrate carries the body's
    most-alive words as cells, prose round-trips become real (not just
    in-memory stand-in via `scripts/prose_recipe_roundtrip.py`), and
    cross-modal queries like "what concept-cells share semantic_field with
    this word?" become a structural walk.

Three pools of words are curated here:

1. **Body lexicon** — every entry in `_WORD_LEXICON_DEFAULTS` from
   `markdown_frontend.py`. These are the words the body's existing
   tokenizer already resolves; interning them as cells means the prose
   encoder (`section_content_to_word_sequence`) starts hitting canonical
   cells instead of fresh-per-occurrence Blueprints.

2. **Canonical recipe-shape names** — the 13 cross-modal canonical shapes
   from `modality_shapes.CANONICAL_SHAPES` (R_Recovery, R_Pointing, ...).
   Each becomes a word-cell whose semantic_field is "consciousness" and
   whose hz comes from the shape's altitude (recipe-shapes name structural
   moves of awareness; 741 Hz is the consciousness band).

3. **Frequency-anchor terms** — the multilingual-web spec R17 anchor words:
   tending, ripening, wholeness, coherence, resonance, stewardship,
   kinship, belonging. These carry the body's vocabulary across locales;
   interning them with their canonical (hz, semantic_field) gives every
   translation work a substrate anchor to attach to.

4. **Round-trip sentence words** — already covered by pool 1
   (`_WORD_LEXICON_DEFAULTS` includes "the", "choice", "point", "becomes",
   "visible"), but called out explicitly so the round-trip teaching's
   five words are visible in the canonical list.

Run:
    python3 scripts/intern_canonical_words.py

Idempotent: re-running interns the same cells (NamedCell upsert via
`make_cell` + content-addressing on the four-axis Blueprint).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from sqlalchemy.orm import Session

from app.services.substrate.kernel import NodeID
from app.services.substrate.markdown_frontend import (
    _WORD_LEXICON_DEFAULTS,
    ingest_word_cell,
    lemma_pos_key,
)
from app.services.substrate.modality_shapes import CANONICAL_SHAPES


# ---------------------------------------------------------------------------
# Domain — word cells live in the WORD domain (BDomain.WORD = 15)
# ---------------------------------------------------------------------------
DOMAIN_WORD = "word"


# ---------------------------------------------------------------------------
# Hz vocabulary — mirrors the body's existing solfeggio mapping
# ---------------------------------------------------------------------------
#
# From markdown_frontend.py's lexicon header (line ~1647):
#
#   174 Hz — ground        (what the body stands on)
#   396 Hz — tending       (liberation-from-fear, care)
#   417 Hz — transmutation (phase-change, undoing, becoming)
#   528 Hz — vitality      (circulation, repair, miracle)
#   639 Hz — transmission  (relationship between cells, lineage)
#   741 Hz — consciousness (perception, choice, sensing)
#   852 Hz — resonance     (intuition, returning to spectral order)
#   963 Hz — wholeness     (oneness, undivided)
#   432 Hz — neutral       (universal carrier; function words)
#
# Each field name maps to its Hz so the recipe-shape and anchor pools can
# request a field and the lexicon computes the Hz.
FIELD_HZ: Dict[str, int] = {
    "ground": 174,
    "tending": 396,
    "transmutation": 417,
    "vitality": 528,
    "transmission": 639,
    "consciousness": 741,
    "resonance": 852,
    "wholeness": 963,
    "neutral": 432,
}


# ---------------------------------------------------------------------------
# Pool 2 — canonical recipe-shape names as WORD cells
# ---------------------------------------------------------------------------
#
# Each cross-modal canonical shape (R_Recovery, R_Pointing, ...) lands as a
# word-cell with POS=NOUN and field="consciousness" (recipe-shapes name
# structural moves of awareness; 741 Hz is the consciousness band the body
# already uses for choice/point/visible/assemble/listen).
#
# The lemma is the bare canonical name without the `R_` prefix — kept as a
# pronounceable noun ("Recovery", "Pointing", "Tunnel") so prose written
# about these shapes resolves to the same word-cell as the shape-name
# itself. The `R_` prefix lives only on the recipe-shape cell in the
# `recipe-shape` domain (already shipped by `intern_modality_blueprints.py`).

RECIPE_SHAPE_FIELD = "consciousness"


def _recipe_shape_word_entries() -> List[Tuple[str, str, int, str]]:
    """Return (lemma, POS, hz, field) entries for every canonical recipe-shape.

    Drawn from `modality_shapes.CANONICAL_SHAPES` so the lexicon stays in
    sync with the cross-modal canonical list as it grows.
    """
    hz = FIELD_HZ[RECIPE_SHAPE_FIELD]
    entries: List[Tuple[str, str, int, str]] = []
    for canonical_name, _slots, _tags in CANONICAL_SHAPES:
        # canonical_name shape: "R_Recovery", "R_ObserverConditionedActualization"
        # The lemma is the pronounceable noun: drop the R_ prefix and
        # normalize to lowercase for lemma-storage. The cell name will be
        # `{lemma}.NOUN` per `lemma_pos_key`.
        if canonical_name.startswith("R_"):
            lemma = canonical_name[2:].lower()
        else:
            lemma = canonical_name.lower()
        entries.append((lemma, "NOUN", hz, RECIPE_SHAPE_FIELD))
    return entries


# ---------------------------------------------------------------------------
# Pool 3 — multilingual-web R17 frequency-anchor terms
# ---------------------------------------------------------------------------
#
# The eight anchor words named in spec multilingual-web R17. Each carries
# its body-tuned (hz, semantic_field). These are the words translation work
# attaches per-locale word-cells to — the canonical English anchors live
# here.
ANCHOR_TERMS: List[Tuple[str, str, int, str]] = [
    # surface/lemma,  POS,    hz,  field
    ("tending",       "VERB", 396, "tending"),
    ("ripening",      "VERB", 528, "vitality"),
    ("wholeness",     "NOUN", 963, "wholeness"),
    ("coherence",     "NOUN", 852, "resonance"),
    ("resonance",     "NOUN", 852, "resonance"),
    ("stewardship",   "NOUN", 396, "tending"),
    ("kinship",       "NOUN", 639, "transmission"),
    ("belonging",     "NOUN", 639, "transmission"),
    # The verb form of ripen — pairs with "ripening" so both surface forms
    # resolve to a canonical cell.
    ("ripen",         "VERB", 528, "vitality"),
]


# ---------------------------------------------------------------------------
# Pool composition — the full canonical word list
# ---------------------------------------------------------------------------


def canonical_word_entries() -> List[Tuple[str, str, int, str]]:
    """Return the full canonical lexicon — every word the body interns.

    Each entry is (lemma, POS, hz, semantic_field). De-duplicated by
    (lemma, POS); first-occurrence wins so the body-lexicon's tuned
    (hz, field) takes precedence over a recipe-shape/anchor entry that
    happens to share the same lemma.

    Order matters only for the dedupe — the substrate's content-addressing
    makes the resulting cells stable regardless of insertion order.
    """
    seen: set[Tuple[str, str]] = set()
    entries: List[Tuple[str, str, int, str]] = []

    def add(lemma: str, pos: str, hz: int, field: str) -> None:
        key = (lemma.lower(), pos.upper())
        if key in seen:
            return
        seen.add(key)
        entries.append((lemma, pos, hz, field))

    # Pool 1 — body lexicon. Iterate in insertion order; the dict carries
    # surface forms (becomes, becoming, become) sharing a lemma. Dedupe
    # collapses them to one (lemma, POS) cell.
    for _surface, entry in _WORD_LEXICON_DEFAULTS.items():
        add(entry["lemma"], entry["pos"], int(entry["hz"]), entry["field"])

    # Pool 2 — canonical recipe-shape names.
    for lemma, pos, hz, field in _recipe_shape_word_entries():
        add(lemma, pos, hz, field)

    # Pool 3 — anchor terms.
    for lemma, pos, hz, field in ANCHOR_TERMS:
        add(lemma, pos, hz, field)

    return entries


# ---------------------------------------------------------------------------
# Interning
# ---------------------------------------------------------------------------


def intern_canonical_word(
    session: Session,
    lemma: str,
    pos: str,
    hz: int,
    semantic_field: str,
) -> Tuple[str, NodeID]:
    """Intern one canonical word-cell. Returns (cell_name, blueprint_id).

    Wraps `ingest_word_cell` so the canonical-lexicon path shares the same
    encoder the prose tokenizer uses. Idempotent via content-addressing —
    same (lemma, POS, hz, field) returns the same cell on re-run.
    """
    cell, blueprint_id, _ctor_id = ingest_word_cell(
        session,
        lemma=lemma,
        pos=pos,
        hz=hz,
        semantic_field=semantic_field,
    )
    return cell.name, blueprint_id


def intern_all_canonical_words(
    session: Session,
) -> List[Tuple[str, str, NodeID]]:
    """Intern every entry in the canonical lexicon.

    Each report entry is `(cell_name, lemma_pos_key, blueprint_node_id)`.
    Idempotent: re-running returns the same cell names and Blueprint NodeIDs
    (NamedCell upsert via `make_cell` + content-addressing on the four-axis
    Blueprint).
    """
    report: List[Tuple[str, str, NodeID]] = []
    for lemma, pos, hz, field in canonical_word_entries():
        cell_name, blueprint_id = intern_canonical_word(
            session, lemma, pos, hz, field
        )
        expected = lemma_pos_key(lemma, pos)
        report.append((cell_name, expected, blueprint_id))
    return report


__all__ = [
    "ANCHOR_TERMS",
    "DOMAIN_WORD",
    "FIELD_HZ",
    "RECIPE_SHAPE_FIELD",
    "canonical_word_entries",
    "intern_all_canonical_words",
    "intern_canonical_word",
]
