"""Tests for the recipe-introspection primitives — the meta-circular seam.

The substrate is content-addressed; Form expresses code as Recipe NodeIDs.
The meta-circular promise is that Form can describe Form: a Recipe written
in Form can walk Recipe NodeIDs from inside Form and return values.

These primitives close the seam:

  category(r)        — given a Recipe NodeID, return its category NodeID
  nchildren(r)       — given a Recipe NodeID, return its arity
  child(r, n)        — given a Recipe NodeID + index, return the n-th child
  integer_value(r)   — decode a trivial INTEGER Recipe NodeID to its int
  string_value(r)    — decode a trivial STRING Recipe NodeID to its str
  bool_value(r)      — decode a trivial BOOL Recipe NodeID to its bool

With these, the evaluator in docs/coherence-substrate/form-engine.form can
dispatch on category, recurse on children, bottom-out at trivials — and
the meta-circular loop closes from the Form side.

See docs/coherence-substrate/form-language.md → "Self-evolving" for the
architectural frame.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import form_evaluate_text, form_execute_text
from app.services.substrate.category import Level, RBasic, RMath, RType
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


def _nid_form(nid) -> str:
    """Format a NodeID as Form literal syntax."""
    return f"@{nid.package}.{nid.level}.{nid.type_}.{nid.instance}"


# ---------------------------------------------------------------------------
# category() — return the category NodeID of a recipe
# ---------------------------------------------------------------------------


def test_category_of_math_plus(session):
    """`1 + 2` is a Math.PLUS recipe; category() returns its category NodeID."""
    plus = form_evaluate_text(session, "1 + 2").value
    src = f"category({_nid_form(plus)})"
    result = form_execute_text(session, src)
    assert (result.package, result.level, result.type_, result.instance) == (
        1, Level.BASIC, RBasic.MATH, RMath.PLUS,
    )


def test_category_of_math_multiply(session):
    multiply = form_evaluate_text(session, "3 * 4").value
    src = f"category({_nid_form(multiply)})"
    result = form_execute_text(session, src)
    assert result.type_ == RBasic.MATH
    assert result.instance == RMath.MULTIPLY


def test_category_of_trivial_leaf_is_self(session):
    """A trivial integer's category is itself (the coordinate IS the category)."""
    leaf = form_evaluate_text(session, "42").value
    src = f"category({_nid_form(leaf)})"
    result = form_execute_text(session, src)
    assert result == leaf


# ---------------------------------------------------------------------------
# nchildren() — arity
# ---------------------------------------------------------------------------


def test_nchildren_of_binop_is_2(session):
    plus = form_evaluate_text(session, "1 + 2").value
    src = f"nchildren({_nid_form(plus)})"
    assert form_execute_text(session, src) == 2


def test_nchildren_of_trivial_is_0(session):
    leaf = form_evaluate_text(session, "42").value
    src = f"nchildren({_nid_form(leaf)})"
    assert form_execute_text(session, src) == 0


def test_nchildren_of_nested_arith(session):
    """`(1 + 2) * (3 - 4)` is a MULTIPLY with two composite children."""
    expr = form_evaluate_text(session, "(1 + 2) * (3 - 4)").value
    src = f"nchildren({_nid_form(expr)})"
    assert form_execute_text(session, src) == 2


# ---------------------------------------------------------------------------
# child() — n-th child NodeID
# ---------------------------------------------------------------------------


def test_child_returns_recipe_nodeids(session):
    """`(1 + 2) * 3` — child(0) is a recipe (1+2), child(1) is a trivial (3)."""
    expr = form_evaluate_text(session, "(1 + 2) * 3").value
    src = f"do {{ let r = {_nid_form(expr)}; nchildren(child(r, 0)) }}"
    assert form_execute_text(session, src) == 2

    src2 = f"do {{ let r = {_nid_form(expr)}; nchildren(child(r, 1)) }}"
    assert form_execute_text(session, src2) == 0


def test_child_out_of_range_raises(session):
    leaf = form_evaluate_text(session, "42").value
    src = f"child({_nid_form(leaf)}, 0)"
    with pytest.raises(Exception):
        form_execute_text(session, src)


# ---------------------------------------------------------------------------
# Trivial decoders
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [0, 1, 42, 100, 999])
def test_integer_value_round_trip(session, value):
    nid = form_evaluate_text(session, str(value)).value
    src = f"integer_value({_nid_form(nid)})"
    assert form_execute_text(session, src) == value


@pytest.mark.parametrize("text", ["hello", "with spaces", ""])
def test_string_value_round_trip(session, text):
    quoted = '"' + text + '"'
    nid = form_evaluate_text(session, quoted).value
    src = f"string_value({_nid_form(nid)})"
    assert form_execute_text(session, src) == text


@pytest.mark.parametrize("value", [True, False])
def test_bool_value_round_trip(session, value):
    src_in = "true" if value else "false"
    nid = form_evaluate_text(session, src_in).value
    src = f"bool_value({_nid_form(nid)})"
    assert form_execute_text(session, src) == value


# ---------------------------------------------------------------------------
# The meta-circular evaluator — Form code that evaluates Form recipes
# ---------------------------------------------------------------------------
#
# These tests are the load-bearing proof: a tiny evaluator written in Form
# uses only the introspection primitives to walk a Recipe NodeID and compute
# the same value the Python evaluator would.


def _math_eval_form_src(target_nodeid) -> str:
    """A minimal arithmetic-only meta-evaluator written in Form.

    Dispatches on category. Bottoms out at trivial integer leaves via
    integer_value. Demonstrates that with three primitives + integer_value,
    Form code can evaluate Form recipes."""
    plus = f"@1.{Level.BASIC}.{RBasic.MATH}.{RMath.PLUS}"
    minus = f"@1.{Level.BASIC}.{RBasic.MATH}.{RMath.MINUS}"
    mul = f"@1.{Level.BASIC}.{RBasic.MATH}.{RMath.MULTIPLY}"
    return f"""
    do {{
      defn ev(r) =
        if nchildren(r) == 0
          then integer_value(r)
          else
            do {{
              let cat = category(r);
              let l = ev(child(r, 0));
              let rr = ev(child(r, 1));
              if cat == {plus}
                then l + rr
                else if cat == {minus}
                  then l - rr
                  else if cat == {mul}
                    then l * rr
                    else fail
            }};
      ev({_nid_form(target_nodeid)})
    }}
    """


@pytest.mark.parametrize("expr,expected", [
    ("1 + 2", 3),
    ("3 * 4", 12),
    ("10 - 7", 3),
    ("(1 + 2) * 3", 9),
    ("2 * 3 + 4", 10),
    ("10 - 4 * 2", 2),  # precedence
    ("((1 + 2) * 3) - (4 + 5)", 0),
])
def test_meta_circular_evaluator_matches_python(session, expr, expected):
    """Form code, walking Recipe NodeIDs via the introspection primitives,
    computes the same value as the Python evaluator. This is the
    meta-circular loop closing.
    """
    nid = form_evaluate_text(session, expr).value
    via_form = form_execute_text(session, _math_eval_form_src(nid))
    assert via_form == expected, f"Form evaluator gave {via_form}, expected {expected}"


def test_meta_circular_evaluator_handles_arbitrary_depth(session):
    """A deeply nested expression — Form's evaluator handles it via recursion
    in Form itself, no Python dispatch on the recipe shape involved."""
    expr = "1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9 + 10"  # left-associative
    nid = form_evaluate_text(session, expr).value
    via_form = form_execute_text(session, _math_eval_form_src(nid))
    assert via_form == 55
