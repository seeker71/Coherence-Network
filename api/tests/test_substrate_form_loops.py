"""for/while loops + `set` for mutation across iterations.

Three gaps surfaced from running Form:
- `for x in [1, 2, 3] { x }` — SyntaxError
- `while (n > 0) { ... }` — SyntaxError
- The deeper one: even with for/while, `let total = total + x` in a body
  creates a NEW binding in the loop's sub-frame, so accumulation doesn't
  work. The wholeness move: add `set name = value` which mutates the nearest
  enclosing binding (distinct from `let` which introduces).
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
# for x in xs { body }
# ---------------------------------------------------------------------------


def test_for_returns_list_of_body_results(session):
    assert form_execute_text(
        session, "for x in [1, 2, 3] { x * 2 }"
    ) == [2, 4, 6]


def test_for_over_range(session):
    assert form_execute_text(
        session, "for x in range(4) { x }"
    ) == [0, 1, 2, 3]


def test_for_with_accumulator_via_set(session):
    """The load-bearing pattern — sum via mutable accumulator."""
    assert form_execute_text(
        session,
        "do { let total = 0; for x in [1, 2, 3, 4, 5] { set total = total + x }; total }",
    ) == 15


def test_for_appending_via_set_and_concat(session):
    assert form_execute_text(
        session,
        "do { let xs = []; for x in [10, 20, 30] { set xs = concat(xs, [x * 2]) }; xs }",
    ) == [20, 40, 60]


def test_for_over_string_iterates_chars(session):
    assert form_execute_text(
        session, 'for c in "abc" { c }'
    ) == ["a", "b", "c"]


def test_for_non_iterable_raises(session):
    with pytest.raises(TypeError):
        form_execute_text(session, "for x in 42 { x }")


# ---------------------------------------------------------------------------
# while cond { body }
# ---------------------------------------------------------------------------


def test_while_counts_up_via_set(session):
    assert form_execute_text(
        session, "do { let i = 0; while i < 5 { set i = i + 1 }; i }"
    ) == 5


def test_while_returns_last_body_value(session):
    assert form_execute_text(
        session, "do { let i = 0; while i < 3 { set i = i + 1; i * 10 } }"
    ) == 30


def test_while_unentered_returns_null(session):
    assert form_execute_text(
        session, "while false { 42 }"
    ) is None


def test_while_runaway_protected(session):
    """`while true { 1 }` would loop forever; the runtime cap raises."""
    with pytest.raises(RuntimeError):
        form_execute_text(session, "while true { 1 }")


# ---------------------------------------------------------------------------
# set on its own
# ---------------------------------------------------------------------------


def test_set_updates_existing_binding(session):
    assert form_execute_text(
        session, "do { let x = 5; set x = 99; x }"
    ) == 99


def test_set_without_binding_raises(session):
    with pytest.raises(NameError):
        form_execute_text(session, "set z = 5")


def test_set_walks_to_outer_frame(session):
    """`set` finds the nearest enclosing binding, not just the current frame."""
    assert form_execute_text(
        session,
        "do { let x = 1; do { set x = 99 }; x }"
    ) == 99


def test_set_vs_let_distinction(session):
    """`let` inside a sub-block introduces; `set` mutates the outer."""
    # let creates a NEW x in the inner block; outer x stays.
    assert form_execute_text(
        session,
        "do { let x = 1; do { let x = 99 }; x }"
    ) == 1
