"""Tests for substrate-resident grammar — the BMF-shaped seed.

These tests cover Rule registration, lookup, and enumeration. They do
NOT yet exercise rule-driven parsing (which is future work). What they
prove: parse rules can be expressed as data in the substrate, content-
addressed, and recovered by name. That's the seed; the rule-driven
parser builds on top.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services.substrate import (
    BID_grammar,
    NodeID,
    list_form_rules,
    lookup_form_rule,
    register_form_rule,
)
from app.services.substrate.category import BBasic, BDomain, Level, RBasic, RMath
from app.services.substrate.kernel import DOMAIN_RECIPE, intern_node
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
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    try:
        yield s
        s.commit()
    finally:
        s.close()


def test_grammar_blueprint_is_distinct(session):
    """The Grammar domain blueprint is at instance 9 of BBasic.DOMAIN."""
    bp = BID_grammar()
    assert bp.level == Level.BASIC
    assert bp.type_ == BBasic.DOMAIN
    assert bp.instance == BDomain.GRAMMAR


def test_register_rule_creates_cell(session):
    """Registering a rule produces a NamedCell in the grammar domain."""
    # Build a tiny pattern + action by interning two trivial recipes
    pattern = NodeID(1, Level.TRIVIAL, 5, 1)  # placeholder STRING leaf
    action = intern_node(
        session, DOMAIN_RECIPE,
        NodeID(1, Level.BASIC, RBasic.MATH, RMath.PLUS),
        [NodeID(1, Level.TRIVIAL, 3, 1), NodeID(1, Level.TRIVIAL, 3, 2)],
    )

    rule = register_form_rule(session, "test_addition", pattern, action)
    assert rule.cell is not None
    assert rule.cell.domain == "grammar"
    assert rule.cell.name == "test_addition"
    assert rule.rule_recipe is not None


def test_lookup_rule_recovers_pattern_and_action(session):
    """Round-trip: register a rule, look it up, get back the same (pattern, action)."""
    pattern = NodeID(1, Level.TRIVIAL, 5, 7)
    action = intern_node(
        session, DOMAIN_RECIPE,
        NodeID(1, Level.BASIC, RBasic.MATH, RMath.MULTIPLY),
        [NodeID(1, Level.TRIVIAL, 3, 1), NodeID(1, Level.TRIVIAL, 3, 2)],
    )
    register_form_rule(session, "test_multiply", pattern, action)

    rule = lookup_form_rule(session, "test_multiply")
    assert rule is not None
    assert rule.pattern == pattern
    assert rule.action == action


def test_list_rules_returns_all(session):
    """Multiple rules registered in different sessions all enumerate."""
    p1 = NodeID(1, Level.TRIVIAL, 5, 1)
    p2 = NodeID(1, Level.TRIVIAL, 5, 2)
    a1 = intern_node(
        session, DOMAIN_RECIPE,
        NodeID(1, Level.BASIC, RBasic.MATH, RMath.PLUS),
        [NodeID(1, Level.TRIVIAL, 3, 1), NodeID(1, Level.TRIVIAL, 3, 2)],
    )
    a2 = intern_node(
        session, DOMAIN_RECIPE,
        NodeID(1, Level.BASIC, RBasic.MATH, RMath.MINUS),
        [NodeID(1, Level.TRIVIAL, 3, 3), NodeID(1, Level.TRIVIAL, 3, 4)],
    )
    register_form_rule(session, "rule_a", p1, a1)
    register_form_rule(session, "rule_b", p2, a2)

    rules = list_form_rules(session)
    names = {r.name for r in rules}
    assert "rule_a" in names
    assert "rule_b" in names


def test_register_same_rule_twice_dedups_recipe(session):
    """Two rules with identical (pattern, action) share a rule_recipe NodeID,
    even if they have different names. The CONTENT is what's content-addressed."""
    pattern = NodeID(1, Level.TRIVIAL, 5, 1)
    action = intern_node(
        session, DOMAIN_RECIPE,
        NodeID(1, Level.BASIC, RBasic.MATH, RMath.PLUS),
        [NodeID(1, Level.TRIVIAL, 3, 1), NodeID(1, Level.TRIVIAL, 3, 2)],
    )
    rule_a = register_form_rule(session, "alias_one", pattern, action)
    rule_b = register_form_rule(session, "alias_two", pattern, action)

    assert rule_a.rule_recipe == rule_b.rule_recipe
    # But the cells are distinct (different names = different cells)
    assert rule_a.cell.cell_id != rule_b.cell.cell_id
