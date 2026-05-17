"""Built-in functions in Form runtime — list ops, type coercion, numerics.

Previous gap: `len([1, 2, 3])` raised NameError "unbound name 'len'". Form
had no built-in functions; only user-defined closures and operators worked.
This adds `_BUILTIN_FUNCTIONS` registry that FnCall consults before frame
lookup; user `defn`-bound names still shadow built-ins.

Higher-order built-ins (map, filter, fold) invoke user-defined Closures
correctly by threading the active session via a module-level slot.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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


# ---------------------------------------------------------------------------
# List ops
# ---------------------------------------------------------------------------


def test_len_list(session):
    assert form_execute_text(session, "len([1, 2, 3])") == 3


def test_len_string(session):
    assert form_execute_text(session, 'len("hello")') == 5


def test_head_returns_first(session):
    assert form_execute_text(session, "head([10, 20, 30])") == 10


def test_tail_returns_rest(session):
    assert form_execute_text(session, "tail([10, 20, 30])") == [20, 30]


def test_reverse(session):
    assert form_execute_text(session, "reverse([1, 2, 3])") == [3, 2, 1]


def test_concat(session):
    assert form_execute_text(session, "concat([1, 2], [3, 4])") == [1, 2, 3, 4]


def test_sum(session):
    assert form_execute_text(session, "sum([1, 2, 3, 4, 5])") == 15


def test_range_one_arg(session):
    assert form_execute_text(session, "range(5)") == [0, 1, 2, 3, 4]


def test_range_two_args(session):
    assert form_execute_text(session, "range(2, 8)") == [2, 3, 4, 5, 6, 7]


# ---------------------------------------------------------------------------
# Higher-order: map / filter / fold with user-defined closures
# ---------------------------------------------------------------------------


def test_map_with_closure(session):
    v = form_execute_text(
        session, "do { defn double(n) = n * 2; map(double, [1, 2, 3]) }"
    )
    assert v == [2, 4, 6]


def test_filter_with_closure(session):
    v = form_execute_text(
        session,
        "do { defn even(n) = n % 2 == 0; filter(even, [1, 2, 3, 4, 5]) }",
    )
    assert v == [2, 4]


def test_fold_with_closure(session):
    v = form_execute_text(
        session,
        "do { defn add(a, b) = a + b; fold(add, 0, [1, 2, 3, 4]) }",
    )
    assert v == 10


# ---------------------------------------------------------------------------
# Type coercion
# ---------------------------------------------------------------------------


def test_str_of_int(session):
    assert form_execute_text(session, "str(42)") == "42"


def test_int_of_string(session):
    assert form_execute_text(session, 'int("123")') == 123


def test_bool_truthy(session):
    assert form_execute_text(session, "bool(1)") is True


def test_bool_falsy(session):
    assert form_execute_text(session, "bool(0)") is False


# ---------------------------------------------------------------------------
# User defn shadows built-in
# ---------------------------------------------------------------------------


def test_user_defn_shadows_builtin(session):
    """A locally-bound name takes precedence over a built-in of the same name."""
    v = form_execute_text(
        session, 'do { defn len(x) = 99; len([1, 2, 3]) }'
    )
    assert v == 99


# ---------------------------------------------------------------------------
# Numerics
# ---------------------------------------------------------------------------


def test_abs(session):
    assert form_execute_text(session, "abs(-5)") == 5


def test_min_max(session):
    assert form_execute_text(session, "min(3, 1, 2)") == 1
    assert form_execute_text(session, "max(3, 1, 2)") == 3
