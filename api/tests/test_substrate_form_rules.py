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
    from app.services.substrate.substrate_strings import SubstrateStringORM
    SubstrateStringORM.__table__.create(engine, checkfirst=True)
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


# ---------------------------------------------------------------------------
# Substrate-resident persistence — patterns survive in the body
# ---------------------------------------------------------------------------


def test_pattern_to_recipe_round_trip(session):
    """A pattern serializes to a Recipe NodeID and reconstructs identically."""
    from app.services.substrate import pattern_to_recipe, recipe_to_pattern

    original = Sequence([
        Literal("IDENT", "unless"),
        Capture("cond"),
        Literal("IDENT", "then"),
        Capture("body"),
    ])
    rid = pattern_to_recipe(session, original)
    rebuilt = recipe_to_pattern(session, rid)

    assert isinstance(rebuilt, Sequence)
    assert len(rebuilt.parts) == 4
    assert isinstance(rebuilt.parts[0], Literal)
    assert rebuilt.parts[0].kind == "IDENT"
    assert rebuilt.parts[0].value == "unless"
    assert isinstance(rebuilt.parts[1], Capture)
    assert rebuilt.parts[1].name == "cond"


def test_pattern_dedup_in_substrate(session):
    """Two structurally-identical patterns share a Recipe NodeID."""
    from app.services.substrate import pattern_to_recipe

    p1 = Sequence([Literal("IDENT", "x"), Capture("y")])
    p2 = Sequence([Literal("IDENT", "x"), Capture("y")])
    a = pattern_to_recipe(session, p1)
    b = pattern_to_recipe(session, p2)
    assert a == b


def test_pattern_distinct_for_different_shapes(session):
    """Different patterns get different Recipe NodeIDs."""
    from app.services.substrate import pattern_to_recipe

    a = pattern_to_recipe(session, Literal("IDENT", "foo"))
    b = pattern_to_recipe(session, Literal("IDENT", "bar"))
    assert a != b


def test_register_form_keyword_with_session_persists(session):
    """When called with session, register_form_keyword stores the pattern
    as a Cell in the grammar domain. lookup_form_rule recovers it."""
    from app.services.substrate import lookup_form_rule

    register_form_keyword(
        "unless",
        Sequence([
            Literal("IDENT", "unless"),
            Capture("cond"),
            Literal("IDENT", "then"),
            Capture("body"),
        ]),
        builder=lambda c: IfExpr(
            cond=UnaryOp("!", c["cond"]),
            then_branch=c["body"],
        ),
        session=session,
    )

    rule = lookup_form_rule(session, "unless")
    assert rule is not None
    assert not rule.pattern.is_undefined()
    assert not rule.action.is_undefined()


def test_load_keyword_from_substrate_after_register(session):
    """Persist a keyword, drop the in-memory registration, load it back
    from the substrate, parse correctly."""
    from app.services.substrate import (
        load_keyword_from_substrate,
        register_builder,
        unregister_form_keyword,
    )

    def my_builder(c):
        return IfExpr(
            cond=UnaryOp("!", c["cond"]),
            then_branch=c["body"],
        )

    register_form_keyword(
        "unless",
        Sequence([
            Literal("IDENT", "unless"),
            Capture("cond"),
            Literal("IDENT", "then"),
            Capture("body"),
        ]),
        builder=my_builder,
        session=session,
    )

    # Simulate process restart: clear the in-memory keyword registry but
    # keep the builder name registry (those would be re-registered at
    # process boot in real life).
    unregister_form_keyword("unless")
    register_builder("unless", my_builder)  # named-builder rebind

    # Now load from substrate
    loaded = load_keyword_from_substrate(session, "unless")
    assert loaded is not None
    pattern, builder = loaded
    assert isinstance(pattern, Sequence)
    assert callable(builder)

    # And the parser picks it up again
    ast = form_parse("unless x then y")
    assert isinstance(ast, IfExpr)
    assert isinstance(ast.cond, UnaryOp)


def test_load_all_keywords_from_substrate(session):
    """Bulk-load all persisted keywords."""
    from app.services.substrate import (
        load_all_keywords_from_substrate,
        register_builder,
        unregister_form_keyword,
    )

    def b1(c):
        return IfExpr(cond=UnaryOp("!", c["cond"]), then_branch=c["body"])

    def b2(c):
        return IfExpr(cond=c["cond"], then_branch=c["body"])

    register_form_keyword(
        "unless",
        Sequence([
            Literal("IDENT", "unless"), Capture("cond"),
            Literal("IDENT", "then"), Capture("body"),
        ]),
        builder=b1, session=session,
    )
    register_form_keyword(
        "whenever",
        Sequence([
            Literal("IDENT", "whenever"), Capture("cond"),
            Literal("IDENT", "do"), Capture("body"),
        ]),
        builder=b2, session=session,
    )

    # Clear in-memory keyword registry; rebind named builders only
    unregister_form_keyword("unless")
    unregister_form_keyword("whenever")
    register_builder("unless", b1)
    register_builder("whenever", b2)

    loaded = load_all_keywords_from_substrate(session)
    assert "unless" in loaded
    assert "whenever" in loaded


# ---------------------------------------------------------------------------
# IdentCapture + RepeatedCapture — pattern DSL extensions
# ---------------------------------------------------------------------------


def test_ident_capture_round_trip(session):
    """IdentCapture serializes and reconstructs."""
    from app.services.substrate import IdentCapture, pattern_to_recipe, recipe_to_pattern
    rid = pattern_to_recipe(session, IdentCapture("name"))
    rebuilt = recipe_to_pattern(session, rid)
    assert isinstance(rebuilt, IdentCapture)
    assert rebuilt.name == "name"


def test_repeated_capture_round_trip(session):
    """RepeatedCapture (with separator) serializes and reconstructs."""
    from app.services.substrate import (
        RepeatedCapture, pattern_to_recipe, recipe_to_pattern,
    )
    original = RepeatedCapture(
        "items",
        item_pattern=Capture("__item__"),
        separator=Literal("COMMA", None),
    )
    rid = pattern_to_recipe(session, original)
    rebuilt = recipe_to_pattern(session, rid)
    assert isinstance(rebuilt, RepeatedCapture)
    assert rebuilt.name == "items"
    assert isinstance(rebuilt.item_pattern, Capture)
    assert isinstance(rebuilt.separator, Literal)
    assert rebuilt.separator.kind == "COMMA"


def test_repeated_capture_no_separator_round_trip(session):
    """RepeatedCapture without separator round-trips correctly."""
    from app.services.substrate import (
        RepeatedCapture, pattern_to_recipe, recipe_to_pattern,
    )
    original = RepeatedCapture(
        "items", item_pattern=Capture("__item__"), separator=None,
    )
    rid = pattern_to_recipe(session, original)
    rebuilt = recipe_to_pattern(session, rid)
    assert isinstance(rebuilt, RepeatedCapture)
    assert rebuilt.separator is None


def test_pattern_dedup_with_new_primitives(session):
    """Two structurally-identical patterns using new primitives share NodeIDs."""
    from app.services.substrate import (
        IdentCapture, RepeatedCapture, pattern_to_recipe,
    )
    a = pattern_to_recipe(
        session,
        Sequence([
            Literal("IDENT", "let"), IdentCapture("name"),
            Literal("ASSIGN", None), Capture("value"),
        ]),
    )
    b = pattern_to_recipe(
        session,
        Sequence([
            Literal("IDENT", "let"), IdentCapture("name"),
            Literal("ASSIGN", None), Capture("value"),
        ]),
    )
    assert a == b
