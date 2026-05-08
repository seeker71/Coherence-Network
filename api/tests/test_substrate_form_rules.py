"""Tests for runtime-registered Form keywords.

Step 3 of the bootstrap-to-self-hosting path: the parser actually
consumes user-registered rules. A new keyword can be added at runtime
without editing form.py.

The proof: `unless x then y` is NOT in the bootstrap grammar. After
register_form_keyword("unless", ...), it parses correctly. After
unregister, it fails again. The grammar is alive.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    Capture,
    Literal,
    NodeID,
    Opt,
    Sequence,
    form_evaluate_text,
    form_parse,
    list_registered_keywords,
    lookup_form_keyword,
    register_form_keyword,
    unregister_form_keyword,
)
from app.services.substrate.form import IfExpr, UnaryOp
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
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


@pytest.fixture(autouse=True)
def clean_keyword_registry():
    """Each test starts with a clean keyword registry."""
    # Capture state
    from app.services.substrate.form_rules import _KEYWORDS
    saved = dict(_KEYWORDS)
    yield
    # Restore
    _KEYWORDS.clear()
    _KEYWORDS.update(saved)


# ---------------------------------------------------------------------------
# Unknown keyword behavior — a real Identifier or auto-declare
# ---------------------------------------------------------------------------


def test_unknown_keyword_becomes_identifier():
    """Without a rule, an unknown keyword parses as a bare Identifier."""
    ast = form_parse("unless")
    from app.services.substrate.form import Identifier
    assert isinstance(ast, Identifier)
    assert ast.name == "unless"


# ---------------------------------------------------------------------------
# Register-and-parse — the core demonstration
# ---------------------------------------------------------------------------


def _register_unless():
    """Register the `unless` keyword that desugars to `if !cond then body [else other]`."""
    register_form_keyword(
        "unless",
        Sequence([
            Literal("IDENT", "unless"),
            Capture("cond"),
            Literal("IDENT", "then"),
            Capture("body"),
            Opt(Sequence([
                Literal("IDENT", "else"),
                Capture("other"),
            ])),
        ]),
        builder=lambda c: IfExpr(
            cond=UnaryOp("!", c["cond"]),
            then_branch=c["body"],
            else_branch=c.get("other"),
        ),
    )


def test_register_form_keyword_parses_unless():
    """After registering, `unless x then y` parses to an IfExpr with negated condition."""
    _register_unless()
    ast = form_parse("unless x then y")
    assert isinstance(ast, IfExpr)
    assert isinstance(ast.cond, UnaryOp)
    assert ast.cond.op == "!"
    assert ast.else_branch is None


def test_register_form_keyword_parses_unless_with_else():
    """`unless x then y else z` carries the else branch through."""
    _register_unless()
    ast = form_parse("unless x then y else z")
    assert isinstance(ast, IfExpr)
    assert isinstance(ast.cond, UnaryOp)
    assert ast.else_branch is not None


def test_unless_evaluates_to_recipe(session):
    """Going all the way through evaluation: unless produces a Recipe NodeID
    structurally equivalent to its desugared form."""
    _register_unless()
    a = form_evaluate_text(session, "unless x then y else z")
    b = form_evaluate_text(session, "if !x then y else z")
    assert a.kind == "recipe"
    assert b.kind == "recipe"
    # Same shape → same Recipe NodeID. The grammar is alive.
    assert a.value == b.value


def test_unregister_form_keyword_removes_capability():
    """After unregister, the keyword falls back to bare Identifier behavior."""
    _register_unless()
    ast = form_parse("unless x then y")
    assert isinstance(ast, IfExpr)

    unregister_form_keyword("unless")

    ast2 = form_parse("unless")
    from app.services.substrate.form import Identifier
    assert isinstance(ast2, Identifier)


def test_list_registered_keywords():
    """Enumerate all keywords currently registered."""
    _register_unless()
    keywords = list_registered_keywords()
    assert "unless" in keywords


def test_lookup_form_keyword_returns_pattern_and_builder():
    """Lookup returns the (pattern, builder) tuple."""
    _register_unless()
    entry = lookup_form_keyword("unless")
    assert entry is not None
    pattern, builder = entry
    assert isinstance(pattern, Sequence)
    assert callable(builder)


# ---------------------------------------------------------------------------
# Multiple keywords — proving the registry scales
# ---------------------------------------------------------------------------


def test_multiple_keywords_coexist(session):
    """Register `unless` AND `whenever`; both parse correctly."""
    _register_unless()

    # `whenever cond do body` desugars to `if cond then body`
    register_form_keyword(
        "whenever",
        Sequence([
            Literal("IDENT", "whenever"),
            Capture("cond"),
            Literal("IDENT", "do"),
            Capture("body"),
        ]),
        builder=lambda c: IfExpr(cond=c["cond"], then_branch=c["body"]),
    )

    a = form_parse("unless x then y")
    b = form_parse("whenever x do y")

    assert isinstance(a, IfExpr)
    assert isinstance(a.cond, UnaryOp)  # unless → negated
    assert isinstance(b, IfExpr)
    # `whenever` doesn't negate
    from app.services.substrate.form import Identifier
    assert isinstance(b.cond, Identifier)
