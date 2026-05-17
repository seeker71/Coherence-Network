"""Form-level interpreter — proof that Form walks its own Recipe NodeIDs.

The evaluator source lives in `docs/coherence-substrate/form-engine.form`
between `# >>> BEGIN engine` / `# >>> END engine` markers. The substrate
holds its own interpreter; the test loads it from disk and runs it.

Three lines of defense against drift:

1. The dispatch table is flat NodeID literals (`@1.2.12.1` for MATH.PLUS,
   etc.). If `RBasic.MATH` ever moves from 12 to anything else, the
   literal stops matching the recipe Form produces — answers change,
   tests fail.

2. `test_form_engine_literals_match_python_enums` reads every `@l.t.i`
   literal from the engine block and asserts each one points at the
   `(Level.BASIC, RBasic.<verb>, instance)` triple a Python enum names.
   Rename `RBasic.MATH` and this test names the wrong literal.

3. `test_form_engine_matches_python_engine_over_random_expressions`
   generates random arithmetic / logic / comparison expressions and
   asserts both engines produce the same answer. Drift in semantics
   shows up as a divergence.
"""
from __future__ import annotations

import random
import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import form_evaluate_text
from app.services.substrate.category import (
    Level,
    RBasic,
    RCompare,
    RCond,
    RLogic,
    RMath,
)
from app.services.substrate.form_runtime import (
    form_execute_text,
    reset_runtime_registries,
)
from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM


_ENGINE_PATH = Path(__file__).parent.parent.parent / "docs" / "coherence-substrate" / "form-engine.form"


def _load_engine() -> str:
    src = _ENGINE_PATH.read_text()
    m = re.search(r"# >>> BEGIN engine\n(.*?)\n# >>> END engine", src, re.DOTALL)
    if not m:
        raise RuntimeError(
            f"engine markers not found in {_ENGINE_PATH}; the test loads "
            "the evaluator from disk and needs `# >>> BEGIN engine` / "
            "`# >>> END engine` to bracket the source."
        )
    return m.group(1)


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


def _form_eval(session, expr: str):
    """Intern the expression, then evaluate via the Form-level engine."""
    nid = form_evaluate_text(session, expr).value
    engine = _load_engine()
    return form_execute_text(session, f"do {{\n{engine}\n; ev(@{nid})\n}}")


# ---------------------------------------------------------------------------
# Smoke tests — every category arm exercised at least once
# ---------------------------------------------------------------------------


def test_engine_plus(session):
    assert _form_eval(session, "1 + 2") == 3


def test_engine_minus(session):
    assert _form_eval(session, "10 - 4") == 6


def test_engine_multiply(session):
    assert _form_eval(session, "6 * 7") == 42


def test_engine_divide(session):
    assert _form_eval(session, "20 / 4") == 5


def test_engine_modulo(session):
    assert _form_eval(session, "17 % 5") == 2


def test_engine_precedence(session):
    assert _form_eval(session, "1 + 2 * 3") == 7
    assert _form_eval(session, "(1 + 2) * 3") == 9


def test_engine_equal(session):
    assert _form_eval(session, "7 == 7") is True
    assert _form_eval(session, "7 == 8") is False


def test_engine_not_equal(session):
    assert _form_eval(session, "5 != 3") is True


def test_engine_less(session):
    assert _form_eval(session, "3 < 5") is True


def test_engine_less_equal(session):
    assert _form_eval(session, "5 <= 5") is True


def test_engine_greater(session):
    assert _form_eval(session, "5 > 3") is True


def test_engine_greater_equal(session):
    assert _form_eval(session, "5 >= 5") is True


def test_engine_logic_and(session):
    assert _form_eval(session, "true && true") is True
    assert _form_eval(session, "true && false") is False


def test_engine_logic_or(session):
    assert _form_eval(session, "false || true") is True


def test_engine_logic_not(session):
    assert _form_eval(session, "!false") is True


def test_engine_if_then_else(session):
    assert _form_eval(session, "if 5 > 3 then 100 else 200") == 100
    assert _form_eval(session, "if 5 < 3 then 100 else 200") == 200


def test_engine_nested(session):
    assert _form_eval(
        session, "if (2 * 3) > (1 + 2) then (10 * 5) else (20 / 2)"
    ) == 50


# ---------------------------------------------------------------------------
# Drift sentinel — every literal in the engine block names a real enum
# ---------------------------------------------------------------------------


# Each tuple: (NodeID 4-tuple as it appears in form-engine.form,
#              the Python enum value it must encode)
_EXPECTED_LITERALS = [
    ((1, 2, RBasic.MATH, RMath.PLUS),         "RBasic.MATH / RMath.PLUS"),
    ((1, 2, RBasic.MATH, RMath.MINUS),        "RBasic.MATH / RMath.MINUS"),
    ((1, 2, RBasic.MATH, RMath.MULTIPLY),     "RBasic.MATH / RMath.MULTIPLY"),
    ((1, 2, RBasic.MATH, RMath.DIVIDE),       "RBasic.MATH / RMath.DIVIDE"),
    ((1, 2, RBasic.MATH, RMath.MODULO),       "RBasic.MATH / RMath.MODULO"),
    ((1, 2, RBasic.COMPARE, RCompare.EQUAL),         "RBasic.COMPARE / RCompare.EQUAL"),
    ((1, 2, RBasic.COMPARE, RCompare.NOT_EQUAL),     "RBasic.COMPARE / RCompare.NOT_EQUAL"),
    ((1, 2, RBasic.COMPARE, RCompare.LESS),          "RBasic.COMPARE / RCompare.LESS"),
    ((1, 2, RBasic.COMPARE, RCompare.LESS_EQUAL),    "RBasic.COMPARE / RCompare.LESS_EQUAL"),
    ((1, 2, RBasic.COMPARE, RCompare.GREATER),       "RBasic.COMPARE / RCompare.GREATER"),
    ((1, 2, RBasic.COMPARE, RCompare.GREATER_EQUAL), "RBasic.COMPARE / RCompare.GREATER_EQUAL"),
    ((1, 2, RBasic.LOGIC, RLogic.AND),       "RBasic.LOGIC / RLogic.AND"),
    ((1, 2, RBasic.LOGIC, RLogic.OR),        "RBasic.LOGIC / RLogic.OR"),
    ((1, 2, RBasic.LOGIC, RLogic.NOT),       "RBasic.LOGIC / RLogic.NOT"),
    ((1, 2, RBasic.COND, RCond.IF_THEN),      "RBasic.COND / RCond.IF_THEN"),
    ((1, 2, RBasic.COND, RCond.IF_THEN_ELSE), "RBasic.COND / RCond.IF_THEN_ELSE"),
]


def test_form_engine_literals_match_python_enums():
    """If `RBasic.MATH` moves from 12 to anything else, the literal
    `@1.2.12.1` in the engine block silently points at the wrong row.
    This test catches that the moment it happens."""
    engine = _load_engine()
    found = set(
        tuple(int(x) for x in m.groups())
        for m in re.finditer(r"@(\d+)\.(\d+)\.(\d+)\.(\d+)", engine)
    )
    for nid_tuple, label in _EXPECTED_LITERALS:
        assert nid_tuple in found, (
            f"engine block is missing literal @{'.'.join(str(x) for x in nid_tuple)} "
            f"({label}); did the dispatch table get out of sync with the enums?"
        )
    # Also assert the literals that ARE in the file all decode to known enums —
    # catches the inverse drift (engine literal exists but no enum points at it).
    known = {nid for nid, _ in _EXPECTED_LITERALS}
    # Trivial-leaf literals (level=1) live in the `_` arm via runtime checks,
    # not as match patterns — so the file holds only composite literals (level=2).
    composite_literals = {nid for nid in found if nid[1] == Level.BASIC}
    unknown = composite_literals - known
    assert not unknown, (
        f"engine block has literals not named by _EXPECTED_LITERALS: {unknown}. "
        "Either add them to the test, or remove the stale arm."
    )


# ---------------------------------------------------------------------------
# Parity sentinel — random expressions, both engines, equal answers
# ---------------------------------------------------------------------------


def _random_expr(rng: random.Random, depth: int) -> str:
    if depth <= 0 or rng.random() < 0.3:
        return str(rng.randint(1, 9))
    op = rng.choice(["+", "-", "*"])  # avoid `/` (zero-div) and `%` (zero-mod)
    a = _random_expr(rng, depth - 1)
    b = _random_expr(rng, depth - 1)
    return f"({a} {op} {b})"


def test_form_engine_matches_python_engine_over_random_expressions(session):
    """Two engines, identical answer — that's the strong proof, sampled
    across a generated population rather than three handpicked exprs."""
    rng = random.Random(20260517)
    for _ in range(40):
        expr = _random_expr(rng, depth=3)
        python_result = form_execute_text(session, expr)
        form_result = _form_eval(session, expr)
        assert python_result == form_result, (
            f"engine divergence on {expr!r}: python={python_result} form={form_result}"
        )


def test_form_engine_matches_python_engine_over_conditionals(session):
    """Parity also for conditionals + comparisons, where the answer
    type differs (bool vs int)."""
    rng = random.Random(20260517)
    for _ in range(20):
        a = rng.randint(1, 9)
        b = rng.randint(1, 9)
        op = rng.choice(["==", "!=", "<", "<=", ">", ">="])
        then_v = rng.randint(10, 99)
        else_v = rng.randint(100, 999)
        expr = f"if {a} {op} {b} then {then_v} else {else_v}"
        assert _form_eval(session, expr) == form_execute_text(session, expr), expr
