"""Source round-trip fidelity: text → Recipe → text' → Recipe' is identity.

The substrate is content-addressed. Two textually-different surfaces of
the same shape intern to the same Recipe NodeID. This test verifies the
inverse: the canonical text emitted by `recipe_to_form`, when re-parsed
through `form_evaluate_text`, produces the same Recipe NodeID.

Three properties checked:

1. **Round-trip identity** — for every supported source expression,
   parse → decompile → re-parse produces the same Recipe NodeID.

2. **Equivalence-class absorption** — textually-different but semantically-
   identical surfaces (whitespace, redundant parens, comments) all map
   to the same Recipe NodeID. The decompiler's output is one
   representative of that equivalence class.

3. **Fine-grained discrimination** — semantically-different expressions
   intern to DIFFERENT Recipe NodeIDs. Content-addressing is fine enough
   to distinguish operator precedence, operator identity, operand order,
   conditional branches, and block contents.

Together these three are the strongest fidelity claim the substrate can
make at the source layer: any prose statement of structural equivalence
between two pieces of code can be checked by decompiling and re-parsing.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.services.substrate import orm  # noqa: F401  (registers ORM)
from app.services.substrate import form_evaluate_text
from app.services.substrate.form_decompile import recipe_to_form


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


# (1) Round-trip identity

ROUND_TRIP_CASES = [
    "1 + 2",
    "1 - 2",
    "3 * 4",
    "10 / 2",
    "7 % 3",
    "1 + 2 * 3",
    "(1 + 2) * 3",
    "1 == 2",
    "1 != 2",
    "1 < 2",
    "1 <= 2",
    "3 > 2",
    "3 >= 2",
    "1 < 2 && 3 > 2",
    "1 == 2 || 3 == 3",
    "!(1 == 2)",
    "if 1 > 0 then 42 else 0",
    "if 1 == 1 then 99",
    # R_Block coverage (DO, SEQUENCE, LET) — added when running
    # idea-realization-engine through the substrate revealed
    # verb-category 1.2.9 (R_Block) was not yet decompilable.
    #
    # LET round-trip required two upstream changes that also landed in
    # this PR:
    #   1. RType.SLUG decoding in _trivial_value (form_runtime.py).
    #   2. Identifier interning as a SLUG via substrate_strings instead
    #      of a one-way hash at type=7 (form.py). The hash collided with
    #      RType.DATE and made the name unrecoverable.
    # Both fixed; LET now round-trips cleanly.
    "do { 1 + 2; 3 * 4 }",
    "do { 1 }",
    "let x = 42",
    "let answer = (1 + 2)",
    "let pi = 314",
]


@pytest.mark.parametrize("src", ROUND_TRIP_CASES)
def test_round_trip_preserves_recipe_node_id(session, src):
    """text → Recipe → text' → Recipe' yields the same Recipe NodeID."""
    r1 = form_evaluate_text(session, src).value
    emitted = recipe_to_form(session, r1)
    r2 = form_evaluate_text(session, emitted).value
    assert r1 == r2, (
        f"Round-trip failed:\n"
        f"  source     : {src!r}\n"
        f"  recipe r1  : {r1}\n"
        f"  decompiled : {emitted!r}\n"
        f"  recipe r2  : {r2}\n"
    )


# (2) Equivalence-class absorption

EQUIVALENCE_PAIRS = [
    ("1 + 2", "1+2"),
    ("1 + 2", "1   +   2"),
    ("1 + 2 * 3", "1 + (2 * 3)"),
    ("if x > 0 then 1 else 0", "if x>0 then 1 else 0"),
    ("do { let a = 1; a + 2 }", "do { let a = 1; a + 2 }"),
]


@pytest.mark.parametrize("left,right", EQUIVALENCE_PAIRS)
def test_textually_different_expressions_intern_to_same_recipe(session, left, right):
    """Whitespace / redundant-paren / comment differences are not structural."""
    nid_left = form_evaluate_text(session, left).value
    nid_right = form_evaluate_text(session, right).value
    assert nid_left == nid_right, (
        f"Expected same NodeID for textually-equivalent expressions:\n"
        f"  left  : {left!r}  →  {nid_left}\n"
        f"  right : {right!r}  →  {nid_right}\n"
    )


# (3) Fine-grained discrimination

DIFFERENCE_PAIRS = [
    ("1 + 2 * 3", "(1 + 2) * 3"),       # precedence
    ("a + b", "a - b"),                  # operator identity
    ("a - b", "b - a"),                  # operand order (non-commutative)
    ("if x then 1 else 0", "if x then 0 else 1"),    # conditional branches
    ("do { let a = 1; a + 2 }", "do { let a = 1; a * 2 }"),  # block contents
]


@pytest.mark.parametrize("left,right", DIFFERENCE_PAIRS)
def test_semantically_different_expressions_intern_to_different_recipes(session, left, right):
    """Semantic differences produce different NodeIDs. No accidental collision."""
    nid_left = form_evaluate_text(session, left).value
    nid_right = form_evaluate_text(session, right).value
    assert nid_left != nid_right, (
        f"NodeID collision between semantically-different expressions:\n"
        f"  left  : {left!r}  →  {nid_left}\n"
        f"  right : {right!r}  →  {nid_right}\n"
        f"Content-addressing must be fine enough to distinguish these."
    )
