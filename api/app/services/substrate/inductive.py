"""INDUCTIVE / CONSTRUCTOR / CHOICE arms — algebraic datatypes on the substrate.

This module mirrors :mod:`form/form-kernel-ts/src/inductive.ts`. An
inductive type is a substrate recipe whose category is ``RBasic.INDUCTIVE``
(slot 71). Its shape — defined here once, read everywhere by
content-addressing — is::

    INDUCTIVE[
      type-name        : Triv.STRING        ; "Nat", "List", ...
      type-params      : RBasic.LIST        ; parametric types (T, E, ...)
      ctor0            : RBasic.CONSTRUCTOR ; the type's constructors
      ctor1            : RBasic.CONSTRUCTOR ;
      ...
    ]

A constructor recipe is ``RBasic.CONSTRUCTOR`` (slot 72) with children::

    CONSTRUCTOR[
      inductive-ref    : NodeID  ; the inductive type this ctor belongs to
      ctor-name        : Triv.STRING
      ctor-index       : Triv.INT
      arg-type0        : NodeID  ; type-recipe (self-ref allowed)
      arg-type1        : NodeID
      ...
    ]

Constructor *application* — the value-shape — reuses the same
``RBasic.CONSTRUCTOR`` recipe shape but with concrete value-recipes in place
of arg-types. :func:`walk_constructor` walks one to a :class:`CtorValue`.

A pattern-match is a ``RBasic.CHOICE_MATCH`` recipe (slot 35)::

    CHOICE_MATCH[
      scrutinee,
      arm0-ctor-name : Triv.STRING,
      arm0-body      : NodeID,
      arm1-ctor-name : Triv.STRING,
      arm1-body      : NodeID,
      ...
    ]

:func:`walk_choice` verifies every constructor declared on the scrutinee's
inductive appears among the arms — non-total matches raise.

Because the recipes are content-addressed, two inductives defined with
identical name + identical params + identical constructor lists are the
SAME substrate cell. That is what the substrate's promise of structural
equivalence buys us here.

Cross-kernel: TS at slot 71 / 72 / 35 (see
``form/form-kernel-ts/src/inductive.ts``); Python at the same
slots. A Form program that defines ``Nat`` in either kernel produces
matching NodeIDs for ``Nat``, ``zero``, and ``succ`` — content-addressing
across kernels.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from app.services.substrate.category import Level, RBasic, RBlock, RType
from app.services.substrate.kernel import (
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
# Structural descriptions handed to the kernel at intern time
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstructorDef:
    """A constructor declaration on an inductive type."""

    ctor_name: str
    ctor_index: int
    # `arg_types` are NodeIDs of type-recipes. Self-reference uses the
    # parent inductive's type-name trivial as a sentinel (see make_inductive).
    arg_types: Tuple[NodeID, ...]


@dataclass(frozen=True)
class InductiveType:
    """Structural description of an inductive type.

    The recipe interned into the substrate is the source of truth; this
    dataclass is the in-memory handle.
    """

    type_name: str
    type_params: Tuple[NodeID, ...]
    constructors: Tuple[ConstructorDef, ...]
    node_id: NodeID


# ---------------------------------------------------------------------------
# Trivial-leaf encoding helpers
#
# Match the quotient.py sign-bijective integer encoding so that ctor-index
# trivials live in the same shard as other integer trivials. Strings go
# through the existing substrate string table.
# ---------------------------------------------------------------------------


def _int_trivial_id(value: int) -> NodeID:
    """Encode a (possibly negative) int as a Trivial RType.INTEGER NodeID."""
    if value >= 0:
        instance = 2 * value + 1
    else:
        instance = 2 * (-value)
    return NodeID(1, Level.TRIVIAL, RType.INTEGER, instance)


def _int_trivial_value(nid: NodeID) -> int:
    """Decode an int encoded by :func:`_int_trivial_id`."""
    if nid.level != Level.TRIVIAL or nid.type_ != RType.INTEGER:
        raise ValueError(f"inductive: NodeID {nid} is not a trivial INTEGER")
    inst = nid.instance
    if inst == 0:
        return 0
    if inst % 2 == 1:
        return (inst - 1) // 2
    return -(inst // 2)


def _string_trivial_id(session: Session, value: str) -> NodeID:
    """Encode a string as a Trivial RType.STRING NodeID."""
    inst = intern_string_instance(session, value)
    return NodeID(1, Level.TRIVIAL, RType.STRING, inst)


def _string_trivial_value(session: Session, nid: NodeID) -> str:
    """Decode a string trivial NodeID via the substrate string-table."""
    if nid.level != Level.TRIVIAL or nid.type_ != RType.STRING:
        raise ValueError(f"inductive: NodeID {nid} is not a trivial STRING")
    value = lookup_string_value(session, nid.instance)
    if value is None:
        raise ValueError(
            f"inductive: string trivial {nid} has no entry in the string table"
        )
    return value


def _node_children(session: Session, nid: NodeID) -> List[NodeID]:
    """Ordered children of a composite NodeID."""
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


def _node_category_type(session: Session, nid: NodeID) -> Optional[int]:
    """Read the category type baked into a composite row's serialized prefix.

    Returns ``None`` for trivials or unknown shapes.
    """
    if nid.level <= Level.BASIC:
        # Trivials and bare categories carry their category in their own
        # `type_` slot.
        return nid.type_
    row = lookup_node(session, nid)
    if row is None or not row.serialized:
        return None
    head = row.serialized.split("+", 1)[0]
    parts = head.split(".")
    if len(parts) != 4:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Category-NodeID helpers
# ---------------------------------------------------------------------------


def _cat(arm_type: int, inst: int = 1) -> NodeID:
    """Build a category NodeID for an RBasic arm at (pkg=1, BASIC)."""
    return NodeID(1, Level.BASIC, arm_type, inst)


# ---------------------------------------------------------------------------
# Constructor recipe construction
# ---------------------------------------------------------------------------


def make_inductive(
    session: Session,
    name: str,
    params: Sequence[NodeID],
    ctors: Sequence[ConstructorDef],
) -> NodeID:
    """Intern an INDUCTIVE recipe. Returns the NodeID of the inductive type.

    Two inductives with identical (name, params, ctor-list) hash to the
    SAME NodeID through content-addressing. Constructor type-definitions
    are interned as nested CONSTRUCTOR recipes whose ``inductive-ref``
    child is the type-name trivial (self-ref sentinel — the inductive's
    NodeID isn't known until it's interned, so type-definition CONSTRUCTOR
    recipes carry the name as a stable identity).
    """
    type_name_nid = _string_trivial_id(session, name)
    # Params list — a BLOCK/SEQUENCE recipe holding the type-parameter
    # trivials. (The Python kernel composes lists as `R_Block.SEQUENCE`
    # per the structural-composition discipline; the TS kernel uses
    # `RBasic.LIST` directly. The two encodings produce different cells
    # but identical Form-level semantics — list = sequence of children.)
    params_list = intern_node(
        session,
        DOMAIN_RECIPE,
        _cat(RBasic.BLOCK, int(RBlock.SEQUENCE)),
        list(params),
    )

    ctor_defs: List[NodeID] = []
    for c in ctors:
        ctor_name_nid = _string_trivial_id(session, c.ctor_name)
        ctor_index_nid = _int_trivial_id(c.ctor_index)
        ctor_defs.append(
            intern_node(
                session,
                DOMAIN_RECIPE,
                _cat(RBasic.CONSTRUCTOR),
                [type_name_nid, ctor_name_nid, ctor_index_nid, *c.arg_types],
            )
        )

    return intern_node(
        session,
        DOMAIN_RECIPE,
        _cat(RBasic.INDUCTIVE),
        [type_name_nid, params_list, *ctor_defs],
    )


def make_constructor(
    session: Session,
    inductive: NodeID,
    ctor_name: str,
    args: Sequence[NodeID],
) -> NodeID:
    """Apply a constructor to value-recipe arguments, producing a value-recipe.

    The first child is the inductive type's NodeID (so the walker and
    totality checker can find the type without a symbol table).
    """
    idx = constructor_index(session, inductive, ctor_name)
    if idx < 0:
        raise ValueError(
            f"make_constructor: {ctor_name!r} is not a constructor of "
            f"inductive {inductive}"
        )
    ctor_name_nid = _string_trivial_id(session, ctor_name)
    ctor_index_nid = _int_trivial_id(idx)
    return intern_node(
        session,
        DOMAIN_RECIPE,
        _cat(RBasic.CONSTRUCTOR),
        [inductive, ctor_name_nid, ctor_index_nid, *args],
    )


def constructor_index(
    session: Session, inductive: NodeID, ctor_name: str
) -> int:
    """Look up a constructor's index by name. Returns -1 if absent."""
    if _node_category_type(session, inductive) != int(RBasic.INDUCTIVE):
        return -1
    kids = _node_children(session, inductive)
    # children: [type-name, params-list, ctor0, ctor1, ...]
    for ctor_nid in kids[2:]:
        ctor_kids = _node_children(session, ctor_nid)
        if len(ctor_kids) < 3:
            continue
        name_nid = ctor_kids[1]
        idx_nid = ctor_kids[2]
        if name_nid.level != Level.TRIVIAL or name_nid.type_ != RType.STRING:
            continue
        if _string_trivial_value(session, name_nid) == ctor_name:
            if idx_nid.level == Level.TRIVIAL and idx_nid.type_ == RType.INTEGER:
                return _int_trivial_value(idx_nid)
    return -1


def constructor_names(session: Session, inductive: NodeID) -> List[str]:
    """Every constructor name declared on an inductive, in declaration order."""
    if _node_category_type(session, inductive) != int(RBasic.INDUCTIVE):
        return []
    kids = _node_children(session, inductive)
    out: List[str] = []
    for ctor_nid in kids[2:]:
        ctor_kids = _node_children(session, ctor_nid)
        if len(ctor_kids) < 2:
            continue
        name_nid = ctor_kids[1]
        if name_nid.level == Level.TRIVIAL and name_nid.type_ == RType.STRING:
            try:
                out.append(_string_trivial_value(session, name_nid))
            except ValueError:
                continue
    return out


def is_total(
    session: Session, inductive: NodeID, arm_names: Sequence[str]
) -> bool:
    """True iff every constructor of ``inductive`` appears in ``arm_names``."""
    declared = constructor_names(session, inductive)
    arms = set(arm_names)
    return all(n in arms for n in declared)


# ---------------------------------------------------------------------------
# CtorValue — runtime tagged value
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CtorValue:
    """A constructor application result (the value-shape of an inductive)."""

    inductive: NodeID
    ctor_name: str
    ctor_index: int
    args: Tuple["Value", ...]


# A Value is either a NodeID-tagged trivial / nested ctor — for the
# pattern-match arm we keep the type-space tight: anything that flows
# through CHOICE is either a CtorValue, a literal trivial NodeID, or
# the NodeID of a recipe. Test code constructs ints / strings as raw
# trivial NodeIDs.
Value = object  # union of CtorValue and NodeID


def walk_value(session: Session, node: NodeID) -> Value:
    """Walk a value-recipe to a runtime Value.

    Trivials and non-CONSTRUCTOR composites pass through as raw NodeIDs.
    CONSTRUCTOR recipes are materialized as :class:`CtorValue`.
    Other recipes (LIST, MATH, etc.) are not interpreted here — the
    full kernel walker lives in ``form_runtime``; this module only
    needs the CONSTRUCTOR / CHOICE arms.
    """
    if node.level <= Level.BASIC:
        # Trivial leaf or bare category — pass through as NodeID.
        return node
    if _node_category_type(session, node) == int(RBasic.CONSTRUCTOR):
        return walk_constructor(session, node)
    if _node_category_type(session, node) == int(RBasic.CHOICE_MATCH):
        return walk_choice(session, node)
    return node


def walk_constructor(session: Session, node: NodeID) -> CtorValue:
    """Materialize a CONSTRUCTOR value-recipe into a :class:`CtorValue`.

    Recipe shape: ``CONSTRUCTOR[inductive-ref, ctor-name, ctor-index, arg0, ...]``.
    """
    kids = _node_children(session, node)
    if len(kids) < 3:
        raise ValueError(
            "constructor: need 3+ children (inductive-ref, name, index)"
        )
    inductive = kids[0]
    name_nid = kids[1]
    idx_nid = kids[2]
    if name_nid.level != Level.TRIVIAL or name_nid.type_ != RType.STRING:
        raise ValueError("constructor: name must be a string trivial")
    if idx_nid.level != Level.TRIVIAL or idx_nid.type_ != RType.INTEGER:
        raise ValueError("constructor: index must be an int trivial")
    args = tuple(walk_value(session, c) for c in kids[3:])
    return CtorValue(
        inductive=inductive,
        ctor_name=_string_trivial_value(session, name_nid),
        ctor_index=_int_trivial_value(idx_nid),
        args=args,
    )


# ---------------------------------------------------------------------------
# CHOICE pattern-match recipe
# ---------------------------------------------------------------------------


def make_choice(
    session: Session,
    scrutinee: NodeID,
    arms: Sequence[Tuple[str, NodeID]],
) -> NodeID:
    """Intern a CHOICE_MATCH recipe.

    ``arms`` is a list of ``(ctor_name, body_node)`` pairs. The recipe
    is checked for totality at walk-time, not intern-time — non-total
    matches are still valid substrate cells (they just raise when walked).
    """
    children: List[NodeID] = [scrutinee]
    for name, body in arms:
        children.append(_string_trivial_id(session, name))
        children.append(body)
    return intern_node(
        session, DOMAIN_RECIPE, _cat(RBasic.CHOICE_MATCH), children
    )


def walk_choice(session: Session, node: NodeID) -> Value:
    """Walk a CHOICE_MATCH recipe.

    Verifies every constructor on the scrutinee's inductive appears as
    an arm name. Returns the matched arm's body (walked).
    """
    kids = _node_children(session, node)
    if len(kids) < 1:
        raise ValueError("choice: need scrutinee")
    if (len(kids) - 1) % 2 != 0:
        raise ValueError("choice: arms must be (name, body) pairs")
    scrutinee = walk_value(session, kids[0])
    if not isinstance(scrutinee, CtorValue):
        raise ValueError(
            f"choice: scrutinee must be a ctor value (got {type(scrutinee).__name__})"
        )
    arm_names: List[str] = []
    arm_bodies: List[NodeID] = []
    for i in range(1, len(kids), 2):
        name_nid = kids[i]
        if name_nid.level != Level.TRIVIAL or name_nid.type_ != RType.STRING:
            raise ValueError("choice: arm name must be a string trivial")
        arm_names.append(_string_trivial_value(session, name_nid))
        arm_bodies.append(kids[i + 1])

    # Totality check — read the scrutinee's inductive.
    declared = constructor_names(session, scrutinee.inductive)
    if declared:
        missing = [n for n in declared if n not in arm_names]
        if missing:
            label = "constructor" if len(missing) == 1 else "constructors"
            raise ValueError(
                f"choice: non-total — missing {label}: {', '.join(missing)}"
            )

    # Dispatch on the scrutinee's constructor name.
    for name, body in zip(arm_names, arm_bodies):
        if name == scrutinee.ctor_name:
            return walk_value(session, body)
    raise ValueError(
        f"choice: no arm matches constructor {scrutinee.ctor_name!r}"
    )


# ---------------------------------------------------------------------------
# Imperative pattern-match (test / kernel-internal entry-point)
# ---------------------------------------------------------------------------


def match_value(
    session: Session,
    value: Value,
    arms: Sequence[Tuple[str, Callable[[Tuple[Value, ...]], object]]],
) -> object:
    """Exhaustive runtime pattern match.

    ``arms`` is a list of ``(ctor_name, handler)`` pairs; the handler
    receives the constructor's argument values and returns the arm
    result. Raises on non-totality or if no arm matches.
    """
    if not isinstance(value, CtorValue):
        raise ValueError(
            f"match_value: expected ctor value, got {type(value).__name__}"
        )
    arm_names = [n for (n, _) in arms]
    if not is_total(session, value.inductive, arm_names):
        declared = constructor_names(session, value.inductive)
        missing = [n for n in declared if n not in arm_names]
        raise ValueError(
            f"match_value: non-total — missing: {', '.join(missing)}"
        )
    for name, handler in arms:
        if name == value.ctor_name:
            return handler(value.args)
    raise ValueError(
        f"match_value: no arm matched {value.ctor_name!r}"
    )


# ---------------------------------------------------------------------------
# Built-in inductives
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BuiltinInductives:
    """The standard library of inductives every body has."""

    Nat: NodeID
    Bool: NodeID
    Option: NodeID
    Result: NodeID
    List: NodeID
    # Parametric type-variable placeholders — bare string trivials carrying
    # the parameter name (T, E). Richer parametricity lands later; the
    # proof-of-shape uses bare strings.
    T: NodeID
    E: NodeID


def install_builtin_inductives(session: Session) -> BuiltinInductives:
    """Install the standard library of inductives. Idempotent — same
    NodeIDs across calls."""
    T = _string_trivial_id(session, "T")
    E = _string_trivial_id(session, "E")

    # Nat ::= zero | succ Nat
    # The `succ` constructor's arg type is Nat itself — self-reference
    # uses the type-name trivial as the sentinel.
    Nat_self = _string_trivial_id(session, "Nat")
    Nat = make_inductive(
        session,
        "Nat",
        (),
        (
            ConstructorDef("zero", 0, ()),
            ConstructorDef("succ", 1, (Nat_self,)),
        ),
    )

    Bool = make_inductive(
        session,
        "Bool",
        (),
        (
            ConstructorDef("false", 0, ()),
            ConstructorDef("true", 1, ()),
        ),
    )

    Option = make_inductive(
        session,
        "Option",
        (T,),
        (
            ConstructorDef("none", 0, ()),
            ConstructorDef("some", 1, (T,)),
        ),
    )

    Result = make_inductive(
        session,
        "Result",
        (T, E),
        (
            ConstructorDef("ok", 0, (T,)),
            ConstructorDef("err", 1, (E,)),
        ),
    )

    List_self = _string_trivial_id(session, "List")
    List = make_inductive(
        session,
        "List",
        (T,),
        (
            ConstructorDef("nil", 0, ()),
            ConstructorDef("cons", 1, (T, List_self)),
        ),
    )

    return BuiltinInductives(
        Nat=Nat, Bool=Bool, Option=Option, Result=Result, List=List, T=T, E=E,
    )


# ---------------------------------------------------------------------------
# Convenience builders — common value-recipes
# ---------------------------------------------------------------------------


def nat_zero(session: Session, inductives: BuiltinInductives) -> NodeID:
    return make_constructor(session, inductives.Nat, "zero", ())


def nat_succ(
    session: Session, inductives: BuiltinInductives, prev: NodeID
) -> NodeID:
    return make_constructor(session, inductives.Nat, "succ", (prev,))


def nat_of(
    session: Session, inductives: BuiltinInductives, n: int
) -> NodeID:
    if n < 0:
        raise ValueError("nat_of: negative")
    out = nat_zero(session, inductives)
    for _ in range(n):
        out = nat_succ(session, inductives, out)
    return out


def list_nil(session: Session, inductives: BuiltinInductives) -> NodeID:
    return make_constructor(session, inductives.List, "nil", ())


def list_cons(
    session: Session,
    inductives: BuiltinInductives,
    head: NodeID,
    tail: NodeID,
) -> NodeID:
    return make_constructor(session, inductives.List, "cons", (head, tail))


# ---------------------------------------------------------------------------
# Decoders — Value → Python primitive
# ---------------------------------------------------------------------------


def nat_to_int(v: Value) -> int:
    """Walk a Nat ctor-value into a Python int."""
    n = 0
    cur = v
    while isinstance(cur, CtorValue) and cur.ctor_name == "succ":
        n += 1
        if not cur.args:
            raise ValueError("nat_to_int: succ with no args")
        cur = cur.args[0]
    if not isinstance(cur, CtorValue) or cur.ctor_name != "zero":
        raise ValueError("nat_to_int: not a Nat")
    return n


def list_length(v: Value) -> int:
    """Count cons cells in a List ctor-value."""
    n = 0
    cur = v
    while isinstance(cur, CtorValue) and cur.ctor_name == "cons":
        n += 1
        if len(cur.args) < 2:
            raise ValueError("list_length: cons with insufficient args")
        cur = cur.args[1]
    if not isinstance(cur, CtorValue) or cur.ctor_name != "nil":
        raise ValueError("list_length: not a List")
    return n


__all__ = [
    "BuiltinInductives",
    "ConstructorDef",
    "CtorValue",
    "InductiveType",
    "Value",
    "constructor_index",
    "constructor_names",
    "install_builtin_inductives",
    "is_total",
    "list_cons",
    "list_length",
    "list_nil",
    "make_choice",
    "make_constructor",
    "make_inductive",
    "match_value",
    "nat_of",
    "nat_succ",
    "nat_to_int",
    "nat_zero",
    "walk_choice",
    "walk_constructor",
    "walk_value",
]
