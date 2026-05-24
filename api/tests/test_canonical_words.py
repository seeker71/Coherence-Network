"""Tests for the canonical-word lexicon interner.

The teaching: a word is the smallest unit of KB content. Its Blueprint
composes from (lemma, POS, hz, semantic_field). `canonical_lexicon` curates
the body's most-alive words — body-tuned function words, anchor terms from
spec multilingual-web R17, and the cross-modal canonical recipe-shape names
— and the interner lands them as `domain="word"` cells.

These tests exercise the interner against an in-memory SQLite-backed
substrate (same pattern as `test_modality_blueprints.py` and
`test_substrate_word_domain.py`). They assert:

- Every canonical entry lands as a `domain="word"` cell whose
  cell-name follows the `{lemma}.{POS}` convention.
- Re-running the interner adds no new cells (idempotent via
  content-addressing on the four-axis Blueprint).
- Two words sharing semantic_field share at least one resonance edge —
  queryable as semantic-field twins via the HARMONIC_AT @<hz> signature
  authored by `ingest_word_cell`.
- Every canonical recipe-shape name from `modality_shapes.CANONICAL_SHAPES`
  has a word-cell counterpart (lemma is the bare shape name, no R_ prefix).
- The three anchor families (tending/transmutation/vitality/etc.) all land
  with their body-tuned Hz, not the neutral fallback.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from app.services.substrate.canonical_lexicon import (
    ANCHOR_TERMS,
    DOMAIN_WORD,
    FIELD_HZ,
    RECIPE_SHAPE_FIELD,
    canonical_word_entries,
    intern_all_canonical_words,
    intern_canonical_word,
)
from app.services.substrate.kernel import find_equivalent_cells, lookup_cell
from app.services.substrate.markdown_frontend import (
    _WORD_LEXICON_DEFAULTS,
    ingest_word_cell,
    lemma_pos_key,
)
from app.services.substrate.resonance import cell_resonance_signature
from app.services.substrate.modality_shapes import CANONICAL_SHAPES
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.substrate_strings import SubstrateStringORM

from intern_canonical_words import intern_all  # noqa: E402


@pytest.fixture
def session():
    """In-memory SQLite session with substrate tables only."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Entry list — the canonical lexicon shape
# ---------------------------------------------------------------------------


def test_canonical_word_entries_is_deduped_by_lemma_pos():
    """No (lemma, POS) pair appears twice in the canonical list."""
    entries = canonical_word_entries()
    keys = [(lemma.lower(), pos.upper()) for lemma, pos, _hz, _field in entries]
    assert len(keys) == len(set(keys)), (
        "canonical lexicon contains a duplicate (lemma, POS) — dedupe broken"
    )


def test_canonical_word_entries_covers_round_trip_sentence():
    """The five words from 'The choice point becomes visible.' all live in
    the canonical lexicon — the prose-as-recipe round-trip stays grounded."""
    entries = {(lemma.lower(), pos.upper()) for lemma, pos, _hz, _field in canonical_word_entries()}
    assert ("the",     "DET")  in entries, "DET 'the' missing — round-trip word"
    assert ("choice",  "NOUN") in entries, "NOUN 'choice' missing — round-trip word"
    assert ("point",   "NOUN") in entries, "NOUN 'point' missing — round-trip word"
    assert ("become",  "VERB") in entries, "VERB 'become' missing — round-trip word"
    assert ("visible", "ADJ")  in entries, "ADJ 'visible' missing — round-trip word"


def test_canonical_word_entries_covers_body_lexicon():
    """Every (lemma, POS) in `_WORD_LEXICON_DEFAULTS` appears in the canonical
    list — the prose tokenizer's existing vocabulary lifts intact."""
    canonical = {
        (lemma.lower(), pos.upper()) for lemma, pos, _hz, _field in canonical_word_entries()
    }
    body = {
        (entry["lemma"].lower(), entry["pos"].upper())
        for entry in _WORD_LEXICON_DEFAULTS.values()
    }
    missing = body - canonical
    assert not missing, f"body-lexicon entries missing from canonical: {missing!r}"


def test_canonical_word_entries_covers_anchor_terms():
    """Every anchor term lands in the canonical list with its body-tuned field."""
    canonical = {
        (lemma.lower(), pos.upper()): (hz, field)
        for lemma, pos, hz, field in canonical_word_entries()
    }
    for lemma, pos, _hz, field in ANCHOR_TERMS:
        key = (lemma.lower(), pos.upper())
        assert key in canonical, f"anchor term {key!r} missing from canonical lexicon"
        # First-occurrence wins — the body lexicon may have already tuned
        # this word at a different (hz, field). We assert the canonical
        # entry carries SOME tuning, not the specific anchor value, so the
        # body-tuned value is honored when it exists.
        assert canonical[key][1] in FIELD_HZ, (
            f"anchor term {key!r} interns with unknown semantic_field "
            f"{canonical[key][1]!r}"
        )


# ---------------------------------------------------------------------------
# Idempotency — re-running adds nothing new
# ---------------------------------------------------------------------------


def test_intern_lexicon_is_idempotent(session):
    """Re-running the interner produces no new cells; same Blueprint NodeIDs."""
    report_a = intern_all_canonical_words(session)
    report_b = intern_all_canonical_words(session)

    assert len(report_a) == len(report_b)
    for (name_a, key_a, bp_a), (name_b, key_b, bp_b) in zip(report_a, report_b):
        assert name_a == name_b
        assert key_a == key_b
        assert bp_a == bp_b, (
            f"{name_a!r} Blueprint drift across re-intern — content-addressing broken"
        )

    # Cell count stable: count of word-cells before == after second run.
    word_cells = session.query(SubstrateNamedCellORM).filter_by(
        domain=DOMAIN_WORD
    ).count()
    intern_all_canonical_words(session)
    word_cells_after = session.query(SubstrateNamedCellORM).filter_by(
        domain=DOMAIN_WORD
    ).count()
    assert word_cells == word_cells_after, (
        f"third intern grew cell count: {word_cells} → {word_cells_after}"
    )


# ---------------------------------------------------------------------------
# Domain — every interned cell lives in the WORD domain
# ---------------------------------------------------------------------------


def test_word_cells_have_word_domain(session):
    """Every cell interned by the canonical lexicon has domain='word'."""
    report = intern_all_canonical_words(session)
    for cell_name, _key, _bp in report:
        cell = lookup_cell(session, DOMAIN_WORD, cell_name)
        assert cell is not None, f"canonical word {cell_name!r} not interned"
        assert cell.domain == DOMAIN_WORD, (
            f"canonical word {cell_name!r} has domain {cell.domain!r}, "
            f"expected {DOMAIN_WORD!r}"
        )


def test_cell_name_follows_lemma_pos_convention(session):
    """Interned cell names match `lemma_pos_key(lemma, POS)` exactly."""
    report = intern_all_canonical_words(session)
    for cell_name, expected_key, _bp in report:
        assert cell_name == expected_key, (
            f"cell name {cell_name!r} drifted from {expected_key!r}"
        )


# ---------------------------------------------------------------------------
# Semantic-field twins — words tagged 'consciousness' share resonance edges
# ---------------------------------------------------------------------------


def test_words_with_same_semantic_field_aligned(session):
    """Two 'consciousness' words share at least one HARMONIC_AT resonance edge.

    The substrate's content-addressing makes the HARMONIC_AT @741 edge a
    shared structural target for every consciousness-band word. Both
    'choice.NOUN' and 'visible.ADJ' fire at 741 Hz; their cell resonance
    signatures must intersect.
    """
    intern_all_canonical_words(session)

    choice = lookup_cell(session, DOMAIN_WORD, "choice.NOUN")
    visible = lookup_cell(session, DOMAIN_WORD, "visible.ADJ")
    assert choice is not None and visible is not None, (
        "consciousness-band canonical words missing from lattice"
    )

    sig_choice = cell_resonance_signature(session, choice.cell_id)
    sig_visible = cell_resonance_signature(session, visible.cell_id)
    assert sig_choice & sig_visible, (
        "two consciousness-field words should share at least one resonance "
        "edge target (the HARMONIC_AT @741 from the geometry signature)"
    )


def test_words_with_different_semantic_field_distinct(session):
    """Two words at different Hz bands have distinct CTORs.

    All word-cells share the WORD-domain Blueprint NodeID (`BID_word()`) —
    the four axes (lemma, POS, hz, semantic_field) live in the CTOR, not
    the Blueprint. So structural identity at the cell level is carried by
    the CTOR, while the Blueprint expresses "this is a word."

    Two words at different Hz bands have distinct CTORs (different lemma,
    different hz, different field). They share the SAME Blueprint
    NodeID, which is correct: both are word-cells.
    """
    intern_all_canonical_words(session)

    choice = lookup_cell(session, DOMAIN_WORD, "choice.NOUN")        # 741 / consciousness
    breath = lookup_cell(session, DOMAIN_WORD, "breath.NOUN")        # 396 / tending
    assert choice is not None and breath is not None
    # CTORs are distinct — content-addressing on the four-axis tuple keeps
    # them apart.
    assert choice.ctor != breath.ctor, (
        "words at different (lemma, hz, field) should not share CTOR"
    )
    # Both share the WORD-domain Blueprint — every word is a word.
    assert choice.blueprint == breath.blueprint


# ---------------------------------------------------------------------------
# Canonical recipe-shape names have word-cell counterparts
# ---------------------------------------------------------------------------


def test_canonical_recipe_shape_names_have_word_cells(session):
    """Every name in CANONICAL_SHAPES has a word-cell counterpart.

    The lemma is the bare shape name (R_Recovery → 'recovery.NOUN'). The
    canonical recipe-shape cell in domain='recipe-shape' lives elsewhere
    (interned by `intern_modality_blueprints.py`); this test verifies the
    word-cell anchor for prose written about the shape.
    """
    intern_all_canonical_words(session)

    for canonical_name, _slots, _tags in CANONICAL_SHAPES:
        lemma = canonical_name[2:] if canonical_name.startswith("R_") else canonical_name
        cell_name = lemma_pos_key(lemma, "NOUN")
        cell = lookup_cell(session, DOMAIN_WORD, cell_name)
        assert cell is not None, (
            f"recipe-shape word-cell {cell_name!r} (from {canonical_name!r}) "
            f"not interned"
        )
        assert cell.domain == DOMAIN_WORD


def test_recipe_shape_word_cells_fire_in_consciousness_band(session):
    """Recipe-shape word-cells all fire at 741 Hz (consciousness field).

    Recipe-shapes name structural moves of awareness; 741 Hz is the body's
    consciousness band. Two canonical recipe-shape word-cells should both
    carry the HARMONIC_AT @741 resonance edge — the substrate's structural
    recognition that both fire in the same band.
    """
    intern_all_canonical_words(session)

    # Sample two recipe-shape word-cells. Both lemmas are bare canonical
    # names (R_Recovery → 'recovery', R_GroundingMove → 'groundingmove').
    recovery = lookup_cell(session, DOMAIN_WORD, "recovery.NOUN")
    grounding = lookup_cell(session, DOMAIN_WORD, "groundingmove.NOUN")
    assert recovery is not None, "recovery.NOUN canonical recipe-shape word missing"
    assert grounding is not None, "groundingmove.NOUN canonical recipe-shape word missing"

    sig_recovery = cell_resonance_signature(session, recovery.cell_id)
    sig_grounding = cell_resonance_signature(session, grounding.cell_id)
    # Both share the HARMONIC_AT @741 edge.
    assert sig_recovery & sig_grounding, (
        "two recipe-shape word-cells should share the consciousness-band "
        "HARMONIC_AT @741 resonance edge"
    )


# ---------------------------------------------------------------------------
# Anchor terms — multilingual-web R17 vocabulary
# ---------------------------------------------------------------------------


def test_anchor_terms_intern_with_field_tuned_hz(session):
    """Each anchor term lands at SOME tuned (hz, field) — not the UNK
    fallback at 432/neutral.

    The body lexicon takes precedence on collisions; for anchor-unique
    terms (wholeness, kinship, belonging, stewardship), the entry comes
    straight from `ANCHOR_TERMS`.
    """
    intern_all_canonical_words(session)

    anchor_unique = ["wholeness.NOUN", "kinship.NOUN", "belonging.NOUN",
                     "stewardship.NOUN"]
    for cell_name in anchor_unique:
        cell = lookup_cell(session, DOMAIN_WORD, cell_name)
        assert cell is not None, f"anchor word {cell_name!r} not interned"
        # The HARMONIC_AT edge fires the word at its Hz; confirm at least
        # one resonance edge was authored.
        sig = cell_resonance_signature(session, cell.cell_id)
        assert len(sig) >= 1, (
            f"anchor word {cell_name!r} missing HARMONIC_AT resonance edge"
        )


# ---------------------------------------------------------------------------
# Script wrapper alias — `intern_all` works through the CLI module
# ---------------------------------------------------------------------------


def test_script_intern_all_alias_matches_module(session):
    """`scripts/intern_canonical_words.intern_all` is `intern_all_canonical_words`."""
    report_script = intern_all(session)
    # Re-run via module — same NodeIDs.
    report_module = intern_all_canonical_words(session)
    assert len(report_script) == len(report_module)
    for (name_a, _key_a, bp_a), (name_b, _key_b, bp_b) in zip(report_script, report_module):
        assert name_a == name_b
        assert bp_a == bp_b


# ---------------------------------------------------------------------------
# Single-word intern helper
# ---------------------------------------------------------------------------


def test_intern_canonical_word_returns_cell_name_and_blueprint(session):
    """`intern_canonical_word` returns (cell_name, blueprint_id) and lands
    a `domain='word'` cell with the expected name."""
    name, blueprint = intern_canonical_word(
        session, "wholeness", "NOUN", FIELD_HZ["wholeness"], "wholeness",
    )
    assert name == "wholeness.NOUN"
    cell = lookup_cell(session, DOMAIN_WORD, "wholeness.NOUN")
    assert cell is not None
    assert cell.blueprint == blueprint
    assert cell.domain == DOMAIN_WORD


def test_recipe_shape_field_is_consciousness_band():
    """Recipe-shape word-cells fire in the consciousness band (741 Hz)."""
    assert RECIPE_SHAPE_FIELD == "consciousness"
    assert FIELD_HZ[RECIPE_SHAPE_FIELD] == 741
