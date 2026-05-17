"""String literals recover their value at runtime.

The previous encoding was lossy: `StringLit` interned its instance as
`abs(hash(value)) % 10**9 + 1`, so `recipe_eval_text(s, '"hello"')` returned
a NodeID instead of the string. Switching to `intern_string_instance` /
`lookup_string_value` makes the round-trip work.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate.orm import SubstrateNamedCellORM, SubstrateNodeORM
from app.services.substrate.recipe_eval import eval_text


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
    try:
        yield s
        s.commit()
    finally:
        s.close()


def test_string_literal_round_trips(session):
    assert eval_text(session, '"hello"') == "hello"


def test_empty_string_round_trips(session):
    assert eval_text(session, '""') == ""


def test_repeated_string_dedupes_and_recovers(session):
    """Two evals of the same string return the same value (and same NodeID)."""
    a = eval_text(session, '"alpha"')
    b = eval_text(session, '"alpha"')
    assert a == b == "alpha"


def test_distinct_strings_recover_distinctly(session):
    """Different strings recover to their own values."""
    a = eval_text(session, '"first"')
    b = eval_text(session, '"second"')
    assert a == "first"
    assert b == "second"
    assert a != b


def test_string_with_unicode(session):
    """Non-ASCII characters survive the round-trip."""
    assert eval_text(session, '"café"') == "café"
    assert eval_text(session, '"🌱"') == "🌱"
