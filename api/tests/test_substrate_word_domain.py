"""Tests for the WORD domain — prose-as-recipe encoder + tokenizer + lookup.

The teaching: a word is the smallest unit of KB content. Its Blueprint
composes from (lemma, POS, hz, semantic_field). Sentences then intern as
R_Block.SEQUENCE recipes over WORD cells.

These tests verify:
- BID_word() points at the new BDomain.WORD enum entry
- ingest_word_cell is idempotent (same lemma+POS+hz+field → same cell)
- tokenize_words returns the expected shape for known and unknown words
- lemma_pos_key follows the documented naming convention
- The HARMONIC_AT resonance edge is authored automatically

Closes the test side of GAP-W1+W2+P1+P2 named in
docs/coherence-substrate/prose-as-recipe.form.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    BID_word,
    cell_resonance_signature,
    ingest_word_cell,
    lemma_pos_key,
    tokenize_words,
)
from app.services.substrate.category import BBasic, BDomain, Level
from app.services.substrate.kernel import NodeID
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.substrate_strings import SubstrateStringORM


@pytest.fixture
def session():
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
# BID_word & enum wiring
# ---------------------------------------------------------------------------


def test_word_blueprint_points_at_bdomain_word():
    bp = BID_word()
    assert bp == NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.WORD)
    assert int(BDomain.WORD) == 15


# ---------------------------------------------------------------------------
# lemma_pos_key — naming convention
# ---------------------------------------------------------------------------


def test_lemma_pos_key_normalizes_case():
    assert lemma_pos_key("Visible", "adj") == "visible.ADJ"
    assert lemma_pos_key("BECOME", "verb") == "become.VERB"


def test_lemma_pos_key_disambiguates_homographs():
    """Same lemma, different POS → distinct keys (visible.ADJ ≠ visible.VERB)."""
    assert lemma_pos_key("visible", "ADJ") != lemma_pos_key("visible", "VERB")


# ---------------------------------------------------------------------------
# tokenize_words — locale-light tokenizer
# ---------------------------------------------------------------------------


def test_tokenize_words_known_sentence():
    """The round-trip sentence parses to 5 words + 1 punct."""
    tokens = tokenize_words("The choice point becomes visible.")
    word_tokens = [t for t in tokens if t["kind"] == "word"]
    punct_tokens = [t for t in tokens if t["kind"] == "punct"]
    assert len(word_tokens) == 5
    assert len(punct_tokens) == 1
    assert punct_tokens[0]["surface"] == "."
    # Each known word resolves to its body-tuned (lemma, POS, hz, field).
    by_surface = {t["surface"]: t for t in word_tokens}
    assert by_surface["choice"]["hz"] == 741
    assert by_surface["choice"]["pos"] == "NOUN"
    assert by_surface["becomes"]["lemma"] == "become"
    assert by_surface["becomes"]["hz"] == 417
    assert by_surface["visible"]["field"] == "consciousness"


def test_tokenize_words_unknown_word_falls_back_to_neutral():
    """Unknown words land at 432 Hz / neutral / POS=UNK (GAP-P2 fallback)."""
    tokens = tokenize_words("xylophone")
    assert tokens[0]["kind"] == "word"
    assert tokens[0]["lemma"] == "xylophone"
    assert tokens[0]["pos"] == "UNK"
    assert tokens[0]["hz"] == 432
    assert tokens[0]["field"] == "neutral"


def test_tokenize_words_preserves_surface_form():
    """Surface form survives separately from lemma — for round-trip emit."""
    tokens = tokenize_words("becomes")
    assert tokens[0]["surface"] == "becomes"
    assert tokens[0]["lemma"] == "become"


# ---------------------------------------------------------------------------
# ingest_word_cell — idempotent encoder
# ---------------------------------------------------------------------------


def test_ingest_word_cell_creates_word_in_word_domain(session):
    cell, bp_id, ctor_id = ingest_word_cell(
        session, lemma="choice", pos="NOUN", hz=741, semantic_field="consciousness",
    )
    assert cell.domain == "word"
    assert cell.name == "choice.NOUN"
    assert bp_id == BID_word()


def test_ingest_word_cell_is_idempotent(session):
    """Two ingests with the same (lemma, POS, hz, field) collapse to one cell."""
    a, _, _ = ingest_word_cell(
        session, lemma="visible", pos="ADJ", hz=741, semantic_field="consciousness",
    )
    b, _, _ = ingest_word_cell(
        session, lemma="visible", pos="ADJ", hz=741, semantic_field="consciousness",
    )
    assert a.cell_id == b.cell_id


def test_ingest_word_cell_authors_harmonic_at_edge(session):
    """The word fires at its Hz in the substrate's resonance lattice."""
    cell, _, _ = ingest_word_cell(
        session, lemma="visible", pos="ADJ", hz=741, semantic_field="consciousness",
    )
    sig = cell_resonance_signature(session, cell.cell_id)
    # At least one resonance edge — the HARMONIC_AT @741 from
    # author_geometry_signature inside ingest_word_cell.
    assert len(sig) >= 1


def test_ingest_word_cell_different_pos_makes_different_cells(session):
    """visible.ADJ and visible.VERB are distinct cells with distinct Blueprints."""
    adj, _, _ = ingest_word_cell(
        session, lemma="visible", pos="ADJ", hz=741, semantic_field="consciousness",
    )
    verb, _, _ = ingest_word_cell(
        session, lemma="visible", pos="VERB", hz=417, semantic_field="transmutation",
    )
    assert adj.cell_id != verb.cell_id
    assert adj.name != verb.name


def test_two_consciousness_words_share_harmonic_at_edge(session):
    """Two 741-Hz words have at least one shared (verb, target) in their signatures.

    The shared signature entry is the HARMONIC_AT @741 edge — the substrate's
    structural recognition that both words fire in the consciousness band.
    """
    choice, _, _ = ingest_word_cell(
        session, lemma="choice", pos="NOUN", hz=741, semantic_field="consciousness",
    )
    visible, _, _ = ingest_word_cell(
        session, lemma="visible", pos="ADJ", hz=741, semantic_field="consciousness",
    )
    sig_choice = cell_resonance_signature(session, choice.cell_id)
    sig_visible = cell_resonance_signature(session, visible.cell_id)
    assert sig_choice & sig_visible, (
        "two 741-Hz words should share at least one resonance edge target"
    )


# ---------------------------------------------------------------------------
# find_downstream_cells — T1 closure: "which cells did this projection touch?"
# ---------------------------------------------------------------------------


def test_find_downstream_cells_walks_cell_ref_edges(session):
    """A cell that authored a HARMONIC_AT edge has the Hz-cell downstream.

    `ingest_word_cell` authors a HARMONIC_AT edge from the word → its Hz
    cell. `find_downstream_cells(word)` returns at least that Hz cell.
    """
    from app.services.substrate import find_downstream_cells
    word, _, _ = ingest_word_cell(
        session, lemma="choice", pos="NOUN", hz=741, semantic_field="consciousness",
    )
    downstream = find_downstream_cells(session, word.cell_id)
    # The HARMONIC_AT @741 edge made the Hz(741) cell appear downstream.
    domains = {c.domain for c in downstream}
    assert "spectrum" in domains, (
        f"expected spectrum cell downstream of word; got domains={domains}"
    )


def test_find_downstream_cells_excludes_self(session):
    """The cell never appears in its own downstream set."""
    from app.services.substrate import find_downstream_cells
    word, _, _ = ingest_word_cell(
        session, lemma="visible", pos="ADJ", hz=741, semantic_field="consciousness",
    )
    downstream = find_downstream_cells(session, word.cell_id)
    assert all(c.cell_id != word.cell_id for c in downstream)
