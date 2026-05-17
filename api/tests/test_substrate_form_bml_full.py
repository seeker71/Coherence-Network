"""Close the remaining surface gaps named in form-language.md.

Six constructs ship in this breath, completing the form-layer walk of the
BML lineage:

- `delegate @X to @Y` — BML delegation inheritance
- `undo <recipe>` / `inverse(<recipe>)` — BML reverse semantics
- `common @X @Y` — BML Common Objects
- `method NAME on @X { body }` / `invoke NAME on @X` — BML method-on-object
- `?on_change <recipe> { body }` — reactive lens (subscription engine consumes)
- `?project @cell @coord_fn` — spatial-projection lens (renderer consumes)

Each interns as a Recipe NodeID in its own RBasic category. Runtime execution
semantics (dispatch via delegation, method invocation, reactive subscription,
spatial rendering) waits for the recipe-execution engine — one shared
dependency named separately rather than per-construct.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import BID_concept, form_evaluate_text, form_parse, make_cell
from app.services.substrate.category import (
    RBasic,
    RCommon,
    RDelegate,
    RMethod,
    RProjection,
    RReactive,
    RReverse,
)
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
    make_cell(s, name="lc-a", domain="concept", blueprint=BID_concept())
    make_cell(s, name="lc-b", domain="concept", blueprint=BID_concept())
    s.commit()
    try:
        yield s
        s.commit()
    finally:
        s.close()


# ---------------------------------------------------------------------------
# Delegation inheritance
# ---------------------------------------------------------------------------


def test_delegate_parses(session):
    from app.services.substrate.form import DelegateExpr
    assert isinstance(form_parse("delegate @concept(lc-a) to @concept(lc-b)"), DelegateExpr)


def test_delegate_interns_to_delegate_category(session):
    nid = form_evaluate_text(session, "delegate @concept(lc-a) to @concept(lc-b)").value
    assert nid.type_ == RBasic.DELEGATE


def test_delegate_distinct_pairs_distinct_nodeid(session):
    """Two distinct delegation pairs intern to different Recipe NodeIDs."""
    e1 = form_evaluate_text(session, "delegate @concept(lc-a) to @concept(lc-b)").value
    e2 = form_evaluate_text(session, "delegate @concept(lc-b) to @concept(lc-a)").value
    assert e1 != e2


# ---------------------------------------------------------------------------
# Reverse semantics — undo / inverse
# ---------------------------------------------------------------------------


def test_undo_parses_and_interns(session):
    nid = form_evaluate_text(session, "undo (1 + 2)").value
    assert nid.type_ == RBasic.REVERSE


def test_inverse_parses_and_interns(session):
    nid = form_evaluate_text(session, "inverse(1 + 2)").value
    assert nid.type_ == RBasic.REVERSE


def test_undo_and_inverse_have_distinct_instances(session):
    """Same child but different verb → different instance under REVERSE category."""
    undo_nid = form_evaluate_text(session, "undo (1 + 2)").value
    inv_nid = form_evaluate_text(session, "inverse(1 + 2)").value
    assert undo_nid != inv_nid


# ---------------------------------------------------------------------------
# Common Objects
# ---------------------------------------------------------------------------


def test_common_parses_and_interns(session):
    nid = form_evaluate_text(session, "common @concept(lc-a) @concept(lc-b)").value
    assert nid.type_ == RBasic.COMMON


def test_common_dedup(session):
    """Same (a, b) re-runs share NodeID through content-addressing."""
    a = form_evaluate_text(session, "common @concept(lc-a) @concept(lc-b)").value
    b = form_evaluate_text(session, "common @concept(lc-a) @concept(lc-b)").value
    assert a == b


# ---------------------------------------------------------------------------
# Method definitions + invocation
# ---------------------------------------------------------------------------


def test_method_def_parses_and_interns(session):
    nid = form_evaluate_text(session, "method greet on @concept(lc-a) { 1 + 2 }").value
    assert nid.type_ == RBasic.METHOD


def test_method_invoke_parses_and_interns(session):
    nid = form_evaluate_text(session, "invoke greet on @concept(lc-a)").value
    assert nid.type_ == RBasic.METHOD


def test_method_def_and_invoke_distinct(session):
    """define and invoke use different instances under METHOD category."""
    d = form_evaluate_text(session, "method greet on @concept(lc-a) { 1 + 2 }").value
    i = form_evaluate_text(session, "invoke greet on @concept(lc-a)").value
    assert d != i


def test_method_body_can_be_multi_statement(session):
    """`method NAME on X { stmt; stmt; expr }` accepts a multi-statement body."""
    nid = form_evaluate_text(session, "method greet on @concept(lc-a) { save; 1 + 2; restore }").value
    assert nid.type_ == RBasic.METHOD


# ---------------------------------------------------------------------------
# Reactive lens — ?on_change
# ---------------------------------------------------------------------------


def test_on_change_parses_and_interns(session):
    nid = form_evaluate_text(session, "?on_change @concept(lc-a) { 1 + 2 }").value
    assert nid.type_ == RBasic.REACTIVE


def test_on_change_distinct_bodies(session):
    """Different bodies produce different Recipe NodeIDs (content-addressed)."""
    a = form_evaluate_text(session, "?on_change @concept(lc-a) { 1 + 2 }").value
    b = form_evaluate_text(session, "?on_change @concept(lc-a) { 3 + 4 }").value
    assert a != b


# ---------------------------------------------------------------------------
# Spatial-projection lens — ?project
# ---------------------------------------------------------------------------


def test_project_parses_and_interns(session):
    nid = form_evaluate_text(session, "?project @concept(lc-a) @concept(lc-b)").value
    assert nid.type_ == RBasic.PROJECTION


def test_project_distinct_targets(session):
    """Different (cell, coord_fn) pairs intern to distinct NodeIDs."""
    a = form_evaluate_text(session, "?project @concept(lc-a) @concept(lc-b)").value
    b = form_evaluate_text(session, "?project @concept(lc-b) @concept(lc-a)").value
    assert a != b


# ---------------------------------------------------------------------------
# Cross-construct: vocabulary picks up the new categories
# ---------------------------------------------------------------------------


def test_vocabulary_reflects_all_new_categories(session):
    """After running each construct, `?vocabulary` shows the new categories."""
    form_evaluate_text(session, "delegate @concept(lc-a) to @concept(lc-b)")
    form_evaluate_text(session, "undo (1 + 2)")
    form_evaluate_text(session, "common @concept(lc-a) @concept(lc-b)")
    form_evaluate_text(session, "method greet on @concept(lc-a) { 1 + 2 }")
    form_evaluate_text(session, "?on_change @concept(lc-a) { 1 + 2 }")
    form_evaluate_text(session, "?project @concept(lc-a) @concept(lc-b)")
    v = form_evaluate_text(session, "?vocabulary").value
    for cat in (RBasic.DELEGATE, RBasic.REVERSE, RBasic.COMMON,
                RBasic.METHOD, RBasic.REACTIVE, RBasic.PROJECTION):
        assert cat in v["recipes"], f"category {cat!r} missing from vocabulary"
