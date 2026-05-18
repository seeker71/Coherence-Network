"""Tests for the three runtime-extensible registries Form now consults:

  form_lexer    — token-pattern registry  (the bottom of the parse stack)
  form_atoms    — primary-atom registry   (the leaves of the expression grammar)
  form_queries  — query-handler registry  (?<verb> dispatch)

Together with the keyword registry (form_rules), the operator registry
(form_eval), and the grammar-rule registry (form_rules + grammar.py),
these close the form-language.md gap:

  "The lexer.  tokenize() in form.py is still hand-written regex code."
  "Primary-atom parsing.  Literals, identifiers, @<nodeid>, ~<name>,
    @<domain>(<name>), parenthesized expressions, projections.  These
    are the leaves the structured keywords compose over."
  "Query operators.  ?cells, ?equivalent, ?shaped_by, ?harmonic_at,
    ?lattice, ?keywords, ?vocabulary are still hardcoded in
    _evaluate_query."

After this commit, every one of those surfaces is registry-driven:
adding/replacing a token kind, atom shape, or query verb is a runtime
registration call. form.py keeps the parser flow itself (recursive
descent, precedence climbing) — every leaf is reachable from outside.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import form_evaluate_text
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


# ---------------------------------------------------------------------------
# Token-pattern registry (form_lexer)
# ---------------------------------------------------------------------------


def test_lexer_registry_lists_seed_patterns():
    from app.services.substrate.form_lexer import list_token_patterns

    kinds = [k for k, _ in list_token_patterns()]
    # Spot-check the seed set — must include the core operators + delimiters
    for expected in ("WS", "COMMENT", "EQ", "NEQ", "AND", "OR", "AT", "INT", "IDENT"):
        assert expected in kinds, f"seed set missing {expected}"


def test_lexer_register_then_use():
    """Register a new token kind, verify the master regex picks it up."""
    from app.services.substrate.form_lexer import (
        get_token_regex,
        register_token_pattern,
        unregister_token_pattern,
    )

    try:
        # Register $ as a new token kind, before PLUS so the alternation
        # tries it first (which doesn't matter for non-overlapping patterns
        # but proves the position-control API works).
        register_token_pattern("DOLLAR", r"\$", before="PLUS")
        regex = get_token_regex()
        m = regex.match("$")
        assert m is not None and m.lastgroup == "DOLLAR"
    finally:
        unregister_token_pattern("DOLLAR")


def test_lexer_unregister_invalidates_cache():
    from app.services.substrate.form_lexer import (
        get_token_regex,
        register_token_pattern,
        unregister_token_pattern,
    )

    try:
        register_token_pattern("HASH_OP", r"##")
        assert get_token_regex().match("##") is not None
        unregister_token_pattern("HASH_OP")
        # After unregister, the cache should rebuild without the pattern
        m = get_token_regex().match("##")
        # `#` matches COMMENT; `##` should now be COMMENT, not HASH_OP
        assert m.lastgroup == "COMMENT"
    finally:
        unregister_token_pattern("HASH_OP")


# ---------------------------------------------------------------------------
# Primary-atom registry (form_atoms)
# ---------------------------------------------------------------------------


def test_atom_registry_lists_seed():
    from app.services.substrate.form_atoms import list_atoms

    kinds = list_atoms()
    for expected in ("AT", "TILDE", "INT", "STRING", "LPAREN", "LBRACK", "LBRACE", "IDENT", "DOT", "QMARK"):
        assert expected in kinds


def test_atom_register_override_int():
    """Replace the INT atom handler at runtime; verify the parser uses it."""
    from app.services.substrate.form import IntLit
    from app.services.substrate.form_atoms import (
        lookup_atom,
        register_atom,
    )

    original = lookup_atom("INT")
    sentinel_called = []

    def custom_int_handler(parser):
        sentinel_called.append(True)
        tok = parser.consume("INT")
        # Return double the value — proves the override is invoked
        return IntLit(int(tok.value) * 2)

    try:
        register_atom("INT", custom_int_handler)
        from app.services.substrate.form import parse
        ast = parse("5")
        assert sentinel_called == [True]
        assert isinstance(ast, IntLit)
        assert ast.value == 10
    finally:
        register_atom("INT", original)


def test_atom_unknown_token_raises():
    """Parser raises a clear SyntaxError when no atom handler is registered."""
    from app.services.substrate.form_atoms import dispatch_atom

    # Build a fake parser with a token kind that nothing knows about
    class FakeTok:
        kind = "MYSTERY"
        value = "?"
        pos = 0

    class FakeParser:
        def peek(self):
            return FakeTok()

    with pytest.raises(SyntaxError, match="MYSTERY"):
        dispatch_atom(FakeParser(), "MYSTERY")


# ---------------------------------------------------------------------------
# Query-handler registry (form_queries)
# ---------------------------------------------------------------------------


def test_query_registry_lists_seed():
    from app.services.substrate.form_queries import list_form_queries

    verbs = list_form_queries()
    for expected in (
        "equivalent", "compatible", "lattice", "keywords", "vocabulary",
        "queries", "on_change", "project", "shaped_by", "harmonic_at", "cells",
    ):
        assert expected in verbs


def test_query_lattice_via_registry(session):
    """`?lattice` flows through the registry and returns the snapshot."""
    result = form_evaluate_text(session, "?lattice")
    assert result.kind == "lattice"
    assert "blueprints_total" in result.value


def test_query_keywords_via_registry(session):
    result = form_evaluate_text(session, "?keywords")
    assert result.kind == "keywords"
    assert isinstance(result.value, list)


def test_queries_lens_lists_query_verbs(session):
    """`?queries` returns the names of every registered ?-verb — the
    query-vocabulary lens added to close the introspection loop."""
    result = form_evaluate_text(session, "?queries")
    assert result.kind == "keywords"  # same shape as ?keywords
    verbs = result.value
    assert "lattice" in verbs
    assert "cells" in verbs
    assert "queries" in verbs  # self-reflective


def test_query_register_custom_verb(session):
    """Register a custom ?-verb at runtime, evaluate it, observe the result."""
    from app.services.substrate.form import FormResult
    from app.services.substrate.form_queries import (
        register_form_query,
        unregister_form_query,
    )

    sentinel = []

    def custom_handler(sess, q):
        sentinel.append(("called", q.kind))
        return FormResult("keywords", ["custom_a", "custom_b"])

    try:
        register_form_query("mycustom", custom_handler)
        result = form_evaluate_text(session, "?mycustom")
        assert sentinel == [("called", "mycustom")]
        assert result.value == ["custom_a", "custom_b"]
    finally:
        unregister_form_query("mycustom")


def test_query_unknown_verb_raises(session):
    """An unregistered verb raises NameError — the body refuses to silently
    fake an unknown query."""
    with pytest.raises(NameError, match="unknown query kind"):
        form_evaluate_text(session, "?totally_unknown_verb")


# ---------------------------------------------------------------------------
# End-to-end — registries cooperate
# ---------------------------------------------------------------------------


def test_end_to_end_via_all_three_registries(session):
    """Parse-and-evaluate a real Form expression that flows through all three
    registries: the lexer tokenizes via the pattern registry, the parser
    dispatches atoms via the atom registry, the evaluator dispatches the
    query via the query registry. None of the dispatched-to functions live
    inside form.py anymore."""
    result = form_evaluate_text(session, "?vocabulary")
    assert result.kind == "vocabulary"
    assert "recipes" in result.value
    assert "blueprints" in result.value
