"""QUOTIENT RBasic arm — canonicalization under equivalence relations.

A recipe whose category is ``RBasic.QUOTIENT`` has the shape:

    QUOTIENT[carrier-recipe, equivalence-recipe]

Where ``equivalence-recipe`` is itself a substrate cell describing the
equivalence relation. When a *value* of the quotient type is interned
(via :func:`intern_quotient_value`), the equivalence-recipe's
``canonicalize_fn`` runs first; the canonical form is what hits the
intern table. Two values equivalent under the relation therefore receive
the SAME NodeID — content-addressing IS the quotient.

This generalizes the canonicalization the numeric-format library already
performs (NaN → quiet, ±0 → +0). The shape: equivalence-recipes are
**substrate cells**, not hardcoded kernel logic. Adding a new equivalence
is a substrate write — the kernel reads the cell and dispatches the
``canonicalize_fn`` via the handler-name registry. The body grows; the
kernel stays small.

See ``docs/coherence-substrate/higher-math-surface.md`` for the full
design (PROOF / INDUCTIVE / symmetry-aware canonicalization all build on
this foundation).

Cross-kernel: handler names are part of the cross-kernel contract. The
TS kernel (:mod:`form/form-kernel-ts/src/quotient.ts`) registers
the same ``integer-from-nat-pair``, ``rational-from-int-pair``,
``commutative-pair``, ``associative-left-fold`` handler names, so a Form
program ingested into either kernel canonicalizes identically. New
built-in equivalences are a cross-kernel coordination breath; Form-
program-local equivalences (handler-as-Form-recipe) need no
coordination.

Decidability + cost policy:

- ``DECIDABLE_CHEAP`` → EAGER canonicalize at intern, fast equality
- ``DECIDABLE_HEAVY`` → LAZY canonicalize on equality query
- ``UNDECIDABLE``    → LAZY (no eager option); future: requires explicit
                       proof recipe to merge NodeIDs

Honest default: EAGER unless the equivalence declares heavy or
undecidable.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.services.substrate.category import Level, RBasic, RType
from app.services.substrate.kernel import (
    DOMAIN_BLUEPRINT,
    DOMAIN_RECIPE,
    NodeID,
    intern_node,
    lookup_node,
)
from app.services.substrate.substrate_strings import (
    intern_string_instance,
    lookup_string_value,
)


# ---------------------------------------------------------------------------
# Decidability + canonicalization-strategy metadata
# ---------------------------------------------------------------------------


class Decidability(IntEnum):
    """How tractable an equivalence is — controls eager/lazy strategy."""
    UNDEFINED = 0
    # Effective algorithm, cheap to run — canonicalize eagerly.
    DECIDABLE_CHEAP = 1
    # Effective algorithm, expensive (e.g. Knuth-Bendix) — canonicalize lazily.
    DECIDABLE_HEAVY = 2
    # No effective algorithm (function-equality, group iso in general).
    UNDECIDABLE = 3


class CanonStrategy(IntEnum):
    """When the canonicalize_fn fires."""
    UNDEFINED = 0
    EAGER = 1
    LAZY = 2


# Per-equivalence canonicalization. Operates on a value's children (the
# raw representative) and returns the canonical-children-tuple. Returning
# the same tuple-shape for any two equivalent inputs is the
# canonicalize_fn's job; the kernel handles the content-addressing.
CanonicalizeFn = Callable[[Session, Sequence[NodeID]], Sequence[NodeID]]


# ---------------------------------------------------------------------------
# Handler registry — name → CanonicalizeFn
#
# In the cross-kernel design the handler-name is itself a substrate
# string trivial; resolution is "look up the registered fn by name".
# Form programs construct equivalence-recipes purely as substrate writes;
# the kernel side of the registry binds the name to a runtime fn. New
# equivalences arrive in two halves: a substrate write (the recipe) and
# a handler registration (the runtime). For purely-Form equivalences
# (canonicalize_fn expressed AS a Form recipe), the handler is a single
# "walk-this-recipe" stub — but that path is follow-up work.
# ---------------------------------------------------------------------------


_HANDLERS: Dict[str, CanonicalizeFn] = {}


def register_handler(name: str, fn: CanonicalizeFn) -> None:
    """Register a canonicalize-fn under a stable name.

    Same name across Python / TS / Go / Rust kernels yields cross-kernel
    NodeID agreement for the same equivalence relation.
    """
    _HANDLERS[name] = fn


def get_handler(name: str) -> Optional[CanonicalizeFn]:
    """Look up a registered handler by name. Returns None if unknown."""
    return _HANDLERS.get(name)


def _strategy_for(decidability: Decidability) -> CanonStrategy:
    """Honest defaults: eager unless the equivalence declares heavy.
    Undecidable equivalences are necessarily lazy (no eager option).
    """
    if decidability == Decidability.DECIDABLE_CHEAP:
        return CanonStrategy.EAGER
    return CanonStrategy.LAZY


# ---------------------------------------------------------------------------
# Trivial-leaf encoding helpers
#
# The Python kernel's existing ``form_builders._int_id`` encodes a
# non-negative int as ``instance = value + 1`` and collapses every
# negative to instance 0. That's lossy — QUOTIENT canonical forms need to
# round-trip signed integers (the integer-from-nat-pair canonical form is
# ``(a-b, 0)`` which can be negative). We use a sign-bijection here:
#
#     v >= 0  →  instance = 2*v + 1     (odd positives)
#     v < 0   →  instance = 2*(-v)      (even positives, encodes negatives)
#
# Decoded by halving. This keeps the trivial NodeIDs in the
# (Level.TRIVIAL, RType.INTEGER) shard so they share with the rest of the
# kernel's trivial-int allocation, but the instance numbering scheme is
# the one this module uses internally for round-tripping.
# ---------------------------------------------------------------------------


def _int_trivial_id(value: int) -> NodeID:
    """Encode a (possibly negative) int as a Trivial RType.INTEGER NodeID
    with a bijective instance encoding."""
    if value >= 0:
        instance = 2 * value + 1
    else:
        instance = 2 * (-value)
    return NodeID(1, Level.TRIVIAL, RType.INTEGER, instance)


def _int_trivial_value(nid: NodeID) -> int:
    """Decode an int encoded by :func:`_int_trivial_id`. Raises if the
    NodeID isn't a sign-bijection integer trivial."""
    if nid.level != Level.TRIVIAL or nid.type_ != RType.INTEGER:
        raise ValueError(
            f"quotient: NodeID {nid} is not a trivial INTEGER"
        )
    inst = nid.instance
    if inst == 0:
        return 0
    if inst % 2 == 1:
        return (inst - 1) // 2
    return -(inst // 2)


def _string_trivial_id(session: Session, value: str) -> NodeID:
    """Encode a string as a Trivial RType.STRING NodeID via the string-table.

    Cross-process stable — same string always maps to the same instance.
    """
    inst = intern_string_instance(session, value)
    return NodeID(1, Level.TRIVIAL, RType.STRING, inst)


def _string_trivial_value(session: Session, nid: NodeID) -> str:
    """Decode a string trivial NodeID via the substrate string-table."""
    if nid.level != Level.TRIVIAL or nid.type_ != RType.STRING:
        raise ValueError(
            f"quotient: NodeID {nid} is not a trivial STRING"
        )
    value = lookup_string_value(session, nid.instance)
    if value is None:
        raise ValueError(
            f"quotient: string trivial {nid} has no entry in the string table"
        )
    return value


def _row_category_instance(session: Session, nid: NodeID) -> Optional[int]:
    """Read the category-instance baked into a composite row's serialized
    prefix. Returns None for trivials (no row, or no children to imply a
    category-instance encoding).

    The Python kernel's ``intern_node`` auto-allocates the resulting
    NodeID's instance but flows the *category*'s instance through into
    the serialized string ("p.l.t.<cat_inst>+child0+child1+..."). For
    QUOTIENT values we use the category instance to distinguish
    canonical (inst=2) from lazy (inst=3) representations.
    """
    row = lookup_node(session, nid)
    if row is None or not row.serialized:
        return None
    head = row.serialized.split("+", 1)[0]
    parts = head.split(".")
    if len(parts) != 4:
        return None
    try:
        return int(parts[3])
    except ValueError:
        return None


def _node_children(session: Session, nid: NodeID) -> List[NodeID]:
    """Ordered children of a composite NodeID. Empty list for trivials.

    Mirrors :func:`form_runtime._node_children` — we inline it here so
    quotient.py keeps no upward dependency on form_runtime (which has
    much heavier dependencies).
    """
    row = lookup_node(session, nid)
    if row is None or not row.serialized:
        return []
    parts = row.serialized.split("+")
    if len(parts) <= 1:
        return []
    out: List[NodeID] = []
    for piece in parts[1:]:
        a, b, c, d = piece.split(".")
        out.append(NodeID(int(a), int(b), int(c), int(d)))
    return out


# ---------------------------------------------------------------------------
# EquivalenceRelation — the substrate-resident relation descriptor
#
# In a Form program this is itself a recipe whose category is a known
# equivalence-relation type (handler_name resolves to a registered fn).
# For the Python proof-of-shape we hold the in-memory side here as a thin
# wrapper; the substrate-cell projection (a recipe carrying name +
# decidability + handler_name as children) is interned in parallel for
# cross-kernel agreement.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EquivalenceRelation:
    """A substrate-resident equivalence relation.

    ``node_id`` is the content-addressed NodeID of the equivalence
    recipe. Two equivalences bootstrapped with the same shape in the
    same kernel share NodeIDs by construction.
    """
    equivalence_name: str
    decidability: Decidability
    strategy: CanonStrategy
    is_decidable: bool
    handler_name: str
    canonicalize_fn: CanonicalizeFn
    node_id: NodeID


# The equivalence-recipe lives at a sibling category to QUOTIENT itself
# (so the equivalence cells don't collide with QUOTIENT recipes). We
# reuse the (pkg=1, Level.BASIC) shard with type = RBasic.QUOTIENT + 1
# to match the TS kernel's slot assignment (EQUIV_CATEGORY_TYPE = 71).
_EQUIV_CATEGORY_PKG = 1
_EQUIV_CATEGORY_LEVEL = Level.BASIC
_EQUIV_CATEGORY_TYPE = RBasic.QUOTIENT + 1  # 71


def _make_equivalence_cell(
    session: Session,
    equivalence_name: str,
    decidability: Decidability,
    strategy: CanonStrategy,
    handler_name: str,
) -> NodeID:
    """Intern the equivalence-recipe shape into the substrate.

    Stored shape (children, all substrate-resident):

        [ name-trivial, decidability-int, strategy-int, handler-name-trivial ]

    The category instance is the decidability code so the NodeID's
    instance already encodes the major axis without a child lookup.
    Two recipes with identical children intern to the SAME NodeID —
    equivalences are content-addressed like everything else.
    """
    category = NodeID(
        _EQUIV_CATEGORY_PKG,
        _EQUIV_CATEGORY_LEVEL,
        _EQUIV_CATEGORY_TYPE,
        int(decidability),
    )
    children = [
        _string_trivial_id(session, equivalence_name),
        _int_trivial_id(int(decidability)),
        _int_trivial_id(int(strategy)),
        _string_trivial_id(session, handler_name),
    ]
    return intern_node(session, DOMAIN_BLUEPRINT, category, children)


def make_equivalence(
    session: Session,
    *,
    equivalence_name: str,
    decidability: Decidability,
    handler_name: str,
) -> EquivalenceRelation:
    """Register a new equivalence relation as a substrate cell.

    The handler must already be registered under ``handler_name``
    (see :func:`register_handler`). Returns the EquivalenceRelation
    handle (carrying the substrate cell NodeID).
    """
    handler = _HANDLERS.get(handler_name)
    if handler is None:
        raise ValueError(
            f"quotient: handler {handler_name!r} is not registered"
        )
    strategy = _strategy_for(decidability)
    nid = _make_equivalence_cell(
        session,
        equivalence_name,
        decidability,
        strategy,
        handler_name,
    )
    return EquivalenceRelation(
        equivalence_name=equivalence_name,
        decidability=decidability,
        strategy=strategy,
        is_decidable=(decidability != Decidability.UNDECIDABLE),
        handler_name=handler_name,
        canonicalize_fn=handler,
        node_id=nid,
    )


def resolve_equivalence(
    session: Session, equiv_nid: NodeID
) -> EquivalenceRelation:
    """Resolve the EquivalenceRelation handle from a substrate-cell NodeID.

    The equivalence cell's children carry
    ``[name, decidability, strategy, handler-name]``; we decode and look
    up the registered handler.
    """
    kids = _node_children(session, equiv_nid)
    if len(kids) != 4:
        raise ValueError(
            f"resolve_equivalence: malformed equivalence cell {equiv_nid} "
            f"(children={len(kids)}, expected 4)"
        )
    name = _string_trivial_value(session, kids[0])
    dec = _int_trivial_value(kids[1])
    strat = _int_trivial_value(kids[2])
    hname = _string_trivial_value(session, kids[3])
    handler = _HANDLERS.get(hname)
    if handler is None:
        raise ValueError(
            f"resolve_equivalence: handler {hname!r} not registered in this kernel"
        )
    decidability = Decidability(dec)
    strategy = CanonStrategy(strat)
    return EquivalenceRelation(
        equivalence_name=name,
        decidability=decidability,
        strategy=strategy,
        is_decidable=(decidability != Decidability.UNDECIDABLE),
        handler_name=hname,
        canonicalize_fn=handler,
        node_id=equiv_nid,
    )


# ---------------------------------------------------------------------------
# QUOTIENT recipe construction
# ---------------------------------------------------------------------------


# Three distinct categories within the QUOTIENT slot, distinguished by the
# category instance baked into the serialized form:
#   inst=1 — the QUOTIENT recipe itself (carrier + equivalence)
#   inst=2 — a canonicalized quotient *value*
#   inst=3 — a lazy (un-canonicalized) quotient value
#
# In the TS kernel, the NodeID inst value preserved by the interner is what
# carries this distinction. In the Python kernel, the interner auto-allocates
# the inst value of the *resulting* NodeID — but the category-instance value
# still flows through ``serialize_tree`` into the row's serialized field,
# so two values with different category-instances always land at different
# rows. We use the serialized prefix (read from the row) to determine
# canon-vs-lazy after the fact.
_QUOTIENT_INST_RECIPE = 1
_QUOTIENT_INST_VALUE_CANON = 2
_QUOTIENT_INST_VALUE_LAZY = 3


def make_quotient_recipe(
    session: Session, carrier: NodeID, equivalence: NodeID
) -> NodeID:
    """Intern a ``QUOTIENT[carrier, equivalence]`` recipe.

    The carrier is the underlying recipe whose values get quotiented;
    the equivalence recipe carries canonicalization rules. Same
    ``(carrier, equivalence)`` pair always interns to the same NodeID
    (content-addressing).
    """
    category = NodeID(1, Level.BASIC, RBasic.QUOTIENT, _QUOTIENT_INST_RECIPE)
    return intern_node(session, DOMAIN_RECIPE, category, [carrier, equivalence])


def quotient_parts(
    session: Session, quotient_recipe: NodeID
) -> Tuple[NodeID, NodeID]:
    """Inspect a QUOTIENT recipe: return ``(carrier, equivalence)``.

    The level of the interned recipe is bumped to ``COMPLEX_1`` by the
    Python kernel's ``intern_node`` (children-of-BASIC-category always
    sit at COMPLEX_1+); we identify QUOTIENT recipes by ``type_`` and
    ``instance`` rather than ``level``.
    """
    if quotient_recipe.type_ != RBasic.QUOTIENT:
        raise ValueError(
            f"quotient_parts: {quotient_recipe} is not a QUOTIENT recipe"
        )
    kids = _node_children(session, quotient_recipe)
    if len(kids) != 2:
        raise ValueError(
            f"quotient_parts: malformed QUOTIENT recipe (children={len(kids)})"
        )
    return kids[0], kids[1]


# ---------------------------------------------------------------------------
# Interning a value through a quotient
#
#   intern_quotient_value(session, quotient_recipe, raw_children)
#
# ``raw_children`` are the carrier-shape children of the raw value (e.g.
# ``[int(3), int(1)]`` for an integer-from-nat-pair representative). The
# equivalence's canonicalize_fn reduces them to canonical-children; the
# kernel then interns a recipe whose category is the QUOTIENT cell and
# whose children are the canonical-children. Two equivalent raw values
# therefore produce the SAME NodeID — that's the quotient.
#
# Strategy = EAGER: canonicalize NOW, then intern canonical form.
# Strategy = LAZY:  intern raw form (as a different recipe shape that
#                   carries the `lazy` marker); equality_query
#                   canonicalizes on demand. The shapes differ
#                   structurally so the raw form has its own NodeID;
#                   equality queries route through
#                   canonicalize-then-compare.
# ---------------------------------------------------------------------------


def intern_quotient_value(
    session: Session,
    quotient_recipe: NodeID,
    raw_children: Sequence[NodeID],
) -> NodeID:
    """Intern a value through a quotient. Returns the value's NodeID.

    Under EAGER strategy two equivalent representatives receive the same
    NodeID immediately. Under LAZY strategy the raw representatives get
    distinct NodeIDs; call :func:`canonical_form` (or
    :func:`quotient_equal`) to merge them on demand.
    """
    _carrier, equivalence = quotient_parts(session, quotient_recipe)
    eq = resolve_equivalence(session, equivalence)

    if eq.strategy == CanonStrategy.EAGER:
        canonical = list(eq.canonicalize_fn(session, raw_children))
        category = NodeID(
            1, Level.BASIC, RBasic.QUOTIENT, _QUOTIENT_INST_VALUE_CANON
        )
        return intern_node(
            session, DOMAIN_RECIPE, category, [quotient_recipe, *canonical]
        )

    # LAZY: intern the raw form with a distinct inst marker so eager- and
    # lazy-shapes don't collide. The canonical form computed on-equality
    # shares the inst=2 slot with the eager path, so cross-strategy hits
    # still land at the same canonical NodeID once forced.
    category = NodeID(
        1, Level.BASIC, RBasic.QUOTIENT, _QUOTIENT_INST_VALUE_LAZY
    )
    return intern_node(
        session, DOMAIN_RECIPE, category, [quotient_recipe, *list(raw_children)]
    )


def canonical_form(session: Session, quotient_value: NodeID) -> NodeID:
    """Force-canonicalize a value (eager or lazy) and return its
    canonical NodeID.

    Used by equality queries and by callers that want to merge
    equivalent representatives explicitly.
    """
    if quotient_value.type_ != RBasic.QUOTIENT:
        raise ValueError(
            f"canonical_form: {quotient_value} is not a QUOTIENT value"
        )
    kids = _node_children(session, quotient_value)
    if not kids:
        raise ValueError("canonical_form: malformed quotient value")
    quotient_recipe = kids[0]
    rest = kids[1:]
    cat_inst = _row_category_instance(session, quotient_value)
    if cat_inst == _QUOTIENT_INST_VALUE_CANON:
        return quotient_value
    # Lazy (inst=3) — canonicalize and re-intern as inst=2.
    _carrier, equivalence = quotient_parts(session, quotient_recipe)
    eq = resolve_equivalence(session, equivalence)
    canonical = list(eq.canonicalize_fn(session, rest))
    category = NodeID(
        1, Level.BASIC, RBasic.QUOTIENT, _QUOTIENT_INST_VALUE_CANON
    )
    return intern_node(
        session, DOMAIN_RECIPE, category, [quotient_recipe, *canonical]
    )


def quotient_equal(session: Session, a: NodeID, b: NodeID) -> bool:
    """Equality under the quotient. Two values are equal iff their
    canonical forms share a NodeID."""
    ca = canonical_form(session, a)
    cb = canonical_form(session, b)
    return ca == cb


# ---------------------------------------------------------------------------
# Built-in equivalence relations
#
# Each registers a handler under a stable name and constructs the
# substrate-resident equivalence-recipe. The names are part of the
# cross-kernel contract — Python / TS / Go / Rust register the same
# handler names so a Form program ingested into any kernel canonicalizes
# identically.
# ---------------------------------------------------------------------------


# ── integer-from-nat-pair ────────────────────────────────────────────────
# Integers as Z := (N × N) / ~ where (a, b) ~ (c, d) iff a + d = b + c.
# Canonical representative: (a - b, 0) — sign carried by the difference.


def _handler_integer_from_nat_pair(
    session: Session, raw: Sequence[NodeID]
) -> Sequence[NodeID]:
    if len(raw) != 2:
        raise ValueError(
            f"integer-from-nat-pair: expected 2 children, got {len(raw)}"
        )
    a = _int_trivial_value(raw[0])
    b = _int_trivial_value(raw[1])
    if a < 0 or b < 0:
        raise ValueError(
            "integer-from-nat-pair: natural-number pair must be non-negative"
        )
    diff = a - b
    return [_int_trivial_id(diff), _int_trivial_id(0)]


# ── rational-from-int-pair ───────────────────────────────────────────────
# Rationals as Q := (Z × Z*) / ~ where (p, q) ~ (r, s) iff p*s = q*r.
# Canonical form: (p/gcd, q/gcd) with sign normalized into the numerator.


def _gcd(a: int, b: int) -> int:
    a = abs(a)
    b = abs(b)
    while b != 0:
        a, b = b, a % b
    return a if a != 0 else 1


def _handler_rational_from_int_pair(
    session: Session, raw: Sequence[NodeID]
) -> Sequence[NodeID]:
    if len(raw) != 2:
        raise ValueError(
            f"rational-from-int-pair: expected 2 children, got {len(raw)}"
        )
    p = _int_trivial_value(raw[0])
    q = _int_trivial_value(raw[1])
    if q == 0:
        raise ValueError("rational-from-int-pair: zero denominator")
    # Sign normalization — keep sign in numerator.
    if q < 0:
        p = -p
        q = -q
    g = _gcd(p, q)
    return [_int_trivial_id(p // g), _int_trivial_id(q // g)]


# ── commutative-pair ─────────────────────────────────────────────────────
# (a, b) ~ (b, a). Canonicalize by sorting on the NodeID's packed key.
# Works for any pair of substrate NodeIDs — no value-level constraint.


def _node_order_key(nid: NodeID) -> Tuple[int, int, int, int]:
    return (nid.package, nid.level, nid.type_, nid.instance)


def _handler_commutative_pair(
    session: Session, raw: Sequence[NodeID]
) -> Sequence[NodeID]:
    if len(raw) != 2:
        raise ValueError(
            f"commutative-pair: expected 2 children, got {len(raw)}"
        )
    a, b = raw[0], raw[1]
    if _node_order_key(a) <= _node_order_key(b):
        return [a, b]
    return [b, a]


# ── associative-left-fold ────────────────────────────────────────────────
# For an N-ary binary op, canonicalize to a left-fold. At the children-
# tuple layer the proof-of-shape returns the children unchanged — real
# left-fold canonicalization needs recipe-tree access (parent-category
# matching for splicing) which is deferred to the symmetry-aware
# canonicalization arm. Structurally-equal inputs still share a NodeID,
# which is the minimum the equivalence promises at this layer.


def _handler_associative_left_fold(
    session: Session, raw: Sequence[NodeID]
) -> Sequence[NodeID]:
    return list(raw)


# ---------------------------------------------------------------------------
# Bootstrap registration
# ---------------------------------------------------------------------------


_HANDLERS_BOOTSTRAPPED = False


def _bootstrap_handlers() -> None:
    """Register the built-in handlers exactly once per process."""
    global _HANDLERS_BOOTSTRAPPED
    if _HANDLERS_BOOTSTRAPPED:
        return
    register_handler("integer-from-nat-pair", _handler_integer_from_nat_pair)
    register_handler("rational-from-int-pair", _handler_rational_from_int_pair)
    register_handler("commutative-pair", _handler_commutative_pair)
    register_handler("associative-left-fold", _handler_associative_left_fold)
    _HANDLERS_BOOTSTRAPPED = True


@dataclass(frozen=True)
class QuotientLibrary:
    """Bootstrap library of built-in equivalence relations."""
    EQUIV_INTEGER_FROM_NAT_PAIR: EquivalenceRelation
    EQUIV_RATIONAL_FROM_INT_PAIR: EquivalenceRelation
    EQUIV_COMMUTATIVE_PAIR: EquivalenceRelation
    EQUIV_ASSOCIATIVE_LEFT_FOLD: EquivalenceRelation


def build_quotient_library(session: Session) -> QuotientLibrary:
    """Bootstrap-register handlers and intern the canonical equivalence
    cells. Idempotent — calling twice returns identical NodeIDs."""
    _bootstrap_handlers()
    return QuotientLibrary(
        EQUIV_INTEGER_FROM_NAT_PAIR=make_equivalence(
            session,
            equivalence_name="integer-from-nat-pair",
            decidability=Decidability.DECIDABLE_CHEAP,
            handler_name="integer-from-nat-pair",
        ),
        EQUIV_RATIONAL_FROM_INT_PAIR=make_equivalence(
            session,
            equivalence_name="rational-from-int-pair",
            decidability=Decidability.DECIDABLE_CHEAP,
            handler_name="rational-from-int-pair",
        ),
        EQUIV_COMMUTATIVE_PAIR=make_equivalence(
            session,
            equivalence_name="commutative-pair",
            decidability=Decidability.DECIDABLE_CHEAP,
            handler_name="commutative-pair",
        ),
        EQUIV_ASSOCIATIVE_LEFT_FOLD=make_equivalence(
            session,
            equivalence_name="associative-left-fold",
            decidability=Decidability.DECIDABLE_CHEAP,
            handler_name="associative-left-fold",
        ),
    )


# ---------------------------------------------------------------------------
# Convenience exports for tests / callers
# ---------------------------------------------------------------------------


__all__ = [
    "CanonStrategy",
    "CanonicalizeFn",
    "Decidability",
    "EquivalenceRelation",
    "QuotientLibrary",
    "build_quotient_library",
    "canonical_form",
    "get_handler",
    "intern_quotient_value",
    "make_equivalence",
    "make_quotient_recipe",
    "quotient_equal",
    "quotient_parts",
    "register_handler",
    "resolve_equivalence",
]
