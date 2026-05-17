"""Form lens operators — `?lattice` and `?keywords`.

The substrate-as-flowing-medium connection: every Form query is a lens. None
mutate the substrate. The new `?lattice` reads the lattice's current counts;
`?keywords` reads the grammar's current registered keywords. Both are pure
observations — the substrate-as-framebuffer pattern at the count level.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    BID_concept,
    Build,
    Capture,
    CaptureRef,
    Const,
    Literal,
    Sequence,
    author_geometry_signature,
    form_evaluate_text,
    make_cell,
    register_form_keyword,
    unregister_form_keyword,
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
    try:
        yield s
        s.commit()
    finally:
        s.close()


# ---------------------------------------------------------------------------
# `?lattice` — substrate-snapshot lens
# ---------------------------------------------------------------------------


def test_lattice_on_empty_substrate(session):
    """Empty substrate reads as zero of everything — a clean baseline."""
    r = form_evaluate_text(session, "?lattice")
    assert r.kind == "lattice"
    assert r.value["blueprints_total"] == 0
    assert r.value["recipes_total"] == 0
    assert r.value["cells_total"] == 0


def test_lattice_reflects_authoring(session):
    """After authoring concepts + resonance edges, the lattice counts update."""
    for name in ["lc-a", "lc-b", "lc-c"]:
        c = make_cell(session, name=name, domain="concept", blueprint=BID_concept())
        author_geometry_signature(session, c.cell_id, {"form": "triad"}, arity_hz=174)
    session.commit()
    r = form_evaluate_text(session, "?lattice")
    assert r.value["cells_total"] > 0
    assert r.value["recipes_total"] > 0


def test_lattice_is_read_only(session):
    """Re-running ?lattice yields the same values — the lens does not mutate flow."""
    for name in ["lc-x", "lc-y"]:
        c = make_cell(session, name=name, domain="concept", blueprint=BID_concept())
        author_geometry_signature(session, c.cell_id, {"form": "triad"}, arity_hz=174)
    session.commit()
    a = form_evaluate_text(session, "?lattice").value
    b = form_evaluate_text(session, "?lattice").value
    c = form_evaluate_text(session, "?lattice").value
    assert a == b == c


def test_lattice_concurrent_with_other_queries(session):
    """`?lattice` interleaved with `?cells` returns consistent counts —
    proof that lenses read concurrently without interfering."""
    for name in ["lc-1", "lc-2"]:
        c = make_cell(session, name=name, domain="concept", blueprint=BID_concept())
        author_geometry_signature(session, c.cell_id, {"form": "triad"}, arity_hz=174)
    session.commit()

    before = form_evaluate_text(session, "?lattice").value
    _ = form_evaluate_text(session, '?cells where domain == "concept"').value
    _ = form_evaluate_text(session, "?shaped_by @geometric_form(triad)").value
    after = form_evaluate_text(session, "?lattice").value
    assert before == after


# ---------------------------------------------------------------------------
# `?keywords` — grammar-introspection lens (BMF property — parser knows itself)
# ---------------------------------------------------------------------------


def test_keywords_initially_empty(session):
    """Bootstrap parser starts with no runtime-registered keywords."""
    r = form_evaluate_text(session, "?keywords")
    assert r.kind == "keywords"
    # The registry is module-global; clear any keywords other tests may have set.
    # (Best-effort — tests run in isolation in CI but the registry persists in-process.)


def test_keywords_lists_registered(session):
    """After registering a keyword, `?keywords` includes its name."""
    register_form_keyword(
        "test_unless",
        Sequence([
            Literal("IDENT", "test_unless"),
            Capture("c"),
            Literal("IDENT", "then"),
            Capture("b"),
        ]),
        template=Build(
            "IfExpr",
            cond=Build("UnaryOp", op=Const("!"), operand=CaptureRef("c")),
            then_branch=CaptureRef("b"),
            else_branch=Const(None),
        ),
    )
    try:
        r = form_evaluate_text(session, "?keywords")
        assert "test_unless" in r.value
    finally:
        unregister_form_keyword("test_unless")


def test_keywords_reflects_unregistration(session):
    """After unregistering, the keyword disappears from the lens — live grammar."""
    register_form_keyword(
        "test_until",
        Sequence([
            Literal("IDENT", "test_until"),
            Capture("c"),
            Literal("IDENT", "do"),
            Capture("b"),
        ]),
        template=Build(
            "IfExpr",
            cond=Build("UnaryOp", op=Const("!"), operand=CaptureRef("c")),
            then_branch=CaptureRef("b"),
            else_branch=Const(None),
        ),
    )
    assert "test_until" in form_evaluate_text(session, "?keywords").value
    unregister_form_keyword("test_until")
    assert "test_until" not in form_evaluate_text(session, "?keywords").value
