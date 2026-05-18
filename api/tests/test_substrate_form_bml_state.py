"""BML state-stack + exception-flow primitives in Form.

Closes two of the BML gaps named in form-language.md:
- `save` / `restore` / `discard` — BML state-stack (RBasic.STATE = 22)
- `raise` / `resume` — BML exception-flow (RBasic.EXCEPTION = 23)

Same structural-first pattern as `choose` / `fail` / `stop` — interns as
Recipe NodeIDs today, runtime execution semantics lands with the recipe-
execution engine. The form carries; the engine catches up later.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import form_evaluate_text, form_parse
from app.services.substrate.category import RBasic, RException, RState
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


# ---------------------------------------------------------------------------
# Each primitive parses to its own AST node type
# ---------------------------------------------------------------------------


def test_save_parses_as_save_expr():
    from app.services.substrate.form import SaveExpr
    assert isinstance(form_parse("save"), SaveExpr)


def test_restore_parses_as_restore_expr():
    from app.services.substrate.form import RestoreExpr
    assert isinstance(form_parse("restore"), RestoreExpr)


def test_discard_parses_as_discard_expr():
    from app.services.substrate.form import DiscardExpr
    assert isinstance(form_parse("discard"), DiscardExpr)


def test_raise_parses_as_raise_expr():
    from app.services.substrate.form import RaiseExpr
    assert isinstance(form_parse("raise"), RaiseExpr)


def test_resume_parses_as_resume_expr():
    from app.services.substrate.form import ResumeExpr
    assert isinstance(form_parse("resume"), ResumeExpr)


# ---------------------------------------------------------------------------
# Each primitive interns to a stable Recipe NodeID in its category
# ---------------------------------------------------------------------------


def test_save_interns_as_state_save(session):
    nid = form_evaluate_text(session, "save").value
    assert nid.type_ == RBasic.STATE
    assert nid.instance == RState.SAVE


def test_restore_interns_as_state_restore(session):
    nid = form_evaluate_text(session, "restore").value
    assert nid.type_ == RBasic.STATE
    assert nid.instance == RState.RESTORE


def test_discard_interns_as_state_discard(session):
    nid = form_evaluate_text(session, "discard").value
    assert nid.type_ == RBasic.STATE
    assert nid.instance == RState.DISCARD


def test_raise_interns_as_exception_raise(session):
    nid = form_evaluate_text(session, "raise").value
    assert nid.type_ == RBasic.EXCEPTION
    assert nid.instance == RException.RAISE


def test_resume_interns_as_exception_resume(session):
    nid = form_evaluate_text(session, "resume").value
    assert nid.type_ == RBasic.EXCEPTION
    assert nid.instance == RException.RESUME


def test_each_primitive_distinct_nodeid(session):
    """All five primitives have distinct Recipe NodeIDs."""
    ids = {
        form_evaluate_text(session, p).value
        for p in ("save", "restore", "discard", "raise", "resume")
    }
    assert len(ids) == 5


def test_repeated_calls_dedupe(session):
    """Re-running the same primitive returns the same NodeID (content-addressed)."""
    for kw in ("save", "restore", "discard", "raise", "resume"):
        a = form_evaluate_text(session, kw).value
        b = form_evaluate_text(session, kw).value
        assert a == b


# ---------------------------------------------------------------------------
# Composition with existing constructs
# ---------------------------------------------------------------------------


def test_state_primitives_compose_inside_do_block(session):
    """`do { save; 1 + 2; restore }` parses, interns, dedupes."""
    a = form_evaluate_text(session, "do { save; 1 + 2; restore }").value
    b = form_evaluate_text(session, "do { save; 1 + 2; restore }").value
    assert a == b


def test_state_primitives_compose_inside_choose(session):
    """`choose [save, raise]` parses and interns as a choose-recipe."""
    nid = form_evaluate_text(session, "choose [save, raise]").value
    # The choose recipe lives in the CHOICE category.
    assert nid.type_ == RBasic.CHOICE


def test_state_inside_with_block(session):
    """`with @1.2.4.1 { save; discard }` — BML's `with` carrying state ops."""
    nid = form_evaluate_text(session, "with @1.2.4.1 { save; discard }").value
    assert nid.type_ == RBasic.BLOCK  # WITH is RBlock.WITH


def test_leaf_primitives_do_not_persist_to_substrate(session):
    """Real implementation surprise: leaf primitives (save, raise) return bare
    category NodeIDs without persisting to substrate_nodes — same as fail/stop.

    The kernel's `intern_node` skips re-interning trivial leaves with no
    children (the NodeID is already canonical). So `?vocabulary` correctly
    shows nothing for `save` alone — it's typed but not stored.

    For these primitives to appear in `?vocabulary`, they need to be embedded
    in a composite recipe (a `do {save; ...}` block, a `choose [save, raise]`,
    or a `with X {save; restore}`); the composite's stored row then carries
    the leaves as children in its serialized form. This is honest about how
    the substrate represents leaves — naming the architectural commitment
    rather than working around it.
    """
    form_evaluate_text(session, "save")
    form_evaluate_text(session, "raise")
    v = form_evaluate_text(session, "?vocabulary").value
    # The leaves don't add rows — vocabulary stays empty until composites land.
    assert RBasic.STATE not in v["recipes"]
    assert RBasic.EXCEPTION not in v["recipes"]
    # But once a composite uses them, the COMPOSITE persists.
    form_evaluate_text(session, "do { save; restore }")
    v2 = form_evaluate_text(session, "?vocabulary").value
    assert RBasic.BLOCK in v2["recipes"]  # the do-block row
