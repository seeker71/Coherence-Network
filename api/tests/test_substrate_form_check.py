"""Static resolution + blueprint-type checking — the third walk over a Form AST.

`form_check` resolves names (bare names, function calls + arity, `set` targets),
blueprints (`~Trivial`, `@domain`, `@domain(name)` cells), and operators, then
infers a conservative blueprint for each expression — collecting EVERY problem in
one pass instead of raising on the first. That is the unlock for refactoring with
confidence: rename a cell or a function and the checker names every break at once.

The load-bearing test is `test_clean_program_is_silent` — a checker that cries
wolf on real code is a checker nobody trusts, so the bar is zero false positives
on the full constructed language. The error tests pin each error CLASS the
checker is responsible for, expressed as the simplest snippet that triggers it.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate.category import BDomain, BType, BBasic, Level
from app.services.substrate.form import TRIVIAL_REFS
from app.services.substrate.form_check import (
    ERROR,
    WARNING,
    check_text,
    has_errors,
)
from app.services.substrate.kernel import NodeID, make_cell
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
    # Seed one global cell so cell-resolution has something real to resolve to.
    make_cell(
        s,
        name="agent-pipeline",
        domain="idea",
        blueprint=NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.IDEA),
    )
    s.flush()
    try:
        yield s
        s.commit()
    finally:
        s.close()


def codes(diags, severity=None):
    return [d.code for d in diags if severity is None or d.severity == severity]


# ---------------------------------------------------------------------------
# The trust bar: a real program with every scoping construct stays silent
# ---------------------------------------------------------------------------


def test_clean_program_is_silent(session):
    src = """
    do {
        defn add_pair(a, b) = a + b;
        defn fib(n) = if n < 2 then n else fib(n - 1) + fib(n - 2);
        let xs = range(0, 5);
        let doubled = map(fib, xs);
        let total = fold(add_pair, 0, doubled);
        let greeting = "fib of five: " + str(total);
        let subject = with @idea(agent-pipeline) { .self };
        let squared = for x in doubled { x * 2 };
        let m = match total { 0 => "zero", _ => greeting };
        ~Integer;
        @memory;
        greeting
    }
    """
    diags = check_text(session, src)
    assert diags == [], f"clean program flagged: {[str(d) for d in diags]}"


# ---------------------------------------------------------------------------
# One snippet, one of each error class — the strange-minimal boundary sweep
# ---------------------------------------------------------------------------


def test_one_of_each_error_class(session):
    # Each line below carries exactly one resolution fault; the do-block lets
    # `goodfn` exist so the arity fault is about count, not existence.
    src = """
    do {
        defn goodfn(a) = a;
        goodfn(1, 2);
        nope;
        missing_fn(3);
        set never = 9;
        ~Nonesuch;
        @idea(does-not-exist);
        @notadomain;
        .self
    }
    """
    diags = check_text(session, src)
    found = set(codes(diags, ERROR))
    expected = {
        "arity-mismatch",       # goodfn(1, 2) — defined with 1 param
        "unresolved-name",      # nope
        "unresolved-function",  # missing_fn(3)
        "set-unbound",          # set never = 9
        "unresolved-blueprint", # ~Nonesuch
        "unresolved-cell",      # @idea(does-not-exist)
        "unknown-domain",       # @notadomain
        "self-outside-with",    # .self at top of do-block
    }
    assert expected <= found, f"missing {expected - found}; got {found}"


# ---------------------------------------------------------------------------
# Cell resolution — the refactoring case: rename a cell, every ref lights up
# ---------------------------------------------------------------------------


def test_known_cell_resolves(session):
    assert check_text(session, "@idea(agent-pipeline)") == []


def test_renamed_cell_is_caught(session):
    diags = check_text(session, "@idea(agent-pipeline-renamed)")
    assert codes(diags, ERROR) == ["unresolved-cell"]


# ---------------------------------------------------------------------------
# Conservative typing — flag the definitely-wrong, never the overloaded
# ---------------------------------------------------------------------------


def test_overloaded_plus_is_not_flagged(session):
    # `+` is string concat / numeric add / list concat — never a type error.
    assert check_text(session, '"a" + "b"') == []
    assert check_text(session, "1 + 2") == []


def test_arithmetic_on_string_warns_not_errors(session):
    diags = check_text(session, '"x" - 1')
    assert codes(diags, ERROR) == []
    assert "type-mismatch" in codes(diags, WARNING)


# ---------------------------------------------------------------------------
# Failures stay diagnostics, not exceptions
# ---------------------------------------------------------------------------


def test_parse_error_is_a_diagnostic(session):
    diags = check_text(session, "do {")
    assert codes(diags, ERROR) == ["parse-error"]
    assert has_errors(diags)
