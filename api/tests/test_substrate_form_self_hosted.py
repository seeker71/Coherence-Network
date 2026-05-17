"""Form-level interpreter — proof that Form is expressive enough to
walk its own Recipe NodeIDs and produce the same values the Python engine does.

The Form code below defines `ev` (and helpers) as Form `defn`s. It reads
substrate state via the same `.category`, `.children`, `.type_`, `.instance`
accessors any Form expression has, dispatches on category, recurses. No
Python is involved in the dispatch — only the bootstrap-engine's leaf
operations (arithmetic, comparison, conditional) carry it through.

This is the smallest concrete demonstration of self-hosting at the
interpreter layer. The parser and the substrate-mutation runtime remain
partially in Python (see self-hosted-eval.md for the honest map).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import form_evaluate_text
from app.services.substrate.form_runtime import (
    form_execute_text,
    reset_runtime_registries,
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
    reset_runtime_registries()
    try:
        yield s
        s.commit()
    finally:
        s.close()
        reset_runtime_registries()


# Form source for the self-hosted interpreter. Lives as a string so the
# test can substitute the recipe NodeID under test. Real-world use would
# read it from a .form file in `docs/coherence-substrate/`.

_FORM_EVAL_SRC = """
do {{
  defn ev_math(node) = do {{
    let a = ev(node.children[0]);
    let b = ev(node.children[1]);
    let op = node.category.instance;
    if op == 1 then a + b
    else if op == 2 then a - b
    else if op == 3 then a * b
    else if op == 4 then a / b
    else if op == 5 then a % b
    else 0
  }};
  defn ev_cmp(node) = do {{
    let a = ev(node.children[0]);
    let b = ev(node.children[1]);
    let op = node.category.instance;
    if op == 1 then a == b
    else if op == 2 then a != b
    else if op == 3 then a < b
    else if op == 4 then a <= b
    else if op == 5 then a > b
    else if op == 6 then a >= b
    else false
  }};
  defn ev_cond(node) = do {{
    let c = ev(node.children[0]);
    if c then ev(node.children[1])
    else if node.category.instance == 2 then ev(node.children[2])
    else null
  }};
  defn ev(node) = do {{
    let ct = node.category.type_;
    if ct == 12 then ev_math(node)
    else if ct == 13 then ev_cmp(node)
    else if ct == 11 then ev_cond(node)
    else if ct == 3 then node.instance - 1
    else if ct == 2 then (if node.instance == 1 then true else false)
    else 0
  }};
  ev(@{nid})
}}
"""


def _form_eval(session, expr: str):
    """Helper: intern the expression via Python parser, then evaluate via
    the Form-level interpreter."""
    nid = form_evaluate_text(session, expr).value
    return form_execute_text(session, _FORM_EVAL_SRC.format(nid=nid))


def test_form_eval_simple_arithmetic(session):
    assert _form_eval(session, "1 + 2") == 3


def test_form_eval_precedence(session):
    assert _form_eval(session, "1 + 2 * 3") == 7
    assert _form_eval(session, "(1 + 2) * 3") == 9


def test_form_eval_subtraction(session):
    assert _form_eval(session, "10 - 4") == 6


def test_form_eval_division(session):
    assert _form_eval(session, "20 / 4") == 5


def test_form_eval_comparison_true(session):
    assert _form_eval(session, "5 > 3") is True


def test_form_eval_comparison_false(session):
    assert _form_eval(session, "5 < 3") is False


def test_form_eval_equality(session):
    assert _form_eval(session, "7 == 7") is True
    assert _form_eval(session, "7 == 8") is False


def test_form_eval_if_then_else_true_branch(session):
    assert _form_eval(session, "if 5 > 3 then 100 else 200") == 100


def test_form_eval_if_then_else_false_branch(session):
    assert _form_eval(session, "if 5 < 3 then 100 else 200") == 200


def test_form_eval_nested_arithmetic_in_cond(session):
    """The Form-level interpreter handles deep recursion through composite
    recipes — this exercises ev_cond -> ev_math -> ev_math."""
    assert _form_eval(session, "if (2 * 3) > (1 + 2) then (10 * 5) else (20 / 2)") == 50


def test_form_eval_matches_python_engine(session):
    """Form-level result equals Python-level result for the same recipe.

    The strong proof: two engines, identical answer. The Form interpreter
    is reading the same substrate Python's engine reads."""
    for expr in ["1 + 2", "5 * 3 - 2", "if 1 == 1 then 42 else 0"]:
        python_result = form_execute_text(session, expr)
        form_result = _form_eval(session, expr)
        assert python_result == form_result, f"divergence on {expr!r}"
