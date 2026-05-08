"""Substrate-resident grammar — the seed of BMF-shaped parsing.

The current `form.py` is a *bootstrap* parser: hand-written recursive
descent with a regex lexer. It produces correct results, but its grammar
lives in Python code, not in the substrate. That makes it static — to add
a new construct, you edit form.py.

BMF (Backtracking Model Form), Bjorg's 2000 thesis foundation, took the
opposite approach: every grammar rule was *data*, not code. A rule was a
(pattern, semantic_action) pair where the pattern matched input and the
action was an executable that fired when the pattern matched. New rules
could be registered at runtime; the grammar grew with the body.

This module is the seed of that capability for Form. It introduces:

  - The `grammar` domain — a new cell-domain whose cells are parse rules.
  - `Rule` shape — pattern + action, stored as a Recipe with two children.
  - `register_form_rule(pattern, action)` — interns a Rule and creates a
    cell in the grammar domain.
  - `list_form_rules()` — enumerate rules for an agent reasoning about
    the parser itself.

What's NOT in this module yet (deferred to a future session):

  - The rule-driven parser that consumes input by walking grammar cells.
  - Self-hosting (the Form-grammar-of-Form expressed as Form rules).
  - Backtracking-without-sediment at the parser level (Choice.FAIL
    unwinding partial parser state).

The teaching: the gap between "we have rules in the substrate" and "the
parser uses those rules" is real. Closing it is its own breath. Naming
the gap and shipping the seed of the grammar-as-data architecture is
the honest movement we can make now.

Lineage: see `docs/field/urs/artifacts/master-thesis-2000/companion/`
(BMF grammar samples in `source-samples/BMF-grammar.bml`,
`bml-search-algorithms.txt`, `angelic-assembler.txt`).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy.orm import Session

from app.services.substrate.category import BBasic, BDomain, Level, RBasic
from app.services.substrate.kernel import (
    DOMAIN_RECIPE,
    NamedCell,
    NodeID,
    intern_node,
    lookup_cell,
    make_cell,
)
from app.services.substrate.orm import SubstrateNamedCellORM


# ---------------------------------------------------------------------------
# The Grammar blueprint — trivial domain blueprint for parse rules
# ---------------------------------------------------------------------------


def BID_grammar() -> NodeID:
    """The trivial Grammar domain blueprint.

    Cells in the `grammar` domain are parse rules. Their CTOR is a Block
    recipe with two children: pattern + action.
    """
    return NodeID(1, Level.BASIC, BBasic.DOMAIN, BDomain.GRAMMAR)


# ---------------------------------------------------------------------------
# Rule shape — interned as a Recipe with (pattern, action) children
# ---------------------------------------------------------------------------


@dataclass
class FormRule:
    """A parse rule: pattern + action, addressable by NodeID.

    `pattern` is a Recipe NodeID describing what input shape this rule
    matches (e.g. a sequence of literal tokens + sub-rule references).

    `action` is a Recipe NodeID describing what to produce when the rule
    fires — typically a composition expression that builds an AST node.

    `name` is a human-readable label for the rule (e.g. "if_expr",
    "binary_compare"). The rule is also addressable as a Cell in the
    grammar domain under this name.
    """

    name: str
    pattern: NodeID
    action: NodeID
    cell: Optional[NamedCell] = None
    rule_recipe: Optional[NodeID] = None


def _rule_category() -> NodeID:
    """Recipe category for grammar rules — Block.SEQUENCE used as a marker."""
    from app.services.substrate.category import RBlock
    return NodeID(1, Level.BASIC, RBasic.BLOCK, RBlock.SEQUENCE)


def register_form_rule(
    session: Session, name: str, pattern: NodeID, action: NodeID
) -> FormRule:
    """Intern a (pattern, action) pair as a parse rule.

    The rule is stored two ways:
      1. As a Recipe (the rule_recipe NodeID) — content-addressed by the
         (pattern, action) shape. Two structurally-identical rules dedupe.
      2. As a NamedCell in the `grammar` domain — addressable by name.

    A future rule-driven parser will enumerate cells in the grammar domain,
    sort them by precedence (encoded in the action), and dispatch input
    against patterns in order.
    """
    rule_recipe = intern_node(
        session, DOMAIN_RECIPE, _rule_category(), [pattern, action]
    )
    cell = make_cell(
        session,
        name=name,
        domain="grammar",
        blueprint=BID_grammar(),
        ctor=rule_recipe,
    )
    return FormRule(
        name=name, pattern=pattern, action=action,
        cell=cell, rule_recipe=rule_recipe,
    )


def lookup_form_rule(session: Session, name: str) -> Optional[FormRule]:
    cell = lookup_cell(session, "grammar", name)
    if cell is None:
        return None
    # Re-extract pattern + action from the rule_recipe by walking its row
    from app.services.substrate.orm import SubstrateNodeORM
    if cell.ctor is None:
        return FormRule(name=cell.name, pattern=NodeID.undefined(),
                        action=NodeID.undefined(), cell=cell)
    rule_row = (
        session.query(SubstrateNodeORM)
        .filter_by(
            package=cell.ctor.package, level=cell.ctor.level,
            type_=cell.ctor.type_, instance=cell.ctor.instance,
        )
        .one_or_none()
    )
    if rule_row is None:
        return FormRule(name=cell.name, pattern=NodeID.undefined(),
                        action=NodeID.undefined(), cell=cell, rule_recipe=cell.ctor)
    parts = rule_row.serialized.split("+")
    if len(parts) < 3:
        return FormRule(name=cell.name, pattern=NodeID.undefined(),
                        action=NodeID.undefined(), cell=cell, rule_recipe=cell.ctor)
    pattern = _parse_node_id(parts[1])
    action = _parse_node_id(parts[2])
    return FormRule(
        name=cell.name, pattern=pattern, action=action,
        cell=cell, rule_recipe=cell.ctor,
    )


def list_form_rules(session: Session) -> List[FormRule]:
    """Enumerate every parse rule registered in the grammar domain."""
    rows = session.query(SubstrateNamedCellORM).filter_by(domain="grammar").all()
    out = []
    for row in rows:
        rule = lookup_form_rule(session, row.name)
        if rule is not None:
            out.append(rule)
    return out


def _parse_node_id(s: str) -> NodeID:
    """Parse a 'p.l.t.i' string back into a NodeID."""
    parts = s.split(".")
    if len(parts) != 4:
        return NodeID.undefined()
    try:
        return NodeID(int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
    except ValueError:
        return NodeID.undefined()
