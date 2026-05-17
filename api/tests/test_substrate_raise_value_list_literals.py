"""List literals execute, raise carries values, catch sees them as .self.

Three gaps surfaced from running Form expressions against the live substrate:
- `[1, 2, 3]` raised TypeError "cannot execute list" — no runtime handler
- `raise <value>` was a SyntaxError — parser only accepted bare `raise`
- `try { raise X } catch { ... }` couldn't see the raised value
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate.form_runtime import (
    RaiseSignal,
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
# List literals execute
# ---------------------------------------------------------------------------


def test_list_of_ints_evaluates(session):
    assert form_execute_text(session, "[1, 2, 3]") == [1, 2, 3]


def test_list_of_expressions_evaluates_each(session):
    assert form_execute_text(session, "[1 + 1, 2 + 2, 3 + 3]") == [2, 4, 6]


def test_empty_list_evaluates(session):
    assert form_execute_text(session, "[]") == []


def test_nested_list_evaluates(session):
    assert form_execute_text(session, "[[1, 2], [3, 4]]") == [[1, 2], [3, 4]]


# ---------------------------------------------------------------------------
# raise with value
# ---------------------------------------------------------------------------


def test_raise_with_string_value(session):
    with pytest.raises(RaiseSignal) as exc_info:
        form_execute_text(session, 'raise "oops"')
    assert exc_info.value.payload == "oops"


def test_raise_with_int_value(session):
    with pytest.raises(RaiseSignal) as exc_info:
        form_execute_text(session, "raise 42")
    assert exc_info.value.payload == 42


def test_raise_with_no_value_stays_compatible(session):
    """Bare `raise` still works (back-compat)."""
    with pytest.raises(RaiseSignal) as exc_info:
        form_execute_text(session, "raise")
    assert exc_info.value.payload is None


# ---------------------------------------------------------------------------
# Catch sees the raised value as .self
# ---------------------------------------------------------------------------


def test_catch_sees_raised_string(session):
    assert form_execute_text(
        session, 'try { raise "oops" } catch { .self }'
    ) == "oops"


def test_catch_sees_raised_int_and_can_compute(session):
    assert form_execute_text(
        session, "try { raise 42 } catch { .self + 1 }"
    ) == 43


def test_catch_without_payload_falls_through(session):
    """Bare raise without value — catch returns whatever the handler computes
    independent of .self (which would error if used)."""
    assert form_execute_text(
        session, "try { raise } catch { 99 }"
    ) == 99
