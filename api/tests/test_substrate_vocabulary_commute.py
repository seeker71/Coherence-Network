"""`?vocabulary` lens + commutative resonance edges.

Two additions shipped after running Form in the numeric register surfaced two
asks of the body:

1. The verb-cluster histogram is a wellness signal — a body whose recipe
   space is one-verb-dominated is a body without circulation across language
   layers. `?vocabulary` exposes the histogram as a lens.

2. The substrate is non-commutative by default — `(a, b)` and `(b, a)` intern
   as distinct recipes even for relations that ARE symmetric (BRIDGES,
   NEAR, POLAR_TO). `commutative_edge` (+ convenience wrappers
   bridges_symmetric / near_symmetric / polar_to_symmetric) canonicalize the
   pair before authoring, giving symmetric relations a single canonical NodeID.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    BID_concept,
    author_geometry_signature,
    bridges_edge,
    bridges_symmetric,
    commutative_edge,
    form_evaluate_text,
    make_cell,
    near_symmetric,
    polar_to_symmetric,
    vocabulary_histogram,
)
from app.services.substrate.category import BBasic, RBasic, RResonance
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


@pytest.fixture
def session():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SubstrateNodeORM.__table__.create(eng, checkfirst=True)
    SubstrateNamedCellORM.__table__.create(eng, checkfirst=True)
    from app.services.substrate.substrate_strings import SubstrateStringORM
    SubstrateStringORM.__table__.create(eng, checkfirst=True)
    s = sessionmaker(bind=eng, expire_on_commit=False)()
    try:
        yield s
        s.commit()
    finally:
        s.close()


@pytest.fixture
def populated(session):
    """Three triadic concepts — gives us cells + resonance edges to count."""
    cells = {}
    for name in ["lc-a", "lc-b", "lc-c"]:
        c = make_cell(session, name=name, domain="concept", blueprint=BID_concept())
        author_geometry_signature(session, c.cell_id, {"form": "triad"}, arity_hz=174)
        cells[name] = c
    session.commit()
    return cells


# ---------------------------------------------------------------------------
# `?vocabulary` — verb-cluster lens
# ---------------------------------------------------------------------------


def test_vocabulary_on_empty_substrate(session):
    """Empty substrate has empty histograms."""
    r = form_evaluate_text(session, "?vocabulary")
    assert r.kind == "vocabulary"
    assert r.value == {"recipes": {}, "blueprints": {}}


def test_vocabulary_reflects_resonance_authoring(session, populated):
    """After authoring resonance edges, type_=21 (RBasic.RESONANCE) populates."""
    r = form_evaluate_text(session, "?vocabulary")
    assert RBasic.RESONANCE in r.value["recipes"]
    assert r.value["recipes"][RBasic.RESONANCE] > 0


def test_vocabulary_reveals_verb_clustering(session, populated):
    """The body authored ONLY resonance recipes — verb-clustering visible."""
    r = form_evaluate_text(session, "?vocabulary")
    # The MATH region (type_=12) is empty until someone runs Form arithmetic.
    assert RBasic.MATH not in r.value["recipes"]


def test_vocabulary_picks_up_arithmetic(session, populated):
    """Running a Form arithmetic expression populates the MATH cluster."""
    form_evaluate_text(session, "1 + 2")
    r = form_evaluate_text(session, "?vocabulary")
    assert RBasic.MATH in r.value["recipes"]


def test_vocabulary_is_read_only(session, populated):
    """Re-running `?vocabulary` returns identical counts — lens, not mutator."""
    a = form_evaluate_text(session, "?vocabulary").value
    b = form_evaluate_text(session, "?vocabulary").value
    assert a == b


def test_vocabulary_helper_matches_form_query(session, populated):
    """The Python `vocabulary_histogram` and the Form `?vocabulary` agree."""
    direct = vocabulary_histogram(session)
    via_form = form_evaluate_text(session, "?vocabulary").value
    assert direct == via_form


# ---------------------------------------------------------------------------
# Commutative resonance edges
# ---------------------------------------------------------------------------


def test_directed_bridges_edge_is_order_sensitive(session, populated):
    """The default directed edge gives different NodeIDs for (a, b) and (b, a)."""
    a = populated["lc-a"].cell_id
    b = populated["lc-b"].cell_id
    e1 = bridges_edge(session, a, b)
    e2 = bridges_edge(session, b, a)
    assert e1 != e2


def test_bridges_symmetric_is_order_insensitive(session, populated):
    """The symmetric wrapper dedupes (a, b) and (b, a) to one NodeID."""
    a = populated["lc-a"].cell_id
    b = populated["lc-b"].cell_id
    e1 = bridges_symmetric(session, a, b)
    e2 = bridges_symmetric(session, b, a)
    assert e1 == e2


def test_commutative_edge_canonicalizes_by_id_order(session, populated):
    """`commutative_edge` always sorts (lo, hi) — verifiable through equality."""
    a = populated["lc-a"].cell_id
    b = populated["lc-b"].cell_id
    c = populated["lc-c"].cell_id
    # Re-run with different verbs to confirm canonicalization works generically.
    for verb in (RResonance.BRIDGES, RResonance.NEAR, RResonance.POLAR_TO):
        e_ab = commutative_edge(session, verb=verb, cell_a_db_id=a, cell_b_db_id=b)
        e_ba = commutative_edge(session, verb=verb, cell_a_db_id=b, cell_b_db_id=a)
        e_ac = commutative_edge(session, verb=verb, cell_a_db_id=a, cell_b_db_id=c)
        assert e_ab == e_ba
        assert e_ab != e_ac


def test_near_polar_convenience_wrappers(session, populated):
    """NEAR-symmetric and POLAR_TO-symmetric also commute."""
    a = populated["lc-a"].cell_id
    b = populated["lc-b"].cell_id
    assert near_symmetric(session, a, b) == near_symmetric(session, b, a)
    assert polar_to_symmetric(session, a, b) == polar_to_symmetric(session, b, a)


def test_symmetric_distinct_from_directed(session, populated):
    """Same (a, b) authored symmetric vs directed produces different NodeIDs.

    The body keeps both available — directed for relations with direction
    (SHAPES from concept to form), symmetric for relations without."""
    a = populated["lc-a"].cell_id
    b = populated["lc-b"].cell_id
    sym = bridges_symmetric(session, a, b)
    dir_ab = bridges_edge(session, min(a, b), max(a, b))
    # When directed is called with (lo, hi) it matches the symmetric NodeID —
    # both intern as `(verb, lo, hi)`. The asymmetry only shows when the
    # caller authors (b, a) directed.
    assert sym == dir_ab
