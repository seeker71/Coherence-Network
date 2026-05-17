"""String interpolation and multiline strings.

Two tactical gaps from the named follow-on list:

- "hello {dollar}{open}name{close}" desugars at parse-time to a concat
  chain of str(expr) and string literals — so the surface stays natural
  while the runtime gets a BinOp tree it already knows how to evaluate.
- Triple-quoted multiline strings extend the STRING regex to capture
  any content (including newlines) between the markers.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate.form_runtime import form_execute_text, reset_runtime_registries
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
# Interpolation
# ---------------------------------------------------------------------------


def test_plain_string_still_works(session):
    assert form_execute_text(session, '"hello"') == "hello"


def test_interpolation_with_arithmetic(session):
    assert form_execute_text(session, '"hello ${1 + 2}"') == "hello 3"


def test_interpolation_with_let_binding(session):
    assert form_execute_text(
        session, 'do { let name = "world"; "hello ${name}" }'
    ) == "hello world"


def test_interpolation_alone(session):
    # Whole-string interpolation case.
    assert form_execute_text(session, '"${5 * 6}"') == "30"


def test_multiple_interpolations(session):
    assert form_execute_text(
        session,
        'do { let x = 10; "x is ${x} and 2x is ${x * 2}" }',
    ) == "x is 10 and 2x is 20"


def test_interpolation_at_start(session):
    assert form_execute_text(
        session, '"${1} apple"'
    ) == "1 apple"


def test_interpolation_in_method_body(session):
    # Interpolation works inside methods, with .self visible.
    from app.services.substrate import BID_concept, make_cell
    make_cell(session, name="lc-greet", domain="concept", blueprint=BID_concept())
    session.commit()
    form_execute_text(
        session, 'method label on @concept(lc-greet) { "${.self.name}!" }'
    )
    assert form_execute_text(
        session, "invoke label on @concept(lc-greet)"
    ) == "lc-greet!"


def test_unterminated_interpolation_raises(session):
    with pytest.raises(SyntaxError):
        form_execute_text(session, '"hello ${missing"')


# ---------------------------------------------------------------------------
# Multiline strings — """..."""
# ---------------------------------------------------------------------------


def test_multiline_string_captures_newlines(session):
    v = form_execute_text(session, '"""line 1\nline 2\nline 3"""')
    assert v == "line 1\nline 2\nline 3"


def test_multiline_string_with_internal_quotes(session):
    # Triple-quoted strings allow embedded single double-quotes without escape.
    v = form_execute_text(session, '"""he said "hi" and left"""')
    assert v == 'he said "hi" and left'


def test_multiline_string_empty(session):
    assert form_execute_text(session, '""""""') == ""


def test_multiline_string_with_interpolation(session):
    # Interpolation markers work inside triple-quoted strings too.
    assert form_execute_text(
        session,
        'do { let n = 7; """value:\n  ${n}\n""" }',
    ) == "value:\n  7\n"
