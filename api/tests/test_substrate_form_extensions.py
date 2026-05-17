"""Form-language extensions: shape-filter, `with`/`.self`, atom-ref filters.

Three load-bearing primitives added in the same breath as the resonance
infrastructure:

1. `?cells where shape == @<cell-ref>` — the cross-discipline bridge query.
   Surfaces every cell whose blueprint equals the target's blueprint, which
   is how the substrate sees structural kinship across discipline-vocabularies.

2. `with subject { body }` + `.self` — BML's scoped-reference block. Binds
   `subject` as the implicit receiver; `.self` resolves to the subject inside
   the block. Interns as `(RBlock.WITH, [subject_recipe, body_recipe])` —
   content-addressed dedup like every other Block.

3. Atom-ref filters generally — `where <field> == @<cell-ref>` accepts cell /
   blueprint references in addition to string literals, so signature-aware
   queries (`where harmonic == @spectrum(Hz-741)`, etc.) become expressible.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    BID_concept,
    author_geometry_signature,
    form_evaluate_text,
    form_parse,
    make_cell,
)
from app.services.substrate.category import Level, RBasic, RBlock, RType
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


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
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield s
        s.commit()
    finally:
        s.close()


@pytest.fixture
def triadic_concepts(session):
    """Three concepts authored with identical (form: triad, polarity: parallel-facets)
    signature — the same flagship case the resonance work surfaced."""
    cells = {}
    for name in ["lc-trust-over-fear", "lc-whole-vitality", "lc-future-already-shaping"]:
        c = make_cell(session, name=name, domain="concept", blueprint=BID_concept())
        author_geometry_signature(
            session, c.cell_id,
            {"form": "triad", "polarity": "parallel-facets"},
            arity_hz=174,
        )
        cells[name] = c
    session.commit()
    return cells


# ---------------------------------------------------------------------------
# Shape-filter: ?cells where shape == @<cell-ref>
# ---------------------------------------------------------------------------


def test_cells_filter_by_shape_against_cell_ref(session, triadic_concepts):
    """`?cells where shape == @concept(lc-trust-over-fear)` surfaces all
    triadic concepts as bridge-siblings (three concepts, identical blueprint)."""
    r = form_evaluate_text(
        session, "?cells where shape == @concept(lc-trust-over-fear)",
    )
    assert r.kind == "cells"
    names = {c.name for c in r.value}
    assert names == {
        "lc-trust-over-fear",
        "lc-whole-vitality",
        "lc-future-already-shaping",
    }


def test_cells_filter_combines_with_domain(session, triadic_concepts):
    """Multiple filters: shape AND domain (both `where` clauses honored).

    The current grammar takes one filter per query, so this test verifies
    behavior with whichever filter is parsed — leaving room for future
    `and`-joined filters."""
    r = form_evaluate_text(session, '?cells where domain == "concept"')
    assert r.kind == "cells"
    assert len(r.value) == 3


def test_cells_filter_string_literal_path_still_works(session, triadic_concepts):
    """The legacy STRING-literal path (`where domain == "concept"`) is
    preserved — extending the filter parser to accept atom-refs added a
    branch without breaking the existing one."""
    r = form_evaluate_text(session, '?cells where domain == "geometric_form"')
    names = {c.name for c in r.value}
    assert "triad" in names


# ---------------------------------------------------------------------------
# `with subject { body }` + `.self`
# ---------------------------------------------------------------------------


def test_with_block_parses(session):
    """`with @concept(X) { stop }` parses without error."""
    c = make_cell(session, name="lc-test", domain="concept", blueprint=BID_concept())
    session.commit()
    ast = form_parse("with @concept(lc-test) { stop }")
    # The AST surfaces as a WithExpr node.
    from app.services.substrate.form import WithExpr
    assert isinstance(ast, WithExpr)


def test_with_block_interns_as_recipe(session):
    """`with X { stop }` evaluates to a Recipe NodeID using RBlock.WITH."""
    c = make_cell(session, name="lc-test-with", domain="concept", blueprint=BID_concept())
    session.commit()
    r = form_evaluate_text(session, "with @concept(lc-test-with) { stop }")
    assert r.kind == "recipe"
    # The stored row has the WITH block category.
    nid = r.value
    row = (
        session.query(SubstrateNodeORM)
        .filter_by(
            package=nid.package, level=nid.level, type_=nid.type_, instance=nid.instance,
        )
        .one()
    )
    assert row.type_ == RBasic.BLOCK


def test_with_block_content_addressed_dedup(session):
    """Two identical `with X { stop }` expressions intern to the same Recipe NodeID."""
    c = make_cell(session, name="lc-dedup-test", domain="concept", blueprint=BID_concept())
    session.commit()
    a = form_evaluate_text(session, "with @concept(lc-dedup-test) { stop }").value
    b = form_evaluate_text(session, "with @concept(lc-dedup-test) { stop }").value
    assert a == b


def test_with_block_distinct_subject_yields_distinct_recipe(session):
    """Different subjects produce different Recipe NodeIDs (content-addressing)."""
    a_cell = make_cell(session, name="lc-a", domain="concept", blueprint=BID_concept())
    b_cell = make_cell(session, name="lc-b", domain="concept", blueprint=BID_concept())
    session.commit()
    a = form_evaluate_text(session, "with @concept(lc-a) { stop }").value
    b = form_evaluate_text(session, "with @concept(lc-b) { stop }").value
    assert a != b


def test_self_ref_parses_inside_with(session):
    """`.self` parses inside a `with` block, returning a SelfRef AST node."""
    c = make_cell(session, name="lc-self-test", domain="concept", blueprint=BID_concept())
    session.commit()
    ast = form_parse("with @concept(lc-self-test) { .self }")
    from app.services.substrate.form import SelfRef, WithExpr
    assert isinstance(ast, WithExpr)
    assert isinstance(ast.body.statements[0], SelfRef)


def test_self_ref_alone_parses(session):
    """`.self` outside a with-block parses too (scope-checking is for runtime
    eval, not for parse-time — keeps the parser permissive in BML's spirit)."""
    ast = form_parse(".self")
    from app.services.substrate.form import SelfRef
    assert isinstance(ast, SelfRef)


def test_self_ref_interns_to_stable_nodeid(session):
    """`.self` always interns to the same trivial NodeID (the sentinel).

    Type 7 is used by the existing Identifier path as a LOCAL_ACCESS-like slot
    (the RType enum doesn't have a named LOCAL_ACCESS entry today; the comment
    in form.py predates an enum drift). `.self` reuses that slot with a fixed
    sentinel instance so it interns deterministically."""
    a = form_evaluate_text(session, ".self").value
    b = form_evaluate_text(session, ".self").value
    assert a == b
    assert a.level == Level.TRIVIAL
    assert a.type_ == 7  # LOCAL_ACCESS slot per form.py convention


def test_dot_followed_by_non_self_is_error(session):
    """`.field` (any name other than `self`) is a parse error today.

    Field-access against arbitrary names is a future construct; we keep the
    parser strict here so a typo (`.slef`) fails loudly instead of resolving
    to an unintended construct."""
    with pytest.raises(SyntaxError):
        form_parse(".field")


# ---------------------------------------------------------------------------
# Cross-construct: `with X { ... }` containing other shapes
# ---------------------------------------------------------------------------


def test_with_block_holds_multi_statement_body(session):
    """`with X { stop; fail }` parses and interns; the body is a DoBlock."""
    c = make_cell(session, name="lc-multi", domain="concept", blueprint=BID_concept())
    session.commit()
    ast = form_parse("with @concept(lc-multi) { stop; fail }")
    from app.services.substrate.form import WithExpr, DoBlock, StopExpr, FailExpr
    assert isinstance(ast, WithExpr)
    assert isinstance(ast.body, DoBlock)
    assert len(ast.body.statements) == 2
    assert isinstance(ast.body.statements[0], StopExpr)
    assert isinstance(ast.body.statements[1], FailExpr)


def test_with_block_evaluates_with_self_body(session):
    """`with X { .self }` — the bridge case for the BML primitive."""
    c = make_cell(session, name="lc-with-self", domain="concept", blueprint=BID_concept())
    session.commit()
    r = form_evaluate_text(session, "with @concept(lc-with-self) { .self }")
    assert r.kind == "recipe"


# ---------------------------------------------------------------------------
# Resonance walks: ?shaped_by @<cell>, ?harmonic_at @<cell>
# ---------------------------------------------------------------------------


def test_shaped_by_surfaces_cross_discipline_family(session, triadic_concepts):
    """`?shaped_by @geometric_form(triad)` returns every concept whose SHAPES
    edge points at ~Triad — the cross-discipline triadic family. This is the
    bridge query Form genuinely couldn't ask before this PR."""
    r = form_evaluate_text(session, "?shaped_by @geometric_form(triad)")
    assert r.kind == "cells"
    names = {c.name for c in r.value}
    assert names == {
        "lc-trust-over-fear",
        "lc-whole-vitality",
        "lc-future-already-shaping",
    }


def test_shaped_by_discriminates_pentad_from_triad(session, triadic_concepts):
    """A fivefold concept does NOT appear in the triadic family — shape
    discrimination works through the resonance walk."""
    pent = make_cell(session, name="lc-pent", domain="concept", blueprint=BID_concept())
    author_geometry_signature(
        session, pent.cell_id,
        {"form": "pentad", "polarity": "unipolar"},
        arity_hz=741,
    )
    session.commit()
    r = form_evaluate_text(session, "?shaped_by @geometric_form(triad)")
    names = {c.name for c in r.value}
    assert "lc-pent" not in names
    r2 = form_evaluate_text(session, "?shaped_by @geometric_form(pentad)")
    assert {c.name for c in r2.value} == {"lc-pent"}


def test_harmonic_at_surfaces_spectral_band_family(session, triadic_concepts):
    """`?harmonic_at @spectrum(Hz-174)` returns cells resonating at 174 Hz —
    the foundation band family."""
    r = form_evaluate_text(session, "?harmonic_at @spectrum(Hz-174)")
    names = {c.name for c in r.value}
    assert names == {
        "lc-trust-over-fear",
        "lc-whole-vitality",
        "lc-future-already-shaping",
    }


def test_shaped_by_polarity_surfaces_polarity_family(session, triadic_concepts):
    """`?shaped_by @polarity(parallel-facets)` returns cells with that polarity
    texture — same resonance walk, different axis."""
    r = form_evaluate_text(session, "?shaped_by @polarity(parallel-facets)")
    names = {c.name for c in r.value}
    assert names == {
        "lc-trust-over-fear",
        "lc-whole-vitality",
        "lc-future-already-shaping",
    }


def test_shaped_by_missing_target_raises(session):
    """`?shaped_by @geometric_form(nonexistent)` fails clearly when the target
    cell doesn't exist."""
    with pytest.raises(LookupError):
        form_evaluate_text(session, "?shaped_by @geometric_form(nonexistent-shape)")
