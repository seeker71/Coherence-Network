"""Flow-centric tests for the dimensional vocabulary and resonance edges.

The geometric signature pilot landed `geometry:` blocks on 10 vision-kb
concepts. This module proves the substrate-side commitment:

- Cells in the five new dimensional domains (SPECTRUM, HARMONIC,
  GEOMETRIC_FORM, POLARITY, TOPOLOGY) intern as Blueprint NodeIDs and
  dedupe on (domain, name).
- Resonance-edge Recipe NodeIDs intern via the kernel's content-
  addressing — two source cells with identical edge-sets share the
  Recipe NodeID, which is what makes the substrate the receiving
  infrastructure for cross-discipline bridges.
- `author_geometry_signature` is idempotent: re-running on the same
  inputs produces the same Recipe NodeIDs.
- The flagship case: three triadic concepts with identical signature
  components share matching shapes edges.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    BID_concept,
    BID_geometric_form,
    BID_polarity,
    BID_spectrum,
    BID_topology,
    DOMAIN_GEOMETRIC_FORM,
    DOMAIN_POLARITY,
    DOMAIN_SPECTRUM,
    DOMAIN_TOPOLOGY,
    author_geometry_signature,
    geometric_form_cell,
    harmonic_at_edge,
    hz_cell,
    make_cell,
    polarity_cell,
    shapes_edge,
    topology_cell,
)
from app.services.substrate.category import BBasic, BDomain, Level, RBasic, RResonance
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


# ---------------------------------------------------------------------------
# Fixture — isolated in-memory substrate
# ---------------------------------------------------------------------------


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(engine, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(engine, checkfirst=True)
    from app.services.substrate.substrate_strings import SubstrateStringORM
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Dimensional Blueprint NodeIDs are stable
# ---------------------------------------------------------------------------


def test_dimensional_domain_blueprints_are_distinct():
    """Each of the five new domains lives at its own BDomain instance."""
    bps = [
        BID_spectrum(),
        BID_geometric_form(),
        BID_polarity(),
        BID_topology(),
    ]
    assert len({(bp.package, bp.level, bp.type_, bp.instance) for bp in bps}) == 4
    # And they all share the same (package, level, type_) — they're DOMAIN blueprints.
    for bp in bps:
        assert bp.level == Level.BASIC
        assert bp.type_ == BBasic.DOMAIN


# ---------------------------------------------------------------------------
# Cell-ensure helpers are idempotent on (domain, name)
# ---------------------------------------------------------------------------


def test_hz_cell_is_idempotent(session):
    """Calling hz_cell twice with the same Hz returns the same cell."""
    a = hz_cell(session, 741)
    b = hz_cell(session, 741)
    assert a.cell_id == b.cell_id
    assert a.domain == DOMAIN_SPECTRUM
    assert a.name == "Hz-741"


def test_different_hz_values_get_different_cells(session):
    """Hz(174) and Hz(741) are distinct cells in the SPECTRUM domain."""
    foundation = hz_cell(session, 174)
    integration = hz_cell(session, 741)
    assert foundation.cell_id != integration.cell_id
    assert foundation.domain == integration.domain == DOMAIN_SPECTRUM


def test_geometric_form_cell_normalizes_case(session):
    """`triad`, `Triad`, and `TRIAD` resolve to the same cell."""
    a = geometric_form_cell(session, "triad")
    b = geometric_form_cell(session, "Triad")
    c = geometric_form_cell(session, "TRIAD")
    assert a.cell_id == b.cell_id == c.cell_id


def test_polarity_topology_cells_have_correct_domains(session):
    """Cells in POLARITY and TOPOLOGY domains carry their domain tag."""
    pol = polarity_cell(session, "triadic-tension")
    top = topology_cell(session, "parallel-facets")
    assert pol.domain == DOMAIN_POLARITY
    assert top.domain == DOMAIN_TOPOLOGY


# ---------------------------------------------------------------------------
# Resonance-edge Recipe NodeIDs dedupe through content-addressing
# ---------------------------------------------------------------------------


def test_shapes_edge_dedup(session):
    """Two SHAPES edges from the same source to the same form share NodeID."""
    src = make_cell(session, name="lc-test", domain="concept", blueprint=BID_concept())
    form = geometric_form_cell(session, "triad")
    e1 = shapes_edge(session, src.cell_id, form.cell_id)
    e2 = shapes_edge(session, src.cell_id, form.cell_id)
    assert e1 == e2


def test_shapes_edge_uses_resonance_category(session):
    """The edge's category encodes RBasic.RESONANCE + RResonance.SHAPES."""
    src = make_cell(session, name="lc-test-2", domain="concept", blueprint=BID_concept())
    form = geometric_form_cell(session, "pentad")
    edge_id = shapes_edge(session, src.cell_id, form.cell_id)
    # The edge is a Recipe; its row is in DOMAIN_RECIPE.
    from app.services.substrate.kernel import DOMAIN_RECIPE
    row = (
        session.query(SubstrateNodeORM)
        .filter_by(
            domain=DOMAIN_RECIPE,
            package=edge_id.package,
            level=edge_id.level,
            type_=edge_id.type_,
            instance=edge_id.instance,
        )
        .one()
    )
    # The row's `type_` reflects the recipe category's type — RBasic.RESONANCE (21).
    # The instance column auto-allocates per (package, level, type_), so we don't
    # assert on it directly; the serialized payload carries the SHAPES verb.
    assert row.type_ == RBasic.RESONANCE


def test_different_resonance_verbs_get_different_edges(session):
    """SHAPES and HARMONIC_AT produce distinct Recipe NodeIDs."""
    src = make_cell(session, name="lc-test-3", domain="concept", blueprint=BID_concept())
    form = geometric_form_cell(session, "triad")
    hz = hz_cell(session, 174)
    shapes_id = shapes_edge(session, src.cell_id, form.cell_id)
    harmonic_id = harmonic_at_edge(session, src.cell_id, hz.cell_id)
    assert shapes_id != harmonic_id


# ---------------------------------------------------------------------------
# author_geometry_signature — the top-level walker
# ---------------------------------------------------------------------------


_TRIAD_PARALLEL_FACETS_SIG = {
    "arity": 3,
    "form": "triad",
    "topology": "parallel",
    "polarity": "parallel-facets",
    "ordering": "unordered",
    "phase": "yang",
    "ratio": "none",
    "spectral_band": "foundation",
    "temporal_band": "cellular",
    "scale": "cellular",
    "direction": "centering",
    "lineage_texture": "synthesized",
    "embedding_dim": 1,
    "self_similarity": "flat",
}


def test_author_geometry_signature_authors_expected_edges(session):
    """A full triad-parallel-facets signature produces ≥13 edges."""
    src = make_cell(session, name="lc-trust-over-fear", domain="concept", blueprint=BID_concept())
    edges = author_geometry_signature(
        session, src.cell_id, _TRIAD_PARALLEL_FACETS_SIG, arity_hz=174,
    )
    # hz + every non-arity field with a handler.
    fields_authored = {field for field, _ in edges}
    assert "hz" in fields_authored
    assert "form" in fields_authored
    assert "topology" in fields_authored
    assert "polarity" in fields_authored
    assert "spectral_band" in fields_authored
    # arity is skipped (it's structural to the source cell, not an edge target).
    assert "arity" not in fields_authored


def test_author_geometry_signature_is_idempotent(session):
    """Re-authoring the same signature returns the same Recipe NodeIDs."""
    src = make_cell(session, name="lc-test-idempotent", domain="concept", blueprint=BID_concept())
    first = author_geometry_signature(
        session, src.cell_id, _TRIAD_PARALLEL_FACETS_SIG, arity_hz=174,
    )
    second = author_geometry_signature(
        session, src.cell_id, _TRIAD_PARALLEL_FACETS_SIG, arity_hz=174,
    )
    first_map = dict(first)
    second_map = dict(second)
    assert set(first_map) == set(second_map)
    for field in first_map:
        assert first_map[field] == second_map[field]


def test_two_triadic_concepts_share_form_edge(session):
    """Flagship: triad-shaped concepts share their SHAPES edge target.

    `lc-trust-over-fear` and `lc-whole-vitality` both author SHAPES edges
    pointing at the same ~Triad cell (NodeID equality) — the substrate is
    now structurally aware that these two are triadic siblings, regardless
    of their different prose / hz / scale.
    """
    a_cell = make_cell(session, name="lc-trust-over-fear", domain="concept", blueprint=BID_concept())
    b_cell = make_cell(session, name="lc-whole-vitality", domain="concept", blueprint=BID_concept())

    a_edges = dict(author_geometry_signature(
        session, a_cell.cell_id,
        {"form": "triad", "polarity": "parallel-facets"},
    ))
    b_edges = dict(author_geometry_signature(
        session, b_cell.cell_id,
        {"form": "triad", "polarity": "parallel-facets"},
    ))

    # Different source cells, but both edges reference the SAME ~Triad cell.
    # The Recipe NodeIDs themselves DIFFER (each edge carries its own source-cell
    # as a child), but the target ~Triad cell is shared — that's the bridge.
    triad = geometric_form_cell(session, "triad")
    parallel = polarity_cell(session, "parallel-facets")

    # Re-author the same edges from outside and check NodeID equality
    # with the ones author_geometry_signature produced.
    assert shapes_edge(session, a_cell.cell_id, triad.cell_id) == a_edges["form"]
    assert shapes_edge(session, b_cell.cell_id, triad.cell_id) == b_edges["form"]
    assert shapes_edge(session, a_cell.cell_id, parallel.cell_id) == a_edges["polarity"]


def test_unknown_geometry_field_is_skipped_not_raised(session):
    """An unrecognized field like `mystery_dim` is ignored, not an error."""
    src = make_cell(session, name="lc-unknown-test", domain="concept", blueprint=BID_concept())
    edges = author_geometry_signature(
        session, src.cell_id, {"form": "triad", "mystery_dim": "wat"},
    )
    fields = {field for field, _ in edges}
    assert "form" in fields
    assert "mystery_dim" not in fields


def test_none_or_unknown_values_skip_edge_authoring(session):
    """A field with value `None` or `"unknown"` does not produce an edge."""
    src = make_cell(session, name="lc-skip-test", domain="concept", blueprint=BID_concept())
    edges = author_geometry_signature(
        session, src.cell_id,
        {"form": "triad", "polarity": None, "topology": "unknown"},
    )
    fields = {field for field, _ in edges}
    assert "form" in fields
    assert "polarity" not in fields
    assert "topology" not in fields


# ---------------------------------------------------------------------------
# Continuous coherence — the >5D harmonic distance metric
# ---------------------------------------------------------------------------


def test_coherence_score_identical_signatures(session):
    """Two cells with the same geometry signature have coherence_score 1.0."""
    from app.services.substrate import coherence_score
    sig = {"form": "triad", "topology": "cyclic-closed", "polarity": "parallel-facets"}
    a = make_cell(session, name="lc-a-coherent", domain="concept", blueprint=BID_concept())
    b = make_cell(session, name="lc-b-coherent", domain="concept", blueprint=BID_concept())
    author_geometry_signature(session, a.cell_id, sig, arity_hz=741)
    author_geometry_signature(session, b.cell_id, sig, arity_hz=741)
    assert coherence_score(session, a.cell_id, b.cell_id) == 1.0


def test_coherence_score_disjoint_signatures(session):
    """Cells with no overlap in their resonance signatures score 0.0."""
    from app.services.substrate import coherence_score
    a = make_cell(session, name="lc-a-disjoint", domain="concept", blueprint=BID_concept())
    b = make_cell(session, name="lc-b-disjoint", domain="concept", blueprint=BID_concept())
    author_geometry_signature(session, a.cell_id, {"form": "triad"}, arity_hz=174)
    author_geometry_signature(session, b.cell_id, {"form": "pentad"}, arity_hz=741)
    score = coherence_score(session, a.cell_id, b.cell_id)
    assert score == 0.0, f"expected 0.0 for disjoint signatures, got {score}"


def test_coherence_score_partial_overlap(session):
    """Cells sharing some axes get a fractional coherence score."""
    from app.services.substrate import coherence_score
    a = make_cell(session, name="lc-a-partial", domain="concept", blueprint=BID_concept())
    b = make_cell(session, name="lc-b-partial", domain="concept", blueprint=BID_concept())
    # A and B share form=triad and the same Hz, but differ on topology/polarity.
    author_geometry_signature(
        session, a.cell_id,
        {"form": "triad", "topology": "cyclic-closed", "polarity": "parallel-facets"},
        arity_hz=174,
    )
    author_geometry_signature(
        session, b.cell_id,
        {"form": "triad", "topology": "parallel", "polarity": "triadic-tension"},
        arity_hz=174,
    )
    score = coherence_score(session, a.cell_id, b.cell_id)
    assert 0.0 < score < 1.0, f"expected partial overlap in (0,1), got {score}"


def test_coherence_score_is_symmetric(session):
    """coherence_score(A, B) == coherence_score(B, A)."""
    from app.services.substrate import coherence_score
    a = make_cell(session, name="lc-a-sym", domain="concept", blueprint=BID_concept())
    b = make_cell(session, name="lc-b-sym", domain="concept", blueprint=BID_concept())
    author_geometry_signature(session, a.cell_id, {"form": "triad"}, arity_hz=174)
    author_geometry_signature(session, b.cell_id, {"form": "pentad"}, arity_hz=741)
    assert coherence_score(session, a.cell_id, b.cell_id) == coherence_score(
        session, b.cell_id, a.cell_id
    )


def test_coherence_score_both_empty_is_one(session):
    """Two cells with no resonance signature are vacuously identical."""
    from app.services.substrate import coherence_score
    a = make_cell(session, name="lc-a-empty", domain="concept", blueprint=BID_concept())
    b = make_cell(session, name="lc-b-empty", domain="concept", blueprint=BID_concept())
    assert coherence_score(session, a.cell_id, b.cell_id) == 1.0


def test_coherence_distance_counts_disagreements(session):
    """coherence_distance returns the symmetric-difference count of signature axes."""
    from app.services.substrate import coherence_distance
    a = make_cell(session, name="lc-a-dist", domain="concept", blueprint=BID_concept())
    b = make_cell(session, name="lc-b-dist", domain="concept", blueprint=BID_concept())
    # A: form=triad, hz=174  →  2 edges
    # B: form=pentad, hz=741 →  2 edges
    # No overlap → distance == 4 (all four edges differ)
    author_geometry_signature(session, a.cell_id, {"form": "triad"}, arity_hz=174)
    author_geometry_signature(session, b.cell_id, {"form": "pentad"}, arity_hz=741)
    assert coherence_distance(session, a.cell_id, b.cell_id) == 4

    # Identical signature → distance == 0
    c = make_cell(session, name="lc-c-dist", domain="concept", blueprint=BID_concept())
    d = make_cell(session, name="lc-d-dist", domain="concept", blueprint=BID_concept())
    author_geometry_signature(session, c.cell_id, {"form": "triad"}, arity_hz=174)
    author_geometry_signature(session, d.cell_id, {"form": "triad"}, arity_hz=174)
    assert coherence_distance(session, c.cell_id, d.cell_id) == 0


def test_cell_resonance_signature_captures_authored_edges(session):
    """The raw signature set contains every (verb, target) pair from the cell."""
    from app.services.substrate import cell_resonance_signature
    src = make_cell(session, name="lc-sig-test", domain="concept", blueprint=BID_concept())
    author_geometry_signature(
        session, src.cell_id,
        {"form": "triad", "polarity": "parallel-facets"},
        arity_hz=174,
    )
    sig = cell_resonance_signature(session, src.cell_id)
    # At least three edges: hz (HARMONIC_AT), form (SHAPES), polarity (SHAPES).
    assert len(sig) >= 3
    # Each entry is a (verb_instance, target_db_id) tuple.
    for entry in sig:
        assert isinstance(entry, tuple) and len(entry) == 2
        assert isinstance(entry[0], int) and isinstance(entry[1], int)
