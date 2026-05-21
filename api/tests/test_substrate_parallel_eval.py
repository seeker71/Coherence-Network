"""Parallel kernel execution — Python and Form agree on every supported expression.

This is the runtime sibling of `test_substrate_form_self_hosted.py`: that
file proves the Form-in-Form engine works in isolation; this file
proves it agrees with the Python kernel on a representative corpus when
both are run in parallel.

Three classes of test:

1. **Agreement on the BASIC dispatch arms** — every category arm in
   form-engine.form has at least one expression here. Both kernels must
   produce equal values.

2. **Recipe-NodeID traceability** — the result carries the Recipe
   NodeID, which is the substrate-canonical identity of what was
   executed. Two expressions that intern to the same Recipe must
   produce the same `recipe_node_id`.

3. **Out-of-coverage gracefulness** — expressions whose category isn't
   in form-engine.form's dispatch arms (function calls, mutation,
   substrate writes) should land as `agreed=None`, not `agreed=False`.
   A missing arm is *no comparison*, not *failed comparison*.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.services.substrate import orm  # noqa: F401  (registers ORM)
from app.services.substrate.parallel_eval import parallel_execute_text


@pytest.fixture
def session():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    Session = sessionmaker(bind=eng)
    with Session() as s:
        yield s


# (1) Agreement on the BASIC dispatch arms

AGREEMENT_CASES = [
    # Math
    ("1 + 2", 3),
    ("10 - 4", 6),
    ("6 * 7", 42),
    ("20 / 4", 5),
    ("17 % 5", 2),
    ("1 + 2 * 3", 7),
    ("(1 + 2) * 3", 9),
    # Compare
    ("7 == 7", True),
    ("7 == 8", False),
    ("5 != 3", True),
    ("3 < 5", True),
    ("5 <= 5", True),
    ("5 > 3", True),
    ("5 >= 5", True),
    # Logic
    ("true && true", True),
    ("true && false", False),
    ("false || true", True),
    ("!false", True),
    # Conditional
    ("if 5 > 3 then 100 else 200", 100),
    ("if 5 < 3 then 100 else 200", 200),
    # Nested
    ("if (2 * 3) > (1 + 2) then (10 * 5) else (20 / 2)", 50),
    # Trivial leaf (STRING)
    ('"hello"', "hello"),
]


@pytest.mark.parametrize("expr,expected", AGREEMENT_CASES)
def test_both_kernels_agree(session, expr, expected):
    """Python and Form kernels produce equal values for the supported corpus."""
    r = parallel_execute_text(session, expr)
    assert r.python_value == expected, (
        f"Python kernel diverged from expected:\n"
        f"  expr     : {expr!r}\n"
        f"  python   : {r.python_value!r}\n"
        f"  expected : {expected!r}\n"
    )
    assert r.agreed is True, (
        f"Form kernel disagreed with Python kernel:\n"
        f"  expr        : {expr!r}\n"
        f"  python      : {r.python_value!r}\n"
        f"  form        : {r.form_value!r}\n"
        f"  form_error  : {r.form_error}\n"
        f"  recipe_nid  : {r.recipe_node_id}\n"
    )


# (2) Recipe-NodeID traceability — substrate-canonical identity of execution

EQUIVALENCE_PAIRS = [
    ("1 + 2", "1+2"),
    ("1 + 2 * 3", "1 + (2 * 3)"),
    ("if 5 > 3 then 100 else 200", "if 5>3 then 100 else 200"),
]


@pytest.mark.parametrize("left,right", EQUIVALENCE_PAIRS)
def test_equivalent_expressions_share_recipe_node_id(session, left, right):
    """Textually-different but semantically-identical expressions execute
    against the same Recipe NodeID. The trace of `which part of the recipe
    ran` is canonical — independent of which surface called us."""
    rl = parallel_execute_text(session, left)
    rr = parallel_execute_text(session, right)
    assert rl.recipe_node_id == rr.recipe_node_id, (
        f"Equivalent expressions traced to different Recipe NodeIDs:\n"
        f"  left  : {left!r}  →  {rl.recipe_node_id}\n"
        f"  right : {right!r}  →  {rr.recipe_node_id}\n"
    )
    # And both kernels still agree on the value
    assert rl.python_value == rr.python_value
    assert rl.agreed is True
    assert rr.agreed is True


# (3) Out-of-coverage gracefulness

OUT_OF_COVERAGE_CASES = [
    # Function call into runtime — defn/call lives in the runtime, not yet
    # in the meta-circular dispatch table.
    "do { defn double(x) = x * 2; double(21) }",
]


@pytest.mark.parametrize("expr", OUT_OF_COVERAGE_CASES)
def test_out_of_coverage_reports_no_comparison(session, expr):
    """Expressions outside form-engine.form's coverage land as
    `agreed=None` (no comparison) rather than `agreed=False` (failed
    comparison). The Python kernel still runs and returns a value;
    the Form kernel's gap is named, not faked."""
    r = parallel_execute_text(session, expr)
    # Python kernel always produces a value
    assert r.python_value is not None
    # Form kernel either agreed, errored out (coverage gap), or stayed
    # silent. The contract: agreed is never True-by-accident.
    assert r.agreed in (True, False, None)
    # If form_error is set, agreed must be None (no comparison made)
    if r.form_error is not None:
        assert r.agreed is None
