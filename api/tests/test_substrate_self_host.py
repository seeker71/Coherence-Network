"""Tests for partial self-hosting — Form's grammar expressed as Form rules.

The architectural proof: when the parser is told `prefer_registered=True`
and the bootstrap keywords have been re-registered as substrate-resident
templates, parsing produces Recipe NodeIDs IDENTICAL to the bootstrap.

This is NOT yet full self-hosting — `do`, `match`, `let`, `choose`, and
operators still rely on the bootstrap because their syntax requires
pattern-DSL extensions (IdentCapture, RepeatedCapture). What's
demonstrated: `if` (and the convenience keywords `unless`, `whenever`)
can be expressed entirely as substrate data and used by the parser.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    bootstrap_self_host,
    form_evaluate_text,
    form_parse,
    list_bootstrap_self_host_keywords,
    list_registered_keywords,
)
from app.services.substrate.form import IfExpr
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
    from app.services.substrate.form_rules import _BUILDERS, _KEYWORDS
    saved_kw = dict(_KEYWORDS)
    saved_b = dict(_BUILDERS)
    yield
    _KEYWORDS.clear()
    _KEYWORDS.update(saved_kw)
    _BUILDERS.clear()
    _BUILDERS.update(saved_b)


# ---------------------------------------------------------------------------
# bootstrap_self_host registers what we expect
# ---------------------------------------------------------------------------


def test_bootstrap_self_host_registers_keywords(session):
    """bootstrap_self_host registers if / unless / whenever as templates."""
    registered = bootstrap_self_host(session)
    assert "if" in registered
    assert "unless" in registered
    assert "whenever" in registered


def test_list_bootstrap_self_host_keywords_matches_registration(session):
    """The advertised list matches what bootstrap_self_host actually does."""
    advertised = set(list_bootstrap_self_host_keywords())
    registered = set(bootstrap_self_host(session))
    assert advertised == registered


# ---------------------------------------------------------------------------
# Default behavior: bootstrap takes priority
# ---------------------------------------------------------------------------


def test_default_uses_bootstrap_even_after_self_host(session):
    """Without prefer_registered, the bootstrap if-handler runs first.
    Registered if-template exists but is bypassed."""
    bootstrap_self_host(session)
    # No prefer_registered flag — uses bootstrap
    ast = form_parse("if x then y else z")
    assert isinstance(ast, IfExpr)


# ---------------------------------------------------------------------------
# The killer test: registered-if and bootstrap-if produce the same Recipe
# ---------------------------------------------------------------------------


def test_registered_if_produces_same_recipe_as_bootstrap(session):
    """Self-hosting proof: with prefer_registered=True, the registered
    template drives parsing for `if`. The resulting Recipe NodeID is
    identical to the bootstrap path's NodeID — same shape → same identity.
    """
    bootstrap_self_host(session)

    bootstrap_path = form_evaluate_text(session, "if x then y else z")
    self_host_path = form_evaluate_text(
        session, "if x then y else z", prefer_registered=True
    )

    assert bootstrap_path.kind == "recipe"
    assert self_host_path.kind == "recipe"
    # The architectural payoff — content-addressed dedup means both paths
    # land at the same NodeID because they produce the same shape.
    assert bootstrap_path.value == self_host_path.value


def test_registered_if_without_else_matches_bootstrap(session):
    """Same proof for the if-without-else shape (different category instance
    in the substrate vocabulary)."""
    bootstrap_self_host(session)

    bootstrap_path = form_evaluate_text(session, "if x then y")
    self_host_path = form_evaluate_text(
        session, "if x then y", prefer_registered=True
    )

    assert bootstrap_path.value == self_host_path.value


def test_unless_via_self_host_works_in_prefer_mode(session):
    """The `unless` keyword (not a bootstrap built-in) works in
    prefer_registered mode just like in default mode."""
    bootstrap_self_host(session)
    ast = form_parse("unless x then y", prefer_registered=True)
    assert isinstance(ast, IfExpr)


# ---------------------------------------------------------------------------
# Persistence: self-host registrations persist across "process restart"
# ---------------------------------------------------------------------------


def test_self_host_keywords_persist_in_substrate(session):
    """bootstrap_self_host writes substrate cells that survive in-memory
    registry clearing."""
    from app.services.substrate import (
        load_all_keywords_from_substrate,
        load_keyword_from_substrate,
    )
    from app.services.substrate.form_rules import _BUILDERS, _KEYWORDS

    bootstrap_self_host(session)

    # Drop both in-memory registries (simulate process restart)
    _KEYWORDS.clear()
    _BUILDERS.clear()

    # Reload everything from substrate — templates carry the builders
    loaded = load_all_keywords_from_substrate(session)
    assert "if" in loaded
    assert "unless" in loaded
    assert "whenever" in loaded

    # And the parser picks them up again in prefer-registered mode
    ast = form_parse("if x then y else z", prefer_registered=True)
    assert isinstance(ast, IfExpr)


# ---------------------------------------------------------------------------
# What's NOT self-hosted (honest acknowledgment via test)
# ---------------------------------------------------------------------------


def test_do_block_still_uses_bootstrap_in_prefer_mode(session):
    """`do { ... }` doesn't have a registered template — the parser falls
    back to the bootstrap handler even in prefer_registered mode.

    This is the honest gap: do-blocks need RepeatedCapture in the pattern
    DSL before they can be self-hosted. The fall-through proves the
    safety mechanism: prefer_registered is opt-in per-keyword via the
    presence of a matching rule, not a global on/off.
    """
    bootstrap_self_host(session)
    # `do` is NOT registered — parser falls through to bootstrap parse_do_block
    ast = form_evaluate_text(session, "do { let x = 5; x + 1 }", prefer_registered=True)
    assert ast.kind == "recipe"  # bootstrap handler produced a Recipe