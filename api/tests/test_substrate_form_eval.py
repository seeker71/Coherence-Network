"""Tests for the data-driven evaluator — operator-symbol → recipe-category.

Closes the gap from the operator-self-hosting commit. Custom operators
with non-standard symbols can now intern as recipes via the eval registry.
The hardcoded switch in `_to_recipe_node_id` is replaced by a single
dictionary lookup; built-ins are pre-registered with the same categories
they had before.

The architectural payoff: parser, builder, AND evaluator are all
data-driven. A custom operator's full lifecycle (parse → AST → intern)
is now expressible without touching form.py's code.
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
    bootstrap_self_host_operators,
    form_evaluate_text,
    list_eval_mappings,
    lookup_eval_category,
    register_eval,
    register_operator,
    reset_eval_registry,
)
from app.services.substrate.category import Level, RBasic, RMath
from app.services.substrate.kernel import NodeID
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
def clean_state():
    """Each test starts with default registries."""
    from app.services.substrate.form_eval import _BINARY_EVAL, _UNARY_EVAL
    from app.services.substrate.form_operators import (
        _BINARY_OPERATORS, _UNARY_PREFIX_OPERATORS,
    )
    saved = {
        "be": dict(_BINARY_EVAL), "ue": dict(_UNARY_EVAL),
        "bo": dict(_BINARY_OPERATORS), "uo": dict(_UNARY_PREFIX_OPERATORS),
    }
    yield
    _BINARY_EVAL.clear(); _BINARY_EVAL.update(saved["be"])
    _UNARY_EVAL.clear(); _UNARY_EVAL.update(saved["ue"])
    _BINARY_OPERATORS.clear(); _BINARY_OPERATORS.update(saved["bo"])
    _UNARY_PREFIX_OPERATORS.clear(); _UNARY_PREFIX_OPERATORS.update(saved["uo"])


# ---------------------------------------------------------------------------
# Built-in registrations preserved
# ---------------------------------------------------------------------------


def test_builtin_binary_ops_registered():
    """Default registrations match the previous hardcoded behavior."""
    for sym in ("+", "-", "*", "/", "%", "==", "!=", "<", "<=", ">", ">=", "&&", "||"):
        cat = lookup_eval_category(sym, "binary")
        assert cat is not None, f"binary op {sym!r} not registered"


def test_builtin_unary_ops_registered():
    """Default registrations include unary -, !"""
    for sym in ("-", "!"):
        cat = lookup_eval_category(sym, "unary")
        assert cat is not None, f"unary op {sym!r} not registered"


# ---------------------------------------------------------------------------
# Default behavior preserved end-to-end
# ---------------------------------------------------------------------------


def test_existing_arithmetic_still_interns(session):
    """1 + 2 still works after the data-driven rewrite."""
    result = form_evaluate_text(session, "1 + 2")
    assert result.kind == "recipe"
    assert result.value.type_ == RBasic.MATH


def test_existing_compare_still_interns(session):
    result = form_evaluate_text(session, "x == 5")
    assert result.kind == "recipe"


def test_existing_logic_still_interns(session):
    result = form_evaluate_text(session, "a && b")
    assert result.kind == "recipe"


def test_unary_minus_still_interns(session):
    result = form_evaluate_text(session, "-x")
    assert result.kind == "recipe"


def test_unary_not_still_interns(session):
    result = form_evaluate_text(session, "!flag")
    assert result.kind == "recipe"


# ---------------------------------------------------------------------------
# Custom operator with new symbol can register an eval mapping
# ---------------------------------------------------------------------------


def test_custom_operator_with_eval_mapping_interns(session):
    """Register `%%` operator + eval mapping → it interns as a recipe."""
    bootstrap_self_host_operators(session)

    # Register an OperatorRule for PERCENT producing op="%%"
    register_operator(
        "%%", "PERCENT", 5,
        arity="binary",
        template=Build(
            "BinOp", op=Const("%%"),
            left=CaptureRef("__left__"), right=CaptureRef("__right__"),
        ),
    )

    # Register the eval mapping for "%%" → reuse the existing
    # Math.MODULO category (or pick any). For this test we'll use MODULO
    # so the new operator behaves like the old one.
    custom_category = NodeID(1, Level.BASIC, RBasic.MATH, RMath.MODULO)
    register_eval("%%", custom_category, arity="binary")

    # Now 2 % 3 (parsed via the registered operator with op="%%") interns
    # successfully. Without the eval mapping this would have raised.
    result = form_evaluate_text(session, "2 % 3", prefer_registered=True)
    assert result.kind == "recipe"
    assert result.value.type_ == RBasic.MATH


def test_unknown_op_without_eval_mapping_raises(session):
    """An op symbol with no eval mapping raises SyntaxError clearly."""
    from app.services.substrate.form import BinOp, Identifier
    from app.services.substrate.form import evaluate as form_evaluate

    # Hand-construct a BinOp with a made-up op
    ast = BinOp(op="<<<weird>>>", left=Identifier("a"), right=Identifier("b"))
    with pytest.raises(SyntaxError) as exc:
        form_evaluate(session, ast)
    assert "no eval mapping" in str(exc.value)


# ---------------------------------------------------------------------------
# Registry inspection
# ---------------------------------------------------------------------------


def test_list_eval_mappings_returns_copy():
    """list_eval_mappings returns a snapshot, not the live dict."""
    snapshot = list_eval_mappings("binary")
    snapshot["fake"] = NodeID(1, 1, 1, 1)
    fresh = list_eval_mappings("binary")
    assert "fake" not in fresh


def test_reset_eval_registry_repopulates_builtins():
    """After reset_eval_registry, the built-in mappings are still there."""
    reset_eval_registry()
    assert lookup_eval_category("+", "binary") is not None
    assert lookup_eval_category("==", "binary") is not None
    assert lookup_eval_category("!", "unary") is not None
