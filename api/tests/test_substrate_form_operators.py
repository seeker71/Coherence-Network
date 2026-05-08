"""Tests for operator self-hosting — the last keyword-layer gap.

The proof: with `bootstrap_self_host_operators(session)` and
`prefer_registered=True`, expressions parsed via the registered
precedence-climbing path produce Recipe NodeIDs identical to the
hardcoded bootstrap precedence ladder.

Operator precedence + associativity must match exactly: `1 + 2 * 3`
must group as `1 + (2 * 3)`, not `(1 + 2) * 3`. The killer test
validates this through Recipe NodeID equality — content-addressing
exposes any precedence drift.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    Build,
    CaptureRef,
    Const,
    OperatorRule,
    bootstrap_self_host,
    bootstrap_self_host_operators,
    form_evaluate_text,
    form_parse,
    list_operators,
    lookup_binary_operator,
    lookup_unary_prefix_operator,
    register_operator,
    reset_operator_registry,
)
from app.services.substrate.form import BinOp, UnaryOp
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
def clean_state():
    """Each test starts with empty operator + keyword registries."""
    from app.services.substrate.form_rules import _BUILDERS, _KEYWORDS
    from app.services.substrate.form_operators import (
        _BINARY_OPERATORS, _UNARY_PREFIX_OPERATORS,
    )
    saved = {
        "kw": dict(_KEYWORDS), "b": dict(_BUILDERS),
        "bin": dict(_BINARY_OPERATORS), "un": dict(_UNARY_PREFIX_OPERATORS),
    }
    yield
    _KEYWORDS.clear(); _KEYWORDS.update(saved["kw"])
    _BUILDERS.clear(); _BUILDERS.update(saved["b"])
    _BINARY_OPERATORS.clear(); _BINARY_OPERATORS.update(saved["bin"])
    _UNARY_PREFIX_OPERATORS.clear(); _UNARY_PREFIX_OPERATORS.update(saved["un"])


# ---------------------------------------------------------------------------
# Registry plumbing
# ---------------------------------------------------------------------------


def test_register_operator_stored_in_correct_registry():
    """Binary and unary_prefix go into separate maps."""
    reset_operator_registry()
    register_operator(
        "+", "PLUS", 4, arity="binary",
        builder=lambda l, r: BinOp("+", l, r),
    )
    register_operator(
        "!", "BANG", 6, arity="unary_prefix",
        builder=lambda x: UnaryOp("!", x),
    )
    assert lookup_binary_operator("PLUS") is not None
    assert lookup_unary_prefix_operator("BANG") is not None
    assert lookup_unary_prefix_operator("PLUS") is None
    assert lookup_binary_operator("BANG") is None


def test_minus_can_be_both_binary_and_unary():
    """The same token kind (MINUS) can carry binary + unary_prefix
    rules independently — they live in separate registries."""
    reset_operator_registry()
    register_operator(
        "-", "MINUS", 4, arity="binary",
        builder=lambda l, r: BinOp("-", l, r),
    )
    register_operator(
        "-", "MINUS", 6, arity="unary_prefix",
        builder=lambda x: UnaryOp("-", x),
    )
    assert lookup_binary_operator("MINUS") is not None
    assert lookup_unary_prefix_operator("MINUS") is not None


def test_bootstrap_self_host_operators_registers_all(session):
    """bootstrap_self_host_operators registers every built-in operator."""
    bootstrap_self_host_operators(session)
    # Binary
    for kind in ("OR", "AND", "EQ", "NEQ", "LT", "LE", "GT", "GE",
                 "PLUS", "MINUS", "STAR", "SLASH", "PERCENT"):
        assert lookup_binary_operator(kind) is not None, f"{kind} not registered as binary"
    # Unary prefix
    for kind in ("BANG", "MINUS"):
        assert lookup_unary_prefix_operator(kind) is not None, f"{kind} not registered as unary"


# ---------------------------------------------------------------------------
# The killer test — bootstrap and registered modes produce same NodeIDs
# ---------------------------------------------------------------------------


def test_simple_binary_matches_bootstrap(session):
    bootstrap_self_host_operators(session)
    boot = form_evaluate_text(session, "1 + 2")
    self_host = form_evaluate_text(session, "1 + 2", prefer_registered=True)
    assert boot.value == self_host.value


def test_precedence_matches_bootstrap(session):
    """The classic precedence test: `1 + 2 * 3` must group as
    `1 + (2 * 3)`, both via bootstrap and via the registry."""
    bootstrap_self_host_operators(session)
    boot = form_evaluate_text(session, "1 + 2 * 3")
    self_host = form_evaluate_text(session, "1 + 2 * 3", prefer_registered=True)
    assert boot.value == self_host.value


def test_left_associativity_matches_bootstrap(session):
    """`1 - 2 - 3` must group as `(1 - 2) - 3`."""
    bootstrap_self_host_operators(session)
    boot = form_evaluate_text(session, "1 - 2 - 3")
    self_host = form_evaluate_text(session, "1 - 2 - 3", prefer_registered=True)
    assert boot.value == self_host.value


def test_compare_matches_bootstrap(session):
    bootstrap_self_host_operators(session)
    boot = form_evaluate_text(session, "x < 5")
    self_host = form_evaluate_text(session, "x < 5", prefer_registered=True)
    assert boot.value == self_host.value


def test_logic_matches_bootstrap(session):
    bootstrap_self_host_operators(session)
    boot = form_evaluate_text(session, "a && b || c")
    self_host = form_evaluate_text(session, "a && b || c", prefer_registered=True)
    assert boot.value == self_host.value


def test_unary_not_matches_bootstrap(session):
    bootstrap_self_host_operators(session)
    boot = form_evaluate_text(session, "!flag")
    self_host = form_evaluate_text(session, "!flag", prefer_registered=True)
    assert boot.value == self_host.value


def test_unary_minus_matches_bootstrap(session):
    bootstrap_self_host_operators(session)
    boot = form_evaluate_text(session, "-x")
    self_host = form_evaluate_text(session, "-x", prefer_registered=True)
    assert boot.value == self_host.value


def test_complex_mixed_precedence(session):
    """`!a && b == c + 2 * 3` exercises every precedence level at once."""
    bootstrap_self_host_operators(session)
    src = "!a && b == c + 2 * 3"
    boot = form_evaluate_text(session, src)
    self_host = form_evaluate_text(session, src, prefer_registered=True)
    assert boot.value == self_host.value


def test_combined_with_keyword_self_hosting(session):
    """Operators + keywords self-hosted together: a fully
    substrate-driven parse of a complex expression."""
    bootstrap_self_host(session)
    bootstrap_self_host_operators(session)
    src = "do { let x = 1 + 2 * 3; if x > 5 then stop else fail }"
    boot = form_evaluate_text(session, src)
    self_host = form_evaluate_text(session, src, prefer_registered=True)
    assert boot.value == self_host.value


# ---------------------------------------------------------------------------
# Custom user-registered operator
# ---------------------------------------------------------------------------


def test_register_custom_operator_changes_parsed_ast(session):
    """A user can register an operator at runtime and the parser
    picks it up. We verify the AST output (not Recipe interning,
    because the evaluator's hardcoded BinOp symbol-table is a
    separate breath of work).
    """
    bootstrap_self_host_operators(session)

    # Override PERCENT with a custom operator that produces a different
    # symbol in the BinOp AST. The autouse fixture restores the registry
    # after the test.
    register_operator(
        "%%", "PERCENT", 5,
        arity="binary",
        template=Build(
            "BinOp", op=Const("%%"),
            left=CaptureRef("__left__"), right=CaptureRef("__right__"),
        ),
    )
    ast = form_parse("2 % 3", prefer_registered=True)
    assert isinstance(ast, BinOp)
    # The custom operator's template produced op="%%", not "%"
    assert ast.op == "%%"


def test_custom_operator_higher_precedence_changes_grouping(session):
    """Demonstrate runtime grammar mutation: register `&&` at higher
    precedence than `+`. The parsed AST groups differently."""
    bootstrap_self_host_operators(session)

    # Re-register && at precedence 5 (higher than + which is 4)
    register_operator(
        "&&", "AND", 5, arity="binary",
        template=Build(
            "BinOp", op=Const("&&"),
            left=CaptureRef("__left__"), right=CaptureRef("__right__"),
        ),
    )

    # Parse `a + b && c`. With `&&` at higher precedence than `+`,
    # this should group as `a + (b && c)` — not `(a + b) && c` as in
    # the bootstrap.
    ast = form_parse("a + b && c", prefer_registered=True)
    assert isinstance(ast, BinOp)
    assert ast.op == "+"  # outermost is + because && binds tighter
    # Right side is the && expression
    assert isinstance(ast.right, BinOp)
    assert ast.right.op == "&&"

    # Bootstrap groups the other way: `(a + b) && c`
    boot = form_parse("a + b && c")
    assert isinstance(boot, BinOp)
    assert boot.op == "&&"  # outermost is && because + binds tighter